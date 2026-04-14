import unittest

from backend.attendance_normalization import (
    STATUS_ABSENT,
    STATUS_FIRST_HALF,
    STATUS_PRESENT,
    STATUS_SECOND_HALF,
    determine_presence_status,
)


class DeterminePresenceStatusTests(unittest.TestCase):
    """Business cases derived from the current JavaScript adapter."""

    def test_returns_presente_when_both_halves_reach_threshold(self):
        result = determine_presence_status(
            minutes_first_half=40,
            minutes_second_half=40,
            duration_first_half=50,
            duration_second_half=50,
            threshold=0.8,
        )
        self.assertEqual(result, STATUS_PRESENT)

    def test_returns_prima_meta_when_only_first_half_reaches_threshold(self):
        result = determine_presence_status(
            minutes_first_half=40,
            minutes_second_half=20,
            duration_first_half=50,
            duration_second_half=50,
            threshold=0.8,
        )
        self.assertEqual(result, STATUS_FIRST_HALF)

    def test_returns_seconda_meta_when_only_second_half_reaches_threshold(self):
        result = determine_presence_status(
            minutes_first_half=20,
            minutes_second_half=40,
            duration_first_half=50,
            duration_second_half=50,
            threshold=0.8,
        )
        self.assertEqual(result, STATUS_SECOND_HALF)

    def test_returns_assente_when_neither_half_reaches_threshold(self):
        result = determine_presence_status(
            minutes_first_half=20,
            minutes_second_half=20,
            duration_first_half=50,
            duration_second_half=50,
            threshold=0.8,
        )
        self.assertEqual(result, STATUS_ABSENT)

    def test_counts_exact_threshold_as_valid_presence_for_that_half(self):
        result = determine_presence_status(
            minutes_first_half=40,
            minutes_second_half=40,
            duration_first_half=50,
            duration_second_half=50,
            threshold=0.8,
        )
        self.assertEqual(result, STATUS_PRESENT)

    def test_below_threshold_by_small_margin_does_not_count(self):
        result = determine_presence_status(
            minutes_first_half=39.9,
            minutes_second_half=40,
            duration_first_half=50,
            duration_second_half=50,
            threshold=0.8,
        )
        self.assertEqual(result, STATUS_SECOND_HALF)

    def test_zero_duration_half_can_never_count_as_present(self):
        result = determine_presence_status(
            minutes_first_half=0,
            minutes_second_half=20,
            duration_first_half=0,
            duration_second_half=20,
            threshold=0.8,
        )
        self.assertEqual(result, STATUS_SECOND_HALF)

    def test_custom_threshold_changes_the_result(self):
        result = determine_presence_status(
            minutes_first_half=35,
            minutes_second_half=35,
            duration_first_half=50,
            duration_second_half=50,
            threshold=0.7,
        )
        self.assertEqual(result, STATUS_PRESENT)

    def test_custom_threshold_can_leave_a_borderline_case_as_assente(self):
        result = determine_presence_status(
            minutes_first_half=34,
            minutes_second_half=20,
            duration_first_half=50,
            duration_second_half=50,
            threshold=0.7,
        )
        self.assertEqual(result, STATUS_ABSENT)


if __name__ == "__main__":
    unittest.main()
