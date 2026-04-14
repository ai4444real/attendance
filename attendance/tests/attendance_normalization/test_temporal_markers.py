from datetime import datetime
import unittest

from backend.attendance_normalization.aggregator import ZoomMeeting, ZoomSegment
from backend.attendance_normalization.temporal_markers import (
    detect_break_window,
    snap_effective_start,
)


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SnapEffectiveStartTests(unittest.TestCase):
    def test_snaps_1923_to_1930(self):
        self.assertEqual(
            snap_effective_start(dt("2026-04-10T19:23:00")),
            dt("2026-04-10T19:30:00"),
        )

    def test_snaps_1947_to_2000(self):
        self.assertEqual(
            snap_effective_start(dt("2026-04-10T19:47:00")),
            dt("2026-04-10T20:00:00"),
        )

    def test_does_not_snap_before_real_zoom_start(self):
        self.assertEqual(
            snap_effective_start(dt("2026-04-10T19:08:00")),
            dt("2026-04-10T19:08:00"),
        )

    def test_does_not_snap_after_the_meeting_end_when_meeting_is_too_short(self):
        self.assertEqual(
            snap_effective_start(
                dt("2026-04-10T18:50:00"),
                meeting_end=dt("2026-04-10T18:51:00"),
            ),
            dt("2026-04-10T18:50:00"),
        )


class DetectBreakWindowTests(unittest.TestCase):
    def test_detects_a_real_valley_when_most_people_disconnect_for_a_break(self):
        segments = []
        for name in ["Mario", "Lucia", "Anna", "Paolo"]:
            segments.extend(
                [
                    ZoomSegment(
                        first_name=name,
                        last_name="Rossi",
                        email=f"{name.lower()}@example.com",
                        full_name=f"{name} Rossi",
                        join_time=dt("2026-04-10T19:00:00"),
                        leave_time=dt("2026-04-10T19:50:00"),
                    ),
                    ZoomSegment(
                        first_name=name,
                        last_name="Rossi",
                        email=f"{name.lower()}@example.com",
                        full_name=f"{name} Rossi",
                        join_time=dt("2026-04-10T20:05:00"),
                        leave_time=dt("2026-04-10T21:00:00"),
                    ),
                ]
            )

        meeting = ZoomMeeting(
            course="PNL Practicum",
            meeting_id="m-valley",
            start_time=dt("2026-04-10T19:00:00"),
            end_time=dt("2026-04-10T21:00:00"),
            duration_minutes=120,
            segments=segments,
        )

        detected = detect_break_window(meeting)

        self.assertIsNotNone(detected)
        self.assertEqual(detected.break_start, dt("2026-04-10T19:50:00"))
        self.assertEqual(detected.break_end, dt("2026-04-10T20:05:00"))

    def test_detects_boundary_when_many_people_leave_together_without_long_valley(self):
        leave_times = [
            dt("2026-04-10T20:00:00"),
            dt("2026-04-10T20:00:15"),
            dt("2026-04-10T20:00:30"),
            dt("2026-04-10T20:00:45"),
            dt("2026-04-10T20:01:00"),
        ]
        segments = []
        names = ["Mario", "Lucia", "Anna", "Paolo", "Sara"]
        for name, leave_time in zip(names, leave_times):
            segments.extend(
                [
                    ZoomSegment(
                        first_name=name,
                        last_name="Rossi",
                        email=f"{name.lower()}@example.com",
                        full_name=f"{name} Rossi",
                        join_time=dt("2026-04-10T19:00:00"),
                        leave_time=leave_time,
                    ),
                    ZoomSegment(
                        first_name=name,
                        last_name="Rossi",
                        email=f"{name.lower()}@example.com",
                        full_name=f"{name} Rossi",
                        join_time=dt("2026-04-10T20:04:00"),
                        leave_time=dt("2026-04-10T21:00:00"),
                    ),
                ]
            )

        meeting = ZoomMeeting(
            course="PNL Practicum",
            meeting_id="m-boundary",
            start_time=dt("2026-04-10T19:00:00"),
            end_time=dt("2026-04-10T21:00:00"),
            duration_minutes=120,
            segments=segments,
        )

        detected = detect_break_window(meeting)

        self.assertIsNotNone(detected)
        self.assertEqual(detected.break_start, dt("2026-04-10T20:00:30"))
        self.assertEqual(detected.break_end, dt("2026-04-10T20:00:30"))

    def test_returns_none_when_no_break_pattern_is_detected(self):
        meeting = ZoomMeeting(
            course="PNL Practicum",
            meeting_id="m-none",
            start_time=dt("2026-04-10T19:00:00"),
            end_time=dt("2026-04-10T21:00:00"),
            duration_minutes=120,
            segments=[
                ZoomSegment(
                    first_name="Mario",
                    last_name="Rossi",
                    email="mario@example.com",
                    full_name="Mario Rossi",
                    join_time=dt("2026-04-10T19:00:00"),
                    leave_time=dt("2026-04-10T21:00:00"),
                ),
                ZoomSegment(
                    first_name="Lucia",
                    last_name="Verdi",
                    email="lucia@example.com",
                    full_name="Lucia Verdi",
                    join_time=dt("2026-04-10T19:05:00"),
                    leave_time=dt("2026-04-10T20:55:00"),
                ),
            ],
        )

        self.assertIsNone(detect_break_window(meeting))


if __name__ == "__main__":
    unittest.main()
