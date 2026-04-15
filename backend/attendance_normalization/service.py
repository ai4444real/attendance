"""High-level normalization service for Zoom CSV attendance files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .aggregator import AttendanceAggregationRecord, aggregate_meeting
from .identity_rules import load_identity_rules
from .meeting_overrides import apply_effective_time_overrides, load_meeting_overrides
from .meeting_selection import filter_meetings_by_courses, preselected_course_names
from .presence_rules import determine_presence_status
from .temporal_markers import detect_break_window, snap_effective_start
from .zoom_parser import parse_zoom_csv_file

MIN_MEETING_DURATION_MINUTES = 20.0
MIN_RECORD_TOTAL_MINUTES = 5.0


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
    effective_end: str
    threshold: float
    trim_start_minutes: float
    trim_end_minutes: float


@dataclass(frozen=True)
class TimelinePoint:
    timestamp: str
    active_count: int


@dataclass(frozen=True)
class MeetingDiagnostic:
    course: str
    meeting_id: str
    date: str
    effective_start: str
    break_point: str
    effective_end: str
    break_source: str
    threshold: float
    trim_start_minutes: float
    trim_end_minutes: float
    participant_count: int
    peak_active_count: int
    sampled_every_minutes: float
    timeline: list[TimelinePoint]


@dataclass(frozen=True)
class NormalizationResult:
    source_path: str
    threshold: float
    total_meetings_found: int
    selected_courses: list[str]
    selected_meetings_count: int
    warnings: list[str]
    meetings: list[MeetingDiagnostic]
    records: list[NormalizedAttendanceRecord]


def normalize_zoom_csv_file(
    path: str | Path,
    threshold: float = 0.8,
    identity_rules_path: str | Path | None = None,
    meeting_overrides_path: str | Path | None = None,
) -> NormalizationResult:
    source_path = str(path)
    parsed = parse_zoom_csv_file(source_path)
    identity_rules = load_identity_rules(identity_rules_path)
    meetings = identity_rules.apply_to_meetings(parsed.meetings)
    meeting_overrides = load_meeting_overrides(meeting_overrides_path)

    selected_courses = preselected_course_names(meetings)
    selected_meetings = filter_meetings_by_courses(meetings, set(selected_courses))
    warnings = list(parsed.warnings)

    normalized_records: list[NormalizedAttendanceRecord] = []
    normalized_meetings: list[MeetingDiagnostic] = []
    kept_meetings_count = 0

    for meeting in selected_meetings:
        if meeting.duration_minutes < MIN_MEETING_DURATION_MINUTES:
            warnings.append(
                f'Meeting "{meeting.course}" ({meeting.meeting_id}) ignorato: durata {meeting.duration_minutes:.1f} min, meno di 20 minuti'
            )
            continue

        kept_meetings_count += 1
        effective_start = snap_effective_start(meeting.start_time, meeting.end_time)
        meeting_override = meeting_overrides.find_for(meeting)
        effective_start, effective_end, time_override_info = apply_effective_time_overrides(
            meeting,
            effective_start,
            meeting_override,
        )
        meeting_threshold = float(meeting_override.threshold) if (
            meeting_override is not None and meeting_override.threshold is not None
        ) else threshold

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
            effective_end=effective_end,
        )

        normalized_meetings.append(
            _build_meeting_diagnostic(
                meeting=meeting,
                effective_start=effective_start,
                break_point=break_point,
                effective_end=effective_end,
                break_source=break_source,
                threshold=meeting_threshold,
                trim_start_minutes=time_override_info["trim_start_minutes"],
                trim_end_minutes=time_override_info["trim_end_minutes"],
            )
        )

        normalized_records.extend(
            _to_normalized_record(
                record,
                meeting_threshold,
                break_source,
                effective_start,
                break_point,
                effective_end,
                time_override_info["trim_start_minutes"],
                time_override_info["trim_end_minutes"],
            )
            for record in aggregated
            if not _should_ignore_record(record, warnings)
        )

    return NormalizationResult(
        source_path=source_path,
        threshold=threshold,
        total_meetings_found=len(parsed.meetings),
        selected_courses=selected_courses,
        selected_meetings_count=kept_meetings_count,
        warnings=warnings,
        meetings=normalized_meetings,
        records=normalized_records,
    )


def _to_normalized_record(
    record: AttendanceAggregationRecord,
    threshold: float,
    break_source: str,
    effective_start,
    break_point,
    effective_end,
    trim_start_minutes: float,
    trim_end_minutes: float,
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
        effective_end=effective_end.isoformat(),
        threshold=threshold,
        trim_start_minutes=trim_start_minutes,
        trim_end_minutes=trim_end_minutes,
    )


def _should_ignore_record(record: AttendanceAggregationRecord, warnings: list[str]) -> bool:
    if record.total_minutes >= MIN_RECORD_TOTAL_MINUTES:
        return False

    full_name = f"{record.first_name} {record.last_name}".strip() or record.email or "(senza nome)"
    warnings.append(
        f'Record "{full_name}" nel meeting "{record.course}" ({record.meeting_id}) ignorato: presenza totale {record.total_minutes:.1f} min, meno di 5 minuti'
    )
    return True


def _build_meeting_diagnostic(
    meeting,
    effective_start: datetime,
    break_point: datetime,
    effective_end: datetime,
    break_source: str,
    threshold: float,
    trim_start_minutes: float,
    trim_end_minutes: float,
) -> MeetingDiagnostic:
    timeline = _build_timeline(meeting, effective_start, effective_end)
    peak_active_count = max((point.active_count for point in timeline), default=0)
    participant_count = len(_participant_keys(meeting))

    return MeetingDiagnostic(
        course=meeting.course,
        meeting_id=meeting.meeting_id,
        date=meeting.start_time.date().isoformat(),
        effective_start=effective_start.isoformat(),
        break_point=break_point.isoformat(),
        effective_end=effective_end.isoformat(),
        break_source=break_source,
        threshold=threshold,
        trim_start_minutes=trim_start_minutes,
        trim_end_minutes=trim_end_minutes,
        participant_count=participant_count,
        peak_active_count=peak_active_count,
        sampled_every_minutes=10.0,
        timeline=timeline,
    )


def _build_timeline(
    meeting,
    effective_start: datetime,
    effective_end: datetime,
    step_minutes: float = 10.0,
) -> list[TimelinePoint]:
    if effective_end <= effective_start:
        return [
            TimelinePoint(
                timestamp=effective_start.isoformat(),
                active_count=0,
            )
        ]

    step = timedelta(minutes=step_minutes)
    current = effective_start
    points: list[TimelinePoint] = []

    while current < effective_end:
        points.append(
            TimelinePoint(
                timestamp=current.isoformat(),
                active_count=_count_active_participants(meeting, current, effective_end),
            )
        )
        current += step

    points.append(
        TimelinePoint(
            timestamp=effective_end.isoformat(),
            active_count=_count_active_participants(meeting, effective_end, effective_end),
        )
    )
    return points


def _count_active_participants(meeting, probe_time: datetime, effective_end: datetime) -> int:
    adjusted_probe = probe_time if probe_time < effective_end else effective_end - timedelta(seconds=1)
    active = set()

    for segment in meeting.segments:
        if segment.join_time <= adjusted_probe < segment.leave_time:
            active.add(segment.email or segment.full_name)

    return len(active)


def _participant_keys(meeting) -> set[str]:
    return {
        segment.email or segment.full_name
        for segment in meeting.segments
    }
