BEGIN;

CREATE SEQUENCE IF NOT EXISTS attendance_identities_id_seq;

ALTER TABLE attendance_identities
    ADD COLUMN IF NOT EXISTS id BIGINT;

UPDATE attendance_identities
SET id = nextval('attendance_identities_id_seq')
WHERE id IS NULL;

ALTER TABLE attendance_identities
    ALTER COLUMN id SET DEFAULT nextval('attendance_identities_id_seq'),
    ALTER COLUMN id SET NOT NULL;

ALTER SEQUENCE attendance_identities_id_seq
    OWNED BY attendance_identities.id;

ALTER TABLE attendance_identities
    DROP CONSTRAINT IF EXISTS attendance_identities_pkey;

ALTER TABLE attendance_identities
    ADD CONSTRAINT attendance_identities_pkey PRIMARY KEY (id);

CREATE UNIQUE INDEX IF NOT EXISTS attendance_identities_identity_key_idx
    ON attendance_identities (identity_key);

ALTER TABLE attendance_identities OWNER TO rebekko_app;
ALTER SEQUENCE attendance_identities_id_seq OWNER TO rebekko_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_identities TO rebekko_app;
GRANT USAGE, SELECT ON SEQUENCE attendance_identities_id_seq TO rebekko_app;

COMMIT;
