"""PostgreSQL repository for the accounting consultant MVP."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from backend.accounting_app.models import (
    AccountingAccount,
    AccountingCodeHint,
    AccountingFeedbackRule,
    AccountingPredictionRule,
    AccountingTrainingExample,
)

from .connection import get_db_connection


class PostgresAccountingRepository:
    def list_persisted_source_transactions(self, source_type: str, source_key: str) -> list[dict[str, Any]]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT t.identity_key, t.transaction_date, t.description, t.amount,
                           t.statement_balance
                    FROM accounting_ledger_transactions t
                    JOIN accounting_sources s ON s.id = t.source_id
                    WHERE s.source_type = %s AND s.source_key = %s
                    """,
                    (source_type, source_key),
                )
                rows = cursor.fetchall()
        return [
            {
                "identity_key": str(row[0]),
                "date": row[1].strftime("%d.%m.%Y"),
                "description": str(row[2]),
                "amount": row[3],
                "balance": row[4],
            }
            for row in rows
        ]

    def persist_prediction_batch(
        self,
        *,
        filename: str,
        file_sha256: str,
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, status FROM accounting_import_batches WHERE file_sha256 = %s",
                    (file_sha256,),
                )
                existing_batch = cursor.fetchone()
                if existing_batch is not None:
                    if str(existing_batch[1]) == "draft":
                        for record in records:
                            cursor.execute(
                                """
                                UPDATE accounting_ledger_transactions t
                                SET account_code = %s,
                                    prediction_source = %s,
                                    updated_at = now()
                                FROM accounting_sources s
                                WHERE t.source_id = s.id
                                  AND s.source_type = %s
                                  AND s.source_key = %s
                                  AND t.identity_key = %s
                                  AND t.status = 'draft'
                                """,
                                (
                                    record["account_code"], record["prediction_source"],
                                    record["source_type"], record["source_key"],
                                    record["identity_key"],
                                ),
                            )
                        connection.commit()
                    cursor.execute(
                        """
                        SELECT COUNT(*) FILTER (WHERE bt.was_new),
                               COUNT(*) FILTER (WHERE NOT bt.was_new)
                        FROM accounting_batch_transactions bt
                        WHERE bt.batch_id = %s
                        """,
                        (existing_batch[0],),
                    )
                    counts = cursor.fetchone() or (0, 0)
                    return {
                        "batch_id": int(existing_batch[0]),
                        "status": str(existing_batch[1]),
                        "new_count": int(counts[0] or 0),
                        "duplicate_count": int(counts[1] or 0),
                        "existing_file": True,
                    }
                cursor.execute(
                    """
                    INSERT INTO accounting_import_batches (filename, file_sha256)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (filename, file_sha256),
                )
                batch_id = int(cursor.fetchone()[0])
                new_count = 0
                duplicate_count = 0
                for record in records:
                    cursor.execute(
                        """
                        INSERT INTO accounting_sources (
                            source_type, source_key, group_name, display_name,
                            currency, counter_account_code
                        )
                        VALUES (%s, %s, %s, %s, 'CHF', %s)
                        ON CONFLICT (source_type, source_key) DO UPDATE
                        SET display_name = EXCLUDED.display_name,
                            group_name = EXCLUDED.group_name,
                            counter_account_code = EXCLUDED.counter_account_code
                        RETURNING id
                        """,
                        (
                            record["source_type"], record["source_key"],
                            record["group_name"], record["display_name"],
                            record["counter_account_code"],
                        ),
                    )
                    source_id = int(cursor.fetchone()[0])
                    cursor.execute(
                        """
                        SELECT id, transaction_date, description, amount, statement_balance
                        FROM accounting_ledger_transactions
                        WHERE source_id = %s AND identity_key = %s
                        """,
                        (source_id, record["identity_key"]),
                    )
                    existing = cursor.fetchone()
                    was_new = existing is None
                    if existing is not None:
                        existing_values = (
                            existing[1].strftime("%d.%m.%Y"), str(existing[2]),
                            existing[3], existing[4],
                        )
                        incoming_values = (
                            record["date"], record["description"],
                            record["amount"], record["balance"],
                        )
                        if existing_values != incoming_values:
                            raise RuntimeError(
                                "Conflitto su una transazione gia' importata: "
                                f"{record['date']} / {record['identity_key']}."
                            )
                        transaction_id = int(existing[0])
                        duplicate_count += 1
                    else:
                        cursor.execute(
                            """
                            INSERT INTO accounting_ledger_transactions (
                                source_id, identity_key, transaction_date, description,
                                amount, statement_balance, account_code, prediction_source,
                                first_batch_id
                            )
                            VALUES (%s, %s, to_date(%s, 'DD.MM.YYYY'), %s, %s, %s, %s, %s, %s)
                            RETURNING id
                            """,
                            (
                                source_id, record["identity_key"], record["date"],
                                record["description"], record["amount"], record["balance"],
                                record["account_code"], record["prediction_source"], batch_id,
                            ),
                        )
                        transaction_id = int(cursor.fetchone()[0])
                        new_count += 1
                    cursor.execute(
                        """
                        INSERT INTO accounting_batch_transactions (batch_id, transaction_id, was_new)
                        VALUES (%s, %s, %s)
                        """,
                        (batch_id, transaction_id, was_new),
                    )
            connection.commit()
        return {
            "batch_id": batch_id,
            "status": "draft",
            "new_count": new_count,
            "duplicate_count": duplicate_count,
            "existing_file": False,
        }

    def list_import_batches(self, *, status: str = "draft") -> list[dict[str, Any]]:
        where_clause = "" if status == "all" else "WHERE b.status = %s"
        parameters = () if status == "all" else (status,)
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT b.id, b.filename, b.status, b.created_at, b.confirmed_at,
                           COUNT(*) FILTER (WHERE bt.was_new)
                    FROM accounting_import_batches b
                    LEFT JOIN accounting_batch_transactions bt ON bt.batch_id = b.id
                    {where_clause}
                    GROUP BY b.id
                    ORDER BY b.created_at DESC
                    """,
                    parameters,
                )
                rows = cursor.fetchall()
        return [
            {"id": int(r[0]), "filename": str(r[1]), "status": str(r[2]),
             "created_at": r[3].isoformat(), "confirmed_at": r[4].isoformat() if r[4] else None,
             "new_count": int(r[5] or 0)}
            for r in rows
        ]

    def get_import_batch_transactions(self, batch_id: int) -> list[dict[str, Any]]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT t.id, to_char(t.transaction_date, 'DD.MM.YYYY'), t.description,
                           t.amount, t.statement_balance, t.account_code, t.prediction_source,
                           t.status, s.source_type, s.source_key, s.group_name,
                           s.display_name, s.counter_account_code
                    FROM accounting_batch_transactions bt
                    JOIN accounting_ledger_transactions t ON t.id = bt.transaction_id
                    JOIN accounting_sources s ON s.id = t.source_id
                    WHERE bt.batch_id = %s AND bt.was_new = TRUE
                    ORDER BY s.id, t.transaction_date, t.id
                    """,
                    (batch_id,),
                )
                rows = cursor.fetchall()
        return [
            {"id": int(r[0]), "date": str(r[1]), "description": str(r[2]), "amount": r[3],
             "balance": r[4], "account_code": str(r[5]) if r[5] else None,
             "prediction_source": r[6], "status": str(r[7]), "source_type": str(r[8]),
             "source_key": str(r[9]), "group_name": str(r[10]), "display_name": str(r[11]),
             "counter_account_code": str(r[12])}
            for r in rows
        ]

    def confirm_import_batch(self, batch_id: int, assignments: dict[int, str]) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT status FROM accounting_import_batches WHERE id = %s FOR UPDATE", (batch_id,))
                batch = cursor.fetchone()
                if batch is None:
                    raise ValueError("Import non trovato.")
                cursor.execute(
                    """SELECT t.id FROM accounting_batch_transactions bt
                       JOIN accounting_ledger_transactions t ON t.id = bt.transaction_id
                       WHERE bt.batch_id = %s AND bt.was_new = TRUE""",
                    (batch_id,),
                )
                transaction_ids = {int(r[0]) for r in cursor.fetchall()}
                if transaction_ids != set(assignments):
                    raise ValueError("Ogni nuova transazione deve avere un conto prima della conferma.")
                for transaction_id, account_code in assignments.items():
                    cursor.execute(
                        """UPDATE accounting_ledger_transactions
                           SET account_code = %s, status = 'confirmed', updated_at = now()
                           WHERE id = %s""",
                        (account_code, transaction_id),
                    )
                cursor.execute(
                    """UPDATE accounting_import_batches
                       SET status = 'confirmed', confirmed_at = COALESCE(confirmed_at, now()) WHERE id = %s""",
                    (batch_id,),
                )
            connection.commit()

    def delete_import_batch(self, batch_id: int) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT status FROM accounting_import_batches WHERE id = %s FOR UPDATE",
                    (batch_id,),
                )
                batch = cursor.fetchone()
                if batch is None:
                    raise ValueError("Import non trovato.")
                if str(batch[0]) != "draft":
                    raise ValueError("Solo una bozza puo' essere cancellata.")
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM accounting_ledger_transactions t
                    JOIN accounting_batch_transactions bt ON bt.transaction_id = t.id
                    WHERE t.first_batch_id = %s AND bt.batch_id <> %s
                    """,
                    (batch_id, batch_id),
                )
                if int(cursor.fetchone()[0]) > 0:
                    raise ValueError(
                        "La bozza e' collegata a import successivi e non puo' essere cancellata."
                    )
                cursor.execute("DELETE FROM accounting_batch_transactions WHERE batch_id = %s", (batch_id,))
                cursor.execute("DELETE FROM accounting_ledger_transactions WHERE first_batch_id = %s", (batch_id,))
                cursor.execute("DELETE FROM accounting_import_batches WHERE id = %s", (batch_id,))
            connection.commit()

    def list_confirmed_transactions(self, date_from: str, date_to: str) -> list[dict[str, Any]]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT to_char(t.transaction_date, 'DD.MM.YYYY'), t.description, t.amount,
                           t.account_code, s.source_type, s.source_key, s.group_name,
                           s.display_name, s.counter_account_code
                    FROM accounting_ledger_transactions t
                    JOIN accounting_sources s ON s.id = t.source_id
                    WHERE t.status = 'confirmed'
                      AND t.transaction_date BETWEEN %s::date AND %s::date
                    ORDER BY s.group_name, s.display_name, t.transaction_date, t.id
                    """,
                    (date_from, date_to),
                )
                rows = cursor.fetchall()
        return [
            {"date": str(r[0]), "description": str(r[1]), "amount": r[2],
             "account_code": str(r[3]), "source_type": str(r[4]), "source_key": str(r[5]),
             "group_name": str(r[6]), "display_name": str(r[7]),
             "counter_account_code": str(r[8])}
            for r in rows
        ]

    def list_accounts(self) -> list[AccountingAccount]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT code, description, active
                    FROM accounting_accounts
                    WHERE active = TRUE
                    ORDER BY code ASC
                    """
                )
                rows = cursor.fetchall()
        return [
            AccountingAccount(code=str(row[0]), description=str(row[1]), active=bool(row[2]))
            for row in rows
        ]

    def list_all_accounts(self) -> list[AccountingAccount]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT code, description, active
                    FROM accounting_accounts
                    ORDER BY code ASC
                    """
                )
                rows = cursor.fetchall()
        return [
            AccountingAccount(code=str(row[0]), description=str(row[1]), active=bool(row[2]))
            for row in rows
        ]

    def upsert_account(self, code: str, description: str, active: bool) -> AccountingAccount:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO accounting_accounts (code, description, active, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (code) DO UPDATE
                    SET description = EXCLUDED.description,
                        active = EXCLUDED.active,
                        updated_at = now()
                    RETURNING code, description, active
                    """,
                    (code, description, active),
                )
                row = cursor.fetchone()
            connection.commit()
        if row is None:
            raise RuntimeError("Failed to save accounting account.")
        return AccountingAccount(code=str(row[0]), description=str(row[1]), active=bool(row[2]))

    def set_account_active(self, code: str, active: bool) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE accounting_accounts
                    SET active = %s,
                        updated_at = now()
                    WHERE code = %s
                    """,
                    (active, code),
                )
            connection.commit()

    def list_code_hints(self) -> dict[str, str]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT code, account_code
                    FROM accounting_code_hints
                    WHERE active = TRUE
                    """
                )
                rows = cursor.fetchall()
        return {str(row[0]).strip().casefold(): str(row[1]) for row in rows}

    def list_code_hint_records(self) -> list[AccountingCodeHint]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT h.code, h.account_code, a.description, h.active
                    FROM accounting_code_hints h
                    LEFT JOIN accounting_accounts a ON a.code = h.account_code
                    ORDER BY h.code ASC
                    """
                )
                rows = cursor.fetchall()
        return [
            AccountingCodeHint(
                code=str(row[0]),
                account_code=str(row[1]),
                account_description=str(row[2]) if row[2] is not None else None,
                active=bool(row[3]),
            )
            for row in rows
        ]

    def upsert_code_hint(self, code: str, account_code: str, active: bool) -> AccountingCodeHint:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO accounting_code_hints (code, account_code, active, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (code) DO UPDATE
                    SET account_code = EXCLUDED.account_code,
                        active = EXCLUDED.active,
                        updated_at = now()
                    RETURNING code, account_code, active
                    """,
                    (code, account_code, active),
                )
                row = cursor.fetchone()
            connection.commit()
        if row is None:
            raise RuntimeError("Failed to save accounting code hint.")
        return AccountingCodeHint(
            code=str(row[0]),
            account_code=str(row[1]),
            account_description=None,
            active=bool(row[2]),
        )

    def delete_code_hint(self, code: str) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM accounting_code_hints
                    WHERE code = %s
                    """,
                    (code,),
                )
            connection.commit()

    def list_training_examples(self) -> list[AccountingTrainingExample]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT raw_text, normalized_text, amount, target_account_code, source
                    FROM accounting_training_examples
                    WHERE target_account_code IN (
                        SELECT code FROM accounting_accounts WHERE active = TRUE
                    )
                    ORDER BY id ASC
                    """
                )
                rows = cursor.fetchall()
        return [
            AccountingTrainingExample(
                raw_text=str(row[0]),
                normalized_text=str(row[1]),
                amount=row[2],
                target_account_code=str(row[3]),
                source=str(row[4]),
            )
            for row in rows
        ]

    def find_latest_feedback(self, normalized_text: str, amount: Decimal) -> AccountingFeedbackRule | None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT f.id, f.raw_text, f.normalized_text, f.amount, f.account_code,
                           a.description, f.prediction_source, f.created_at
                    FROM accounting_feedback f
                    LEFT JOIN accounting_accounts a ON a.code = f.account_code
                    WHERE normalized_text = %s
                      AND (amount = %s OR amount IS NULL)
                    ORDER BY
                        CASE WHEN amount = %s THEN 0 ELSE 1 END,
                        created_at DESC,
                        id DESC
                    LIMIT 1
                    """,
                    (normalized_text, amount, amount),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return AccountingFeedbackRule(
            id=int(row[0]),
            raw_text=str(row[1]),
            normalized_text=str(row[2]),
            amount=row[3],
            account_code=str(row[4]),
            account_description=str(row[5]) if row[5] is not None else None,
            prediction_source=row[6],
            created_at=row[7].isoformat() if row[7] is not None else None,
        )

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
    ) -> int:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        raw_text,
                        normalized_text,
                        amount,
                        account_code,
                        predicted_account_code,
                        prediction_source,
                        created_by,
                    ),
                )
                row = cursor.fetchone()
            connection.commit()
        if row is None:
            raise RuntimeError("Failed to create accounting feedback.")
        return int(row[0])

    def list_feedback_rules(self, limit: int = 200) -> list[AccountingFeedbackRule]:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT f.id, f.raw_text, f.normalized_text, f.amount, f.account_code,
                           a.description, f.prediction_source, f.created_at
                    FROM accounting_feedback f
                    LEFT JOIN accounting_accounts a ON a.code = f.account_code
                    ORDER BY f.created_at DESC, f.id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()
        return [
            AccountingFeedbackRule(
                id=int(row[0]),
                raw_text=str(row[1]),
                normalized_text=str(row[2]),
                amount=row[3],
                account_code=str(row[4]),
                account_description=str(row[5]) if row[5] is not None else None,
                prediction_source=row[6],
                created_at=row[7].isoformat() if row[7] is not None else None,
            )
            for row in rows
        ]

    def update_feedback_account(self, feedback_id: int, account_code: str) -> AccountingFeedbackRule:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE accounting_feedback
                    SET account_code = %s
                    WHERE id = %s
                    RETURNING id, raw_text, normalized_text, amount, account_code,
                              prediction_source, created_at
                    """,
                    (account_code, feedback_id),
                )
                row = cursor.fetchone()
            connection.commit()
        if row is None:
            raise RuntimeError("Accounting feedback not found.")
        account_description = None
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT description FROM accounting_accounts WHERE code = %s", (account_code,))
                account_row = cursor.fetchone()
        if account_row is not None:
            account_description = str(account_row[0])
        return AccountingFeedbackRule(
            id=int(row[0]),
            raw_text=str(row[1]),
            normalized_text=str(row[2]),
            amount=row[3],
            account_code=str(row[4]),
            account_description=account_description,
            prediction_source=row[5],
            created_at=row[6].isoformat() if row[6] is not None else None,
        )

    def delete_feedback_rule(self, feedback_id: int) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM accounting_feedback
                    WHERE id = %s
                    """,
                    (feedback_id,),
                )
            connection.commit()

    def list_prediction_rules(self, *, active_only: bool = False) -> list[AccountingPredictionRule]:
        where_clause = "WHERE r.active = TRUE" if active_only else ""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT r.id, r.name, r.account_code, a.description, r.priority, r.active,
                           r.amount_sign, r.min_abs_amount, r.max_abs_amount,
                           r.required_tokens, r.any_tokens, r.message
                    FROM accounting_prediction_rules r
                    LEFT JOIN accounting_accounts a ON a.code = r.account_code
                    {where_clause}
                    ORDER BY r.priority ASC, r.id ASC
                    """
                )
                rows = cursor.fetchall()
        return [
            AccountingPredictionRule(
                id=int(row[0]),
                name=str(row[1]),
                account_code=str(row[2]),
                account_description=str(row[3]) if row[3] is not None else None,
                priority=int(row[4]),
                active=bool(row[5]),
                amount_sign=str(row[6]),
                min_abs_amount=row[7],
                max_abs_amount=row[8],
                required_tokens=[str(item) for item in row[9] or []],
                any_tokens=[str(item) for item in row[10] or []],
                message=str(row[11]) if row[11] is not None else None,
            )
            for row in rows
        ]

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
    ) -> AccountingPredictionRule:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                if rule_id is None:
                    cursor.execute(
                        """
                        INSERT INTO accounting_prediction_rules (
                            name, account_code, priority, active, amount_sign,
                            min_abs_amount, max_abs_amount, required_tokens,
                            any_tokens, message, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                        ON CONFLICT (name) DO UPDATE
                        SET account_code = EXCLUDED.account_code,
                            priority = EXCLUDED.priority,
                            active = EXCLUDED.active,
                            amount_sign = EXCLUDED.amount_sign,
                            min_abs_amount = EXCLUDED.min_abs_amount,
                            max_abs_amount = EXCLUDED.max_abs_amount,
                            required_tokens = EXCLUDED.required_tokens,
                            any_tokens = EXCLUDED.any_tokens,
                            message = EXCLUDED.message,
                            updated_at = now()
                        RETURNING id
                        """,
                        (
                            name,
                            account_code,
                            priority,
                            active,
                            amount_sign,
                            min_abs_amount,
                            max_abs_amount,
                            required_tokens,
                            any_tokens,
                            message,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE accounting_prediction_rules
                        SET name = %s,
                            account_code = %s,
                            priority = %s,
                            active = %s,
                            amount_sign = %s,
                            min_abs_amount = %s,
                            max_abs_amount = %s,
                            required_tokens = %s,
                            any_tokens = %s,
                            message = %s,
                            updated_at = now()
                        WHERE id = %s
                        RETURNING id
                        """,
                        (
                            name,
                            account_code,
                            priority,
                            active,
                            amount_sign,
                            min_abs_amount,
                            max_abs_amount,
                            required_tokens,
                            any_tokens,
                            message,
                            rule_id,
                        ),
                    )
                row = cursor.fetchone()
            connection.commit()
        if row is None:
            raise RuntimeError("Accounting prediction rule not found.")
        rules = [rule for rule in self.list_prediction_rules() if rule.id == int(row[0])]
        if not rules:
            raise RuntimeError("Failed to reload accounting prediction rule.")
        return rules[0]

    def delete_prediction_rule(self, rule_id: int) -> None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM accounting_prediction_rules
                    WHERE id = %s
                    """,
                    (rule_id,),
                )
            connection.commit()
