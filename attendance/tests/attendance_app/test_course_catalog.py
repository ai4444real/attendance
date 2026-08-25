import unittest

from backend.attendance_app.course_catalog import (
    AttendanceCourseCatalogImportService,
    CourseCatalogImportResult,
    CourseCatalogSourceRow,
    parse_course_catalog_values,
)


class CourseCatalogParsingTests(unittest.TestCase):
    def test_parses_google_courses_without_inventing_logical_course(self):
        rows, warnings = parse_course_catalog_values(
            [
                ["target_key", "classroom_course_id", "calendar_id", "folder", "default_link"],
                [
                    "FSEA_21.03.2026",
                    "832312697255",
                    "c_classroomf436401b@group.calendar.google.com",
                    "Fsea 21.03.2026",
                    "https://zoom.example/register/fsea",
                ],
            ]
        )

        self.assertEqual(warnings, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].row_number, 2)
        self.assertEqual(rows[0].target_key, "FSEA_21.03.2026")
        self.assertEqual(rows[0].display_name, "Fsea 21.03.2026")
        self.assertEqual(
            rows[0].identifiers,
            {
                "recipient_key": "FSEA_21.03.2026",
                "classroom_course_id": "832312697255",
                "calendar_id": "c_classroomf436401b@group.calendar.google.com",
                "default_link": "https://zoom.example/register/fsea",
            },
        )

    def test_skips_blank_and_duplicate_target_keys_leniently(self):
        rows, warnings = parse_course_catalog_values(
            [
                ["target_key", "classroom_course_id", "calendar_id", "folder", "default_link"],
                ["PRACTITIONER", "123", "calendar", "Practitioner", ""],
                ["", "456", "calendar-2", "Senza chiave", ""],
                ["practitioner", "789", "calendar-3", "Duplicato", ""],
            ]
        )

        self.assertEqual([row.target_key for row in rows], ["PRACTITIONER"])
        self.assertEqual(len(warnings), 2)
        self.assertIn("target_key e' vuota", warnings[0])
        self.assertIn("target_key duplicata", warnings[1])

    def test_requires_target_key_header(self):
        with self.assertRaisesRegex(ValueError, "target_key"):
            parse_course_catalog_values([["name", "description"], ["FSEA", "Fsea"]])

    def test_source_hash_changes_when_source_data_changes(self):
        first = CourseCatalogSourceRow(2, "FSEA", "1", "cal", "Fsea", None)
        second = CourseCatalogSourceRow(2, "FSEA", "1", "cal", "Fsea aggiornata", None)

        self.assertNotEqual(first.source_hash, second.source_hash)


class CourseCatalogImportServiceTests(unittest.TestCase):
    def test_combines_reader_and_repository_warnings(self):
        source_row = CourseCatalogSourceRow(2, "FSEA", None, None, "Fsea", None)

        class Reader:
            def read_rows(self):
                return [source_row], ["avviso lettura"]

        class Repository:
            def import_google_rows(self, rows):
                self.rows = rows
                return CourseCatalogImportResult(1, 1, 0, 0, 0, ["avviso repository"])

        repository = Repository()
        result = AttendanceCourseCatalogImportService(repository, Reader()).import_from_google()

        self.assertEqual(repository.rows, [source_row])
        self.assertEqual(result.created, 1)
        self.assertEqual(result.warnings, ["avviso lettura", "avviso repository"])


if __name__ == "__main__":
    unittest.main()
