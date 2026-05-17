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
    SchoolAttendanceRecordView,
    AttendanceIdentityCandidateView,
    SchoolCourseLessonView,
    SchoolCourseOverviewView,
    SchoolStudentFollowupView,
)

from .connection import get_db_connection


class PostgresAttendanceDraftQueryRepository:
    """Read draft batches, lessons and participants from PostgreSQL."""

    def list_batches(self, limit: int = 20, scope: str = "open") -> list[ImportBatchSummary]:
        if scope not in {"open", "closed", "all"}:
            raise ValueError(f"Unsupported batch scope: {scope}")
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                where_clause = ""
                if scope == "open":
                    where_clause = """
                    WHERE EXISTS (
                        SELECT 1
                        FROM attendance_lessons AS lx
                        WHERE lx.import_batch_id = b.id
                          AND lx.status = 'draft'
                          AND lx.is_ignored = FALSE
                    )
                    """
                elif scope == "closed":
                    where_clause = """
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM attendance_lessons AS lx
                        WHERE lx.import_batch_id = b.id
                          AND lx.status = 'draft'
                          AND lx.is_ignored = FALSE
                    )
                    """
                cursor.execute(
                    f"""
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
                    {where_clause}
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
                    WITH instructor_names AS (
                        SELECT lower(instructor_name) AS name_key
                        FROM attendance_instructors
                    )
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
                    ORDER BY l.lesson_date ASC, l.course_name ASC, l.id ASC
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
                    WITH instructor_names AS (
                        SELECT lower(instructor_name) AS name_key
                        FROM attendance_instructors
                    )
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
                        p.presence_source,
                        p.flags_json,
                        p.metadata_json
                    FROM attendance_lesson_participants AS p
                    WHERE p.lesson_id = %s
                      AND NOT EXISTS (
                          SELECT 1
                          FROM attendance_instructors AS i
                          WHERE lower(i.instructor_name) IN (
                              lower(p.canonical_full_name),
                              lower(COALESCE(p.raw_full_name, ''))
                          )
                      )
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
                        presence_source=str(row[14]),
                        flags=list(row[15] or []),
                        metadata=dict(row[16] or {}),
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

    def list_lesson_ids_for_identity_rebuild(self) -> list[int]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT l.id
                    FROM attendance_lessons AS l
                    WHERE l.is_ignored = FALSE
                      AND EXISTS (
                          SELECT 1
                          FROM attendance_lesson_source_segments AS s
                          WHERE s.lesson_id = l.id
                      )
                    ORDER BY l.id ASC
                    """
                )
                rows = cursor.fetchall()
        return [int(row[0]) for row in rows]

    def search_identity_candidates(self, query: str, limit: int = 30) -> list[AttendanceIdentityCandidateView]:
        normalized_query = " ".join((query or "").strip().split())
        if len(normalized_query) < 2:
            return []
        safe_limit = max(1, min(int(limit or 30), 80))
        pattern = f"%{normalized_query}%"
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH instructor_names AS (
                        SELECT lower(instructor_name) AS name_key
                        FROM attendance_instructors
                    )
                    SELECT
                        p.canonical_full_name,
                        p.email,
                        COUNT(*) AS appearances_count,
                        COUNT(DISTINCT p.lesson_id) AS lessons_count,
                        MAX(l.lesson_date) AS last_seen_at
                    FROM attendance_lesson_participants AS p
                    JOIN attendance_lessons AS l
                        ON l.id = p.lesson_id
                    WHERE l.is_ignored = FALSE
                      AND (
                          p.canonical_full_name ILIKE %s
                          OR COALESCE(p.email, '') ILIKE %s
                          OR COALESCE(p.raw_full_name, '') ILIKE %s
                      )
                      AND NOT EXISTS (
                          SELECT 1
                          FROM instructor_names AS i
                          WHERE i.name_key IN (
                              lower(p.canonical_full_name),
                              lower(COALESCE(p.raw_full_name, ''))
                          )
                      )
                    GROUP BY p.canonical_full_name, p.email
                    ORDER BY p.canonical_full_name ASC, p.email ASC NULLS LAST
                    LIMIT %s
                    """,
                    (pattern, pattern, pattern, safe_limit),
                )
                rows = cursor.fetchall()

        return [
            AttendanceIdentityCandidateView(
                canonical_full_name=str(row[0]),
                email=row[1],
                appearances_count=int(row[2]),
                lessons_count=int(row[3]),
                last_seen_at=row[4].isoformat(),
            )
            for row in rows
        ]

    def list_school_attendance_records(self) -> list[SchoolAttendanceRecordView]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH instructor_names AS (
                        SELECT lower(instructor_name) AS name_key
                        FROM attendance_instructors
                    ),
                    official_lessons AS (
                        SELECT
                            id,
                            course_name,
                            lesson_date
                        FROM attendance_lessons
                        WHERE status = 'official'
                          AND is_ignored = FALSE
                    ),
                    lesson_counts AS (
                        SELECT
                            course_name,
                            COUNT(*) AS official_lessons_count
                        FROM official_lessons
                        GROUP BY course_name
                    )
                    SELECT
                        l.id,
                        l.course_name,
                        l.lesson_date,
                        p.canonical_full_name,
                        p.email,
                        p.final_presence_status,
                        COALESCE(c.expected_lessons_count, lc.official_lessons_count) AS expected_lessons_count,
                        CASE
                            WHEN c.expected_lessons_count IS NULL THEN 'official_lessons'
                            ELSE 'configured'
                        END AS expected_lessons_source
                    FROM official_lessons AS l
                    JOIN attendance_lesson_participants AS p
                        ON p.lesson_id = l.id
                    JOIN lesson_counts AS lc
                        ON lc.course_name = l.course_name
                    LEFT JOIN attendance_courses AS c
                        ON c.course_name = l.course_name
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM instructor_names AS i
                        WHERE i.name_key IN (
                            lower(p.canonical_full_name),
                            lower(COALESCE(p.raw_full_name, ''))
                        )
                    )
                    ORDER BY l.course_name ASC, l.lesson_date ASC, p.canonical_full_name ASC, p.id ASC
                    """
                )
                rows = cursor.fetchall()

        return [
            SchoolAttendanceRecordView(
                lesson_id=int(row[0]),
                course_name=str(row[1]),
                lesson_date=row[2].isoformat(),
                canonical_full_name=str(row[3]),
                email=row[4],
                final_presence_status=str(row[5]),
                expected_lessons_count=int(row[6]),
                expected_lessons_source=str(row[7]),
            )
            for row in rows
        ]

    def list_school_course_overview(self) -> list[SchoolCourseOverviewView]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH instructor_names AS (
                        SELECT lower(instructor_name) AS name_key
                        FROM attendance_instructors
                    )
                    SELECT
                        l.id,
                        l.course_name,
                        l.lesson_date,
                        l.source_meeting_id,
                        c.expected_lessons_count,
                        COUNT(p.id) AS total_records,
                        COUNT(*) FILTER (WHERE p.final_presence_status = 'presente') AS presente_count,
                        COUNT(*) FILTER (WHERE p.final_presence_status = 'prima_meta') AS prima_meta_count,
                        COUNT(*) FILTER (WHERE p.final_presence_status = 'seconda_meta') AS seconda_meta_count,
                        COUNT(*) FILTER (WHERE p.final_presence_status = 'assente') AS assente_count
                    FROM attendance_lessons AS l
                    LEFT JOIN attendance_courses AS c
                        ON c.course_name = l.course_name
                    LEFT JOIN attendance_lesson_participants AS p
                        ON p.lesson_id = l.id
                       AND NOT EXISTS (
                           SELECT 1
                           FROM instructor_names AS i
                           WHERE i.name_key IN (
                               lower(p.canonical_full_name),
                               lower(COALESCE(p.raw_full_name, ''))
                           )
                       )
                    WHERE l.status = 'official'
                      AND l.is_ignored = FALSE
                    GROUP BY l.id, c.expected_lessons_count
                    ORDER BY l.course_name ASC, l.lesson_date ASC, l.id ASC
                    """
                )
                rows = cursor.fetchall()

        grouped_by_course: dict[str, list[SchoolCourseLessonView]] = {}
        expected_by_course: dict[str, int | None] = {}
        for row in rows:
            lesson = SchoolCourseLessonView(
                lesson_id=int(row[0]),
                course_name=str(row[1]),
                lesson_date=row[2].isoformat(),
                source_meeting_id=str(row[3]),
                total_records=int(row[5]),
                presente_count=int(row[6]),
                prima_meta_count=int(row[7]),
                seconda_meta_count=int(row[8]),
                assente_count=int(row[9]),
            )
            expected_by_course.setdefault(lesson.course_name, int(row[4]) if row[4] is not None else None)
            grouped_by_course.setdefault(lesson.course_name, []).append(lesson)

        course_overviews: list[SchoolCourseOverviewView] = []
        for course_name, lessons in grouped_by_course.items():
            configured_expected = expected_by_course.get(course_name)
            course_overviews.append(
                SchoolCourseOverviewView(
                    course_name=course_name,
                    expected_lessons_count=configured_expected if configured_expected is not None else len(lessons),
                    expected_lessons_source="configured" if configured_expected is not None else "official_lessons",
                    lessons=lessons,
                )
            )
        return course_overviews

    def list_school_student_followups(
        self,
        *,
        recent_lessons_limit: int = 4,
        missed_lessons_threshold: int = 3,
    ) -> list[SchoolStudentFollowupView]:
        if recent_lessons_limit <= 0:
            raise ValueError("recent_lessons_limit must be positive.")
        if missed_lessons_threshold <= 0:
            raise ValueError("missed_lessons_threshold must be positive.")

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH instructor_names AS (
                        SELECT lower(instructor_name) AS name_key
                        FROM attendance_instructors
                    ),
                    ranked_lessons AS (
                        SELECT
                            l.id,
                            l.course_name,
                            l.lesson_date,
                            ROW_NUMBER() OVER (
                                PARTITION BY l.course_name
                                ORDER BY l.lesson_date DESC, l.id DESC
                            ) AS lesson_rank
                        FROM attendance_lessons AS l
                        WHERE l.status = 'official'
                          AND l.is_ignored = FALSE
                    ),
                    recent_lessons AS (
                        SELECT
                            id,
                            course_name,
                            lesson_date
                        FROM ranked_lessons
                        WHERE lesson_rank <= %s
                    ),
                    course_students AS (
                        SELECT
                            l.course_name,
                            p.canonical_full_name,
                            MIN(p.email) FILTER (WHERE p.email IS NOT NULL AND p.email <> '') AS email
                        FROM attendance_lessons AS l
                        JOIN attendance_lesson_participants AS p
                            ON p.lesson_id = l.id
                        WHERE l.status = 'official'
                          AND l.is_ignored = FALSE
                          AND NOT EXISTS (
                              SELECT 1
                              FROM instructor_names AS i
                              WHERE i.name_key IN (
                                  lower(p.canonical_full_name),
                                  lower(COALESCE(p.raw_full_name, ''))
                              )
                          )
                        GROUP BY l.course_name, p.canonical_full_name
                    ),
                    student_recent_lessons AS (
                        SELECT
                            cs.course_name,
                            cs.canonical_full_name,
                            cs.email,
                            rl.id AS lesson_id,
                            rl.lesson_date,
                            CASE WHEN p.id IS NULL THEN FALSE ELSE TRUE END AS attended
                        FROM course_students AS cs
                        JOIN recent_lessons AS rl
                            ON rl.course_name = cs.course_name
                        LEFT JOIN attendance_lesson_participants AS p
                            ON p.lesson_id = rl.id
                           AND p.canonical_full_name = cs.canonical_full_name
                    ),
                    aggregated AS (
                        SELECT
                            course_name,
                            canonical_full_name,
                            email,
                            COUNT(*) AS checked_lessons_count,
                            COUNT(*) FILTER (WHERE attended = FALSE) AS missed_lessons_count,
                            COUNT(*) FILTER (WHERE attended = TRUE) AS attended_lessons_count,
                            jsonb_agg(
                                jsonb_build_object(
                                    'lesson_id', lesson_id,
                                    'lesson_date', lesson_date,
                                    'attended', attended
                                )
                                ORDER BY lesson_date ASC, lesson_id ASC
                            ) AS recent_lessons_json
                        FROM student_recent_lessons
                        GROUP BY course_name, canonical_full_name, email
                    )
                    SELECT
                        course_name,
                        canonical_full_name,
                        email,
                        checked_lessons_count,
                        missed_lessons_count,
                        attended_lessons_count,
                        recent_lessons_json
                    FROM aggregated
                    WHERE checked_lessons_count = %s
                      AND missed_lessons_count >= %s
                    ORDER BY missed_lessons_count DESC, course_name ASC, canonical_full_name ASC
                    """,
                    (recent_lessons_limit, recent_lessons_limit, missed_lessons_threshold),
                )
                rows = cursor.fetchall()

        return [
            SchoolStudentFollowupView(
                course_name=str(row[0]),
                canonical_full_name=str(row[1]),
                email=row[2],
                checked_lessons_count=int(row[3]),
                missed_lessons_count=int(row[4]),
                attended_lessons_count=int(row[5]),
                recent_lessons=[
                    {
                        "lesson_id": str(item["lesson_id"]),
                        "lesson_date": item["lesson_date"],
                        "attended": bool(item["attended"]),
                    }
                    for item in list(row[6] or [])
                ],
            )
            for row in rows
        ]

    def _load_lesson_summary(self, cursor, lesson_id: int) -> dict[str, int]:
        cursor.execute(
            """
            WITH instructor_names AS (
                SELECT lower(instructor_name) AS name_key
                FROM attendance_instructors
            )
            SELECT
                COUNT(*) FILTER (WHERE p.final_presence_status = 'presente') AS presente,
                COUNT(*) FILTER (WHERE p.final_presence_status = 'prima_meta') AS prima_meta,
                COUNT(*) FILTER (WHERE p.final_presence_status = 'seconda_meta') AS seconda_meta,
                COUNT(*) FILTER (WHERE p.final_presence_status = 'assente') AS assente
            FROM attendance_lesson_participants AS p
            WHERE p.lesson_id = %s
              AND NOT EXISTS (
                  SELECT 1
                  FROM instructor_names AS i
                  WHERE i.name_key IN (
                      lower(p.canonical_full_name),
                      lower(COALESCE(p.raw_full_name, ''))
                  )
              )
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
