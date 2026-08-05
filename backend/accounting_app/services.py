"""Application services for the accounting consultant MVP."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol
from collections import Counter

import pdfplumber

from .models import (
    AccountingAccount,
    AccountingCodeHint,
    AccountingPrediction,
    AccountingPredictionRule,
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
    def list_prediction_rules(self, *, active_only: bool = False) -> list[AccountingPredictionRule]: ...
    def upsert_prediction_rule(
        self,
        *,
        rule_id: int | None,
        name: str,
        account_code: str,
        priority: int,
        active: bool,
        amount_sign: str,
        min_abs_amount: Decimal | None,
        max_abs_amount: Decimal | None,
        required_tokens: list[str],
        any_tokens: list[str],
        message: str | None,
    ) -> AccountingPredictionRule: ...
    def delete_prediction_rule(self, rule_id: int) -> None: ...
    def list_persisted_source_transactions(self, source_type: str, source_key: str): ...
    def persist_prediction_batch(self, *, filename: str, file_sha256: str, records: list[dict]): ...
    def get_import_batch_transactions(self, batch_id: int): ...
    def list_import_batches(self, *, status: str = "draft"): ...
    def confirm_import_batch(self, batch_id: int, assignments: dict[int, str]) -> None: ...
    def delete_import_batch(self, batch_id: int) -> None: ...
    def list_confirmed_transactions(self, date_from: str, date_to: str): ...
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
        "mask": ["D:dd.mm.yyyy", "T", "A", "A", "X", "B"],
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
    source_key = ""
    for row in rows[:8]:
        if len(row) >= 2 and row[0].strip().casefold() == "account:":
            source_key = row[1].strip().strip('"').strip("=").strip('"')
            break
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
        balance: Decimal | None = None
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
            elif mask == "B":
                balance = parse_accounting_amount(value)
        if not date and not description:
            continue
        transactions.append(
            ParsedBankTransaction(
                row_index=row_index,
                date=date,
                description=description,
                amount=amount.quantize(Decimal("0.01")),
                source_key=source_key or bank,
                balance=balance,
            )
        )

    return transactions


_PAYROLL_ACCOUNT_MAP = {
    "10220": ("2062", "Stipendio netto"),
    "22700": ("5720", "LPP"),
    "22710": ("5700", "AVS/AD"),
    "22730": ("5730", "LAINF"),
    "22790": ("5790", "Imposte alla fonte"),
    "50000": ("5000", "Stipendio lordo"),
}


def parse_fibu_payroll_csv(text: str) -> list[ParsedBankTransaction]:
    reader = csv.DictReader(io.StringIO(text), delimiter=";", quotechar='"')
    required = {"Datum", "Konto", "Soll", "Haben"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError("Formato FIBU stipendi non riconosciuto.")
    transactions: list[ParsedBankTransaction] = []
    for row_index, row in enumerate(reader, start=2):
        source_account = str(row.get("Konto") or "").strip()
        mapping = _PAYROLL_ACCOUNT_MAP.get(source_account)
        if mapping is None:
            raise ValueError(f"Conto FIBU stipendi non mappato: {source_account or '-'}.")
        debit = parse_accounting_amount(row.get("Soll")) if row.get("Soll") else Decimal("0.00")
        credit = parse_accounting_amount(row.get("Haben")) if row.get("Haben") else Decimal("0.00")
        if (debit > 0) == (credit > 0):
            raise ValueError(f"Riga FIBU {row_index}: valorizzare esattamente uno tra Soll e Haben.")
        try:
            date = datetime.strptime(str(row.get("Datum") or ""), "%Y-%m-%d").strftime("%d.%m.%Y")
        except ValueError as exc:
            raise ValueError(f"Data FIBU non valida alla riga {row_index}.") from exc
        target_account, description = mapping
        transactions.append(ParsedBankTransaction(
            row_index=row_index,
            date=date,
            description=description,
            amount=debit if debit > 0 else credit,
            source_key="payroll",
            translated_account_code=target_account,
            entry_side="debit" if debit > 0 else "credit",
        ))
    if not transactions:
        raise ValueError("Nessuna registrazione trovata nel file FIBU stipendi.")
    debit_total = sum((item.amount for item in transactions if item.entry_side == "debit"), Decimal("0"))
    credit_total = sum((item.amount for item in transactions if item.entry_side == "credit"), Decimal("0"))
    if debit_total != credit_total:
        raise ValueError(
            f"Scrittura stipendi non bilanciata: Dare {debit_total:.2f}, Avere {credit_total:.2f}."
        )
    return transactions


_CREDIT_CARD_TRANSACTION_RE = re.compile(
    r"^(?P<booking_date>\d{2}\.\d{2}\.\d{2})\s+"
    r"(?P<purchase_date>\d{2}\.\d{2}\.\d{2})\s+"
    r"(?P<description>.+?)\s+"
    r"(?P<chf_amount>-?[\d'’]+\.\d{2})$"
)


def parse_postfinance_credit_card_text(
    text: str,
    *,
    starting_row_index: int = 1,
    source_key: str | None = None,
) -> list[ParsedBankTransaction]:
    """Parse transaction rows from extracted PostFinance credit-card text."""
    transactions: list[ParsedBankTransaction] = []
    for line_offset, raw_line in enumerate(text.splitlines()):
        line = re.sub(r"\s+", " ", raw_line).strip()
        match = _CREDIT_CARD_TRANSACTION_RE.match(line)
        if match is None:
            continue
        booking_date = datetime.strptime(match.group("booking_date"), "%d.%m.%y")
        statement_amount = parse_accounting_amount(
            match.group("chf_amount").replace("’", "'")
        )
        transactions.append(
            ParsedBankTransaction(
                row_index=starting_row_index + line_offset,
                date=booking_date.strftime("%d.%m.%Y"),
                description=match.group("description").strip(),
                # Card charges are printed positive; credits carry a minus sign.
                # Invert them to preserve the bank CSV accounting convention.
                amount=-statement_amount,
                source_key=source_key,
            )
        )
    return transactions


def parse_postfinance_credit_card_pdf(content: bytes) -> list[ParsedBankTransaction]:
    """Extract normalized transactions from a PostFinance credit-card PDF."""
    if not content:
        raise ValueError("PDF carta di credito vuoto.")
    transactions: list[ParsedBankTransaction] = []
    page_texts: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as document:
            for page_number, page in enumerate(document.pages, start=1):
                text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                page_texts.append(text)
                card_match = re.search(
                    r"(?:Transazioni|Totale) PostFinance Visa Business Card,.*?XXXX\s+(\d{4})",
                    text,
                )
                source_key = card_match.group(1) if card_match else None
                transactions.extend(
                    parse_postfinance_credit_card_text(
                        text,
                        starting_row_index=page_number * 10_000,
                        source_key=source_key,
                    )
                )
    except Exception as exc:
        raise ValueError("Impossibile leggere il PDF della carta di credito PostFinance.") from exc
    document_text = "\n".join(page_texts)
    if "PostFinance" not in document_text or "carta di credito" not in document_text.casefold():
        raise ValueError("Il PDF non e' un resoconto carta di credito PostFinance riconosciuto.")
    if not transactions:
        raise ValueError("Nessuna transazione trovata nel PDF della carta di credito PostFinance.")
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

    def list_prediction_rules(self) -> list[AccountingPredictionRule]:
        try:
            return self._repository.list_prediction_rules(active_only=False)
        except Exception:
            return []

    def save_prediction_rule(
        self,
        *,
        rule_id: int | None,
        name: str,
        account_code: str,
        priority: int,
        active: bool,
        amount_sign: str,
        min_abs_amount: Decimal | None,
        max_abs_amount: Decimal | None,
        required_tokens: list[str],
        any_tokens: list[str],
        message: str | None,
    ) -> AccountingPredictionRule:
        clean_name = name.strip()
        clean_account_code = account_code.strip()
        clean_amount_sign = amount_sign.strip().casefold()
        if not clean_name:
            raise ValueError("Nome regola mancante.")
        if not clean_account_code:
            raise ValueError("Conto mancante.")
        if clean_amount_sign not in {"any", "positive", "negative"}:
            raise ValueError("Segno importo non valido.")
        accounts = {account.code for account in self._repository.list_all_accounts()}
        if clean_account_code not in accounts:
            raise ValueError(f"Conto inesistente: {clean_account_code}")
        clean_required_tokens = self._clean_rule_tokens(required_tokens)
        clean_any_tokens = self._clean_rule_tokens(any_tokens)
        if not clean_required_tokens and not clean_any_tokens:
            raise ValueError("La regola deve avere almeno un token.")
        return self._repository.upsert_prediction_rule(
            rule_id=rule_id,
            name=clean_name,
            account_code=clean_account_code,
            priority=int(priority),
            active=active,
            amount_sign=clean_amount_sign,
            min_abs_amount=min_abs_amount,
            max_abs_amount=max_abs_amount,
            required_tokens=clean_required_tokens,
            any_tokens=clean_any_tokens,
            message=message.strip() if message else None,
        )

    def delete_prediction_rule(self, rule_id: int) -> None:
        if rule_id <= 0:
            raise ValueError("Regola non valida.")
        self._repository.delete_prediction_rule(rule_id)

    def parse_and_predict_bank_csv(self, content: bytes, bank: str) -> list[PredictedBankTransaction]:
        text = decode_upload(content)
        transactions = parse_bank_csv(text, bank)
        return self._predict_transactions(transactions)

    def parse_and_predict_credit_card_pdf(self, content: bytes) -> list[PredictedBankTransaction]:
        transactions = parse_postfinance_credit_card_pdf(content)
        return self._predict_transactions(transactions)

    def parse_payroll_csv(self, content: bytes) -> list[PredictedBankTransaction]:
        transactions = parse_fibu_payroll_csv(decode_upload(content))
        accounts = {account.code: account for account in self._repository.list_accounts()}
        result = []
        for transaction in transactions:
            account_code = transaction.translated_account_code or ""
            account = accounts.get(account_code)
            if account is None:
                raise ValueError(f"Conto contabile stipendi inesistente o disattivato: {account_code}.")
            result.append(self._with_prediction(transaction, AccountingPrediction(
                account_code=account_code,
                account_description=account.description,
                source="fibu_translation",
                confidence="alta",
                needs_review=False,
                message="Traduzione deterministica FIBU stipendi.",
            )))
        return result

    def import_and_predict_bank_csv(self, content: bytes, bank: str, filename: str) -> dict:
        predictions = self.parse_and_predict_bank_csv(content, bank)
        return self._persist_predictions(filename, content, "bank", predictions)

    def import_and_predict_credit_card_pdf(self, content: bytes, filename: str) -> dict:
        predictions = self.parse_and_predict_credit_card_pdf(content)
        return self._persist_predictions(filename, content, "credit_card", predictions)

    def import_payroll_csv(self, content: bytes, filename: str) -> dict:
        return self._persist_predictions(filename, content, "payroll", self.parse_payroll_csv(content))

    def _persist_predictions(
        self,
        filename: str,
        content: bytes,
        source_type: str,
        predictions: list[PredictedBankTransaction],
    ) -> dict:
        by_source: dict[str, list[PredictedBankTransaction]] = {}
        for item in predictions:
            source_key = item.source_key or ("postfinance" if source_type == "bank" else "unknown")
            if source_type == "credit_card" and source_key == "unknown":
                raise ValueError("Impossibile identificare la carta di credito di una transazione.")
            by_source.setdefault(source_key, []).append(item)

        identities: dict[int, str] = {}
        occurrence_counts: Counter[tuple[str, str, str, str]] = Counter()
        for source_key, items in by_source.items():
            if source_type == "bank":
                self._validate_bank_continuity(source_key, items)
            for item in items:
                if source_type == "bank":
                    if item.balance is None:
                        raise ValueError("Saldo PostFinance mancante su una transazione.")
                    identity_raw = f"{source_key}|{item.date}|{item.balance:.2f}"
                elif source_type == "payroll":
                    identity_raw = (
                        f"{source_key}|{item.date}|{item.prediction.account_code}|{item.entry_side}"
                    )
                else:
                    base = (source_key, item.date, item.description, f"{item.amount:.2f}")
                    occurrence_counts[base] += 1
                    identity_raw = "|".join(base) + f"|{occurrence_counts[base]}"
                identities[id(item)] = hashlib.sha256(identity_raw.encode("utf-8")).hexdigest()

        records = []
        for item in predictions:
            source_key = item.source_key or "postfinance"
            is_card = source_type == "credit_card"
            is_payroll = source_type == "payroll"
            records.append({
                "source_type": source_type,
                "source_key": source_key,
                "group_name": "Stipendi" if is_payroll else "Carte di credito" if is_card else "Conti bancari",
                "display_name": "Stipendi FIBU" if is_payroll else f"Carta PostFinance {source_key}" if is_card else f"PostFinance {source_key}",
                "counter_account_code": None if is_payroll else "2070" if is_card else "1025",
                "identity_key": identities[id(item)],
                "date": item.date,
                "description": item.description,
                "amount": item.amount,
                "balance": item.balance,
                "account_code": item.prediction.account_code,
                "prediction_source": item.prediction.source,
                "entry_side": item.entry_side,
            })
        metadata = self._repository.persist_prediction_batch(
            filename=filename or "import",
            file_sha256=hashlib.sha256(content).hexdigest(),
            records=records,
        )
        metadata["transactions"] = self.load_import_batch(int(metadata["batch_id"]))
        return metadata

    def _validate_bank_continuity(
        self,
        source_key: str,
        items: list[PredictedBankTransaction],
    ) -> None:
        for current, older in zip(items, items[1:]):
            if current.balance is None or older.balance is None:
                raise ValueError("Saldo PostFinance mancante: impossibile riconciliare il file.")
            expected_older_balance = current.balance - current.amount
            if expected_older_balance != older.balance:
                raise ValueError(
                    "Saldo PostFinance non riconciliato: dopo la transazione del "
                    f"{current.date} atteso {expected_older_balance:.2f}, trovato {older.balance:.2f}."
                )
        existing = self._repository.list_persisted_source_transactions("bank", source_key)
        if not existing:
            return
        existing_keys = {str(row["identity_key"]) for row in existing}
        incoming_keys = {
            hashlib.sha256(f"{source_key}|{item.date}|{item.balance:.2f}".encode("utf-8")).hexdigest()
            for item in items if item.balance is not None
        }
        if existing_keys.isdisjoint(incoming_keys):
            raise ValueError(
                "Nessuna continuita' con i movimenti PostFinance gia' salvati: "
                "l'importazione e' stata fermata. Includi almeno una transazione sovrapposta."
            )

    def list_import_batches(self) -> list[dict]:
        return self._repository.list_import_batches(status="all")

    def load_import_batch(self, batch_id: int) -> list[PredictedBankTransaction]:
        accounts = {account.code: account for account in self._repository.list_all_accounts()}
        rows = self._repository.get_import_batch_transactions(batch_id)
        result = []
        for row in rows:
            account_code = row["account_code"]
            account = accounts.get(account_code) if account_code else None
            result.append(PredictedBankTransaction(
                row_index=int(row["id"]),
                date=row["date"],
                description=row["description"],
                amount=row["amount"],
                prediction=AccountingPrediction(
                    account_code=account_code,
                    account_description=account.description if account else None,
                    source=str(row["prediction_source"] or "review"),
                    needs_review=not bool(account_code),
                    message="Bozza persistente",
                ),
                source_key=str(row["source_key"]),
                balance=row["balance"],
                ledger_id=int(row["id"]),
                counter_account_code=(
                    str(row["counter_account_code"])
                    if row["counter_account_code"] is not None
                    else None
                ),
                entry_side=row["entry_side"],
            ))
        return result

    def confirm_import_batch(self, batch_id: int, assignments: dict[int, str]) -> None:
        valid_accounts = {account.code for account in self._repository.list_accounts()}
        if not assignments or any(code not in valid_accounts for code in assignments.values()):
            raise ValueError("Ogni transazione deve avere un conto contabile valido.")
        self._repository.confirm_import_batch(batch_id, assignments)

    def delete_import_batch(self, batch_id: int) -> None:
        if batch_id <= 0:
            raise ValueError("Import non valido.")
        self._repository.delete_import_batch(batch_id)

    def list_confirmed_transactions(self, date_from: str, date_to: str):
        return self._repository.list_confirmed_transactions(date_from, date_to)

    def _predict_transactions(
        self,
        transactions: list[ParsedBankTransaction],
    ) -> list[PredictedBankTransaction]:
        accounts = {account.code: account for account in self._repository.list_accounts()}
        code_hints = self._repository.list_code_hints()
        prediction_rules = self._list_active_prediction_rules()
        training_examples = self._repository.list_training_examples()
        return [
            self._predict_transaction_with_context(
                transaction,
                accounts,
                code_hints,
                prediction_rules,
                training_examples,
            )
            for transaction in transactions
        ]

    def predict_transaction(self, transaction: ParsedBankTransaction) -> PredictedBankTransaction:
        accounts = {account.code: account for account in self._repository.list_accounts()}
        code_hints = self._repository.list_code_hints()
        prediction_rules = self._list_active_prediction_rules()
        training_examples = self._repository.list_training_examples()
        return self._predict_transaction_with_context(
            transaction,
            accounts,
            code_hints,
            prediction_rules,
            training_examples,
        )

    def _predict_transaction_with_context(
        self,
        transaction: ParsedBankTransaction,
        accounts: dict[str, AccountingAccount],
        code_hints: dict[str, str],
        prediction_rules: list[AccountingPredictionRule],
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

        configured_rule_prediction = self._predict_from_configured_rules(
            normalized_text,
            transaction.amount,
            accounts,
            prediction_rules,
        )
        if configured_rule_prediction is not None:
            return self._with_prediction(transaction, configured_rule_prediction)

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
                message="Nessuna regola, feedback, code hint o corrispondenza training applicabile.",
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

    @staticmethod
    def _clean_rule_tokens(values: list[str]) -> list[str]:
        tokens: list[str] = []
        for value in values:
            token = normalize_accounting_text(str(value))
            if token and token not in tokens:
                tokens.append(token)
        return tokens

    def _list_active_prediction_rules(self) -> list[AccountingPredictionRule]:
        try:
            return self._repository.list_prediction_rules(active_only=True)
        except Exception as exc:
            raise RuntimeError(
                "Nessuna regola di predizione disponibile: impossibile leggere accounting_prediction_rules."
            ) from exc

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

    def _predict_from_configured_rules(
        self,
        normalized_text: str,
        amount: Decimal,
        accounts: dict[str, AccountingAccount],
        rules: list[AccountingPredictionRule],
    ) -> AccountingPrediction | None:
        for rule in rules:
            if not self._configured_rule_matches(rule, normalized_text, amount):
                continue
            return self._rule_prediction(
                account_code=rule.account_code,
                source="configured_rule",
                message=rule.message or f"Regola configurata: {rule.name}",
                amount=amount,
                accounts=accounts,
                tokens=[*rule.required_tokens, *rule.any_tokens],
            )
        return None

    @staticmethod
    def _configured_rule_matches(
        rule: AccountingPredictionRule,
        normalized_text: str,
        amount: Decimal,
    ) -> bool:
        if rule.amount_sign == "positive" and amount <= 0:
            return False
        if rule.amount_sign == "negative" and amount >= 0:
            return False
        abs_amount = abs(amount)
        if rule.min_abs_amount is not None and abs_amount < rule.min_abs_amount:
            return False
        if rule.max_abs_amount is not None and abs_amount > rule.max_abs_amount:
            return False
        if any(token not in normalized_text for token in rule.required_tokens):
            return False
        if rule.any_tokens and not any(token in normalized_text for token in rule.any_tokens):
            return False
        return True

    @staticmethod
    def _rule_prediction(
        *,
        account_code: str,
        source: str,
        message: str,
        amount: Decimal,
        accounts: dict[str, AccountingAccount],
        tokens: list[str],
    ) -> AccountingPrediction | None:
        account = accounts.get(account_code)
        if account is None:
            return None
        return AccountingPrediction(
            account_code=account_code,
            account_description=account.description,
            source=source,
            confidence="alta",
            needs_review=False,
            message=message,
            score=1.0,
            evidence=[
                {
                    "account_code": account_code,
                    "source": "rule",
                    "score": 1.0,
                    "amount": format(amount, "f"),
                    "common_tokens": tokens,
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
        evidence_account_codes = {str(candidate["account_code"]) for candidate in evidence}

        if best_score >= 0.68 and (
            second is None
            or margin >= 0.08
            or evidence_account_codes == {str(best["account_code"])}
        ):
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
            source_key=transaction.source_key,
            balance=transaction.balance,
            entry_side=transaction.entry_side,
        )
