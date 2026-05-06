"""PostgreSQL mutations for recalculated attendance draft lessons."""

from __future__ import annotations

import json
from datetime import date, datetime

from backend.attendance_app.models import DraftLessonSourceSegment, DraftLessonView

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


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)
