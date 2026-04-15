"""Export helpers for normalized attendance results."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from io import StringIO
from pathlib import Path

from .service import NormalizationResult


CSV_HEADERS = [
    "Corso",
    "Data",
    "Nome",
    "Cognome",
    "Email",
    "Presenza",
    "Min Prima Meta",
    "Min Seconda Meta",
    "Durata Prima Meta",
    "Durata Seconda Meta",
    "Minuti Totali",
    "Segmenti",
    "Meeting ID",
    "Effective Start",
    "Break Point",
    "Effective End",
    "Threshold",
    "Trim Start Minutes",
    "Trim End Minutes",
    "Break Source",
]


def normalization_result_to_json(result: NormalizationResult) -> str:
    return json.dumps(_build_json_payload(result), ensure_ascii=False, indent=2)


def normalization_result_to_csv(result: NormalizationResult) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADERS)

    for record in result.records:
        writer.writerow(
            [
                record.course,
                _format_date(record.date),
                record.first_name,
                record.last_name,
                record.email,
                record.calculated_presence_status,
                record.minutes_first_half,
                record.minutes_second_half,
                record.duration_first_half,
                record.duration_second_half,
                record.total_minutes,
                record.segment_count,
                record.meeting_id,
                record.effective_start,
                record.break_point,
                record.effective_end,
                record.threshold,
                record.trim_start_minutes,
                record.trim_end_minutes,
                record.break_source,
            ]
        )

    return buffer.getvalue()


def write_normalization_result_json(result: NormalizationResult, destination: str | Path) -> Path:
    path = Path(destination)
    path.write_text(normalization_result_to_json(result), encoding="utf-8")
    return path


def write_normalization_result_csv(result: NormalizationResult, destination: str | Path) -> Path:
    path = Path(destination)
    path.write_text("\ufeff" + normalization_result_to_csv(result), encoding="utf-8")
    return path


def build_default_output_path(
    source_path: str | Path,
    suffix: str,
    extension: str,
) -> Path:
    source = Path(source_path)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return source.with_name(f"{source.stem}_{suffix}_{timestamp}.{extension}")


def _format_date(value: str) -> str:
    return value[:10] if "T" in value else value


def _build_json_payload(result: NormalizationResult) -> dict:
    grouped_courses: dict[str, dict] = {}

    meetings_index = {
        (meeting.course, meeting.meeting_id, meeting.date): meeting
        for meeting in result.meetings
    }

    for record in result.records:
        course_bucket = grouped_courses.setdefault(
            record.course,
            {
                "course": record.course,
                "meeting_count": 0,
                "participant_count": 0,
                "meetings": {},
            },
        )

        meeting_key = f"{record.meeting_id}|{record.date}"
        meeting_bucket = course_bucket["meetings"].setdefault(
            meeting_key,
            {
                "meeting_id": record.meeting_id,
                "date": _format_date(record.date),
                "effective_start": record.effective_start,
                "break_point": record.break_point,
                "effective_end": record.effective_end,
                "break_source": record.break_source,
                "threshold": record.threshold,
                "trim_start_minutes": record.trim_start_minutes,
                "trim_end_minutes": record.trim_end_minutes,
                "participants": [],
            },
        )

        meeting_bucket["participants"].append(
            {
                "first_name": record.first_name,
                "last_name": record.last_name,
                "full_name": f"{record.first_name} {record.last_name}".strip(),
                "email": record.email,
                "calculated_presence_status": record.calculated_presence_status,
                "minutes_first_half": record.minutes_first_half,
                "minutes_second_half": record.minutes_second_half,
                "duration_first_half": record.duration_first_half,
                "duration_second_half": record.duration_second_half,
                "total_minutes": record.total_minutes,
                "segment_count": record.segment_count,
            }
        )

    courses = []
    for course_name in sorted(grouped_courses.keys(), key=lambda value: value.lower()):
        course_bucket = grouped_courses[course_name]
        meetings = list(course_bucket["meetings"].values())
        meetings.sort(key=lambda meeting: (meeting["date"], meeting["meeting_id"]))

        for meeting in meetings:
            diagnostic = meetings_index.get((course_name, meeting["meeting_id"], meeting["date"]))
            meeting["participant_count"] = len(meeting["participants"])
            meeting["summary"] = _build_meeting_summary(meeting["participants"])
            meeting["diagnostics"] = _build_meeting_diagnostics_payload(diagnostic)

        course_bucket["meeting_count"] = len(meetings)
        course_bucket["participant_count"] = sum(meeting["participant_count"] for meeting in meetings)
        course_bucket["meetings"] = meetings
        courses.append(course_bucket)

    return {
        "schema_version": 2,
        "kind": "attendance_normalization",
        "source": {
            "path": result.source_path,
        },
        "normalization": {
            "threshold": result.threshold,
            "total_meetings_found": result.total_meetings_found,
            "selected_meetings_count": result.selected_meetings_count,
            "selected_courses": result.selected_courses,
            "warnings_count": len(result.warnings),
            "records_count": len(result.records),
        },
        "warnings": result.warnings,
        "courses": courses,
    }


def _build_meeting_summary(participants: list[dict]) -> dict:
    counts = {
        "presente": 0,
        "prima_meta": 0,
        "seconda_meta": 0,
        "assente": 0,
    }
    for participant in participants:
        status = participant["calculated_presence_status"]
        counts[status] = counts.get(status, 0) + 1
    return counts


def _build_meeting_diagnostics_payload(diagnostic) -> dict:
    if diagnostic is None:
        return {
            "participant_count": 0,
            "peak_active_count": 0,
            "sampled_every_minutes": 10.0,
            "timeline": [],
        }

    return {
        "participant_count": diagnostic.participant_count,
        "peak_active_count": diagnostic.peak_active_count,
        "sampled_every_minutes": diagnostic.sampled_every_minutes,
        "trim_start_minutes": diagnostic.trim_start_minutes,
        "trim_end_minutes": diagnostic.trim_end_minutes,
        "timeline": [
            {
                "timestamp": point.timestamp,
                "active_count": point.active_count,
            }
            for point in diagnostic.timeline
        ],
    }
