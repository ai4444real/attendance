from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from zoneinfo import ZoneInfo

from backend.attendance_app.lesson_enrichment import (
    LessonEnrichmentImportResult,
    PlannedLessonSourceRow,
    normalize_course_label,
)

from .connection import get_db_connection


class PostgresAttendanceLessonEnrichmentRepository:
    def import_google_rows(
        self,
        rows: list[PlannedLessonSourceRow],
        parse_warnings: list[str] | None = None,
    ) -> LessonEnrichmentImportResult:
        matched = updated = unchanged = 0
        missing_catalog_mapping = missing_attendance_lesson = ambiguous = 0
        warnings = list(parse_warnings or [])
        claimed_lesson_ids: set[int] = set()

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                recipient_map = self._load_recipient_map(cursor)
                course_labels = self._load_course_labels(cursor)
                lessons_by_date, lessons_by_external_id = self._load_lessons(cursor)

                for source_row in rows:
                    target, match_method, failure = self._match_row(
                        source_row,
                        recipient_map,
                        course_labels,
                        lessons_by_date,
                        lessons_by_external_id,
                        claimed_lesson_ids,
                    )
                    if failure == "missing_catalog_mapping":
                        missing_catalog_mapping += 1
                        continue
                    if failure == "missing_attendance_lesson":
                        missing_attendance_lesson += 1
                        continue
                    if failure == "ambiguous":
                        ambiguous += 1
                        continue
                    if target is None:
                        continue

                    matched += 1
                    mapping = recipient_map.get(source_row.home_recipient_key.casefold()) if source_row.home_recipient_key else None
                    edition_id = mapping[0] if mapping else target["catalog_course_edition_id"]
                    claimed_lesson_ids.add(target["id"])
                    if (
                        target["external_lesson_id"] == source_row.external_lesson_id
                        and target["planned_source_hash"] == source_row.source_hash
                        and target["catalog_course_edition_id"] == edition_id
                    ):
                        unchanged += 1
                        continue

                    cursor.execute(
                        """
                        UPDATE attendance_lessons
                        SET catalog_course_edition_id = %s,
                            external_lesson_id = %s,
                            topic = CASE WHEN topic_source = 'manual' THEN topic ELSE %s END,
                            topic_source = CASE WHEN topic_source = 'manual' THEN topic_source ELSE 'google_sheets' END,
                            planned_event_title = %s,
                            planned_home_recipient_key = %s,
                            planned_recipients_json = %s::jsonb,
                            planned_start_time = %s,
                            planned_end_time = %s,
                            planned_drive_url = %s,
                            planned_zoom_url = %s,
                            planned_source_row_number = %s,
                            planned_source_hash = %s,
                            planned_match_method = %s,
                            planned_synced_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            edition_id,
                            source_row.external_lesson_id,
                            source_row.topic,
                            source_row.event_title,
                            source_row.home_recipient_key,
                            json.dumps(source_row.recipients, ensure_ascii=False),
                            source_row.start_time,
                            source_row.end_time,
                            source_row.drive_url,
                            source_row.zoom_url,
                            source_row.row_number,
                            source_row.source_hash,
                            match_method,
                            target["id"],
                        ),
                    )
                    updated += 1
                    target["external_lesson_id"] = source_row.external_lesson_id
                    target["planned_source_hash"] = source_row.source_hash
                    target["catalog_course_edition_id"] = edition_id
                    lessons_by_external_id[source_row.external_lesson_id].append(target)
            connection.commit()

        return LessonEnrichmentImportResult(
            rows_read=len(rows),
            matched=matched,
            updated=updated,
            unchanged=unchanged,
            missing_catalog_mapping=missing_catalog_mapping,
            missing_attendance_lesson=missing_attendance_lesson,
            ambiguous=ambiguous,
            skipped=len(warnings),
            warnings=warnings[:50],
        )

    def _load_recipient_map(self, cursor) -> dict[str, tuple[int, int | None]]:
        cursor.execute(
            """
            SELECT i.identifier_value, e.id, e.course_id
            FROM attendance_catalog_course_identifiers AS i
            JOIN attendance_catalog_course_editions AS e ON e.id = i.course_edition_id
            WHERE i.identifier_type = 'recipient_key'
            """
        )
        return {str(row[0]).strip().casefold(): (int(row[1]), int(row[2]) if row[2] else None) for row in cursor.fetchall()}

    def _load_course_labels(self, cursor) -> dict[int, set[str]]:
        cursor.execute(
            """
            SELECT c.id, c.code, c.display_name, i.identifier_value
            FROM attendance_catalog_courses AS c
            LEFT JOIN attendance_catalog_logical_course_identifiers AS i
              ON i.course_id = c.id AND i.identifier_type = 'attendance_course_name'
            """
        )
        labels: dict[int, set[str]] = defaultdict(set)
        for row in cursor.fetchall():
            course_id = int(row[0])
            labels[course_id].add(normalize_course_label(str(row[1])))
            labels[course_id].add(normalize_course_label(str(row[2])))
            if row[3]:
                labels[course_id].add(normalize_course_label(str(row[3])))
        return labels

    def _load_lessons(self, cursor):
        cursor.execute(
            """
            SELECT
                id, course_name, lesson_date, meeting_start_at,
                external_lesson_id, planned_source_hash, catalog_course_edition_id
            FROM attendance_lessons
            WHERE status = 'official' AND is_ignored = FALSE
            ORDER BY lesson_date, id
            """
        )
        by_date: dict = defaultdict(list)
        by_external_id: dict[str, list[dict]] = defaultdict(list)
        for row in cursor.fetchall():
            lesson = {
                "id": int(row[0]),
                "course_name": str(row[1]),
                "lesson_date": row[2],
                "meeting_start_at": row[3],
                "external_lesson_id": row[4],
                "planned_source_hash": row[5],
                "catalog_course_edition_id": int(row[6]) if row[6] else None,
            }
            by_date[lesson["lesson_date"]].append(lesson)
            if lesson["external_lesson_id"]:
                by_external_id[str(lesson["external_lesson_id"])].append(lesson)
        return by_date, by_external_id

    def _match_row(
        self,
        source_row,
        recipient_map,
        course_labels,
        lessons_by_date,
        lessons_by_external_id,
        claimed_lesson_ids,
    ):
        existing = lessons_by_external_id.get(source_row.external_lesson_id, [])
        if len(existing) == 1:
            return existing[0], "external_lesson_id", None
        if len(existing) > 1:
            return None, None, "ambiguous"

        home_key = source_row.home_recipient_key
        mapping = recipient_map.get(home_key.casefold()) if home_key else None
        if mapping is None or mapping[1] is None:
            return None, None, "missing_catalog_mapping"
        course_id = mapping[1]
        labels = course_labels.get(course_id, set())
        candidates = [
            lesson
            for lesson in lessons_by_date.get(source_row.lesson_date, [])
            if lesson["id"] not in claimed_lesson_ids
            if normalize_course_label(lesson["course_name"]) in labels
        ]
        if len(candidates) == 1:
            return candidates[0], "date_and_logical_course", None
        if len(candidates) > 1 and source_row.start_time:
            scheduled = datetime.combine(source_row.lesson_date, source_row.start_time, tzinfo=ZoneInfo("Europe/Zurich"))
            ranked = sorted(
                ((abs((lesson["meeting_start_at"].astimezone(ZoneInfo("Europe/Zurich")) - scheduled).total_seconds()), lesson) for lesson in candidates),
                key=lambda item: item[0],
            )
            if ranked[0][0] <= 4 * 3600 and (len(ranked) == 1 or ranked[0][0] < ranked[1][0]):
                return ranked[0][1], "date_logical_course_and_time", None
        if candidates:
            return None, None, "ambiguous"
        return None, None, "missing_attendance_lesson"
