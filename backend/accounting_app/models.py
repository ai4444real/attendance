"""Models for the accounting consultant MVP."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AccountingAccount:
    code: str
    description: str
    active: bool


@dataclass(frozen=True)
class AccountingFeedbackRule:
    raw_text: str
    normalized_text: str
    amount: Decimal | None
    account_code: str
    prediction_source: str | None


@dataclass(frozen=True)
class ParsedBankTransaction:
    row_index: int
    date: str
    description: str
    amount: Decimal


@dataclass(frozen=True)
class AccountingPrediction:
    account_code: str | None
    account_description: str | None
    source: str
    confidence: str | None = None
    needs_review: bool = False
    message: str | None = None


@dataclass(frozen=True)
class PredictedBankTransaction:
    row_index: int
    date: str
    description: str
    amount: Decimal
    prediction: AccountingPrediction
