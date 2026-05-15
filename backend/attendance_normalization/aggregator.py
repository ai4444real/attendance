"""Meeting aggregation logic migrated from ``attendance/adapter/js/aggregator.js``.

This module intentionally keeps the "marker" problem outside of itself:
- the caller provides ``effective_start`` (blue marker)
- the caller provides ``break_point`` (yellow marker)

That keeps aggregation deterministic and easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable


MAX_RECONNECT_GAP_MINUTES = 5.0


@dataclass(frozen=True)
class ZoomSegment:
    first_name: str
    last_name: str
    email: str
    full_name: str
    join_time: datetime
    leave_time: datetime


@dataclass(frozen=True)
class ZoomMeeting:
    course: str
    meeting_id: str
    start_time: datetime
    end_time: datetime
    duration_minutes: float
    segments: list[ZoomSegment]


@dataclass(frozen=True)
class AttendanceAggregationRecord:
    course: str
    meeting_id: str
    date: datetime
    meeting_start: datetime
    meeting_end: datetime
    meeting_duration: float
    first_name: str
    last_name: str
    email: str
    full_name: str
    minutes_first_half: float
    minutes_second_half: float
    duration_first_half: float
    duration_second_half: float
    total_minutes: float
    segment_count: int
    segments: list[tuple[datetime, datetime]]
    first_half_end: datetime
    second_half_start: datetime


def aggregate_meeting(
    meeting: ZoomMeeting,
    effective_start: datetime,
    break_point: datetime,
    effective_end: datetime | None = None,
) -> list[AttendanceAggregationRecord]:
    """Aggregate a single meeting into one record per participant.

    This mirrors the current JavaScript adapter behavior when explicit markers
    are already available.
    """

    if not meeting.segments:
        return []

    effective_meeting_end = effective_end or meeting.end_time
    first_half_end = break_point
    second_half_start = break_point

    duration_first_half = _minutes_between(effective_start, first_half_end)
    duration_second_half = _minutes_between(second_half_start, effective_meeting_end)

    records: list[AttendanceAggregationRecord] = []
    for participant_segments in _group_by_participant(meeting.segments).values():
        first = participant_segments[0]
        raw_intervals = [
            (segment.join_time, segment.leave_time)
            for segment in participant_segments
        ]
        attendance_intervals = _merge_nearby_intervals(raw_intervals)

        minutes_first_half = 0.0
        minutes_second_half = 0.0

        for segment_start, segment_end in attendance_intervals:
            minutes_first_half += _overlap_minutes(
                segment_start,
                segment_end,
                effective_start,
                first_half_end,
            )
            minutes_second_half += _overlap_minutes(
                segment_start,
                segment_end,
                second_half_start,
                effective_meeting_end,
            )

        records.append(
            AttendanceAggregationRecord(
                course=meeting.course,
                meeting_id=meeting.meeting_id,
                date=meeting.start_time,
                meeting_start=meeting.start_time,
                meeting_end=effective_meeting_end,
                meeting_duration=meeting.duration_minutes,
                first_name=first.first_name,
                last_name=first.last_name,
                email=first.email,
                full_name=first.full_name,
                minutes_first_half=_round1(minutes_first_half),
                minutes_second_half=_round1(minutes_second_half),
                duration_first_half=_round1(duration_first_half),
                duration_second_half=_round1(duration_second_half),
                total_minutes=_round1(minutes_first_half + minutes_second_half),
                segment_count=len(participant_segments),
                segments=raw_intervals,
                first_half_end=first_half_end,
                second_half_start=second_half_start,
            )
        )

    return records


def _group_by_participant(
    segments: Iterable[ZoomSegment],
) -> dict[str, list[ZoomSegment]]:
    groups: dict[str, list[ZoomSegment]] = {}
    for segment in segments:
        key = segment.email or segment.full_name
        groups.setdefault(key, []).append(segment)
    return groups


def _overlap_minutes(
    segment_start: datetime,
    segment_end: datetime,
    range_start: datetime,
    range_end: datetime,
) -> float:
    start = max(segment_start, range_start)
    end = min(segment_end, range_end)
    return max(0.0, (end - start).total_seconds() / 60)


def _merge_nearby_intervals(
    intervals: list[tuple[datetime, datetime]],
    max_gap: timedelta = timedelta(minutes=MAX_RECONNECT_GAP_MINUTES),
) -> list[tuple[datetime, datetime]]:
    if not intervals:
        return []

    ordered = sorted(intervals, key=lambda interval: interval[0])
    merged: list[list[datetime]] = [[ordered[0][0], ordered[0][1]]]

    for start, end in ordered[1:]:
        last = merged[-1]
        if start <= last[1] + max_gap:
            if end > last[1]:
                last[1] = end
        else:
            merged.append([start, end])

    return [(start, end) for start, end in merged]


def _minutes_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 60


def _round1(value: float) -> float:
    return round(value, 1)
