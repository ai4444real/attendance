from datetime import datetime
import unittest

from backend.attendance_normalization.aggregator import ZoomMeeting, ZoomSegment
from backend.attendance_normalization.meeting_selection import (
    filter_meetings_by_courses,
    is_excluded_course_name,
    is_uppercase_course_name,
    preselected_course_names,
)


def meeting(course: str, meeting_id: str) -> ZoomMeeting:
    return ZoomMeeting(
        course=course,
        meeting_id=meeting_id,
        start_time=datetime.fromisoformat("2026-04-10T19:00:00"),
        end_time=datetime.fromisoformat("2026-04-10T20:00:00"),
        duration_minutes=60,
        segments=[
            ZoomSegment(
                first_name="Mario",
                last_name="Rossi",
                email="mario@example.com",
                full_name="Mario Rossi",
                join_time=datetime.fromisoformat("2026-04-10T19:00:00"),
                leave_time=datetime.fromisoformat("2026-04-10T20:00:00"),
            )
        ],
    )


class UppercaseCourseRuleTests(unittest.TestCase):
    def test_accepts_names_with_only_uppercase_letters(self):
        self.assertTrue(is_uppercase_course_name("PNL PRACTITIONER"))

    def test_accepts_uppercase_even_with_numbers_and_symbols(self):
        self.assertTrue(is_uppercase_course_name("PNL 2026 - MODULO 1"))

    def test_rejects_mixed_case_names(self):
        self.assertFalse(is_uppercase_course_name("Pnl Practitioner"))

    def test_rejects_when_letters_are_missing(self):
        self.assertFalse(is_uppercase_course_name("2026 - 01"))

    def test_excludes_esame_and_team_meeting_patterns(self):
        self.assertTrue(is_excluded_course_name("ESAME"))
        self.assertTrue(is_excluded_course_name("TEAM MEETING"))
        self.assertTrue(is_excluded_course_name("TEAM   MEETING DOCENTI"))
        self.assertFalse(is_excluded_course_name("PRACTITIONER"))


class MeetingSelectionTests(unittest.TestCase):
    def test_preselects_unique_uppercase_courses_in_sorted_order(self):
        meetings = [
            meeting("PNL MASTER", "m-1"),
            meeting("Pnl Master", "m-2"),
            meeting("PNL BASE", "m-3"),
            meeting("PNL MASTER", "m-4"),
            meeting("ESAME", "m-5"),
            meeting("TEAM MEETING", "m-6"),
        ]

        selected = preselected_course_names(meetings)

        self.assertEqual(selected, ["PNL BASE", "PNL MASTER"])

    def test_filters_meetings_by_selected_course_names(self):
        meetings = [
            meeting("PNL MASTER", "m-1"),
            meeting("Pnl Master", "m-2"),
            meeting("PNL BASE", "m-3"),
            meeting("TEAM MEETING", "m-4"),
        ]

        filtered = filter_meetings_by_courses(meetings, {"PNL BASE", "PNL MASTER"})

        self.assertEqual([m.meeting_id for m in filtered], ["m-1", "m-3"])


if __name__ == "__main__":
    unittest.main()
