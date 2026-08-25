import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from backend.attendance_app.lesson_enrichment import (
    PlannedLessonSourceRow,
    normalize_course_label,
    parse_planned_lesson_values,
)
from backend.db.attendance_lesson_enrichment_repository import PostgresAttendanceLessonEnrichmentRepository


HEADERS = [
    "lesson_id", "docente", "tutor", "", "vecchio_titolo", "titolo_evento",
    "argomento", "data", "ora_inizio", "ora_fine", "destinatari",
    "url_cartella_drive", "url_zoom",
]


class PlannedLessonParsingTests(unittest.TestCase):
    def test_parses_relevant_lesson_columns_and_first_recipient(self):
        rows, warnings = parse_planned_lesson_values(
            [
                HEADERS,
                [
                    1209,
                    "SG",
                    "SG",
                    "",
                    "SG SG Practitioner",
                    "Practitioner",
                    "Il generatore di un nuovo comportamento",
                    46106,
                    19 / 24,
                    22.5 / 24,
                    "PRACTITIONER, ASSISTENTI_PRACTITIONER, MENTORE_AZIENDALE",
                    "https://drive.example/folder",
                    "https://zoom.example/register",
                ],
            ]
        )

        self.assertEqual(warnings, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].external_lesson_id, "1209")
        self.assertEqual(rows[0].lesson_date, date(2026, 3, 25))
        self.assertEqual(rows[0].start_time, time(19, 0))
        self.assertEqual(rows[0].end_time, time(22, 30))
        self.assertEqual(rows[0].home_recipient_key, "PRACTITIONER")
        self.assertEqual(len(rows[0].recipients), 3)

    def test_skips_duplicate_external_ids(self):
        values = [HEADERS]
        values.append([1209, "", "", "", "", "Practitioner", "A", 46106, "19:00", "22:30", "PRACTITIONER"])
        values.append([1209, "", "", "", "", "Practitioner", "B", 46107, "19:00", "22:30", "PRACTITIONER"])

        rows, warnings = parse_planned_lesson_values(values)

        self.assertEqual(len(rows), 1)
        self.assertEqual(len(warnings), 1)
        self.assertIn("duplicato", warnings[0])

    def test_normalizes_course_labels_without_fuzzy_matching(self):
        self.assertEqual(normalize_course_label("Direttore_vendite"), "DIRETTORE VENDITE")
        self.assertEqual(normalize_course_label("  Direttore   Vendite "), "DIRETTORE VENDITE")


class LessonMatchingTests(unittest.TestCase):
    def setUp(self):
        self.repository = PostgresAttendanceLessonEnrichmentRepository()
        self.source = PlannedLessonSourceRow(
            row_number=5,
            external_lesson_id="1303",
            event_title="DIRETTORE VENDITE",
            topic="HR 1",
            lesson_date=date(2026, 1, 15),
            start_time=time(18, 0),
            end_time=time(21, 30),
            recipients=["SALES_DIRECTOR"],
            drive_url=None,
            zoom_url=None,
        )
        self.lesson = {
            "id": 42,
            "course_name": "DIRETTORE VENDITE",
            "lesson_date": date(2026, 1, 15),
            "meeting_start_at": datetime(2026, 1, 15, 18, 3, tzinfo=ZoneInfo("Europe/Zurich")),
            "external_lesson_id": None,
            "planned_source_hash": None,
            "catalog_course_edition_id": None,
        }

    def test_matches_date_and_explicit_attendance_name(self):
        target, method, failure = self.repository._match_row(
            self.source,
            {"sales_director": (8, 3)},
            {3: {"DIRETTORE VENDITE"}},
            {self.source.lesson_date: [self.lesson]},
            {},
            set(),
        )

        self.assertEqual(target["id"], 42)
        self.assertEqual(method, "date_and_logical_course")
        self.assertIsNone(failure)

    def test_does_not_guess_without_catalog_mapping(self):
        target, method, failure = self.repository._match_row(
            self.source,
            {},
            {},
            {self.source.lesson_date: [self.lesson]},
            {},
            set(),
        )

        self.assertIsNone(target)
        self.assertIsNone(method)
        self.assertEqual(failure, "missing_catalog_mapping")

    def test_does_not_reuse_lesson_already_claimed_in_same_import(self):
        target, _, failure = self.repository._match_row(
            self.source,
            {"sales_director": (8, 3)},
            {3: {"DIRETTORE VENDITE"}},
            {self.source.lesson_date: [self.lesson]},
            {},
            {42},
        )

        self.assertIsNone(target)
        self.assertEqual(failure, "missing_attendance_lesson")


if __name__ == "__main__":
    unittest.main()
