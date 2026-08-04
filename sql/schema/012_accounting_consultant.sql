-- Accounting consultant MVP.
-- Isolated schema for bank/card accounting prediction experiments.

CREATE TABLE IF NOT EXISTS accounting_accounts (
    code TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS accounting_code_hints (
    code TEXT PRIMARY KEY,
    account_code TEXT NOT NULL REFERENCES accounting_accounts(code),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS accounting_feedback (
    id BIGSERIAL PRIMARY KEY,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    amount NUMERIC(14, 2),
    account_code TEXT NOT NULL REFERENCES accounting_accounts(code),
    predicted_account_code TEXT,
    prediction_source TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_accounting_feedback_normalized_text
    ON accounting_feedback (normalized_text, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_accounting_feedback_normalized_text_amount
    ON accounting_feedback (normalized_text, amount, created_at DESC);

CREATE TABLE IF NOT EXISTS accounting_training_examples (
    id BIGSERIAL PRIMARY KEY,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    amount NUMERIC(14, 2),
    target_account_code TEXT NOT NULL REFERENCES accounting_accounts(code),
    source TEXT NOT NULL,
    source_reference TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_accounting_training_examples_normalized_text
    ON accounting_training_examples (normalized_text);
