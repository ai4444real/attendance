BEGIN;

ALTER TABLE attendance_lesson_participants
    ADD COLUMN presence_source TEXT NOT NULL DEFAULT 'zoom';

ALTER TABLE attendance_lesson_participants
    ADD CONSTRAINT attendance_lesson_participants_presence_source_check
    CHECK (presence_source IN ('zoom', 'manual', 'qr_form', 'csv_manual'));

CREATE INDEX attendance_lesson_participants_presence_source_idx
    ON attendance_lesson_participants (presence_source);

ALTER TABLE attendance_lesson_participants OWNER TO rebekko_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attendance_lesson_participants TO rebekko_app;

COMMIT;
