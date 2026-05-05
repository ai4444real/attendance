"""PostgreSQL read-only queries for attendance draft imports."""

from __future__ import annotations

from datetime import datetime

from backend.attendance_app.models import (
    DraftBatchDetail,
    DraftLessonSummary,
    DraftLessonParticipantView,
    DraftLessonSourceSegment,
    DraftReviewActionView,
    DraftLessonView,
    ImportBatchSummary,
)

from .connection import get_db_connection


class PostgresAttendanceDraftQueryRepository:
    """Read draft batches, lessons and participants from PostgreSQL."""

    def list_batches(self, limit: int = 20) -> list[ImportBatchSummary]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        b.id,
                        b.source_system,
                        b.source_file_name,
                        b.status,
                        b.created_at,
                        COUNT(DISTINCT l.id) AS lessons_count,
                        COUNT(p.id) AS participants_count
                    FROM attendance_import_batches AS b
                    LEFT JOIN attendance_lessons AS l
                        ON l.import_batch_id = b.id
                    LEFT JOIN attendance_lesson_participants AS p
                        ON p.lesson_id = l.id
                    WHERE EXISTS (
                        SELECT 1
                        FROM attendance_lessons AS lx
                        WHERE lx.import_batch_id = b.id
                          AND lx.status = 'draft'
                          AND lx.is_ignored = FALSE
                    )
                    GROUP BY b.id
                    ORDER BY b.created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()

        return [
            ImportBatchSummary(
                id=int(row[0]),
                source_system=str(row[1]),
                source_file_name=str(row[2]),
                status=str(row[3]),
                created_at=_ensure_datetime(row[4]),
                lessons_count=int(row[5]),
                participants_count=int(row[6]),
            )
            for row in rows
        ]

    def get_batch_detail(self, batch_id: int) -> DraftBatchDetail:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        b.id,
                        b.source_system,
                        b.source_file_name,
                        b.status,
                        b.created_at,
                        COUNT(DISTINCT l.id) AS lessons_count,
                        COUNT(p.id) AS participants_count
                    FROM attendance_import_batches AS b
                    LEFT JOIN attendance_lessons AS l
                        ON l.import_batch_id = b.id
                    LEFT JOIN attendance_lesson_participants AS p
                        ON p.lesson_id = l.id
                    WHERE b.id = %s
                    GROUP BY b.id
                    """,
                    (batch_id,),
                )
                batch_row = cursor.fetchone()
                if batch_row is None:
                    raise LookupError(f"Attendance import batch {batch_id} not found.")

                batch = ImportBatchSummary(
                    id=int(batch_row[0]),
                    source_system=str(batch_row[1]),
                    source_file_name=str(batch_row[2]),
                    status=str(batch_row[3]),
                    created_at=_ensure_datetime(batch_row[4]),
                    lessons_count=int(batch_row[5]),
                    participants_count=int(batch_row[6]),
                )

                cursor.execute(
                    """
                    SELECT
                        l.id,
                        l.course_name,
                        l.lesson_date,
                        l.source_meeting_id,
                        l.status,
                        l.is_ignored,
                        l.threshold_ratio
                    FROM attendance_lessons AS l
                    WHERE l.import_batch_id = %s
                    ORDER BY l.lesson_date DESC, l.course_name ASC, l.id ASC
                    """,
                    (batch_id,),
                )
                lesson_rows = cursor.fetchall()

                lessons: list[DraftLessonSummary] = []
                for lesson_row in lesson_rows:
                    lesson_id = int(lesson_row[0])
                    summary = self._load_lesson_summary(cursor, lesson_id)

                    lessons.append(
                        DraftLessonSummary(
                            id=lesson_id,
                            course_name=str(lesson_row[1]),
                            lesson_date=lesson_row[2].isoformat(),
                            source_meeting_id=str(lesson_row[3]),
                            status=str(lesson_row[4]),
                            is_ignored=bool(lesson_row[5]),
                            threshold_ratio=float(lesson_row[6]),
                            summary=summary,
                        )
                    )

        return DraftBatchDetail(batch=batch, lessons=lessons)

    def get_lesson_detail(self, lesson_id: int) -> DraftLessonView:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        l.id,
                        l.course_name,
                        l.lesson_date,
                        l.source_meeting_id,
                        l.status,
                        l.is_ignored,
                        l.threshold_ratio,
                        l.meeting_start_at,
                        l.meeting_end_at,
                        l.effective_start_at,
                        l.break_point_at,
                        l.effective_end_at,
                        l.break_source,
                        l.effective_start_source,
                        l.effective_end_source,
                        l.warnings_json,
                        l.diagnostics_json
                    FROM attendance_lessons AS l
                    WHERE l.id = %s
                    """,
                    (lesson_id,),
                )
                lesson_row = cursor.fetchone()
                if lesson_row is None:
                    raise LookupError(f"Attendance lesson {lesson_id} not found.")

                cursor.execute(
                    """
                    SELECT
                        p.id,
                        p.participant_key,
                        p.canonical_full_name,
                        p.raw_full_name,
                        p.email,
                        p.segment_count,
                        p.minutes_first_half,
                        p.minutes_second_half,
                        p.duration_first_half,
                        p.duration_second_half,
                        p.total_minutes,
                        p.calculated_presence_status,
                        p.manual_override_presence_status,
                        p.final_presence_status,
                        p.flags_json,
                        p.metadata_json
                    FROM attendance_lesson_participants AS p
                    WHERE p.lesson_id = %s
                    ORDER BY p.canonical_full_name ASC
                    """,
                    (lesson_id,),
                )
                participant_rows = cursor.fetchall()
                participants = [
                    DraftLessonParticipantView(
                        id=int(row[0]),
                        participant_key=str(row[1]),
                        canonical_full_name=str(row[2]),
                        raw_full_name=row[3],
                        email=row[4],
                        segment_count=int(row[5]),
                        minutes_first_half=float(row[6]),
                        minutes_second_half=float(row[7]),
                        duration_first_half=float(row[8]),
                        duration_second_half=float(row[9]),
                        total_minutes=float(row[10]),
                        calculated_presence_status=str(row[11]),
                        manual_override_presence_status=row[12],
                        final_presence_status=str(row[13]),
                        flags=list(row[14] or []),
                        metadata=dict(row[15] or {}),
                    )
                    for row in participant_rows
                ]

                cursor.execute(
                    """
                    SELECT
                        ra.id,
                        ra.lesson_id,
                        ra.participant_id,
                        ra.action_type,
                        ra.payload_json,
                        ra.created_by,
                        ra.created_at,
                        ra.applied_at,
                        ra.is_applied,
                        ra.notes
                    FROM attendance_review_actions AS ra
                    WHERE ra.lesson_id = %s
                    ORDER BY ra.created_at DESC, ra.id DESC
                    """,
                    (lesson_id,),
                )
                action_rows = cursor.fetchall()
                review_actions = [
                    DraftReviewActionView(
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
                    for row in action_rows
                ]

                summary = self._load_lesson_summary(cursor, lesson_id)

        return DraftLessonView(
            id=int(lesson_row[0]),
            course_name=str(lesson_row[1]),
            lesson_date=lesson_row[2].isoformat(),
            source_meeting_id=str(lesson_row[3]),
            status=str(lesson_row[4]),
            is_ignored=bool(lesson_row[5]),
            threshold_ratio=float(lesson_row[6]),
            meeting_start_at=_ensure_datetime(lesson_row[7]).isoformat(),
            meeting_end_at=_ensure_datetime(lesson_row[8]).isoformat(),
            effective_start_at=_ensure_datetime(lesson_row[9]).isoformat(),
            break_point_at=_optional_datetime_iso(lesson_row[10]),
            effective_end_at=_ensure_datetime(lesson_row[11]).isoformat(),
            break_source=str(lesson_row[12]),
            effective_start_source=str(lesson_row[13]),
            effective_end_source=str(lesson_row[14]),
            warnings=list(lesson_row[15] or []),
            diagnostics=dict(lesson_row[16] or {}),
            summary=summary,
            participants=participants,
            review_actions=review_actions,
        )

    def get_lesson_source_segments(self, lesson_id: int) -> list[DraftLessonSourceSegment]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        observed_full_name,
                        observed_email,
                        join_time,
                        leave_time,
                        metadata_json
                    FROM attendance_lesson_source_segments
                    WHERE lesson_id = %s
                    ORDER BY join_time ASC, leave_time ASC
                    """,
                    (lesson_id,),
                )
                rows = cursor.fetchall()
        return [
            DraftLessonSourceSegment(
                observed_full_name=str(row[0]),
                observed_email=row[1],
                join_time=_ensure_datetime(row[2]).isoformat(),
                leave_time=_ensure_datetime(row[3]).isoformat(),
                metadata=dict(row[4] or {}),
            )
            for row in rows
        ]

    def _load_lesson_summary(self, cursor, lesson_id: int) -> dict[str, int]:
        cursor.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE p.final_presence_status = 'presente') AS presente,
                COUNT(*) FILTER (WHERE p.final_presence_status = 'prima_meta') AS prima_meta,
                COUNT(*) FILTER (WHERE p.final_presence_status = 'seconda_meta') AS seconda_meta,
                COUNT(*) FILTER (WHERE p.final_presence_status = 'assente') AS assente
            FROM attendance_lesson_participants AS p
            WHERE p.lesson_id = %s
            """,
            (lesson_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return {"presente": 0, "prima_meta": 0, "seconda_meta": 0, "assente": 0}
        return {
            "presente": int(row[0]),
            "prima_meta": int(row[1]),
            "seconda_meta": int(row[2]),
            "assente": int(row[3]),
        }


def _ensure_datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise RuntimeError("Expected datetime from PostgreSQL.")
    return value


def _optional_datetime_iso(value: object) -> str | None:
    if value is None:
        return None
    return _ensure_datetime(value).isoformat()
