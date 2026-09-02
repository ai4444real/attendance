from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.attendance_app.legacy_lesson_topics import LegacyLessonTopicRow
from backend.attendance_app.lesson_enrichment import normalize_course_label

from .connection import get_db_connection


class PostgresAttendanceLegacyTopicRepository:
    def import_rows(self, rows: list[LegacyLessonTopicRow], *, apply: bool) -> dict:
        details: list[dict] = []
        counts: dict[str, int] = defaultdict(int)
        claimed: set[int] = set()
        source_conflicts = self._source_conflicts(rows)

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                label_courses, course_attendance_labels = self._load_catalog_labels(cursor)
                lessons_by_date = self._load_lessons(cursor)
                for source in sorted(rows, key=lambda row: (row.start_time is None, row.row_number)):
                    base = {"row": source.row_number, "course": source.course_name, "date": source.lesson_date.isoformat(), "topic": source.topic}
                    source_key = (normalize_course_label(source.course_name), source.lesson_date, source.start_time)
                    if source_key in source_conflicts:
                        status = "conflitto_nel_csv"
                        details.append({**base, "reason": status})
                        counts[status] += 1
                        continue

                    source_label = normalize_course_label(source.course_name)
                    logical_ids = label_courses.get(source_label, set())
                    accepted_labels = {source_label}
                    for course_id in logical_ids:
                        accepted_labels.update(course_attendance_labels.get(course_id, set()))
                    candidates = [lesson for lesson in lessons_by_date.get(source.lesson_date, []) if lesson[0] not in claimed and normalize_course_label(lesson[1]) in accepted_labels]
                    target = self._pick_candidate(source, candidates)
                    if target is None:
                        status = "lezione_ambigua" if candidates else "lezione_non_trovata"
                        details.append({**base, "reason": status})
                        counts[status] += 1
                        continue

                    lesson_id, attendance_course, _, current_topic, current_source = target
                    claimed.add(lesson_id)
                    if current_topic == source.topic and current_source == "manual":
                        status = "invariata"
                    elif apply:
                        cursor.execute(
                            "UPDATE attendance_lessons SET topic = %s, topic_source = 'manual', updated_at = NOW() WHERE id = %s",
                            (source.topic, lesson_id),
                        )
                        status = "aggiornata"
                    else:
                        status = "da_aggiornare"
                    counts[status] += 1
                    details.append({**base, "reason": status, "lesson_id": lesson_id, "attendance_course": attendance_course})
            if apply:
                connection.commit()
            else:
                connection.rollback()
        return {"rows_read": len(rows), "apply": apply, "counts": dict(counts), "details": sorted(details, key=lambda item: item["row"])}

    @staticmethod
    def _source_conflicts(rows):
        topics: dict[tuple, set[str]] = defaultdict(set)
        for row in rows:
            topics[(normalize_course_label(row.course_name), row.lesson_date, row.start_time)].add(row.topic)
        return {key for key, values in topics.items() if len(values) > 1}

    @staticmethod
    def _pick_candidate(source, candidates):
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1 and source.start_time:
            scheduled = datetime.combine(source.lesson_date, source.start_time, tzinfo=ZoneInfo("Europe/Zurich"))
            ranked = sorted((abs((lesson[2].astimezone(ZoneInfo("Europe/Zurich")) - scheduled).total_seconds()), lesson) for lesson in candidates if lesson[2])
            if ranked and ranked[0][0] <= 4 * 3600 and (len(ranked) == 1 or ranked[0][0] < ranked[1][0]):
                return ranked[0][1]
        return None

    @staticmethod
    def _load_catalog_labels(cursor):
        cursor.execute(
            """
            SELECT c.id, c.code, c.display_name, li.identifier_value, e.edition_key, e.display_name, ei.identifier_value
            FROM attendance_catalog_courses c
            LEFT JOIN attendance_catalog_logical_course_identifiers li ON li.course_id = c.id AND li.identifier_type = 'attendance_course_name'
            LEFT JOIN attendance_catalog_course_editions e ON e.course_id = c.id
            LEFT JOIN attendance_catalog_course_identifiers ei ON ei.course_edition_id = e.id AND ei.identifier_type = 'recipient_key'
            """
        )
        label_courses: dict[str, set[int]] = defaultdict(set)
        attendance_labels: dict[int, set[str]] = defaultdict(set)
        for course_id, code, display_name, logical_identifier, edition_key, edition_name, recipient_key in cursor.fetchall():
            course_id = int(course_id)
            for value in (code, display_name, edition_key, edition_name, recipient_key):
                if value:
                    label_courses[normalize_course_label(str(value))].add(course_id)
            for value in (code, display_name, logical_identifier):
                if value:
                    attendance_labels[course_id].add(normalize_course_label(str(value)))
        return label_courses, attendance_labels

    @staticmethod
    def _load_lessons(cursor):
        cursor.execute(
            """
            SELECT id, course_name, meeting_start_at, topic, topic_source, lesson_date
            FROM attendance_lessons
            WHERE status = 'official' AND is_ignored = FALSE AND lesson_date >= DATE '2025-01-01' AND lesson_date < DATE '2026-01-01'
            ORDER BY lesson_date, id
            """
        )
        lessons: dict = defaultdict(list)
        for lesson_id, course, start_at, topic, topic_source, lesson_date in cursor.fetchall():
            lessons[lesson_date].append((int(lesson_id), str(course), start_at, topic, topic_source))
        return lessons
