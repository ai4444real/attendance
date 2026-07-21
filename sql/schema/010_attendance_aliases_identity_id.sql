BEGIN;

ALTER TABLE attendance_identity_aliases
    ADD COLUMN IF NOT EXISTS identity_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'attendance_identity_aliases_identity_id_fkey'
    ) THEN
        ALTER TABLE attendance_identity_aliases
            ADD CONSTRAINT attendance_identity_aliases_identity_id_fkey
            FOREIGN KEY (identity_id)
            REFERENCES attendance_identities(id);
    END IF;
END $$;

UPDATE attendance_identity_aliases AS a
SET identity_id = i.id
FROM attendance_identities AS i
WHERE a.identity_id IS NULL
  AND a.is_active = TRUE
  AND i.identity_key = CASE
      WHEN NULLIF(lower(trim(a.canonical_email)), '') IS NOT NULL
          THEN 'email:' || NULLIF(lower(trim(a.canonical_email)), '')
      ELSE 'name:' || lower(regexp_replace(trim(a.canonical_full_name), '\s+', ' ', 'g'))
  END;

CREATE INDEX IF NOT EXISTS attendance_identity_aliases_identity_id_idx
    ON attendance_identity_aliases (identity_id);

ALTER TABLE attendance_identity_aliases OWNER TO rebekko_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_identity_aliases TO rebekko_app;

COMMIT;
