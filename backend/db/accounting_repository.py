"""PostgreSQL repository for the accounting consultant MVP."""

from __future__ import annotations

from decimal import Decimal

from backend.accounting_app.models import (
    AccountingAccount,
    AccountingCodeHint,
    AccountingFeedbackRule,
    AccountingTrainingExample,
)

from .connection import get_db_connection


class PostgresAccountingRepository:
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
