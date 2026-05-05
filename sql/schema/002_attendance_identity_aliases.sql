BEGIN;

CREATE TABLE attendance_identity_aliases (
    id BIGSERIAL PRIMARY KEY,
    canonical_full_name TEXT NOT NULL,
    alias_full_name TEXT NOT NULL,
    normalized_canonical_key TEXT NOT NULL,
    normalized_alias_key TEXT NOT NULL UNIQUE,
    created_by TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (normalized_canonical_key <> ''),
    CHECK (normalized_alias_key <> '')
);

CREATE INDEX attendance_identity_aliases_canonical_idx
    ON attendance_identity_aliases (normalized_canonical_key);

CREATE INDEX attendance_identity_aliases_active_idx
    ON attendance_identity_aliases (is_active, normalized_alias_key);

ALTER TABLE attendance_identity_aliases OWNER TO rebekko_app;
ALTER SEQUENCE attendance_identity_aliases_id_seq OWNER TO rebekko_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_identity_aliases TO rebekko_app;
GRANT USAGE, SELECT ON SEQUENCE attendance_identity_aliases_id_seq TO rebekko_app;

COMMIT;
