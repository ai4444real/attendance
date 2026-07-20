"""PostgreSQL implementation for observed attendance identities."""

from __future__ import annotations

from backend.attendance_app.models import AttendanceIdentity, AttendanceIdentityRebuildResult

from .connection import get_db_connection


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
                    source_identities AS (
                        SELECT
                            CASE
                                WHEN NULLIF(lower(trim(p.email)), '') IS NOT NULL
                                    THEN 'email:' || NULLIF(lower(trim(p.email)), '')
                                ELSE 'name:' || lower(regexp_replace(trim(p.canonical_full_name), '\\s+', ' ', 'g'))
                            END AS identity_key,
                            MIN(p.canonical_full_name) AS display_name,
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
                        GROUP BY
                            CASE
                                WHEN NULLIF(lower(trim(p.email)), '') IS NOT NULL
                                    THEN 'email:' || NULLIF(lower(trim(p.email)), '')
                                ELSE 'name:' || lower(regexp_replace(trim(p.canonical_full_name), '\\s+', ' ', 'g'))
                            END,
                            NULLIF(lower(trim(p.email)), '')
                    ),
                    upserted AS (
                        INSERT INTO attendance_identities (
                            identity_key,
                            display_name,
                            email
                        )
                        SELECT
                            identity_key,
                            display_name,
                            email
                        FROM source_identities
                        ON CONFLICT (identity_key)
                        DO UPDATE SET
                            display_name = COALESCE(NULLIF(attendance_identities.display_name, ''), EXCLUDED.display_name),
                            email = COALESCE(attendance_identities.email, EXCLUDED.email)
                        RETURNING identity_key
                    )
                    SELECT
                        (SELECT COUNT(*) FROM source_identities) AS source_identities_count,
                        (SELECT COUNT(*) FROM upserted) AS rows_upserted,
                        (SELECT COUNT(*) FROM attendance_identities) AS identities_count
                    """
                )
                row = cursor.fetchone()
            connection.commit()

        if row is None:
            return AttendanceIdentityRebuildResult(
                source_identities=0,
                rows_upserted=0,
                identities_count=0,
            )

        return AttendanceIdentityRebuildResult(
            source_identities=int(row[0]),
            rows_upserted=int(row[1]),
            identities_count=int(row[2]),
        )
