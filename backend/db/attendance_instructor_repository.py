"""PostgreSQL persistence for attendance instructors."""

from __future__ import annotations

from backend.attendance_app.models import AttendanceInstructor

from .connection import get_db_connection


class PostgresAttendanceInstructorRepository:
    """Read/write instructor names and aliases."""

    def list_instructors(self) -> list[AttendanceInstructor]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        i.id,
                        i.instructor_name,
                        i.alias_of_id,
                        c.instructor_name AS canonical_name,
                        i.notes,
                        i.created_at,
                        i.updated_at
                    FROM attendance_instructors AS i
                    LEFT JOIN attendance_instructors AS c
                        ON c.id = i.alias_of_id
                    ORDER BY
                        COALESCE(c.instructor_name, i.instructor_name) ASC,
                        i.alias_of_id NULLS FIRST,
                        i.instructor_name ASC
                    """
                )
                rows = cursor.fetchall()
        return [
            AttendanceInstructor(
                id=int(row[0]),
                instructor_name=str(row[1]),
                alias_of_id=int(row[2]) if row[2] is not None else None,
                canonical_name=str(row[3]) if row[3] is not None else None,
                notes=row[4],
                created_at=row[5],
                updated_at=row[6],
            )
            for row in rows
        ]

    def create_instructor(
        self,
        *,
        instructor_name: str,
        alias_of_id: int | None = None,
        notes: str | None = None,
    ) -> AttendanceInstructor:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO attendance_instructors (
                        instructor_name,
                        alias_of_id,
                        notes
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (lower(instructor_name))
                    DO UPDATE SET
                        alias_of_id = EXCLUDED.alias_of_id,
                        notes = EXCLUDED.notes,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (instructor_name, alias_of_id, notes),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("Failed to save attendance instructor.")
                instructor_id = int(row[0])
            connection.commit()

        return self.get_instructor(instructor_id)

    def get_instructor(self, instructor_id: int) -> AttendanceInstructor:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        i.id,
                        i.instructor_name,
                        i.alias_of_id,
                        c.instructor_name AS canonical_name,
                        i.notes,
                        i.created_at,
                        i.updated_at
                    FROM attendance_instructors AS i
                    LEFT JOIN attendance_instructors AS c
                        ON c.id = i.alias_of_id
                    WHERE i.id = %s
                    """,
                    (instructor_id,),
                )
                row = cursor.fetchone()
        if row is None:
            raise LookupError(f"Attendance instructor {instructor_id} not found.")
        return AttendanceInstructor(
            id=int(row[0]),
            instructor_name=str(row[1]),
            alias_of_id=int(row[2]) if row[2] is not None else None,
            canonical_name=str(row[3]) if row[3] is not None else None,
            notes=row[4],
            created_at=row[5],
            updated_at=row[6],
        )
