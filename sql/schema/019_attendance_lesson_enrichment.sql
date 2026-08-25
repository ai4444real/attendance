BEGIN;

ALTER TABLE attendance_lessons
    ADD COLUMN catalog_course_edition_id BIGINT
        REFERENCES attendance_catalog_course_editions(id) ON DELETE SET NULL,
    ADD COLUMN external_lesson_id TEXT,
    ADD COLUMN topic TEXT,
    ADD COLUMN topic_source TEXT,
    ADD COLUMN planned_event_title TEXT,
    ADD COLUMN planned_home_recipient_key TEXT,
    ADD COLUMN planned_recipients_json JSONB,
    ADD COLUMN planned_start_time TIME,
    ADD COLUMN planned_end_time TIME,
    ADD COLUMN planned_drive_url TEXT,
    ADD COLUMN planned_zoom_url TEXT,
    ADD COLUMN planned_source_row_number INTEGER,
    ADD COLUMN planned_source_hash TEXT,
    ADD COLUMN planned_match_method TEXT,
    ADD COLUMN planned_synced_at TIMESTAMPTZ;

CREATE INDEX attendance_lessons_external_lesson_id_idx
    ON attendance_lessons (external_lesson_id)
    WHERE external_lesson_id IS NOT NULL;

CREATE INDEX attendance_lessons_catalog_edition_idx
    ON attendance_lessons (catalog_course_edition_id)
    WHERE catalog_course_edition_id IS NOT NULL;

ALTER TABLE attendance_lessons
    ADD CONSTRAINT attendance_lessons_topic_source_check
        CHECK (topic_source IS NULL OR topic_source IN ('google_sheets', 'manual')),
    ADD CONSTRAINT attendance_lessons_planned_source_row_check
        CHECK (planned_source_row_number IS NULL OR planned_source_row_number > 0);

COMMIT;
