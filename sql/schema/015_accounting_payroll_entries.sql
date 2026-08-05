-- Support direct journal rows (payroll) where only the debit or credit side
-- is populated and there is no fixed source counter-account.

ALTER TABLE accounting_sources
    ALTER COLUMN counter_account_code DROP NOT NULL;

ALTER TABLE accounting_ledger_transactions
    ADD COLUMN IF NOT EXISTS entry_side TEXT;

ALTER TABLE accounting_ledger_transactions
    DROP CONSTRAINT IF EXISTS accounting_ledger_transactions_entry_side_check;

ALTER TABLE accounting_ledger_transactions
    ADD CONSTRAINT accounting_ledger_transactions_entry_side_check
    CHECK (entry_side IS NULL OR entry_side IN ('debit', 'credit'));
