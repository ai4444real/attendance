"""Export helpers for normalized attendance results."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
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
    "Break Source",
]


def normalization_result_to_json(result: NormalizationResult) -> str:
    return json.dumps(asdict(result), ensure_ascii=False, indent=2)


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
