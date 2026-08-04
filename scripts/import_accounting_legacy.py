"""Import legacy accounting consultant JSON seed files into PostgreSQL.

Usage:
    python scripts/import_accounting_legacy.py
    python scripts/import_accounting_legacy.py path/to/seed-dir
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.accounting_app.services import normalize_accounting_text  # noqa: E402
from backend.db.config import get_database_url  # noqa: E402


def _amount(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def main() -> int:
    if len(sys.argv) > 2:
        print("Usage: python scripts/import_accounting_legacy.py [seed-dir]", file=sys.stderr)
        return 2
    seed_dir = Path(sys.argv[1]) if len(sys.argv) == 2 else ROOT / "backend" / "accounting_app" / "seed"
    if not seed_dir.exists():
        print(f"Seed directory not found: {seed_dir}", file=sys.stderr)
        return 2

    accounts = json.loads((seed_dir / "accounts.json").read_text(encoding="utf-8"))
    code_hints = json.loads((seed_dir / "code_hints.json").read_text(encoding="utf-8"))
    dataset = json.loads((seed_dir / "training_examples.json").read_text(encoding="utf-8"))
    corrections = json.loads((seed_dir / "corrections.json").read_text(encoding="utf-8"))

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
