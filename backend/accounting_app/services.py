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
    AccountingCodeHint,
    AccountingPrediction,
    AccountingTrainingExample,
    ParsedBankTransaction,
    PredictedBankTransaction,
)


class AccountingRepository(Protocol):
    def list_accounts(self) -> list[AccountingAccount]: ...
    def list_all_accounts(self) -> list[AccountingAccount]: ...
    def upsert_account(self, code: str, description: str, active: bool) -> AccountingAccount: ...
    def set_account_active(self, code: str, active: bool) -> None: ...
    def list_code_hints(self) -> dict[str, str]: ...
    def list_code_hint_records(self) -> list[AccountingCodeHint]: ...
    def upsert_code_hint(self, code: str, account_code: str, active: bool) -> AccountingCodeHint: ...
    def delete_code_hint(self, code: str) -> None: ...
    def list_training_examples(self) -> list[AccountingTrainingExample]: ...
    def find_latest_feedback(self, normalized_text: str, amount: Decimal): ...
    def list_feedback_rules(self, limit: int = 200): ...
    def update_feedback_account(self, feedback_id: int, account_code: str): ...
    def delete_feedback_rule(self, feedback_id: int) -> None: ...
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

_GENERIC_TOKENS = {
    "accredito",
    "addebito",
    "chf",
    "conto",
    "data",
    "del",
    "della",
    "delle",
    "di",
    "fattura",
    "finance",
    "importo",
    "iso",
    "message",
    "mittente",
    "numero",
    "opae",
    "ordine",
    "pagamento",
    "per",
    "prezzo",
    "ridotto",
    "transazioni",
    "versamento",
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


def _accounting_tokens(normalized_text: str) -> set[str]:
    tokens: set[str] = set()
    for token in re.findall(r"\w+", normalized_text, flags=re.UNICODE):
        if len(token) < 3:
            continue
        if token in _GENERIC_TOKENS:
            continue
        if token.isdecimal():
            continue
        if re.fullmatch(r"[0-9a-f]{12,}", token):
            continue
        if re.fullmatch(r"ch\d{10,}", token):
            continue
        tokens.add(token)
    return tokens


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

    def list_all_accounts(self) -> list[AccountingAccount]:
        return self._repository.list_all_accounts()

    def save_account(self, *, code: str, description: str, active: bool = True) -> AccountingAccount:
        clean_code = code.strip()
        clean_description = description.strip()
        if not clean_code:
            raise ValueError("Codice conto mancante.")
        if not clean_description:
            raise ValueError("Descrizione conto mancante.")
        return self._repository.upsert_account(clean_code, clean_description, active)

    def deactivate_account(self, code: str) -> None:
        clean_code = code.strip()
        if not clean_code:
            raise ValueError("Codice conto mancante.")
        self._repository.set_account_active(clean_code, False)

    def list_code_hint_records(self) -> list[AccountingCodeHint]:
        return self._repository.list_code_hint_records()

    def save_code_hint(self, *, code: str, account_code: str, active: bool = True) -> AccountingCodeHint:
        clean_code = code.strip().casefold()
        clean_account_code = account_code.strip()
        if not clean_code:
            raise ValueError("Code hint mancante.")
        if not re.fullmatch(r"[a-z0-9_-]+", clean_code):
            raise ValueError("Code hint non valido: usa lettere, numeri, trattino o underscore.")
        if not clean_account_code:
            raise ValueError("Conto mancante.")
        accounts = {account.code for account in self._repository.list_all_accounts()}
        if clean_account_code not in accounts:
            raise ValueError(f"Conto inesistente: {clean_account_code}")
        return self._repository.upsert_code_hint(clean_code, clean_account_code, active)

    def delete_code_hint(self, code: str) -> None:
        clean_code = code.strip().casefold()
        if not clean_code:
            raise ValueError("Code hint mancante.")
        self._repository.delete_code_hint(clean_code)

    def list_feedback_rules(self, limit: int = 200):
        safe_limit = max(1, min(int(limit), 500))
        return self._repository.list_feedback_rules(safe_limit)

    def update_feedback_account(self, feedback_id: int, account_code: str):
        if feedback_id <= 0:
            raise ValueError("Feedback id non valido.")
        clean_account_code = account_code.strip()
        if not clean_account_code:
            raise ValueError("Conto mancante.")
        accounts = {account.code for account in self._repository.list_all_accounts()}
        if clean_account_code not in accounts:
            raise ValueError(f"Conto inesistente: {clean_account_code}")
        return self._repository.update_feedback_account(feedback_id, clean_account_code)

    def delete_feedback_rule(self, feedback_id: int) -> None:
        if feedback_id <= 0:
            raise ValueError("Feedback id non valido.")
        self._repository.delete_feedback_rule(feedback_id)

    def parse_and_predict_bank_csv(self, content: bytes, bank: str) -> list[PredictedBankTransaction]:
        text = decode_upload(content)
        transactions = parse_bank_csv(text, bank)
        accounts = {account.code: account for account in self._repository.list_accounts()}
        code_hints = self._repository.list_code_hints()
        training_examples = self._repository.list_training_examples()
        return [
            self._predict_transaction_with_context(
                transaction,
                accounts,
                code_hints,
                training_examples,
            )
            for transaction in transactions
        ]

    def predict_transaction(self, transaction: ParsedBankTransaction) -> PredictedBankTransaction:
        accounts = {account.code: account for account in self._repository.list_accounts()}
        code_hints = self._repository.list_code_hints()
        training_examples = self._repository.list_training_examples()
        return self._predict_transaction_with_context(
            transaction,
            accounts,
            code_hints,
            training_examples,
        )

    def _predict_transaction_with_context(
        self,
        transaction: ParsedBankTransaction,
        accounts: dict[str, AccountingAccount],
        code_hints: dict[str, str],
        training_examples: list[AccountingTrainingExample],
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

        customer_invoice_prediction = self._predict_customer_invoice_payment(
            normalized_text,
            transaction.amount,
            accounts,
        )
        if customer_invoice_prediction is not None:
            return self._with_prediction(transaction, customer_invoice_prediction)

        historical_prediction = self._predict_from_training_examples(
            normalized_text,
            transaction.amount,
            accounts,
            training_examples,
        )
        if historical_prediction is not None:
            return self._with_prediction(transaction, historical_prediction)

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
    def _predict_customer_invoice_payment(
        normalized_text: str,
        amount: Decimal,
        accounts: dict[str, AccountingAccount],
    ) -> AccountingPrediction | None:
        account_code = "3400"
        account = accounts.get(account_code)
        if account is None:
            return None
        if amount <= 0:
            return None
        if "accredito" not in normalized_text:
            return None
        if "mittente" not in normalized_text and "comunicazioni" not in normalized_text:
            return None

        is_invoice_payment = "fattura" in normalized_text and "riferimenti" in normalized_text
        is_course_payment = "corso" in normalized_text and (
            "rata" in normalized_text
            or "pnl" in normalized_text
            or "formazione" in normalized_text
        )
        is_customer_credit = "riferimenti" in normalized_text and "notprovided" in normalized_text
        is_generic_customer_credit = "mittente" in normalized_text or "comunicazioni" in normalized_text
        if (
            not is_invoice_payment
            and not is_course_payment
            and not is_customer_credit
            and not is_generic_customer_credit
        ):
            return None

        matched_tokens = ["accredito"]
        if is_invoice_payment:
            matched_tokens.extend(["fattura", "riferimenti"])
        if is_course_payment:
            matched_tokens.extend(["corso", "rata"])
        if is_customer_credit:
            matched_tokens.extend(["mittente", "riferimenti"])
        if is_generic_customer_credit:
            matched_tokens.extend(["mittente", "comunicazioni"])

        return AccountingPrediction(
            account_code=account_code,
            account_description=account.description,
            source="customer_invoice_payment",
            confidence="alta",
            needs_review=False,
            message="Accredito cliente/corso; importo ignorato per questa regola.",
            score=1.0,
            evidence=[
                {
                    "account_code": account_code,
                    "source": "rule",
                    "score": 1.0,
                    "amount": format(amount, "f"),
                    "common_tokens": list(dict.fromkeys(matched_tokens)),
                }
            ],
        )

    def _predict_from_training_examples(
        self,
        normalized_text: str,
        amount: Decimal,
        accounts: dict[str, AccountingAccount],
        training_examples: list[AccountingTrainingExample],
    ) -> AccountingPrediction | None:
        query_tokens = _accounting_tokens(normalized_text)
        if not query_tokens:
            return None

        candidates: list[dict[str, object]] = []
        for example in training_examples:
            if example.target_account_code not in accounts:
                continue
            example_tokens = _accounting_tokens(example.normalized_text)
            if not example_tokens:
                continue
            text_score = self._text_similarity(query_tokens, example_tokens)
            if text_score < 0.18:
                continue
            amount_score = self._amount_similarity(amount, example.amount)
            if amount_score is None:
                continue
            score = (text_score * 0.72) + (amount_score * 0.28)
            if amount_score < 0.15:
                score = min(score, 0.44)
            candidates.append(
                {
                    "account_code": example.target_account_code,
                    "raw_text": example.raw_text,
                    "amount": format(example.amount, "f") if example.amount is not None else None,
                    "source": example.source,
                    "score": round(score, 4),
                    "text_score": round(text_score, 4),
                    "amount_score": round(amount_score, 4),
                    "common_tokens": sorted(query_tokens & example_tokens)[:8],
                }
            )

        if not candidates:
            return None

        best_by_account: dict[str, dict[str, object]] = {}
        for candidate in candidates:
            account_code = str(candidate["account_code"])
            existing = best_by_account.get(account_code)
            if existing is None or float(candidate["score"]) > float(existing["score"]):
                best_by_account[account_code] = candidate

        ranked_accounts = sorted(
            best_by_account.values(),
            key=lambda candidate: float(candidate["score"]),
            reverse=True,
        )
        best = ranked_accounts[0]
        second = ranked_accounts[1] if len(ranked_accounts) > 1 else None
        best_score = float(best["score"])
        second_score = float(second["score"]) if second is not None else 0.0
        margin = best_score - second_score
        evidence = sorted(candidates, key=lambda candidate: float(candidate["score"]), reverse=True)[:3]

        if best_score >= 0.68 and (second is None or margin >= 0.08):
            account_code = str(best["account_code"])
            account = accounts.get(account_code)
            return AccountingPrediction(
                account_code=account_code,
                account_description=account.description if account else None,
                source="historical_example",
                confidence="alta" if best_score >= 0.80 else "media",
                needs_review=False,
                message=f"Esempio storico simile, score {best_score:.2f}.",
                score=round(best_score, 4),
                evidence=evidence,
            )

        if best_score >= 0.54:
            return AccountingPrediction(
                account_code=None,
                account_description=None,
                source="historical_ambiguous",
                confidence=None,
                needs_review=True,
                message=(
                    f"Esempi storici simili ma non abbastanza sicuri "
                    f"(best {best_score:.2f}, margine {margin:.2f})."
                ),
                score=round(best_score, 4),
                evidence=evidence,
            )

        return None

    @staticmethod
    def _text_similarity(query_tokens: set[str], example_tokens: set[str]) -> float:
        common = query_tokens & example_tokens
        if not common:
            return 0.0
        query_coverage = len(common) / len(query_tokens)
        example_coverage = len(common) / len(example_tokens)
        return (query_coverage * 0.72) + (example_coverage * 0.28)

    @staticmethod
    def _amount_similarity(amount: Decimal, example_amount: Decimal | None) -> float | None:
        if example_amount is None:
            return 0.35
        if amount == 0 and example_amount == 0:
            return 1.0
        if amount == 0 or example_amount == 0:
            return 0.0
        if (amount > 0) != (example_amount > 0):
            return None

        current = abs(amount)
        historical = abs(example_amount)
        ratio = min(current, historical) / max(current, historical)
        if ratio >= Decimal("0.95"):
            return 1.0
        if ratio >= Decimal("0.80"):
            return 0.92
        if ratio >= Decimal("0.60"):
            return 0.75
        if ratio >= Decimal("0.35"):
            return 0.50
        if ratio >= Decimal("0.15"):
            return 0.28
        if ratio >= Decimal("0.05"):
            return 0.12
        return 0.0

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
