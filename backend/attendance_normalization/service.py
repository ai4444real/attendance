"""High-level normalization service for Zoom CSV attendance files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .aggregator import AttendanceAggregationRecord, aggregate_meeting
from .meeting_selection import filter_meetings_by_courses, preselected_course_names
from .presence_rules import determine_presence_status
from .temporal_markers import detect_break_window, snap_effective_start
from .zoom_parser import parse_zoom_csv_file


@dataclass(frozen=True)
class NormalizedAttendanceRecord:
    course: str
    meeting_id: str
    date: str
    first_name: str
    last_name: str
    email: str
    calculated_presence_status: str
    minutes_first_half: float
    minutes_second_half: float
    duration_first_half: float
    duration_second_half: float
    total_minutes: float
    segment_count: int
    break_source: str
    effective_start: str
    break_point: str


@dataclass(frozen=True)
class NormalizationResult:
    source_path: str
    total_meetings_found: int
    selected_courses: list[str]
    selected_meetings_count: int
    warnings: list[str]
    records: list[NormalizedAttendanceRecord]


def normalize_zoom_csv_file(path: str | Path, threshold: float = 0.8) -> NormalizationResult:
    source_path = str(path)
    parsed = parse_zoom_csv_file(source_path)

    selected_courses = preselected_course_names(parsed.meetings)
    selected_meetings = filter_meetings_by_courses(parsed.meetings, set(selected_courses))

    normalized_records: list[NormalizedAttendanceRecord] = []

    for meeting in selected_meetings:
        effective_start = snap_effective_start(meeting.start_time, meeting.end_time)
        detected_break = detect_break_window(meeting)
        if detected_break is not None:
            break_point = detected_break.break_start + (
                detected_break.break_end - detected_break.break_start
            ) / 2
            break_source = "auto"
        else:
            break_point = effective_start + (meeting.end_time - effective_start) / 2
            break_source = "midpoint"

        aggregated = aggregate_meeting(
            meeting=meeting,
            effective_start=effective_start,
            break_point=break_point,
        )

        normalized_records.extend(
            _to_normalized_record(record, threshold, break_source, effective_start, break_point)
            for record in aggregated
        )

    return NormalizationResult(
        source_path=source_path,
        total_meetings_found=len(parsed.meetings),
        selected_courses=selected_courses,
        selected_meetings_count=len(selected_meetings),
        warnings=parsed.warnings,
        records=normalized_records,
    )


def _to_normalized_record(
    record: AttendanceAggregationRecord,
    threshold: float,
    break_source: str,
    effective_start,
    break_point,
) -> NormalizedAttendanceRecord:
    calculated_presence_status = determine_presence_status(
        minutes_first_half=record.minutes_first_half,
        minutes_second_half=record.minutes_second_half,
        duration_first_half=record.duration_first_half,
        duration_second_half=record.duration_second_half,
        threshold=threshold,
    )

    return NormalizedAttendanceRecord(
        course=record.course,
        meeting_id=record.meeting_id,
        date=record.date.isoformat(),
        first_name=record.first_name,
        last_name=record.last_name,
        email=record.email,
        calculated_presence_status=calculated_presence_status,
        minutes_first_half=record.minutes_first_half,
        minutes_second_half=record.minutes_second_half,
        duration_first_half=record.duration_first_half,
        duration_second_half=record.duration_second_half,
        total_minutes=record.total_minutes,
        segment_count=record.segment_count,
        break_source=break_source,
        effective_start=effective_start.isoformat(),
        break_point=break_point.isoformat(),
    )
