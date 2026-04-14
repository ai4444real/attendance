"""Zoom CSV parser migrated from ``attendance/adapter/js/zoom-parser.js``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from .aggregator import ZoomMeeting, ZoomSegment


@dataclass(frozen=True)
class ZoomParseResult:
    meetings: list[ZoomMeeting]
    warnings: list[str]


ZOOM_DATETIME_PATTERN = re.compile(
    r"(\d{2})\/(\d{2})\/(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})\s+(AM|PM)",
    re.IGNORECASE,
)


def parse_zoom_csv_text(csv_text: str) -> ZoomParseResult:
    warnings: list[str] = []
    clean = csv_text.removeprefix("\ufeff")
    lines = clean.splitlines()

    if len(lines) < 2:
        raise ValueError("Il file CSV deve contenere almeno intestazioni e una riga")

    raw_headers = _parse_csv_line(lines[0])
    headers = _deduplicate_headers(raw_headers)

    meetings: list[ZoomMeeting] = []
    current_rows: list[dict[str, str]] = []

    for index, line in enumerate(lines[1:], start=2):
        trimmed = line.strip()

        if not trimmed or not trimmed.replace(",", ""):
            if current_rows:
                meeting = _build_meeting(current_rows, warnings)
                if meeting is not None:
                    meetings.append(meeting)
                current_rows = []
            continue

        values = _parse_csv_line(trimmed)
        if len(values) >= len(headers):
            row = {
                header: (values[position] or "").strip()
                for position, header in enumerate(headers)
            }
            current_rows.append(row)
        else:
            warnings.append(
                f"Riga {index}: colonne non corrispondenti ({len(values)}/{len(headers)}), saltata"
            )

    if current_rows:
        meeting = _build_meeting(current_rows, warnings)
        if meeting is not None:
            meetings.append(meeting)

    return ZoomParseResult(meetings=meetings, warnings=warnings)


def parse_zoom_csv_file(path: str) -> ZoomParseResult:
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return parse_zoom_csv_text(handle.read())


def _build_meeting(rows: list[dict[str, str]], warnings: list[str]) -> ZoomMeeting | None:
    if not rows:
        return None

    first = rows[0]
    start_time = _parse_zoom_datetime(first.get("Ora di inizio", ""))
    end_time = _parse_zoom_datetime(first.get("Ora di fine", ""))

    if start_time is None or end_time is None:
        warnings.append(
            f'Meeting "{first.get("Argomento", "?")}": date non valide, saltato'
        )
        return None

    segments: list[ZoomSegment] = []
    for row in rows:
        raw_name = row.get("Nome (nome originale)", "")
        email = row.get("E-mail", "")
        guest_field = row.get("Guest", "").lower()

        if guest_field not in {"sì", "si"}:
            continue

        join_time = _parse_zoom_datetime(row.get("Ora di ingresso", ""))
        leave_time = _parse_zoom_datetime(row.get("Ora di uscita", ""))

        if join_time is None or leave_time is None:
            warnings.append(
                f'Meeting "{first.get("Argomento", "")}": segmento con date non valide per "{raw_name}", saltato'
            )
            continue

        first_name, last_name = _split_name(raw_name)
        segments.append(
            ZoomSegment(
                full_name=raw_name,
                first_name=first_name,
                last_name=last_name,
                email=email,
                join_time=join_time,
                leave_time=leave_time,
            )
        )

    return ZoomMeeting(
        course=first.get("Argomento", ""),
        meeting_id=first.get("ID", ""),
        start_time=start_time,
        end_time=end_time,
        duration_minutes=(end_time - start_time).total_seconds() / 60,
        segments=segments,
    )


def _parse_csv_line(line: str) -> list[str]:
    result: list[str] = []
    current = []
    in_quotes = False
    index = 0

    while index < len(line):
        char = line[index]
        if char == '"':
            if in_quotes and index + 1 < len(line) and line[index + 1] == '"':
                current.append('"')
                index += 1
            else:
                in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            result.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1

    result.append("".join(current))
    return result


def _deduplicate_headers(headers: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    deduplicated: list[str] = []
    for header in headers:
        trimmed = header.strip()
        counts[trimmed] = counts.get(trimmed, 0) + 1
        if counts[trimmed] == 1:
            deduplicated.append(trimmed)
        else:
            deduplicated.append(f"{trimmed}_{counts[trimmed]}")
    return deduplicated


def _parse_zoom_datetime(value: str) -> datetime | None:
    if not value:
        return None

    match = ZOOM_DATETIME_PATTERN.match(value)
    if match is None:
        return None

    month, day, year, hours, minutes, seconds, period = match.groups()
    parsed_hours = int(hours)
    if period.upper() == "PM" and parsed_hours != 12:
        parsed_hours += 12
    if period.upper() == "AM" and parsed_hours == 12:
        parsed_hours = 0

    return datetime(
        int(year),
        int(month),
        int(day),
        parsed_hours,
        int(minutes),
        int(seconds),
    )


def _split_name(full_name: str) -> tuple[str, str]:
    clean = re.sub(r"\(Host\)", "", full_name, flags=re.IGNORECASE)
    clean = re.sub(r"\([^)]*\)", "", clean).strip()
    parts = clean.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return _cap(parts[0]), ""
    return _cap(parts[0]), " ".join(_cap(part) for part in parts[1:])


def _cap(word: str) -> str:
    if not word:
        return ""
    return word[0].upper() + word[1:]
