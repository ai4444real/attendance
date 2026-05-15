from datetime import datetime
import unittest

from backend.attendance_normalization.aggregator import (
    ZoomMeeting,
    ZoomSegment,
    aggregate_meeting,
)


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class AggregateMeetingTests(unittest.TestCase):
    def test_aggregates_one_segment_across_both_halves_with_explicit_markers(self):
        meeting = ZoomMeeting(
            course="PNL Practicum",
            meeting_id="m-001",
            start_time=dt("2026-04-10T18:50:00"),
            end_time=dt("2026-04-10T21:00:00"),
            duration_minutes=130,
            segments=[
                ZoomSegment(
                    first_name="Mario",
                    last_name="Rossi",
                    email="mario@example.com",
                    full_name="Mario Rossi",
                    join_time=dt("2026-04-10T18:55:00"),
                    leave_time=dt("2026-04-10T20:05:00"),
                )
            ],
        )

        records = aggregate_meeting(
            meeting=meeting,
            effective_start=dt("2026-04-10T19:00:00"),
            break_point=dt("2026-04-10T20:00:00"),
        )

        self.assertEqual(len(records), 1)
        record = records[0]

        self.assertEqual(record.minutes_first_half, 60.0)
        self.assertEqual(record.minutes_second_half, 5.0)
        self.assertEqual(record.duration_first_half, 60.0)
        self.assertEqual(record.duration_second_half, 60.0)
        self.assertEqual(record.total_minutes, 65.0)
        self.assertEqual(record.segment_count, 1)

    def test_sums_multiple_segments_for_the_same_participant(self):
        meeting = ZoomMeeting(
            course="PNL Practicum",
            meeting_id="m-002",
            start_time=dt("2026-04-10T19:00:00"),
            end_time=dt("2026-04-10T21:00:00"),
            duration_minutes=120,
            segments=[
                ZoomSegment(
                    first_name="Mario",
                    last_name="Rossi",
                    email="mario@example.com",
                    full_name="Mario Rossi",
                    join_time=dt("2026-04-10T19:10:00"),
                    leave_time=dt("2026-04-10T19:30:00"),
                ),
                ZoomSegment(
                    first_name="Mario",
                    last_name="Rossi",
                    email="mario@example.com",
                    full_name="Mario Rossi",
                    join_time=dt("2026-04-10T20:10:00"),
                    leave_time=dt("2026-04-10T20:40:00"),
                ),
            ],
        )

        records = aggregate_meeting(
            meeting=meeting,
            effective_start=dt("2026-04-10T19:00:00"),
            break_point=dt("2026-04-10T20:00:00"),
        )

        self.assertEqual(len(records), 1)
        record = records[0]

        self.assertEqual(record.minutes_first_half, 20.0)
        self.assertEqual(record.minutes_second_half, 30.0)
        self.assertEqual(record.total_minutes, 50.0)
        self.assertEqual(record.segment_count, 2)

    def test_merges_reconnect_gaps_and_overlaps_for_attendance_minutes(self):
        meeting = ZoomMeeting(
            course="PNL Practicum",
            meeting_id="m-reconnect",
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
                    leave_time=dt("2026-04-10T19:03:00"),
                ),
                ZoomSegment(
                    first_name="Mario",
                    last_name="Rossi",
                    email="mario@example.com",
                    full_name="Mario Rossi",
                    join_time=dt("2026-04-10T19:03:00"),
                    leave_time=dt("2026-04-10T19:04:00"),
                ),
                ZoomSegment(
                    first_name="Mario",
                    last_name="Rossi",
                    email="mario@example.com",
                    full_name="Mario Rossi",
                    join_time=dt("2026-04-10T19:06:00"),
                    leave_time=dt("2026-04-10T19:08:00"),
                ),
                ZoomSegment(
                    first_name="Mario",
                    last_name="Rossi",
                    email="mario@example.com",
                    full_name="Mario Rossi",
                    join_time=dt("2026-04-10T19:06:00"),
                    leave_time=dt("2026-04-10T19:08:00"),
                ),
            ],
        )

        records = aggregate_meeting(
            meeting=meeting,
            effective_start=dt("2026-04-10T19:00:00"),
            break_point=dt("2026-04-10T20:00:00"),
        )

        record = records[0]

        self.assertEqual(record.minutes_first_half, 8.0)
        self.assertEqual(record.total_minutes, 8.0)
        self.assertEqual(record.segment_count, 4)
        self.assertEqual(len(record.segments), 4)

    def test_effective_start_trims_minutes_before_the_real_lesson_start(self):
        meeting = ZoomMeeting(
            course="PNL Practicum",
            meeting_id="m-003",
            start_time=dt("2026-04-10T18:45:00"),
            end_time=dt("2026-04-10T20:30:00"),
            duration_minutes=105,
            segments=[
                ZoomSegment(
                    first_name="Lucia",
                    last_name="Verdi",
                    email="lucia@example.com",
                    full_name="Lucia Verdi",
                    join_time=dt("2026-04-10T18:50:00"),
                    leave_time=dt("2026-04-10T19:20:00"),
                )
            ],
        )

        records = aggregate_meeting(
            meeting=meeting,
            effective_start=dt("2026-04-10T19:00:00"),
            break_point=dt("2026-04-10T19:45:00"),
        )

        self.assertEqual(len(records), 1)
        record = records[0]

        self.assertEqual(record.minutes_first_half, 20.0)
        self.assertEqual(record.minutes_second_half, 0.0)
        self.assertEqual(record.duration_first_half, 45.0)
        self.assertEqual(record.duration_second_half, 45.0)

    def test_uses_full_name_when_email_is_missing(self):
        meeting = ZoomMeeting(
            course="PNL Practicum",
            meeting_id="m-004",
            start_time=dt("2026-04-10T19:00:00"),
            end_time=dt("2026-04-10T21:00:00"),
            duration_minutes=120,
            segments=[
                ZoomSegment(
                    first_name="Anna",
                    last_name="Bianchi",
                    email="",
                    full_name="Anna Bianchi",
                    join_time=dt("2026-04-10T19:05:00"),
                    leave_time=dt("2026-04-10T19:25:00"),
                ),
                ZoomSegment(
                    first_name="Anna",
                    last_name="Bianchi",
                    email="",
                    full_name="Anna Bianchi",
                    join_time=dt("2026-04-10T20:05:00"),
                    leave_time=dt("2026-04-10T20:20:00"),
                ),
            ],
        )

        records = aggregate_meeting(
            meeting=meeting,
            effective_start=dt("2026-04-10T19:00:00"),
            break_point=dt("2026-04-10T20:00:00"),
        )

        self.assertEqual(len(records), 1)
        record = records[0]

        self.assertEqual(record.full_name, "Anna Bianchi")
        self.assertEqual(record.email, "")
        self.assertEqual(record.minutes_first_half, 20.0)
        self.assertEqual(record.minutes_second_half, 15.0)
        self.assertEqual(record.segment_count, 2)

    def test_rounds_minutes_and_durations_to_one_decimal(self):
        meeting = ZoomMeeting(
            course="PNL Practicum",
            meeting_id="m-005",
            start_time=dt("2026-04-10T19:00:00"),
            end_time=dt("2026-04-10T20:00:00"),
            duration_minutes=60,
            segments=[
                ZoomSegment(
                    first_name="Paolo",
                    last_name="Neri",
                    email="paolo@example.com",
                    full_name="Paolo Neri",
                    join_time=dt("2026-04-10T19:00:15"),
                    leave_time=dt("2026-04-10T19:30:45"),
                )
            ],
        )

        records = aggregate_meeting(
            meeting=meeting,
            effective_start=dt("2026-04-10T19:00:00"),
            break_point=dt("2026-04-10T19:30:00"),
        )

        record = records[0]

        self.assertEqual(record.minutes_first_half, 29.8)
        self.assertEqual(record.minutes_second_half, 0.8)
        self.assertEqual(record.duration_first_half, 30.0)
        self.assertEqual(record.duration_second_half, 30.0)
        self.assertEqual(record.total_minutes, 30.5)

    def test_effective_end_trims_tail_minutes_after_the_real_lesson_end(self):
        meeting = ZoomMeeting(
            course="PNL Practicum",
            meeting_id="m-006",
            start_time=dt("2026-04-10T19:00:00"),
            end_time=dt("2026-04-10T20:00:00"),
            duration_minutes=60,
            segments=[
                ZoomSegment(
                    first_name="Paolo",
                    last_name="Neri",
                    email="paolo@example.com",
                    full_name="Paolo Neri",
                    join_time=dt("2026-04-10T19:25:00"),
                    leave_time=dt("2026-04-10T20:00:00"),
                )
            ],
        )

        records = aggregate_meeting(
            meeting=meeting,
            effective_start=dt("2026-04-10T19:00:00"),
            break_point=dt("2026-04-10T19:30:00"),
            effective_end=dt("2026-04-10T19:49:00"),
        )

        record = records[0]

        self.assertEqual(record.minutes_first_half, 5.0)
        self.assertEqual(record.minutes_second_half, 19.0)
        self.assertEqual(record.duration_first_half, 30.0)
        self.assertEqual(record.duration_second_half, 19.0)
        self.assertEqual(record.meeting_end, dt("2026-04-10T19:49:00"))


if __name__ == "__main__":
    unittest.main()
