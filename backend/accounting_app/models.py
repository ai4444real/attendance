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
class AccountingCodeHint:
    code: str
    account_code: str
    account_description: str | None
    active: bool


@dataclass(frozen=True)
class AccountingFeedbackRule:
    id: int | None
    raw_text: str
    normalized_text: str
    amount: Decimal | None
    account_code: str
    account_description: str | None
    prediction_source: str | None
    created_at: str | None = None


@dataclass(frozen=True)
class AccountingPredictionRule:
    id: int | None
    name: str
    account_code: str
    account_description: str | None
    priority: int
    active: bool
    amount_sign: str
    min_abs_amount: Decimal | None
    max_abs_amount: Decimal | None
    required_tokens: list[str]
    any_tokens: list[str]
    message: str | None


@dataclass(frozen=True)
class AccountingTrainingExample:
    raw_text: str
    normalized_text: str
    amount: Decimal | None
    target_account_code: str
    source: str


@dataclass(frozen=True)
class ParsedBankTransaction:
    row_index: int
    date: str
    description: str
    amount: Decimal
    source_key: str | None = None
    balance: Decimal | None = None
    translated_account_code: str | None = None
    entry_side: str | None = None


@dataclass(frozen=True)
class AccountingPrediction:
    account_code: str | None
    account_description: str | None
    source: str
    confidence: str | None = None
    needs_review: bool = False
    message: str | None = None
    score: float | None = None
    evidence: list[dict[str, object]] | None = None


@dataclass(frozen=True)
class PredictedBankTransaction:
    row_index: int
    date: str
    description: str
    amount: Decimal
    prediction: AccountingPrediction
    source_key: str | None = None
    balance: Decimal | None = None
    ledger_id: int | None = None
    counter_account_code: str | None = None
    entry_side: str | None = None
