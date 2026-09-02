import unittest

from backend.attendance_app.legacy_lesson_topics import clean_legacy_topic, parse_legacy_lesson_topics_csv


class LegacyLessonTopicsTest(unittest.TestCase):
    def test_cleans_html_boilerplate_and_mojibake(self):
        value = '<p>Lâ€™Ok condizionato e le spinte</p><p><br></p><p>CORSO AVANZATO</p>'
        self.assertEqual("L’Ok condizionato e le spinte", clean_legacy_topic(value))

    def test_repairs_quotes_and_non_breaking_spaces(self):
        value = '<p>Le posizioni: \u00e2\u20ac\u0153a debito o a credito\u00e2\u20ac\x9d</p> Self leadership\u00c2\u00a0e\u00c2\u00a0s\u00c3\u00a9'
        expected = "Le posizioni: \u201ca debito o a credito\u201d Self leadership e s\u00e9"
        self.assertEqual(expected, clean_legacy_topic(value))

    def test_parses_semicolon_csv_and_start_time(self):
        content = (
            "start;end;corso;data;status;description\n"
            "07.01.2025, 19:00;;COACHING;2025-01-07;confirmed;<p>Basi del coaching</p>\n"
        ).encode("utf-8")
        rows, issues = parse_legacy_lesson_topics_csv(content)
        self.assertEqual([], issues)
        self.assertEqual(1, len(rows))
        self.assertEqual("19:00:00", rows[0].start_time.isoformat())
        self.assertEqual("Basi del coaching", rows[0].topic)


if __name__ == "__main__":
    unittest.main()
