"""Application services for the accounting consultant MVP."""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Protocol

from .models import (
    AccountingAccount,
    AccountingPrediction,
    ParsedBankTransaction,
    PredictedBankTransaction,
)


class AccountingRepository(Protocol):
    def list_accounts(self) -> list[AccountingAccount]: ...
    def list_code_hints(self) -> dict[str, str]: ...
    def find_latest_feedback(self, normalized_text: str, amount: Decimal): ...
    def create_feedback(
        self,
        *,
        raw_text: str,
        normalized_text: str,
        amount: Decimal | None,
        account_code: str,
        predicted_account_code: str | None,
        prediction_source: str | None,
        created_by: str | None,
    ) -> int: ...


BANK_PRESETS = {
    "postfinance": {
        "delimiter": ";",
        "skip_start": 8,
        "skip_end": 3,
        "mask": ["D:dd.mm.yyyy", "T", "A", "A", "X", "X"],
    },
    "raiffeisen": {
        "delimiter": ";",
        "skip_start": 1,
        "skip_end": 0,
        "mask": ["X", "D:yyyy-mm-dd", "T", "A", "X", "X"],
    },
}


def decode_upload(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def normalize_accounting_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = "".join(char for char in text if char.isprintable() or char in "\n\r\t ")
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def parse_accounting_amount(value: object) -> Decimal:
    text = str(value or "").strip().strip('"').strip("=")
    text = text.replace("'", "").replace("’", "").replace(" ", "").replace(",", ".")
    if not text:
        return Decimal("0.00")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0.00")


def _parse_date(value: str, date_format: str) -> str:
    text = (value or "").strip().strip('"').strip("=")
    parts = re.findall(r"\d+", text)
    if len(parts) < 3:
        return text
    if date_format == "dd.mm.yyyy":
        day, month, year = parts[0], parts[1], parts[2]
    elif date_format == "yyyy-mm-dd":
        year, month, day = parts[0], parts[1], parts[2]
    else:
        return text
    return f"{day.zfill(2)}.{month.zfill(2)}.{year}"


def parse_bank_csv(text: str, bank: str) -> list[ParsedBankTransaction]:
    preset = BANK_PRESETS.get(bank)
    if preset is None:
        raise ValueError(f"Unsupported bank preset: {bank}")

    rows = list(csv.reader(io.StringIO(text), delimiter=preset["delimiter"], quotechar='"'))
    skip_start = int(preset["skip_start"])
    skip_end = int(preset["skip_end"])
    data_rows = rows[skip_start : len(rows) - skip_end if skip_end else None]
    transactions: list[ParsedBankTransaction] = []

    for row_index, row in enumerate(data_rows, start=skip_start + 1):
        if not row or all(not cell.strip() for cell in row):
            continue
        date = ""
        description = ""
        amount = Decimal("0.00")
        for index, mask in enumerate(preset["mask"]):
            if index >= len(row):
                continue
            value = row[index]
            if mask.startswith("D:"):
                date = _parse_date(value, mask.split(":", 1)[1])
            elif mask == "T":
                description = value.strip().strip('"')
            elif mask == "A":
                amount += parse_accounting_amount(value)
            elif mask == "A-":
                amount -= parse_accounting_amount(value)
        if not date and not description:
            continue
        transactions.append(
            ParsedBankTransaction(
                row_index=row_index,
                date=date,
                description=description,
                amount=amount.quantize(Decimal("0.01")),
            )
        )

    return transactions


class AccountingPredictionService:
    def __init__(self, repository: AccountingRepository):
        self._repository = repository

    def list_accounts(self) -> list[AccountingAccount]:
        return self._repository.list_accounts()

    def parse_and_predict_bank_csv(self, content: bytes, bank: str) -> list[PredictedBankTransaction]:
        text = decode_upload(content)
        transactions = parse_bank_csv(text, bank)
        accounts = {account.code: account for account in self._repository.list_accounts()}
        code_hints = self._repository.list_code_hints()
        return [
            self._predict_transaction_with_context(transaction, accounts, code_hints)
            for transaction in transactions
        ]

    def predict_transaction(self, transaction: ParsedBankTransaction) -> PredictedBankTransaction:
        accounts = {account.code: account for account in self._repository.list_accounts()}
        code_hints = self._repository.list_code_hints()
        return self._predict_transaction_with_context(transaction, accounts, code_hints)

    def _predict_transaction_with_context(
        self,
        transaction: ParsedBankTransaction,
        accounts: dict[str, AccountingAccount],
        code_hints: dict[str, str],
    ) -> PredictedBankTransaction:
        normalized_text = normalize_accounting_text(transaction.description)

        code_hint_prediction = self._predict_from_code_hint(normalized_text, accounts, code_hints)
        if code_hint_prediction is not None:
            return self._with_prediction(transaction, code_hint_prediction)

        feedback = self._repository.find_latest_feedback(normalized_text, transaction.amount)
        if feedback is not None:
            account = accounts.get(feedback.account_code)
            return self._with_prediction(
                transaction,
                AccountingPrediction(
                    account_code=feedback.account_code,
                    account_description=account.description if account else None,
                    source="feedback_override_amount" if feedback.amount is not None else "feedback_override",
                    confidence="alta",
                    needs_review=False,
                ),
            )

        return self._with_prediction(
            transaction,
            AccountingPrediction(
                account_code=None,
                account_description=None,
                source="review",
                confidence=None,
                needs_review=True,
                message="Nessun code hint o feedback trovato.",
            ),
        )

    def register_feedback(
        self,
        *,
        raw_text: str,
        amount: Decimal | None,
        account_code: str,
        predicted_account_code: str | None,
        prediction_source: str | None,
        created_by: str | None,
    ) -> int:
        normalized_text = normalize_accounting_text(raw_text)
        return self._repository.create_feedback(
            raw_text=raw_text,
            normalized_text=normalized_text,
            amount=amount,
            account_code=account_code,
            predicted_account_code=predicted_account_code,
            prediction_source=prediction_source,
            created_by=created_by,
        )

    def _predict_from_code_hint(
        self,
        normalized_text: str,
        accounts: dict[str, AccountingAccount],
        code_hints: dict[str, str],
    ) -> AccountingPrediction | None:
        match = re.search(r"\bc:([a-z0-9_-]+)\b", normalized_text)
        if not match:
            return None
        code = match.group(1).casefold()
        account_code = code_hints.get(code)
        if account_code is None:
            return AccountingPrediction(
                account_code=None,
                account_description=None,
                source="code_hint_unknown",
                confidence=None,
                needs_review=True,
                message=f"Code hint sconosciuto: c:{code}",
            )
        account = accounts.get(account_code)
        return AccountingPrediction(
            account_code=account_code,
            account_description=account.description if account else None,
            source="code_hint",
            confidence="alta",
            needs_review=False,
        )

    @staticmethod
    def _with_prediction(
        transaction: ParsedBankTransaction,
        prediction: AccountingPrediction,
    ) -> PredictedBankTransaction:
        return PredictedBankTransaction(
            row_index=transaction.row_index,
            date=transaction.date,
            description=transaction.description,
            amount=transaction.amount,
            prediction=prediction,
        )
