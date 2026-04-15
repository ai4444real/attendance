"""Persistent alias rules for attendee identities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re

from .aggregator import ZoomMeeting, ZoomSegment


@dataclass(frozen=True)
class IdentityAliasRule:
    canonical_first_name: str
    canonical_last_name: str
    canonical_full_name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class IdentityRules:
    rules: tuple[IdentityAliasRule, ...]

    @classmethod
    def empty(cls) -> "IdentityRules":
        return cls(rules=())

    def resolve_segment(self, segment: ZoomSegment) -> ZoomSegment:
        candidates = {
            _normalize_name(segment.full_name),
            _normalize_name(f"{segment.first_name} {segment.last_name}".strip()),
        }

        for rule in self.rules:
            alias_keys = {_normalize_name(alias) for alias in rule.aliases}
            if candidates & alias_keys:
                return ZoomSegment(
                    first_name=rule.canonical_first_name,
                    last_name=rule.canonical_last_name,
                    full_name=rule.canonical_full_name,
                    email=segment.email,
                    join_time=segment.join_time,
                    leave_time=segment.leave_time,
                )

        return segment

    def apply_to_meetings(self, meetings: list[ZoomMeeting]) -> list[ZoomMeeting]:
        if not self.rules:
            return meetings

        normalized_meetings: list[ZoomMeeting] = []
        for meeting in meetings:
            normalized_segments = [self.resolve_segment(segment) for segment in meeting.segments]
            normalized_meetings.append(
                ZoomMeeting(
                    course=meeting.course,
                    meeting_id=meeting.meeting_id,
                    start_time=meeting.start_time,
                    end_time=meeting.end_time,
                    duration_minutes=meeting.duration_minutes,
                    segments=normalized_segments,
                )
            )
        return normalized_meetings


def load_identity_rules(path: str | Path | None = None) -> IdentityRules:
    rules_path = Path(path) if path is not None else _default_rules_path()
    if not rules_path.exists():
        return IdentityRules.empty()

    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    aliases = payload.get("aliases", [])
    rules = []
    for item in aliases:
        canonical = item["canonical"]
        rules.append(
            IdentityAliasRule(
                canonical_first_name=canonical["first_name"],
                canonical_last_name=canonical["last_name"],
                canonical_full_name=canonical["full_name"],
                aliases=tuple(item.get("aliases", [])),
            )
        )

    return IdentityRules(rules=tuple(rules))


def _default_rules_path() -> Path:
    return Path(__file__).resolve().parents[2] / "attendance" / "config" / "identity_rules.json"


def _normalize_name(value: str) -> str:
    compact = re.sub(r"\([^)]*\)", "", value or "")
    compact = compact.lower()
    compact = re.sub(r"[^a-z0-9à-ÿ]+", "", compact)
    return compact
