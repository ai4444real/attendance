"""Import legacy accounting consultant JSON files into PostgreSQL.

Usage:
    python scripts/import_accounting_legacy.py consulente-py.zip
"""

from __future__ import annotations

import json
import sys
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.accounting_app.services import normalize_accounting_text  # noqa: E402
from backend.db.config import get_database_url  # noqa: E402


def _read_json(zip_file: zipfile.ZipFile, name: str):
    return json.loads(zip_file.read(name).decode("utf-8"))


def _amount(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/import_accounting_legacy.py consulente-py.zip", file=sys.stderr)
        return 2
    archive_path = Path(sys.argv[1])
    if not archive_path.exists():
        print(f"Archive not found: {archive_path}", file=sys.stderr)
        return 2

    with zipfile.ZipFile(archive_path) as zip_file:
        accounts = _read_json(zip_file, "predictor/temp_data/default_contabilita_labels.json")
        code_hints = _read_json(zip_file, "predictor/temp_data/default_contabilita_code_hints.json")
        dataset = _read_json(zip_file, "local_tools/dataset_ai.json")
        corrections = _read_json(zip_file, "predictor/temp_data/default_contabilita_corrections.json")

    with psycopg.connect(get_database_url()) as connection:
        with connection.cursor() as cursor:
            for code, description in accounts.items():
                cursor.execute(
                    """
                    INSERT INTO accounting_accounts (code, description, active)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (code)
                    DO UPDATE SET description = EXCLUDED.description, active = TRUE, updated_at = now()
                    """,
                    (str(code), str(description)),
                )

            for hint, account_code in code_hints.items():
                if str(account_code) not in accounts:
                    continue
                cursor.execute(
                    """
                    INSERT INTO accounting_code_hints (code, account_code, active)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (code)
                    DO UPDATE SET account_code = EXCLUDED.account_code, active = TRUE, updated_at = now()
                    """,
                    (str(hint).strip().casefold(), str(account_code)),
                )

            for item in dataset:
                raw_text = str(item.get("Description") or "").strip()
                target = str(item.get("Target_Account") or "").strip()
                if not raw_text or target not in accounts:
                    continue
                cursor.execute(
                    """
                    INSERT INTO accounting_training_examples (
                        raw_text,
                        normalized_text,
                        amount,
                        target_account_code,
                        source,
                        source_reference
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        raw_text,
                        normalize_accounting_text(raw_text),
                        _amount(item.get("Importo")),
                        target,
                        "legacy_dataset",
                        str(item.get("Date") or ""),
                    ),
                )

            for correction in corrections:
                raw_text = str(correction.get("text") or "").strip()
                target = str(correction.get("label") or "").strip()
                if not raw_text or target not in accounts:
                    continue
                cursor.execute(
                    """
                    INSERT INTO accounting_feedback (
                        raw_text,
                        normalized_text,
                        amount,
                        account_code,
                        predicted_account_code,
                        prediction_source,
                        created_by
                    )
                    VALUES (%s, %s, NULL, %s, NULL, %s, %s)
                    """,
                    (
                        raw_text,
                        normalize_accounting_text(raw_text),
                        target,
                        "legacy_correction",
                        "legacy-import",
                    ),
                )
        connection.commit()

    print(
        f"Imported {len(accounts)} accounts, {len(code_hints)} code hints, "
        f"{len(dataset)} training rows, {len(corrections)} corrections."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
