BEGIN;

ALTER TABLE attendance_identity_aliases
    ADD COLUMN canonical_email TEXT,
    ADD COLUMN alias_type TEXT NOT NULL DEFAULT 'full_name';

ALTER TABLE attendance_identity_aliases
    ADD CONSTRAINT attendance_identity_aliases_alias_type_check
    CHECK (alias_type IN ('full_name', 'email'));

ALTER TABLE attendance_identity_aliases
    DROP CONSTRAINT IF EXISTS attendance_identity_aliases_normalized_alias_key_key;

CREATE UNIQUE INDEX attendance_identity_aliases_alias_type_key_idx
    ON attendance_identity_aliases (alias_type, normalized_alias_key);

ALTER TABLE attendance_identity_aliases OWNER TO rebekko_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_identity_aliases TO rebekko_app;

COMMIT;
