BEGIN;

CREATE TABLE attendance_identities (
    identity_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    email TEXT,
    CHECK (identity_key <> ''),
    CHECK (display_name <> '')
);

CREATE INDEX attendance_identities_display_name_idx
    ON attendance_identities (display_name);

CREATE INDEX attendance_identities_email_idx
    ON attendance_identities (email);

ALTER TABLE attendance_identities OWNER TO rebekko_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_identities TO rebekko_app;

COMMIT;
