-- Configurable deterministic rules for the accounting consultant.
-- These rules replace hardcoded accounting patterns while keeping the
-- prediction engine generic and explainable.

CREATE TABLE IF NOT EXISTS accounting_prediction_rules (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    account_code TEXT NOT NULL REFERENCES accounting_accounts(code),
    priority INTEGER NOT NULL DEFAULT 100,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    amount_sign TEXT NOT NULL DEFAULT 'any',
    min_abs_amount NUMERIC(14, 2),
    max_abs_amount NUMERIC(14, 2),
    required_tokens TEXT[] NOT NULL DEFAULT '{}',
    any_tokens TEXT[] NOT NULL DEFAULT '{}',
    message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT accounting_prediction_rules_amount_sign_check
        CHECK (amount_sign IN ('any', 'positive', 'negative'))
);

CREATE INDEX IF NOT EXISTS idx_accounting_prediction_rules_active_priority
    ON accounting_prediction_rules (active, priority ASC, id ASC);

INSERT INTO accounting_prediction_rules (
    name,
    account_code,
    priority,
    amount_sign,
    min_abs_amount,
    max_abs_amount,
    required_tokens,
    any_tokens,
    message
)
VALUES
    (
        'Accrediti clienti scuola',
        '3400',
        10,
        'positive',
        NULL,
        NULL,
        ARRAY['accredito'],
        ARRAY['mittente', 'comunicazioni'],
        'Accredito cliente/corso; importo ignorato per questa regola.'
    ),
    (
        'Ordine collettivo OPAE piccolo',
        '6660',
        20,
        'negative',
        NULL,
        200.00,
        ARRAY['ordine', 'collettivo', 'opae'],
        ARRAY[]::TEXT[],
        'Ordine collettivo OPAE piccolo; classificato come spesa paghe/strumento.'
    ),
    (
        'Wise verso Panoramen',
        '4401',
        30,
        'negative',
        NULL,
        NULL,
        ARRAY['wise', 'payments'],
        ARRAY['panoramen', 'eood'],
        'Pagamento Wise verso Panoramen/EOOD.'
    ),
    (
        'POSTA CH SA',
        '6552',
        40,
        'negative',
        NULL,
        NULL,
        ARRAY['posta', 'ch', 'sa'],
        ARRAY[]::TEXT[],
        'Movimento carta/servizio POSTA CH SA.'
    )
ON CONFLICT DO NOTHING;
