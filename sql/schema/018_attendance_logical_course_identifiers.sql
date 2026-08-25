BEGIN;

CREATE TABLE attendance_catalog_logical_course_identifiers (
    id BIGSERIAL PRIMARY KEY,
    course_id BIGINT NOT NULL
        REFERENCES attendance_catalog_courses(id) ON DELETE CASCADE,
    identifier_type TEXT NOT NULL,
    identifier_value TEXT NOT NULL,
    source_system TEXT NOT NULL DEFAULT 'manual',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (course_id, identifier_type, identifier_value),
    CHECK (btrim(identifier_type) <> ''),
    CHECK (btrim(identifier_value) <> '')
);

CREATE INDEX attendance_catalog_logical_identifiers_lookup_idx
    ON attendance_catalog_logical_course_identifiers (identifier_type, identifier_value);

ALTER TABLE attendance_catalog_logical_course_identifiers OWNER TO rebekko_app;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE attendance_catalog_logical_course_identifiers TO rebekko_app;
GRANT USAGE, SELECT
    ON SEQUENCE attendance_catalog_logical_course_identifiers_id_seq TO rebekko_app;

COMMIT;
