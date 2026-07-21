"""PostgreSQL implementation for observed attendance identities."""

from __future__ import annotations

from backend.attendance_app.services import (
    _apply_identity_alias_maps,
    _compatible_identity_key,
    _load_identity_alias_maps,
    _normalize_identity_key,
)
from backend.attendance_app.models import AttendanceIdentity, AttendanceIdentityRebuildResult

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
                        identity_key,
                        display_name,
                        email
                    FROM attendance_identities
                    ORDER BY display_name ASC, email ASC NULLS LAST, identity_key ASC
                    LIMIT %s
                    """,
                    (safe_limit,),
                )
                rows = cursor.fetchall()

        return [
            AttendanceIdentity(
                identity_key=str(row[0]),
                display_name=str(row[1]),
                email=row[2],
            )
            for row in rows
        ]

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
                    identity_key=identity_key,
                    display_name=full_name,
                    email=identity_email or None,
                )
                continue
            identities_by_key[identity_key] = AttendanceIdentity(
                identity_key=identity_key,
                display_name=existing.display_name,
                email=existing.email or identity_email or None,
            )

        return sorted(
            identities_by_key.values(),
            key=lambda identity: (identity.display_name.casefold(), identity.email or "", identity.identity_key),
        )
