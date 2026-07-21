"""PostgreSQL implementation for observed attendance identities."""

from __future__ import annotations

from backend.attendance_app.services import (
    _apply_identity_alias_maps,
    _compatible_identity_key,
    _load_identity_alias_maps,
    _normalize_identity_key,
)
from backend.attendance_app.models import (
    AttendanceAliasIdentitySyncResult,
    AttendanceIdentity,
    AttendanceIdentityRebuildResult,
)

from .connection import get_db_connection
from .attendance_identity_alias_repository import PostgresAttendanceIdentityAliasRepository


class PostgresAttendanceIdentityRepository:
    """Maintain a lightweight registry of identities observed in attendance data."""

    def list_identities(self, limit: int = 500) -> list[AttendanceIdentity]:
        safe_limit = max(1, min(int(limit or 500), 5000))
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        identity_key,
                        display_name,
                        email,
                        is_active
                    FROM attendance_identities
                    WHERE is_active = TRUE
                    ORDER BY display_name ASC, email ASC NULLS LAST, identity_key ASC
                    LIMIT %s
                    """,
                    (safe_limit,),
                )
                rows = cursor.fetchall()

        return [
            AttendanceIdentity(
                id=int(row[0]),
                identity_key=str(row[1]),
                display_name=str(row[2]),
                email=row[3],
                is_active=bool(row[4]),
            )
            for row in rows
        ]

    def deactivate_identity(self, identity_id: int) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE attendance_identities
                    SET is_active = FALSE
                    WHERE id = %s
                    """,
                    (identity_id,),
                )
                if cursor.rowcount == 0:
                    raise LookupError(f"Attendance identity {identity_id} not found.")
            connection.commit()

    def sync_alias_identity(self, alias_id: int) -> AttendanceAliasIdentitySyncResult:
        """Attach one alias row to the stable canonical identity.

        This intentionally does not rebuild lessons and does not rewrite lesson
        participants. It only keeps the identity registry coherent after a new
        alias has been created.
        """
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
                        is_active
                    FROM attendance_identity_aliases
                    WHERE id = %s
                    """,
                    (alias_id,),
                )
                alias_row = cursor.fetchone()
                if alias_row is None:
                    raise LookupError(f"Attendance identity alias {alias_id} not found.")
                if not bool(alias_row[5]):
                    raise ValueError(f"Attendance identity alias {alias_id} is not active.")

                canonical_full_name = _clean_name(alias_row[1])
                canonical_email = _clean_email(alias_row[2])
                alias_value = _clean_name(alias_row[3])
                alias_type = str(alias_row[4] or "full_name")
                if not canonical_full_name:
                    raise ValueError("Canonical full name is required.")
                if not alias_value:
                    raise ValueError("Alias value is required.")

                identity_key = _identity_key(canonical_full_name, canonical_email)
                cursor.execute(
                    """
                    INSERT INTO attendance_identities (
                        identity_key,
                        display_name,
                        email,
                        is_active
                    )
                    VALUES (%s, %s, %s, TRUE)
                    ON CONFLICT (identity_key)
                    DO UPDATE SET
                        display_name = COALESCE(NULLIF(attendance_identities.display_name, ''), EXCLUDED.display_name),
                        email = COALESCE(attendance_identities.email, EXCLUDED.email),
                        is_active = TRUE
                    RETURNING id, (xmax = 0) AS inserted
                    """,
                    (identity_key, canonical_full_name, canonical_email),
                )
                identity_row = cursor.fetchone()
                if identity_row is None:
                    raise RuntimeError("Failed to create or read canonical identity.")
                identity_id = int(identity_row[0])
                identity_created = bool(identity_row[1])

                cursor.execute(
                    """
                    UPDATE attendance_identity_aliases
                    SET identity_id = %s
                    WHERE id = %s
                    """,
                    (identity_id, alias_id),
                )

                alias_identity_key = _alias_identity_key(alias_value, alias_type)
                alias_identity_id = None
                alias_identity_deactivated = False
                if alias_identity_key != identity_key:
                    cursor.execute(
                        """
                        SELECT id
                        FROM attendance_identities
                        WHERE identity_key = %s
                        LIMIT 1
                        """,
                        (alias_identity_key,),
                    )
                    alias_identity_row = cursor.fetchone()
                    if alias_identity_row is not None:
                        alias_identity_id = int(alias_identity_row[0])
                        if alias_identity_id != identity_id:
                            cursor.execute(
                                """
                                UPDATE attendance_identities
                                SET is_active = FALSE
                                WHERE id = %s
                                """,
                                (alias_identity_id,),
                            )
                            alias_identity_deactivated = cursor.rowcount > 0
            connection.commit()

        return AttendanceAliasIdentitySyncResult(
            alias_id=int(alias_id),
            identity_id=identity_id,
            identity_key=identity_key,
            identity_created=identity_created,
            alias_identity_id=alias_identity_id,
            alias_identity_deactivated=alias_identity_deactivated,
        )

    def rebuild_from_participants(self) -> AttendanceIdentityRebuildResult:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH instructor_names AS (
                        SELECT lower(instructor_name) AS name_key
                        FROM attendance_instructors
                    ),
                    source_participants AS (
                        SELECT
                            p.canonical_full_name,
                            NULLIF(lower(trim(p.email)), '') AS email
                        FROM attendance_lesson_participants AS p
                        JOIN attendance_lessons AS l
                            ON l.id = p.lesson_id
                        WHERE l.is_ignored = FALSE
                          AND NOT COALESCE(p.flags_json ? 'ignored_participant', FALSE)
                          AND NOT COALESCE(p.flags_json ? 'local_merged_participant', FALSE)
                          AND trim(p.canonical_full_name) <> ''
                          AND NOT EXISTS (
                              SELECT 1
                              FROM instructor_names AS i
                              WHERE i.name_key IN (
                                  lower(p.canonical_full_name),
                                  lower(COALESCE(p.raw_full_name, ''))
                              )
                          )
                    )
                    SELECT
                        canonical_full_name,
                        email
                    FROM source_participants
                    """
                )
                participant_rows = cursor.fetchall()

        source_identities = self._build_canonical_identities(participant_rows)
        if not source_identities:
            return AttendanceIdentityRebuildResult(source_identities=0, rows_upserted=0, identities_count=0)

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO attendance_identities (
                        identity_key,
                        display_name,
                        email
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (identity_key)
                    DO UPDATE SET
                        display_name = COALESCE(NULLIF(attendance_identities.display_name, ''), EXCLUDED.display_name),
                        email = COALESCE(attendance_identities.email, EXCLUDED.email)
                    """,
                    [
                        (identity.identity_key, identity.display_name, identity.email)
                        for identity in source_identities
                    ],
                )
                rows_upserted = cursor.rowcount
                cursor.execute("SELECT COUNT(*) FROM attendance_identities")
                identities_count_row = cursor.fetchone()
            connection.commit()

        return AttendanceIdentityRebuildResult(
            source_identities=len(source_identities),
            rows_upserted=int(rows_upserted),
            identities_count=int(identities_count_row[0]) if identities_count_row else 0,
        )

    def _build_canonical_identities(self, participant_rows: list[tuple]) -> list[AttendanceIdentity]:
        name_alias_map, email_alias_map = _load_identity_alias_maps(PostgresAttendanceIdentityAliasRepository())
        raw_items: list[tuple[str, str | None]] = []
        emails_by_name: dict[str, set[str]] = {}
        for row in participant_rows:
            full_name = " ".join(str(row[0] or "").strip().split())
            email = str(row[1]).strip().casefold() if row[1] else None
            if not full_name:
                continue
            canonical_name, canonical_email = _apply_identity_alias_maps(
                full_name,
                email,
                name_alias_map,
                email_alias_map,
            )
            canonical_name = " ".join(canonical_name.strip().split())
            canonical_email = canonical_email.strip().casefold() if canonical_email else None
            if not canonical_name:
                continue
            raw_items.append((canonical_name, canonical_email))
            name_key = _normalize_identity_key(canonical_name)
            if name_key and canonical_email:
                emails_by_name.setdefault(name_key, set()).add(canonical_email)

        identities_by_key: dict[str, AttendanceIdentity] = {}
        for full_name, email in raw_items:
            name_key = _normalize_identity_key(full_name)
            known_emails = emails_by_name.get(name_key, set())
            compatible_key = _compatible_identity_key(
                full_name,
                email,
                emails_by_name,
            )
            identity_email = compatible_key if compatible_key in known_emails else email
            identity_key = f"email:{identity_email}" if identity_email and compatible_key == identity_email else f"name:{compatible_key}"
            existing = identities_by_key.get(identity_key)
            if existing is None:
                identities_by_key[identity_key] = AttendanceIdentity(
                    id=0,
                    identity_key=identity_key,
                    display_name=full_name,
                    email=identity_email or None,
                    is_active=True,
                )
                continue
            identities_by_key[identity_key] = AttendanceIdentity(
                id=existing.id,
                identity_key=identity_key,
                display_name=existing.display_name,
                email=existing.email or identity_email or None,
                is_active=existing.is_active,
            )

        return sorted(
            identities_by_key.values(),
            key=lambda identity: (identity.display_name.casefold(), identity.email or "", identity.identity_key),
        )


def _clean_name(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _clean_email(value: object) -> str | None:
    email = str(value or "").strip().casefold()
    return email or None


def _identity_key(full_name: str, email: str | None) -> str:
    if email:
        return f"email:{email}"
    return f"name:{_normalize_identity_key(full_name)}"


def _alias_identity_key(alias_value: str, alias_type: str) -> str:
    if alias_type == "email":
        return f"email:{alias_value.strip().casefold()}"
    return f"name:{_normalize_identity_key(alias_value)}"
