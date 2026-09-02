from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time
from html import unescape
from html.parser import HTMLParser
import io
import re


@dataclass(frozen=True)
class LegacyLessonTopicRow:
    row_number: int
    course_name: str
    lesson_date: date
    start_time: time | None
    topic: str


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"br", "p", "div", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"p", "div", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")


def clean_legacy_topic(value: str) -> str:
    text = unescape(value or "")
    for broken, repaired in {
        "â€œ": "“",
        "â€\x9d": "”",
        "â€™": "’",
        "â€“": "–",
        "â€”": "—",
        "Â\xa0": " ",
        "Ã ": "à",
        "Ã¨": "è",
        "Ã©": "é",
        "Ã¬": "ì",
        "Ã²": "ò",
        "Ã¹": "ù",
    }.items():
        text = text.replace(broken, repaired)
    if any(marker in text for marker in ("Ã", "Â", "â")):
        try:
            repaired = text.encode("cp1252").decode("utf-8")
            if sum(repaired.count(marker) for marker in ("Ã", "Â", "â")) < sum(text.count(marker) for marker in ("Ã", "Â", "â")):
                text = repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    parser = _TextExtractor()
    parser.feed(text)
    text = "".join(parser.parts)
    text = text.replace("�\x9d", "”").replace("�\xa0", " ")
    text = re.sub(r"(?<=\w)�(?=\s|$)", "à", text)
    text = text.replace("�", " ").replace("\xa0", " ").replace("\u200b", "")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    lines = [line for line in lines if line and line.casefold() not in {"corso base", "corso avanzato"}]
    return " ".join(lines).strip(" \t\r\n;-")


def parse_legacy_lesson_topics_csv(content: bytes) -> tuple[list[LegacyLessonTopicRow], list[dict]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=";")
    headers = {str(name or "").strip().casefold() for name in (reader.fieldnames or [])}
    description_field = "description" if "description" in headers else "decription" if "decription" in headers else None
    if not {"corso", "data"}.issubset(headers) or description_field is None:
        raise ValueError("Il CSV deve contenere le colonne corso, data e description (o decription).")

    rows: list[LegacyLessonTopicRow] = []
    issues: list[dict] = []
    for row_number, raw in enumerate(reader, start=2):
        course = " ".join((raw.get("corso") or "").split())
        topic = clean_legacy_topic(raw.get(description_field) or "")
        try:
            lesson_date = datetime.strptime((raw.get("data") or "").strip(), "%Y-%m-%d").date()
        except ValueError:
            issues.append({"row": row_number, "course": course, "date": raw.get("data") or "", "topic": topic, "reason": "data_non_valida"})
            continue
        if lesson_date.year != 2025 or not course or not topic:
            reason = "anno_non_2025" if lesson_date.year != 2025 else "corso_o_argomento_vuoto"
            issues.append({"row": row_number, "course": course, "date": lesson_date.isoformat(), "topic": topic, "reason": reason})
            continue
        rows.append(LegacyLessonTopicRow(row_number, course, lesson_date, _parse_start_time(raw.get("start") or ""), topic))
    return rows, issues


def _parse_start_time(value: str) -> time | None:
    match = re.search(r"(?:,|\s)(\d{1,2}):(\d{2})\s*$", value.strip())
    if not match:
        return None
    try:
        return time(int(match.group(1)), int(match.group(2)))
    except ValueError:
        return None
