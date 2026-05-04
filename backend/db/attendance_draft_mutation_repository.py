"""PostgreSQL mutations for recalculated attendance draft lessons."""

from __future__ import annotations

import json
from datetime import date, datetime

from backend.attendance_app.models import DraftLessonView

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
                            participant["final_presence_status"],
                            participant["id"],
                        ),
                    )
            connection.commit()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)
