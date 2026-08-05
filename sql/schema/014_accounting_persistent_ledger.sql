-- Persistent accounting ledger: source-separated imports, deduplication,
-- immutable statement data, review/confirmation state and period exports.

CREATE TABLE IF NOT EXISTS accounting_sources (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_key TEXT NOT NULL,
    group_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'CHF',
    counter_account_code TEXT NOT NULL REFERENCES accounting_accounts(code),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_type, source_key)
);

CREATE TABLE IF NOT EXISTS accounting_import_batches (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    file_sha256 TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at TIMESTAMPTZ,
    CONSTRAINT accounting_import_batches_status_check
        CHECK (status IN ('draft', 'confirmed'))
);

CREATE TABLE IF NOT EXISTS accounting_ledger_transactions (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES accounting_sources(id),
    identity_key TEXT NOT NULL,
    transaction_date DATE NOT NULL,
    description TEXT NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    statement_balance NUMERIC(14, 2),
    account_code TEXT REFERENCES accounting_accounts(code),
    prediction_source TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    first_batch_id BIGINT NOT NULL REFERENCES accounting_import_batches(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT accounting_ledger_transactions_status_check
        CHECK (status IN ('draft', 'confirmed')),
    UNIQUE (source_id, identity_key)
);

CREATE TABLE IF NOT EXISTS accounting_batch_transactions (
    batch_id BIGINT NOT NULL REFERENCES accounting_import_batches(id) ON DELETE CASCADE,
    transaction_id BIGINT NOT NULL REFERENCES accounting_ledger_transactions(id),
    was_new BOOLEAN NOT NULL,
    PRIMARY KEY (batch_id, transaction_id)
);

CREATE INDEX IF NOT EXISTS idx_accounting_ledger_source_date
    ON accounting_ledger_transactions (source_id, transaction_date, id);
CREATE INDEX IF NOT EXISTS idx_accounting_ledger_status_date
    ON accounting_ledger_transactions (status, transaction_date, id);
CREATE INDEX IF NOT EXISTS idx_accounting_batches_status_created
    ON accounting_import_batches (status, created_at DESC);
