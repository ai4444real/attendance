BEGIN;

CREATE TABLE attendance_catalog_courses (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (btrim(code) <> ''),
    CHECK (btrim(display_name) <> '')
);

CREATE TABLE attendance_catalog_course_editions (
    id BIGSERIAL PRIMARY KEY,
    course_id BIGINT REFERENCES attendance_catalog_courses(id) ON DELETE SET NULL,
    edition_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    source_system TEXT,
    source_row_number INTEGER,
    source_hash TEXT,
    last_imported_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (btrim(edition_key) <> ''),
    CHECK (btrim(display_name) <> ''),
    CHECK (source_row_number IS NULL OR source_row_number > 0)
);

CREATE INDEX attendance_catalog_course_editions_course_idx
    ON attendance_catalog_course_editions (course_id);

CREATE TABLE attendance_catalog_course_identifiers (
    id BIGSERIAL PRIMARY KEY,
    course_edition_id BIGINT NOT NULL
        REFERENCES attendance_catalog_course_editions(id) ON DELETE CASCADE,
    identifier_type TEXT NOT NULL,
    identifier_value TEXT NOT NULL,
    source_system TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (course_edition_id, identifier_type, identifier_value),
    CHECK (btrim(identifier_type) <> ''),
    CHECK (btrim(identifier_value) <> '')
);

CREATE INDEX attendance_catalog_course_identifiers_lookup_idx
    ON attendance_catalog_course_identifiers (identifier_type, identifier_value);

ALTER TABLE attendance_catalog_courses OWNER TO rebekko_app;
ALTER TABLE attendance_catalog_course_editions OWNER TO rebekko_app;
ALTER TABLE attendance_catalog_course_identifiers OWNER TO rebekko_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_catalog_courses TO rebekko_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_catalog_course_editions TO rebekko_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_catalog_course_identifiers TO rebekko_app;
GRANT USAGE, SELECT ON SEQUENCE attendance_catalog_courses_id_seq TO rebekko_app;
GRANT USAGE, SELECT ON SEQUENCE attendance_catalog_course_editions_id_seq TO rebekko_app;
GRANT USAGE, SELECT ON SEQUENCE attendance_catalog_course_identifiers_id_seq TO rebekko_app;

COMMIT;
