"""PostgreSQL implementation for attendance identity aliases."""

from __future__ import annotations

from datetime import datetime

from backend.attendance_app.models import AttendanceIdentityAlias

from .connection import get_db_connection


class PostgresAttendanceIdentityAliasRepository:
    """Persist and read canonical identity aliases for future imports."""

    def list_active_aliases(self) -> list[AttendanceIdentityAlias]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        canonical_full_name,
                        canonical_email,
                        alias_full_name,
                        alias_type,
                        created_by,
                        created_at,
                        is_active,
                        notes
                    FROM attendance_identity_aliases
                    WHERE is_active = TRUE
                    ORDER BY alias_full_name ASC, id ASC
                    """
                )
                rows = cursor.fetchall()

        return [
            AttendanceIdentityAlias(
                id=int(row[0]),
                canonical_full_name=str(row[1]),
                canonical_email=row[2],
                alias_value=str(row[3]),
                alias_type=str(row[4]),
                created_by=row[5],
                created_at=_ensure_datetime(row[6]),
                is_active=bool(row[7]),
                notes=row[8],
            )
            for row in rows
        ]

    def create_alias(
        self,
        *,
        canonical_full_name: str,
        canonical_email: str | None = None,
        alias_value: str,
        alias_type: str = "full_name",
        created_by: str | None = None,
        notes: str | None = None,
    ) -> AttendanceIdentityAlias:
        normalized_alias = _normalize_key(alias_value) if alias_type == "full_name" else _normalize_email(alias_value)
        normalized_canonical = _normalize_key(canonical_full_name)
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO attendance_identity_aliases (
                        canonical_full_name,
                        canonical_email,
                        alias_full_name,
                        alias_type,
                        normalized_canonical_key,
                        normalized_alias_key,
                        created_by,
                        notes,
                        is_active
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                    ON CONFLICT (alias_type, normalized_alias_key)
                    DO UPDATE SET
                        canonical_full_name = EXCLUDED.canonical_full_name,
                        canonical_email = EXCLUDED.canonical_email,
                        normalized_canonical_key = EXCLUDED.normalized_canonical_key,
                        created_by = EXCLUDED.created_by,
                        notes = EXCLUDED.notes,
                        is_active = TRUE
                    RETURNING
                        id,
                        canonical_full_name,
                        canonical_email,
                        alias_full_name,
                        alias_type,
                        created_by,
                        created_at,
                        is_active,
                        notes
                    """,
                    (
                        canonical_full_name,
                        canonical_email,
                        alias_value,
                        alias_type,
                        normalized_canonical,
                        normalized_alias,
                        created_by,
                        notes,
                    ),
                )
                row = cursor.fetchone()
            connection.commit()

        if row is None:
            raise RuntimeError("Failed to create attendance identity alias.")

        return AttendanceIdentityAlias(
            id=int(row[0]),
            canonical_full_name=str(row[1]),
            canonical_email=row[2],
            alias_value=str(row[3]),
            alias_type=str(row[4]),
            created_by=row[5],
            created_at=_ensure_datetime(row[6]),
            is_active=bool(row[7]),
            notes=row[8],
        )

    def deactivate_alias(self, alias_id: int) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE attendance_identity_aliases
                    SET
                        is_active = FALSE
                    WHERE id = %s
                    """,
                    (alias_id,),
                )
                if cursor.rowcount == 0:
                    raise LookupError(f"Attendance identity alias {alias_id} not found.")
            connection.commit()


def _normalize_key(value: str) -> str:
    return " ".join((value or "").strip().casefold().split())


def _normalize_email(value: str) -> str:
    return (value or "").strip().casefold()


def _ensure_datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise RuntimeError("Expected datetime from PostgreSQL.")
    return value
