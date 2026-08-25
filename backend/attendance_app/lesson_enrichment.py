from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import hashlib
import json
import re
import unicodedata

from .course_catalog import GoogleCourseCatalogReader


@dataclass(frozen=True)
class PlannedLessonSourceRow:
    row_number: int
    external_lesson_id: str
    event_title: str | None
    topic: str | None
    lesson_date: date
    start_time: time | None
    end_time: time | None
    recipients: list[str]
    drive_url: str | None
    zoom_url: str | None

    @property
    def home_recipient_key(self) -> str | None:
        return self.recipients[0] if self.recipients else None

    @property
    def source_hash(self) -> str:
        payload = {
            "external_lesson_id": self.external_lesson_id,
            "event_title": self.event_title,
            "topic": self.topic,
            "lesson_date": self.lesson_date.isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "recipients": self.recipients,
            "drive_url": self.drive_url,
            "zoom_url": self.zoom_url,
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LessonEnrichmentImportResult:
    rows_read: int
    matched: int
    updated: int
    unchanged: int
    missing_catalog_mapping: int
    missing_attendance_lesson: int
    ambiguous: int
    skipped: int
    warnings: list[str]


class GoogleLessonSheetReader(GoogleCourseCatalogReader):
    def read_rows(self) -> tuple[list[PlannedLessonSourceRow], list[str]]:
        values = self.read_values(
            "A:M",
            value_render_option="UNFORMATTED_VALUE",
            date_time_render_option="SERIAL_NUMBER",
        )
        return parse_planned_lesson_values(values)


def parse_planned_lesson_values(values: list[list[object]]) -> tuple[list[PlannedLessonSourceRow], list[str]]:
    if not values:
        return [], ["Il foglio Lezioni non contiene righe."]

    header = [_clean_cell(value).lower() for value in values[0]]
    names = {
        "lesson_id": "lesson_id",
        "titolo_evento": "titolo_evento",
        "argomento": "argomento",
        "data": "data",
        "ora_inizio": "ora_inizio",
        "ora_fine": "ora_fine",
        "destinatari": "destinatari",
        "url_cartella_drive": "url_cartella_drive",
        "url_zoom": "url_zoom",
    }
    positions = {key: header.index(name) if name in header else None for key, name in names.items()}
    missing = [name for name in ("lesson_id", "data", "argomento", "destinatari") if positions[name] is None]
    if missing:
        raise ValueError(f"Il foglio Lezioni non contiene le colonne richieste: {', '.join(missing)}.")

    rows: list[PlannedLessonSourceRow] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    for row_number, raw_row in enumerate(values[1:], start=2):
        external_id = _external_id(_raw_at(raw_row, positions["lesson_id"]))
        raw_date = _raw_at(raw_row, positions["data"])
        if not external_id and raw_date in (None, ""):
            continue
        if not external_id:
            warnings.append(f"Riga {row_number}: ignorata perche' lesson_id e' vuoto.")
            continue
        if external_id.casefold() in seen_ids:
            warnings.append(f"Riga {row_number}: lesson_id duplicato ({external_id}), ignorata.")
            continue
        lesson_date = _parse_sheet_date(raw_date)
        if lesson_date is None:
            warnings.append(f"Riga {row_number}: data non valida, ignorata.")
            continue
        seen_ids.add(external_id.casefold())
        recipients_value = _clean_cell(_raw_at(raw_row, positions["destinatari"]))
        recipients = [part.strip() for part in recipients_value.split(",") if part.strip()]
        rows.append(
            PlannedLessonSourceRow(
                row_number=row_number,
                external_lesson_id=external_id,
                event_title=_optional_cell(raw_row, positions["titolo_evento"]),
                topic=_optional_cell(raw_row, positions["argomento"]),
                lesson_date=lesson_date,
                start_time=_parse_sheet_time(_raw_at(raw_row, positions["ora_inizio"])),
                end_time=_parse_sheet_time(_raw_at(raw_row, positions["ora_fine"])),
                recipients=recipients,
                drive_url=_optional_cell(raw_row, positions["url_cartella_drive"]),
                zoom_url=_optional_cell(raw_row, positions["url_zoom"]),
            )
        )
    return rows, warnings


def normalize_course_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = "".join(character for character in normalized if not unicodedata.combining(character))
    return " ".join(re.findall(r"[A-Z0-9]+", ascii_value.upper()))


def _parse_sheet_date(value: object) -> date | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
    text = _clean_cell(value)
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _parse_sheet_time(value: object) -> time | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = round((float(value) % 1) * 86400) % 86400
        return time(seconds // 3600, (seconds % 3600) // 60, seconds % 60)
    text = _clean_cell(value)
    for pattern in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, pattern).time()
        except ValueError:
            continue
    return None


def _external_id(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return _clean_cell(value)


def _optional_cell(row: list[object], position: int | None) -> str | None:
    value = _clean_cell(_raw_at(row, position))
    return value or None


def _raw_at(row: list[object], position: int | None) -> object | None:
    if position is None or position >= len(row):
        return None
    return row[position]


def _clean_cell(value: object) -> str:
    return " ".join(str(value or "").strip().split())
