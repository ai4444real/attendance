from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx


GOOGLE_SHEETS_READ_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"


@dataclass(frozen=True)
class CourseCatalogSourceRow:
    row_number: int
    target_key: str
    classroom_course_id: str | None
    calendar_id: str | None
    display_name: str
    default_link: str | None

    @property
    def source_hash(self) -> str:
        payload = {
            "target_key": self.target_key,
            "classroom_course_id": self.classroom_course_id,
            "calendar_id": self.calendar_id,
            "display_name": self.display_name,
            "default_link": self.default_link,
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @property
    def identifiers(self) -> dict[str, str]:
        values = {"recipient_key": self.target_key}
        if self.classroom_course_id:
            values["classroom_course_id"] = self.classroom_course_id
        if self.calendar_id:
            values["calendar_id"] = self.calendar_id
        if self.default_link:
            values["default_link"] = self.default_link
        return values


@dataclass(frozen=True)
class CourseCatalogImportResult:
    rows_read: int
    created: int
    updated: int
    unchanged: int
    skipped: int
    warnings: list[str]


class CourseCatalogRepository(Protocol):
    def import_google_rows(self, rows: list[CourseCatalogSourceRow]) -> CourseCatalogImportResult:
        ...


class GoogleCourseCatalogReader:
    def __init__(
        self,
        *,
        spreadsheet_id: str,
        service_account_file: str | None = None,
        service_account_json: str | None = None,
        sheet_name: str = "Corsi",
    ) -> None:
        self._spreadsheet_id = spreadsheet_id.strip()
        self._service_account_file = (service_account_file or "").strip()
        self._service_account_json = (service_account_json or "").strip()
        self._sheet_name = sheet_name.strip() or "Corsi"

    def read_rows(self) -> tuple[list[CourseCatalogSourceRow], list[str]]:
        values = self.read_values("A:E", value_render_option="FORMATTED_VALUE")
        return parse_course_catalog_values(values)

    def read_values(
        self,
        cell_range: str,
        *,
        value_render_option: str = "FORMATTED_VALUE",
        date_time_render_option: str | None = None,
    ) -> list[list[object]]:
        if not self._spreadsheet_id:
            raise ValueError("ATTENDANCE_GOOGLE_SPREADSHEET_ID is not configured.")

        credentials = self._load_credentials()
        from google.auth.transport.requests import Request

        credentials.refresh(Request())
        range_name = f"'{self._sheet_name}'!{cell_range}"
        url = (
            "https://sheets.googleapis.com/v4/spreadsheets/"
            f"{self._spreadsheet_id}/values/{quote(range_name, safe='')}"
        )
        params = {"majorDimension": "ROWS", "valueRenderOption": value_render_option}
        if date_time_render_option:
            params["dateTimeRenderOption"] = date_time_render_option
        response = httpx.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {credentials.token}"},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json().get("values") or []

    def _load_credentials(self):
        try:
            from google.oauth2 import service_account
        except ImportError as exc:
            raise RuntimeError("Google authentication dependencies are not installed.") from exc

        if self._service_account_json:
            try:
                info = json.loads(self._service_account_json)
            except json.JSONDecodeError as exc:
                raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc
            return service_account.Credentials.from_service_account_info(
                info,
                scopes=[GOOGLE_SHEETS_READ_SCOPE],
            )
        if self._service_account_file:
            credentials_path = Path(self._service_account_file)
            if not credentials_path.is_file():
                raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE does not point to a readable file.")
            return service_account.Credentials.from_service_account_file(
                str(credentials_path),
                scopes=[GOOGLE_SHEETS_READ_SCOPE],
            )
        raise ValueError(
            "Configure GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE for the Google import."
        )


class AttendanceCourseCatalogImportService:
    def __init__(self, repository: CourseCatalogRepository, reader: GoogleCourseCatalogReader) -> None:
        self._repository = repository
        self._reader = reader

    def import_from_google(self) -> CourseCatalogImportResult:
        rows, parse_warnings = self._reader.read_rows()
        result = self._repository.import_google_rows(rows)
        return CourseCatalogImportResult(
            rows_read=result.rows_read,
            created=result.created,
            updated=result.updated,
            unchanged=result.unchanged,
            skipped=result.skipped,
            warnings=[*parse_warnings, *result.warnings],
        )


def parse_course_catalog_values(values: list[list[object]]) -> tuple[list[CourseCatalogSourceRow], list[str]]:
    if not values:
        return [], ["Il foglio Corsi non contiene righe."]

    header = [_clean_cell(value).lower() for value in values[0]]
    required = ["target_key", "classroom_course_id", "calendar_id", "folder", "default_link"]
    positions = {name: header.index(name) if name in header else None for name in required}
    if positions["target_key"] is None:
        raise ValueError("Il foglio Corsi non contiene la colonna target_key.")

    rows: list[CourseCatalogSourceRow] = []
    warnings: list[str] = []
    seen_keys: set[str] = set()
    for row_number, raw_row in enumerate(values[1:], start=2):
        target_key = _value_at(raw_row, positions["target_key"])
        if not target_key:
            if any(_clean_cell(value) for value in raw_row):
                warnings.append(f"Riga {row_number}: ignorata perche' target_key e' vuota.")
            continue
        normalized_key = target_key.casefold()
        if normalized_key in seen_keys:
            warnings.append(f"Riga {row_number}: target_key duplicata ({target_key}), ignorata.")
            continue
        seen_keys.add(normalized_key)
        display_name = _value_at(raw_row, positions["folder"]) or target_key
        rows.append(
            CourseCatalogSourceRow(
                row_number=row_number,
                target_key=target_key,
                classroom_course_id=_value_at(raw_row, positions["classroom_course_id"]),
                calendar_id=_value_at(raw_row, positions["calendar_id"]),
                display_name=display_name,
                default_link=_value_at(raw_row, positions["default_link"]),
            )
        )
    return rows, warnings


def _value_at(row: list[object], position: int | None) -> str | None:
    if position is None or position >= len(row):
        return None
    value = _clean_cell(row[position])
    return value or None


def _clean_cell(value: object) -> str:
    return " ".join(str(value or "").strip().split())
