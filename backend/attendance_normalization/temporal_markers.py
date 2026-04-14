"""Temporal marker helpers migrated from the browser-side adapter.

This module mirrors the current JavaScript behavior:
- blue marker: snap meeting start toward :00 / :30, but never before the real start
- yellow marker: detect a break using the existing valley/boundary heuristics
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .aggregator import ZoomMeeting


@dataclass(frozen=True)
class BreakWindow:
    break_start: datetime
    break_end: datetime


VALLEY_DROP_THRESHOLD = 0.15
VALLEY_MIN_MINUTES = 5
BOUNDARY_WINDOW_SECONDS = 60
BOUNDARY_MIN_PARTICIPANTS = 0.4


def snap_effective_start(
    meeting_start: datetime,
    meeting_end: datetime | None = None,
) -> datetime:
    """Snap to the nearest :00 / :30 without leaving the meeting interval."""

    rounded = meeting_start.replace(second=0, microsecond=0)
    minutes = meeting_start.minute

    if minutes < 15:
        rounded = rounded.replace(minute=0)
    elif minutes < 45:
        rounded = rounded.replace(minute=30)
    else:
        rounded = rounded.replace(minute=0) + timedelta(hours=1)

    if rounded < meeting_start:
        return meeting_start
    if meeting_end is not None and rounded > meeting_end:
        return meeting_start
    return rounded


def detect_break_window(meeting: ZoomMeeting) -> BreakWindow | None:
    if not meeting.segments:
        return None

    valley = _detect_valley(meeting)
    if valley:
        return valley

    boundary = _detect_boundary(meeting)
    if boundary:
        return boundary

    return None


def _detect_valley(meeting: ZoomMeeting) -> BreakWindow | None:
    start = meeting.start_time
    end = meeting.end_time
    timeline = []
    current = start

    while current <= end:
        count = 0
        for segment in meeting.segments:
            if segment.join_time <= current < segment.leave_time:
                count += 1
        timeline.append((current, count))
        current += timedelta(minutes=1)

    peak = max(count for _, count in timeline)
    if peak < 2:
        return None

    cutoff = peak * VALLEY_DROP_THRESHOLD
    duration_seconds = (end - start).total_seconds()
    best: tuple[datetime, datetime] | None = None
    valley_start: datetime | None = None

    for point_time, count in timeline:
        if count <= cutoff:
            if valley_start is None:
                valley_start = point_time
        elif valley_start is not None:
            mid_valley = valley_start + (point_time - valley_start) / 2
            rel_pos = (mid_valley - start).total_seconds() / duration_seconds
            if 0.15 <= rel_pos <= 0.85:
                candidate = (valley_start, point_time)
                if best is None or (candidate[1] - candidate[0]) > (best[1] - best[0]):
                    best = candidate
            valley_start = None

    if valley_start is not None:
        mid_valley = valley_start + (end - valley_start) / 2
        rel_pos = (mid_valley - start).total_seconds() / duration_seconds
        if 0.15 <= rel_pos <= 0.85:
            candidate = (valley_start, end)
            if best is None or (candidate[1] - candidate[0]) > (best[1] - best[0]):
                best = candidate

    if best is None:
        return None

    if (best[1] - best[0]).total_seconds() / 60 < VALLEY_MIN_MINUTES:
        return None

    return BreakWindow(break_start=best[0], break_end=best[1])


def _detect_boundary(meeting: ZoomMeeting) -> BreakWindow | None:
    start = meeting.start_time
    end = meeting.end_time
    duration_seconds = (end - start).total_seconds()

    participants = {segment.email or segment.full_name for segment in meeting.segments}
    if len(participants) < 3:
        return None

    leave_events = sorted(
        (
            {
                "time": segment.leave_time,
                "who": segment.email or segment.full_name,
            }
            for segment in meeting.segments
        ),
        key=lambda event: event["time"],
    )

    window = timedelta(seconds=BOUNDARY_WINDOW_SECONDS)
    best_time: datetime | None = None
    best_count = 0

    for index, event in enumerate(leave_events):
        window_start = event["time"]
        rel_pos = (window_start - start).total_seconds() / duration_seconds
        if rel_pos < 0.15 or rel_pos > 0.85:
            continue

        in_window: set[str] = set()
        times: list[datetime] = []
        for next_event in leave_events[index:]:
            if next_event["time"] > window_start + window:
                break
            in_window.add(next_event["who"])
            times.append(next_event["time"])

        if len(in_window) > best_count:
            best_count = len(in_window)
            best_time = times[len(times) // 2]

    if best_time is None:
        return None

    if best_count < len(participants) * BOUNDARY_MIN_PARTICIPANTS:
        return None

    before = best_time - timedelta(minutes=2)
    after = best_time + timedelta(minutes=2)
    count_before = 0
    count_after = 0

    for segment in meeting.segments:
        if segment.join_time <= before < segment.leave_time:
            count_before += 1
        if segment.join_time <= after < segment.leave_time:
            count_after += 1

    peak_count = len(participants)
    if count_after > peak_count * 0.5 and count_before > peak_count * 0.5:
        return None

    return BreakWindow(break_start=best_time, break_end=best_time)
