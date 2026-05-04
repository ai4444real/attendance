"""Persistent meeting-level overrides."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import json

from .aggregator import ZoomMeeting


@dataclass(frozen=True)
class MeetingOverride:
    course: str
    date: str
    meeting_id: str | None = None
    threshold: float | None = None
    trim_start_minutes: float | None = None
    trim_end_minutes: float | None = None

    def matches(self, meeting: ZoomMeeting) -> bool:
        if self.course != meeting.course:
            return False
        if self.date != meeting.start_time.date().isoformat():
            return False
        if self.meeting_id and self.meeting_id != meeting.meeting_id:
            return False
        return True


@dataclass(frozen=True)
class MeetingOverrides:
    rules: tuple[MeetingOverride, ...]

    @classmethod
    def empty(cls) -> "MeetingOverrides":
        return cls(rules=())

    def find_for(self, meeting: ZoomMeeting) -> MeetingOverride | None:
        for rule in self.rules:
            if rule.matches(meeting):
                return rule
        return None


def load_meeting_overrides(path: str | Path | None = None) -> MeetingOverrides:
    overrides_path = Path(path) if path is not None else _default_overrides_path()
    if not overrides_path.exists():
        return MeetingOverrides.empty()

    payload = json.loads(overrides_path.read_text(encoding="utf-8"))
    rules = []
    for item in payload.get("meeting_overrides", []):
        rules.append(
            MeetingOverride(
                course=item["course"],
                date=item["date"],
                meeting_id=item.get("meeting_id"),
                threshold=item.get("threshold"),
                trim_start_minutes=item.get("trim_start_minutes"),
                trim_end_minutes=item.get("trim_end_minutes"),
            )
        )
    return MeetingOverrides(rules=tuple(rules))


def apply_effective_time_overrides(
    meeting: ZoomMeeting,
    effective_start: datetime,
    override: MeetingOverride | None,
    suggested_start: datetime | None = None,
    suggested_end: datetime | None = None,
) -> tuple[datetime, datetime, dict]:
    adjusted_start = effective_start
    adjusted_end = meeting.end_time
    applied = {
        "trim_start_minutes": 0.0,
        "effective_start_source": "snap",
        "trim_end_minutes": 0.0,
        "effective_end_source": "meeting_end",
    }

    if override is not None and override.trim_start_minutes is not None:
        trimmed_start = adjusted_start + timedelta(minutes=override.trim_start_minutes)
        if trimmed_start < adjusted_end:
            adjusted_start = trimmed_start
            applied["trim_start_minutes"] = float(override.trim_start_minutes)
            applied["effective_start_source"] = "trim_start_minutes"
    elif suggested_start is not None and suggested_start > adjusted_start and suggested_start < adjusted_end:
        adjusted_start = suggested_start
        applied["trim_start_minutes"] = round((suggested_start - effective_start).total_seconds() / 60, 1)
        applied["effective_start_source"] = "auto_suggest"

    if override is not None and override.trim_end_minutes is not None:
        trimmed_end = meeting.end_time - timedelta(minutes=override.trim_end_minutes)
        if trimmed_end > adjusted_start:
            adjusted_end = trimmed_end
            applied["trim_end_minutes"] = float(override.trim_end_minutes)
            applied["effective_end_source"] = "trim_end_minutes"
    elif suggested_end is not None and suggested_end < adjusted_end and suggested_end > adjusted_start:
        adjusted_end = suggested_end
        applied["trim_end_minutes"] = round((meeting.end_time - suggested_end).total_seconds() / 60, 1)
        applied["effective_end_source"] = "auto_suggest"

    return adjusted_start, adjusted_end, applied


def _default_overrides_path() -> Path:
    return Path(__file__).resolve().parents[2] / "attendance" / "config" / "meeting_overrides.json"
