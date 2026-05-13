BEGIN;

CREATE TABLE attendance_courses (
    course_name TEXT PRIMARY KEY,
    expected_lessons_count INTEGER,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (course_name <> ''),
    CHECK (expected_lessons_count IS NULL OR expected_lessons_count > 0)
);

ALTER TABLE attendance_courses OWNER TO rebekko_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_courses TO rebekko_app;

COMMIT;
