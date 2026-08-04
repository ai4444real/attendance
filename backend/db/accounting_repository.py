"""PostgreSQL repository for the accounting consultant MVP."""

from __future__ import annotations

from decimal import Decimal

from backend.accounting_app.models import AccountingAccount, AccountingFeedbackRule

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

    def find_latest_feedback(self, normalized_text: str, amount: Decimal) -> AccountingFeedbackRule | None:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT raw_text, normalized_text, amount, account_code, prediction_source
                    FROM accounting_feedback
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
            raw_text=str(row[0]),
            normalized_text=str(row[1]),
            amount=row[2],
            account_code=str(row[3]),
            prediction_source=row[4],
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
