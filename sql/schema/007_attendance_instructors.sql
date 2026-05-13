BEGIN;

CREATE TABLE attendance_instructors (
    id BIGSERIAL PRIMARY KEY,
    instructor_name TEXT NOT NULL,
    alias_of_id BIGINT REFERENCES attendance_instructors(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (instructor_name <> ''),
    CHECK (alias_of_id IS NULL OR alias_of_id <> id)
);

CREATE UNIQUE INDEX attendance_instructors_name_key
    ON attendance_instructors (lower(instructor_name));

CREATE INDEX attendance_instructors_alias_of_id_idx
    ON attendance_instructors (alias_of_id);

ALTER TABLE attendance_instructors OWNER TO rebekko_app;
ALTER SEQUENCE attendance_instructors_id_seq OWNER TO rebekko_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_instructors TO rebekko_app;
GRANT USAGE, SELECT ON SEQUENCE attendance_instructors_id_seq TO rebekko_app;

COMMIT;
