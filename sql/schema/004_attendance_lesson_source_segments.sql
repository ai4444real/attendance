BEGIN;

CREATE TABLE attendance_lesson_source_segments (
    id BIGSERIAL PRIMARY KEY,
    lesson_id BIGINT NOT NULL REFERENCES attendance_lessons(id) ON DELETE CASCADE,
    observed_full_name TEXT NOT NULL,
    observed_email TEXT,
    join_time TIMESTAMPTZ NOT NULL,
    leave_time TIMESTAMPTZ NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (leave_time >= join_time),
    UNIQUE (lesson_id, observed_full_name, observed_email, join_time, leave_time)
);

CREATE INDEX attendance_lesson_source_segments_lesson_idx
    ON attendance_lesson_source_segments (lesson_id, join_time);

ALTER TABLE attendance_lesson_source_segments OWNER TO rebekko_app;
ALTER SEQUENCE attendance_lesson_source_segments_id_seq OWNER TO rebekko_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_lesson_source_segments TO rebekko_app;
GRANT USAGE, SELECT ON SEQUENCE attendance_lesson_source_segments_id_seq TO rebekko_app;

COMMIT;
