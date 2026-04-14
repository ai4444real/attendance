"""CLI runner for manual Zoom attendance normalization."""

from __future__ import annotations

import argparse

from .exporters import (
    build_default_output_path,
    normalization_result_to_json,
    write_normalization_result_csv,
    write_normalization_result_json,
)
from .service import normalize_zoom_csv_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalizza un report Zoom e mostra un riepilogo del risultato."
    )
    parser.add_argument("csv_file", help="Percorso del file CSV Zoom")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Soglia di presenza per meta' lezione, es. 0.8",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Stampa il risultato completo in JSON",
    )
    parser.add_argument(
        "--save-json",
        nargs="?",
        const="",
        help="Salva il risultato JSON su file. Se omesso il path, genera un nome automatico.",
    )
    parser.add_argument(
        "--save-csv",
        nargs="?",
        const="",
        help="Salva il risultato normalizzato CSV su file. Se omesso il path, genera un nome automatico.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Numero massimo di record da mostrare nel riepilogo testuale",
    )

    args = parser.parse_args()
    result = normalize_zoom_csv_file(args.csv_file, threshold=args.threshold)

    saved_json_path = None
    saved_csv_path = None

    if args.save_json is not None:
        json_path = (
            build_default_output_path(args.csv_file, "normalized", "json")
            if args.save_json == ""
            else args.save_json
        )
        saved_json_path = write_normalization_result_json(result, json_path)

    if args.save_csv is not None:
        csv_path = (
            build_default_output_path(args.csv_file, "normalized", "csv")
            if args.save_csv == ""
            else args.save_csv
        )
        saved_csv_path = write_normalization_result_csv(result, csv_path)

    if args.json:
        print(normalization_result_to_json(result))
        return 0

    print(f"File: {result.source_path}")
    print(f"Meeting trovati: {result.total_meetings_found}")
    print(f"Corsi selezionati: {len(result.selected_courses)}")
    if result.selected_courses:
        print("Elenco corsi selezionati:")
        for course in result.selected_courses:
            print(f"  - {course}")
    print(f"Meeting elaborati: {result.selected_meetings_count}")
    print(f"Record normalizzati: {len(result.records)}")
    print(f"Warning: {len(result.warnings)}")
    if result.warnings:
        print("Primi warning:")
        for warning in result.warnings[:10]:
            print(f"  - {warning}")

    if result.records:
        print("")
        print("Primi record:")
        for record in result.records[: args.limit]:
            full_name = f"{record.first_name} {record.last_name}".strip()
            print(
                f"  - {record.course} | {full_name} | {record.calculated_presence_status} | "
                f"1a: {record.minutes_first_half}/{record.duration_first_half} | "
                f"2a: {record.minutes_second_half}/{record.duration_second_half} | "
                f"split: {record.break_source}"
            )

    if saved_json_path or saved_csv_path:
        print("")
        print("File generati:")
        if saved_json_path:
            print(f"  - JSON: {saved_json_path}")
        if saved_csv_path:
            print(f"  - CSV:  {saved_csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
