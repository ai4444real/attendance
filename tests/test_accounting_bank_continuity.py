from decimal import Decimal

import pytest

from backend.accounting_app.models import AccountingPrediction, PredictedBankTransaction
from backend.accounting_app.services import AccountingPredictionService


def _item(date: str, amount: str, balance: str) -> PredictedBankTransaction:
    return PredictedBankTransaction(
        row_index=1,
        date=date,
        description="movimento",
        amount=Decimal(amount),
        prediction=AccountingPrediction(None, None, "review", needs_review=True),
        source_key="CH-test",
        balance=Decimal(balance),
    )


class ContinuityRepository:
    def __init__(self, existing=None):
        self.existing = existing or []

    def list_persisted_source_transactions(self, source_type, source_key):
        return self.existing


def test_accepts_exact_balance_sequence() -> None:
    service = AccountingPredictionService(ContinuityRepository())
    service._validate_bank_continuity(
        "CH-test",
        [_item("02.01.2026", "100.00", "1100.00"), _item("01.01.2026", "50.00", "1000.00")],
    )


def test_rejects_one_cent_balance_difference() -> None:
    service = AccountingPredictionService(ContinuityRepository())
    with pytest.raises(ValueError, match="non riconciliato"):
        service._validate_bank_continuity(
            "CH-test",
            [_item("02.01.2026", "100.00", "1100.00"), _item("01.01.2026", "50.00", "999.99")],
        )


def test_rejects_import_without_overlap_with_existing_ledger() -> None:
    service = AccountingPredictionService(ContinuityRepository([{"identity_key": "different"}]))
    with pytest.raises(ValueError, match="Nessuna continuita"):
        service._validate_bank_continuity("CH-test", [_item("02.01.2026", "100.00", "1100.00")])
