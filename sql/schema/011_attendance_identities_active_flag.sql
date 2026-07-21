BEGIN;

ALTER TABLE attendance_identities
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS attendance_identities_active_idx
    ON attendance_identities (is_active, display_name);

ALTER TABLE attendance_identities OWNER TO rebekko_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_identities TO rebekko_app;

COMMIT;
