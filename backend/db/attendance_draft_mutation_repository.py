"""PostgreSQL mutations for recalculated attendance draft lessons."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from backend.attendance_app.models import (
    DraftLessonSourceSegment,
    DraftLessonView,
    LessonDraft,
    LessonParticipantDraft,
    ManualPresenceImportCreate,
    ManualPresenceImportResult,
    SplitLessonResult,
)

from .connection import get_db_connection


class PostgresAttendanceDraftMutationRepository:
    """Persist recalculated lesson markers and participant values."""

    def update_lesson_after_recalculation(
        self,
        lesson: DraftLessonView,
        *,
        threshold_ratio: float,
        effective_start_at: str,
        break_point_at: str | None,
        effective_end_at: str,
        break_source: str,
        effective_start_source: str,
        effective_end_source: str,
        diagnostics: dict,
        participants: list[dict],
    ) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE attendance_lessons
                    SET
                        threshold_ratio = %s,
                        effective_start_at = %s,
                        break_point_at = %s,
                        effective_end_at = %s,
                        break_source = %s,
                        effective_start_source = %s,
                        effective_end_source = %s,
                        diagnostics_json = %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        threshold_ratio,
                        _parse_datetime(effective_start_at),
                        _parse_datetime(break_point_at) if break_point_at else None,
                        _parse_datetime(effective_end_at),
                        break_source,
                        effective_start_source,
                        effective_end_source,
                        json.dumps(diagnostics),
                        lesson.id,
                    ),
                )

                for participant in participants:
                    cursor.execute(
                        """
                        UPDATE attendance_lesson_participants
                        SET
                            minutes_first_half = %s,
                            minutes_second_half = %s,
                            duration_first_half = %s,
                            duration_second_half = %s,
                            total_minutes = %s,
                            calculated_presence_status = %s,
                            manual_override_presence_status = %s,
                            final_presence_status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            participant["minutes_first_half"],
                            participant["minutes_second_half"],
                            participant["duration_first_half"],
                            participant["duration_second_half"],
                            participant["total_minutes"],
                            participant["calculated_presence_status"],
                            participant["manual_override_presence_status"],
                            participant["final_presence_status"],
                            participant["id"],
                        ),
                    )
            connection.commit()

    def set_lesson_ignored(self, lesson_id: int, *, is_ignored: bool) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE attendance_lessons
                    SET
                        is_ignored = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (is_ignored, lesson_id),
                )
            connection.commit()

    def set_lesson_status(self, lesson_id: int, *, status: str) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE attendance_lessons
                    SET
                        status = %s,
                        officialized_at = CASE WHEN %s = 'official' THEN NOW() ELSE NULL END,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (status, status, lesson_id),
                )
            connection.commit()

    def replace_lesson_participants_after_identity_rebuild(
        self,
        lesson_id: int,
        *,
        diagnostics: dict,
        participants: list[dict],
    ) -> None:
        if not participants:
            raise ValueError("Cannot replace lesson participants with an empty set.")
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                survivor_ids = [participant["survivor_id"] for participant in participants]
                for survivor_id in survivor_ids:
                    cursor.execute(
                        """
                        UPDATE attendance_lesson_participants
                        SET participant_key = %s
                        WHERE id = %s
                        """,
                        (f"__tmp__{survivor_id}", survivor_id),
                    )

                for participant in participants:
                    survivor_id = participant["survivor_id"]
                    for obsolete_id in participant.get("obsolete_ids", []):
                        cursor.execute(
                            """
                            UPDATE attendance_review_actions
                            SET participant_id = %s
                            WHERE lesson_id = %s AND participant_id = %s
                            """,
                            (survivor_id, lesson_id, obsolete_id),
                        )

                delete_sql = """
                    DELETE FROM attendance_lesson_participants
                    WHERE lesson_id = %s
                      AND id NOT IN ({placeholders})
                """.format(
                    placeholders=", ".join(["%s"] * len(survivor_ids))
                )
                cursor.execute(delete_sql, [lesson_id, *survivor_ids])

                for participant in participants:
                    cursor.execute(
                        """
                        UPDATE attendance_lesson_participants
                        SET
                            participant_key = %s,
                            canonical_full_name = %s,
                            raw_full_name = %s,
                            email = %s,
                            segment_count = %s,
                            minutes_first_half = %s,
                            minutes_second_half = %s,
                            duration_first_half = %s,
                            duration_second_half = %s,
                            total_minutes = %s,
                            calculated_presence_status = %s,
                            manual_override_presence_status = %s,
                            final_presence_status = %s,
                            flags_json = %s::jsonb,
                            metadata_json = %s::jsonb,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            participant["participant_key"],
                            participant["canonical_full_name"],
                            participant["raw_full_name"],
                            participant["email"],
                            participant["segment_count"],
                            participant["minutes_first_half"],
                            participant["minutes_second_half"],
                            participant["duration_first_half"],
                            participant["duration_second_half"],
                            participant["total_minutes"],
                            participant["calculated_presence_status"],
                            participant["manual_override_presence_status"],
                            participant["final_presence_status"],
                            json.dumps(participant["flags"]),
                            json.dumps(participant["metadata"]),
                            participant["survivor_id"],
                        ),
                    )

                cursor.execute(
                    """
                    UPDATE attendance_lessons
                    SET
                        diagnostics_json = %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (json.dumps(diagnostics), lesson_id),
                )
            connection.commit()

    def ensure_lesson_source_segments(
        self,
        lesson_id: int,
        source_segments: list[DraftLessonSourceSegment],
    ) -> int:
        if not source_segments:
            return 0
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM attendance_lesson_source_segments
                    WHERE lesson_id = %s
                    """,
                    (lesson_id,),
                )
                row = cursor.fetchone()
                existing = int(row[0]) if row is not None else 0
                if existing > 0:
                    return 0

                inserted = 0
                for segment in source_segments:
                    cursor.execute(
                        """
                        INSERT INTO attendance_lesson_source_segments (
                            lesson_id,
                            observed_full_name,
                            observed_email,
                            join_time,
                            leave_time,
                            metadata_json
                        )
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (lesson_id, observed_full_name, observed_email, join_time, leave_time)
                        DO NOTHING
                        """,
                        (
                            lesson_id,
                            segment.observed_full_name,
                            segment.observed_email,
                            _parse_datetime(segment.join_time),
                            _parse_datetime(segment.leave_time),
                            json.dumps(segment.metadata or {}),
                        ),
                    )
                    inserted += cursor.rowcount or 0
            connection.commit()
        return inserted

    def delete_lesson(self, lesson_id: int) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM attendance_lessons
                    WHERE id = %s
                    """,
                    (lesson_id,),
                )
                if cursor.rowcount == 0:
                    raise LookupError(f"Attendance lesson {lesson_id} not found.")
            connection.commit()

    def delete_batch(self, batch_id: int) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM attendance_import_batches
                    WHERE id = %s
                    """,
                    (batch_id,),
                )
                if cursor.rowcount == 0:
                    raise LookupError(f"Attendance import batch {batch_id} not found.")
            connection.commit()

    def split_lesson(
        self,
        original_lesson_id: int,
        first_lesson: LessonDraft,
        first_source_segments: list[DraftLessonSourceSegment],
        second_lesson: LessonDraft,
        second_source_segments: list[DraftLessonSourceSegment],
    ) -> SplitLessonResult:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT import_batch_id
                    FROM attendance_lessons
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (original_lesson_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise LookupError(f"Attendance lesson {original_lesson_id} not found.")
                batch_id = int(row[0])

                first_lesson_id = self._insert_split_lesson(cursor, batch_id, first_lesson)
                first_participants_count = self._insert_split_participants(cursor, first_lesson_id, first_lesson.participants)
                self._insert_split_source_segments(cursor, first_lesson_id, first_source_segments)

                second_lesson_id = self._insert_split_lesson(cursor, batch_id, second_lesson)
                second_participants_count = self._insert_split_participants(cursor, second_lesson_id, second_lesson.participants)
                self._insert_split_source_segments(cursor, second_lesson_id, second_source_segments)

                cursor.execute(
                    """
                    DELETE FROM attendance_lessons
                    WHERE id = %s
                    """,
                    (original_lesson_id,),
                )
                if cursor.rowcount == 0:
                    raise LookupError(f"Attendance lesson {original_lesson_id} not found.")
            connection.commit()

        return SplitLessonResult(
            original_lesson_id=original_lesson_id,
            first_lesson_id=first_lesson_id,
            second_lesson_id=second_lesson_id,
            first_participants_count=first_participants_count,
            second_participants_count=second_participants_count,
        )

    def upsert_course_expected_lessons(
        self,
        course_name: str,
        expected_lessons_count: int | None,
    ) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO attendance_courses (
                        course_name,
                        expected_lessons_count,
                        updated_at
                    )
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (course_name)
                    DO UPDATE SET
                        expected_lessons_count = EXCLUDED.expected_lessons_count,
                        updated_at = NOW()
                    """,
                    (course_name, expected_lessons_count),
                )
            connection.commit()

    def _insert_split_lesson(self, cursor, batch_id: int, lesson: LessonDraft) -> int:
        cursor.execute(
            """
            INSERT INTO attendance_lessons (
                import_batch_id,
                source_system,
                source_meeting_id,
                course_name,
                lesson_date,
                meeting_start_at,
                meeting_end_at,
                effective_start_at,
                break_point_at,
                effective_end_at,
                threshold_ratio,
                break_source,
                effective_start_source,
                effective_end_source,
                warnings_json,
                diagnostics_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            RETURNING id
            """,
            (
                batch_id,
                lesson.source_system,
                lesson.source_meeting_id,
                lesson.course_name,
                _parse_date(lesson.lesson_date),
                _parse_datetime(lesson.meeting_start_at),
                _parse_datetime(lesson.meeting_end_at),
                _parse_datetime(lesson.effective_start_at),
                _parse_datetime(lesson.break_point_at) if lesson.break_point_at else None,
                _parse_datetime(lesson.effective_end_at),
                lesson.threshold_ratio,
                lesson.break_source,
                lesson.effective_start_source,
                lesson.effective_end_source,
                json.dumps(lesson.warnings),
                json.dumps(lesson.diagnostics),
            ),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to create split attendance lesson.")
        return int(row[0])

    def _insert_split_participants(
        self,
        cursor,
        lesson_id: int,
        participants: list[LessonParticipantDraft],
    ) -> int:
        count = 0
        for participant in participants:
            cursor.execute(
                """
                INSERT INTO attendance_lesson_participants (
                    lesson_id,
                    participant_key,
                    canonical_full_name,
                    raw_full_name,
                    email,
                    segment_count,
                    minutes_first_half,
                    minutes_second_half,
                    duration_first_half,
                    duration_second_half,
                    total_minutes,
                    calculated_presence_status,
                    final_presence_status,
                    flags_json,
                    metadata_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                """,
                (
                    lesson_id,
                    participant.participant_key,
                    participant.canonical_full_name,
                    participant.raw_full_name,
                    participant.email,
                    participant.segment_count,
                    participant.minutes_first_half,
                    participant.minutes_second_half,
                    participant.duration_first_half,
                    participant.duration_second_half,
                    participant.total_minutes,
                    participant.calculated_presence_status,
                    participant.final_presence_status,
                    json.dumps(participant.flags),
                    json.dumps(participant.metadata),
                ),
            )
            count += 1
        return count

    def _insert_split_source_segments(
        self,
        cursor,
        lesson_id: int,
        source_segments: list[DraftLessonSourceSegment],
    ) -> int:
        count = 0
        for segment in source_segments:
            cursor.execute(
                """
                INSERT INTO attendance_lesson_source_segments (
                    lesson_id,
                    observed_full_name,
                    observed_email,
                    join_time,
                    leave_time,
                    metadata_json
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    lesson_id,
                    segment.observed_full_name,
                    segment.observed_email,
                    _parse_datetime(segment.join_time),
                    _parse_datetime(segment.leave_time),
                    json.dumps(segment.metadata or {}),
                ),
            )
            count += 1
        return count

    def upsert_manual_presence_import(
        self,
        import_data: ManualPresenceImportCreate,
    ) -> ManualPresenceImportResult:
        lesson_date = _parse_date(import_data.lesson_date) if import_data.lesson_id is None else None
        result_course_name = import_data.course_name
        result_lesson_date = import_data.lesson_date
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                existing_lesson = (
                    self._find_existing_lesson_by_id(cursor, import_data.lesson_id)
                    if import_data.lesson_id is not None
                    else self._find_existing_official_lesson(
                        cursor,
                        course_name=import_data.course_name,
                        lesson_date=lesson_date,
                    )
                )
                if existing_lesson is not None:
                    lesson_id, result_course_name, result_lesson_date = existing_lesson
                else:
                    batch_id = self._ensure_manual_batch(cursor, import_data.created_by)
                    lesson_id = self._create_manual_lesson(
                        cursor,
                        batch_id=batch_id,
                        course_name=import_data.course_name,
                        lesson_date=lesson_date or _parse_date(import_data.lesson_date),
                    )
                upserted = 0
                for record in import_data.records:
                    participant_key = (record.email or "").strip().lower() or record.full_name.strip().lower()
                    cursor.execute(
                        """
                        INSERT INTO attendance_lesson_participants (
                            lesson_id,
                            participant_key,
                            canonical_full_name,
                            raw_full_name,
                            email,
                            segment_count,
                            minutes_first_half,
                            minutes_second_half,
                            duration_first_half,
                            duration_second_half,
                            total_minutes,
                            calculated_presence_status,
                            manual_override_presence_status,
                            final_presence_status,
                            presence_source,
                            flags_json,
                            metadata_json
                        )
                        VALUES (%s, %s, %s, %s, %s, 0, 0, 0, 0, 0, 0, %s, NULL, %s, %s, '[]'::jsonb, %s::jsonb)
                        ON CONFLICT (lesson_id, participant_key)
                        DO UPDATE SET
                            canonical_full_name = EXCLUDED.canonical_full_name,
                            raw_full_name = EXCLUDED.raw_full_name,
                            email = EXCLUDED.email,
                            calculated_presence_status = EXCLUDED.calculated_presence_status,
                            manual_override_presence_status = NULL,
                            final_presence_status = EXCLUDED.final_presence_status,
                            presence_source = EXCLUDED.presence_source,
                            metadata_json = EXCLUDED.metadata_json,
                            updated_at = NOW()
                        """,
                        (
                            lesson_id,
                            participant_key,
                            record.full_name,
                            record.full_name,
                            record.email,
                            record.presence_status,
                            record.presence_status,
                            import_data.presence_source,
                            json.dumps({
                                "source": import_data.presence_source,
                                "manual_import": True,
                                "created_by": import_data.created_by,
                            }),
                        ),
                    )
                    upserted += 1
            connection.commit()

        return ManualPresenceImportResult(
            lesson_id=lesson_id,
            course_name=result_course_name,
            lesson_date=result_lesson_date,
            records_processed=len(import_data.records),
            participants_upserted=upserted,
        )

    def _ensure_manual_batch(self, cursor, created_by: str | None) -> int:
        cursor.execute(
            """
            INSERT INTO attendance_import_batches (
                source_system,
                source_file_name,
                imported_by,
                status,
                notes
            )
            VALUES ('manual', 'manual-presence-entry', %s, 'official', 'Contenitore tecnico per presenze inserite manualmente')
            RETURNING id
            """,
            (created_by,),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to create manual attendance batch.")
        return int(row[0])

    def _find_existing_lesson_by_id(self, cursor, lesson_id: int) -> tuple[int, str, str]:
        cursor.execute(
            """
            SELECT id, course_name, lesson_date
            FROM attendance_lessons
            WHERE id = %s
              AND status = 'official'
              AND is_ignored = FALSE
            """,
            (lesson_id,),
        )
        row = cursor.fetchone()
        if row is not None:
            return int(row[0]), str(row[1]), row[2].isoformat()
        raise LookupError(f"Attendance lesson {lesson_id} not found or not official.")

    def _find_existing_official_lesson(
        self,
        cursor,
        *,
        course_name: str,
        lesson_date: date,
    ) -> tuple[int, str, str] | None:
        cursor.execute(
            """
            SELECT id, course_name, lesson_date
            FROM attendance_lessons
            WHERE lower(course_name) = lower(%s)
              AND lesson_date = %s
              AND status = 'official'
              AND is_ignored = FALSE
            ORDER BY id ASC
            LIMIT 1
            """,
            (course_name, lesson_date),
        )
        row = cursor.fetchone()
        if row is not None:
            return int(row[0]), str(row[1]), row[2].isoformat()
        return None

    def _create_manual_lesson(
        self,
        cursor,
        *,
        batch_id: int,
        course_name: str,
        lesson_date: date,
    ) -> int:
        lesson_start = datetime.combine(lesson_date, time(0, 0), tzinfo=ZoneInfo("Europe/Zurich"))
        lesson_end = datetime.combine(lesson_date, time(23, 59), tzinfo=ZoneInfo("Europe/Zurich"))
        cursor.execute(
            """
            INSERT INTO attendance_lessons (
                import_batch_id,
                source_system,
                source_meeting_id,
                course_name,
                lesson_date,
                meeting_start_at,
                meeting_end_at,
                effective_start_at,
                effective_end_at,
                threshold_ratio,
                break_source,
                effective_start_source,
                effective_end_source,
                status,
                officialized_at,
                diagnostics_json
            )
            VALUES (%s, 'manual', %s, %s, %s, %s, %s, %s, %s, 0.8000, 'manual', 'manual', 'manual', 'official', NOW(), %s::jsonb)
            RETURNING id
            """,
            (
                batch_id,
                f"manual:{course_name}:{lesson_date.isoformat()}",
                course_name,
                lesson_date,
                lesson_start,
                lesson_end,
                lesson_start,
                lesson_end,
                json.dumps({"source": "manual"}),
            ),
        )
        inserted = cursor.fetchone()
        if inserted is None:
            raise RuntimeError("Failed to create manual attendance lesson.")
        return int(inserted[0])


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)
