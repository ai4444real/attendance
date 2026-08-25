from __future__ import annotations

from backend.attendance_app.course_catalog import CourseCatalogImportResult, CourseCatalogSourceRow

from .connection import get_db_connection


class PostgresAttendanceCourseCatalogRepository:
    def list_catalog(self) -> list[dict]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        e.id,
                        e.edition_key,
                        e.display_name,
                        e.source_system,
                        e.source_row_number,
                        e.last_imported_at,
                        c.id,
                        c.code,
                        c.display_name,
                        i.identifier_type,
                        i.identifier_value
                    FROM attendance_catalog_course_editions AS e
                    LEFT JOIN attendance_catalog_courses AS c ON c.id = e.course_id
                    LEFT JOIN attendance_catalog_course_identifiers AS i ON i.course_edition_id = e.id
                    ORDER BY lower(COALESCE(c.display_name, e.display_name)), lower(e.edition_key), i.identifier_type
                    """
                )
                rows = cursor.fetchall()

        editions: dict[int, dict] = {}
        for row in rows:
            edition = editions.setdefault(
                int(row[0]),
                {
                    "id": int(row[0]),
                    "edition_key": str(row[1]),
                    "display_name": str(row[2]),
                    "source_system": row[3],
                    "source_row_number": row[4],
                    "last_imported_at": row[5].isoformat() if row[5] else None,
                    "logical_course": (
                        {"id": int(row[6]), "code": str(row[7]), "display_name": str(row[8])}
                        if row[6] is not None
                        else None
                    ),
                    "identifiers": {},
                },
            )
            if row[9] is not None:
                edition["identifiers"].setdefault(str(row[9]), []).append(str(row[10]))
        return list(editions.values())

    def import_google_rows(self, rows: list[CourseCatalogSourceRow]) -> CourseCatalogImportResult:
        created = 0
        updated = 0
        unchanged = 0
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                for source_row in rows:
                    cursor.execute(
                        """
                        SELECT id, display_name, source_hash
                        FROM attendance_catalog_course_editions
                        WHERE lower(edition_key) = lower(%s)
                        FOR UPDATE
                        """,
                        (source_row.target_key,),
                    )
                    existing = cursor.fetchone()
                    if existing is None:
                        cursor.execute(
                            """
                            INSERT INTO attendance_catalog_course_editions (
                                edition_key, display_name, source_system, source_row_number,
                                source_hash, last_imported_at
                            )
                            VALUES (%s, %s, 'google_sheets', %s, %s, NOW())
                            RETURNING id
                            """,
                            (
                                source_row.target_key,
                                source_row.display_name,
                                source_row.row_number,
                                source_row.source_hash,
                            ),
                        )
                        edition_id = int(cursor.fetchone()[0])
                        created += 1
                    else:
                        edition_id = int(existing[0])
                        changed = str(existing[1]) != source_row.display_name or existing[2] != source_row.source_hash
                        cursor.execute(
                            """
                            UPDATE attendance_catalog_course_editions
                            SET display_name = %s,
                                source_system = 'google_sheets',
                                source_row_number = %s,
                                source_hash = %s,
                                last_imported_at = NOW(),
                                updated_at = CASE WHEN %s THEN NOW() ELSE updated_at END
                            WHERE id = %s
                            """,
                            (
                                source_row.display_name,
                                source_row.row_number,
                                source_row.source_hash,
                                changed,
                                edition_id,
                            ),
                        )
                        if changed:
                            updated += 1
                        else:
                            unchanged += 1

                    cursor.execute(
                        """
                        DELETE FROM attendance_catalog_course_identifiers
                        WHERE course_edition_id = %s AND source_system = 'google_sheets'
                        """,
                        (edition_id,),
                    )
                    for identifier_type, identifier_value in source_row.identifiers.items():
                        cursor.execute(
                            """
                            INSERT INTO attendance_catalog_course_identifiers (
                                course_edition_id, identifier_type, identifier_value, source_system
                            )
                            VALUES (%s, %s, %s, 'google_sheets')
                            ON CONFLICT (course_edition_id, identifier_type, identifier_value)
                            DO UPDATE SET source_system = EXCLUDED.source_system, updated_at = NOW()
                            """,
                            (edition_id, identifier_type, identifier_value),
                        )
            connection.commit()

        return CourseCatalogImportResult(
            rows_read=len(rows),
            created=created,
            updated=updated,
            unchanged=unchanged,
            skipped=0,
            warnings=[],
        )
