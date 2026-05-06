"""PostgreSQL implementation of draft attendance import persistence."""

from __future__ import annotations

from datetime import date, datetime
import json

from backend.attendance_app.models import (
    ImportBatch,
    ImportBatchCreate,
    LessonDraft,
    LessonParticipantDraft,
    PersistedDraftImport,
    SkippedDuplicateLesson,
)

from .connection import get_db_connection


class PostgresAttendanceDraftImportRepository:
    """Persist full normalized attendance drafts into PostgreSQL."""

    def save_draft_import(
        self,
        batch_data: ImportBatchCreate,
        lessons: list[LessonDraft],
    ) -> PersistedDraftImport:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                skipped_duplicates: list[SkippedDuplicateLesson] = []
                lessons_to_insert: list[LessonDraft] = []

                for lesson in lessons:
                    duplicate = self._find_existing_duplicate(cursor, lesson)
                    if duplicate is not None:
                        skipped_duplicates.append(duplicate)
                    else:
                        lessons_to_insert.append(lesson)

                batch = None
                lesson_count = 0
                participant_count = 0

                if lessons_to_insert:
                    batch = self._insert_batch(cursor, batch_data)

                    for lesson in lessons_to_insert:
                        lesson_id = self._insert_lesson(cursor, batch.id, lesson)
                        lesson_count += 1
                        participant_count += self._insert_participants(cursor, lesson_id, lesson.participants)
                        self._insert_source_segments(cursor, lesson_id, lesson.participants)

            connection.commit()

        return PersistedDraftImport(
            batch=batch,
            lessons_created=lesson_count,
            participants_created=participant_count,
            duplicate_lessons_skipped=len(skipped_duplicates),
            skipped_duplicates=skipped_duplicates,
        )

    def _insert_batch(self, cursor, data: ImportBatchCreate) -> ImportBatch:
        cursor.execute(
            """
            INSERT INTO attendance_import_batches (
                source_system,
                source_file_name,
                source_file_path,
                source_file_sha256,
                imported_by,
                notes
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING
                id,
                source_system,
                source_file_name,
                source_file_path,
                source_file_sha256,
                imported_by,
                status,
                notes,
                created_at,
                updated_at
            """,
            (
                data.source_system,
                data.source_file_name,
                data.source_file_path,
                data.source_file_sha256,
                data.imported_by,
                data.notes,
            ),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to create attendance import batch.")

        return ImportBatch(
            id=int(row[0]),
            source_system=str(row[1]),
            source_file_name=str(row[2]),
            source_file_path=row[3],
            source_file_sha256=row[4],
            imported_by=row[5],
            status=str(row[6]),
            notes=row[7],
            created_at=_ensure_datetime(row[8]),
            updated_at=_ensure_datetime(row[9]),
        )

    def _insert_lesson(self, cursor, batch_id: int, lesson: LessonDraft) -> int:
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
            raise RuntimeError("Failed to create attendance lesson.")
        return int(row[0])

    def _find_existing_duplicate(self, cursor, lesson: LessonDraft) -> SkippedDuplicateLesson | None:
        cursor.execute(
            """
            SELECT
                id,
                import_batch_id
            FROM attendance_lessons
            WHERE course_name = %s
              AND source_meeting_id = %s
              AND lesson_date = %s
            ORDER BY id ASC
            LIMIT 1
            """,
            (
                lesson.course_name,
                lesson.source_meeting_id,
                _parse_date(lesson.lesson_date),
            ),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return SkippedDuplicateLesson(
            course_name=lesson.course_name,
            source_meeting_id=lesson.source_meeting_id,
            lesson_date=lesson.lesson_date,
            existing_lesson_id=int(row[0]),
            existing_batch_id=int(row[1]),
        )

    def _insert_participants(
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

    def _insert_source_segments(
        self,
        cursor,
        lesson_id: int,
        participants: list[LessonParticipantDraft],
    ) -> int:
        count = 0
        for participant in participants:
            identity_sources = participant.metadata.get("identity_sources")
            if not isinstance(identity_sources, list) or not identity_sources:
                identity_sources = [{
                    "raw_full_name": participant.raw_full_name or participant.canonical_full_name,
                    "email": participant.email or "",
                    "segments": list(participant.metadata.get("segments") or []),
                }]
            for source in identity_sources:
                observed_full_name = str(source.get("raw_full_name") or participant.raw_full_name or participant.canonical_full_name).strip()
                observed_email = str(source.get("email") or participant.email or "").strip() or None
                for segment in list(source.get("segments") or []):
                    if not isinstance(segment, (list, tuple)) or len(segment) != 2:
                        continue
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
                            observed_full_name,
                            observed_email,
                            _parse_datetime(str(segment[0])),
                            _parse_datetime(str(segment[1])),
                            json.dumps({}),
                        ),
                    )
                    count += 1
        return count


def _ensure_datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise RuntimeError("Expected datetime from PostgreSQL.")
    return value


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)
