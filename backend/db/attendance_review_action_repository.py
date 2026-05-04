"""PostgreSQL implementation for attendance review actions."""

from __future__ import annotations

import json
from datetime import datetime

from backend.attendance_app.models import DraftReviewActionView

from .connection import get_db_connection


class PostgresAttendanceReviewActionRepository:
    """Persist manual review actions for one attendance lesson."""

    def create_lesson_review_action(
        self,
        lesson_id: int,
        action_type: str,
        payload: dict,
        *,
        created_by: str | None = None,
        notes: str | None = None,
        participant_id: int | None = None,
    ) -> DraftReviewActionView:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO attendance_review_actions (
                        lesson_id,
                        participant_id,
                        action_type,
                        payload_json,
                        created_by,
                        notes
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                    RETURNING
                        id,
                        lesson_id,
                        participant_id,
                        action_type,
                        payload_json,
                        created_by,
                        created_at,
                        applied_at,
                        is_applied,
                        notes
                    """,
                    (
                        lesson_id,
                        participant_id,
                        action_type,
                        json.dumps(payload),
                        created_by,
                        notes,
                    ),
                )
                row = cursor.fetchone()
            connection.commit()

        if row is None:
            raise RuntimeError("Failed to create attendance review action.")

        return DraftReviewActionView(
            id=int(row[0]),
            lesson_id=int(row[1]),
            participant_id=int(row[2]) if row[2] is not None else None,
            action_type=str(row[3]),
            payload=dict(row[4] or {}),
            created_by=row[5],
            created_at=_ensure_datetime(row[6]).isoformat(),
            applied_at=_optional_datetime_iso(row[7]),
            is_applied=bool(row[8]),
            notes=row[9],
        )


def _ensure_datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise RuntimeError("Expected datetime from PostgreSQL.")
    return value


def _optional_datetime_iso(value: object) -> str | None:
    if value is None:
        return None
    return _ensure_datetime(value).isoformat()
