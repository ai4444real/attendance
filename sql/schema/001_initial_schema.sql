-- Rebekko database bootstrap
-- Database target: rebekko
--
-- Primo schema operativo per il dominio attendance.
--
-- Filosofia:
-- - un solo database condiviso (`rebekko`)
-- - tabelle con prefisso di dominio (`attendance_*`)
-- - import batch -> lezioni -> partecipanti -> review actions
-- - niente automazioni "magiche" lato database in questa fase
--
-- Nota:
-- - i campi JSONB servono per conservare rapidamente diagnostica, warning,
--   flag e payload di revisione senza bloccare l'evoluzione del modello.

BEGIN;

CREATE TABLE attendance_import_batches (
    id BIGSERIAL PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_file_name TEXT NOT NULL,
    source_file_path TEXT,
    source_file_sha256 TEXT,
    imported_by TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('draft', 'processing', 'review', 'official', 'archived'))
);

CREATE INDEX attendance_import_batches_status_idx
    ON attendance_import_batches (status);

CREATE INDEX attendance_import_batches_created_at_idx
    ON attendance_import_batches (created_at DESC);


CREATE TABLE attendance_lessons (
    id BIGSERIAL PRIMARY KEY,
    import_batch_id BIGINT NOT NULL REFERENCES attendance_import_batches(id) ON DELETE CASCADE,
    source_system TEXT NOT NULL,
    source_meeting_id TEXT NOT NULL,
    course_name TEXT NOT NULL,
    lesson_date DATE NOT NULL,
    meeting_start_at TIMESTAMPTZ NOT NULL,
    meeting_end_at TIMESTAMPTZ NOT NULL,
    effective_start_at TIMESTAMPTZ NOT NULL,
    break_point_at TIMESTAMPTZ,
    effective_end_at TIMESTAMPTZ NOT NULL,
    threshold_ratio NUMERIC(5,4) NOT NULL DEFAULT 0.8000,
    break_source TEXT NOT NULL DEFAULT 'midpoint',
    effective_start_source TEXT NOT NULL DEFAULT 'default',
    effective_end_source TEXT NOT NULL DEFAULT 'default',
    status TEXT NOT NULL DEFAULT 'draft',
    is_ignored BOOLEAN NOT NULL DEFAULT FALSE,
    warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    diagnostics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT,
    officialized_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (threshold_ratio >= 0.0000 AND threshold_ratio <= 1.0000),
    CHECK (status IN ('draft', 'review', 'official', 'archived')),
    CHECK (meeting_end_at >= meeting_start_at),
    CHECK (effective_end_at >= effective_start_at),
    UNIQUE (import_batch_id, source_meeting_id, course_name, lesson_date)
);

CREATE INDEX attendance_lessons_import_batch_idx
    ON attendance_lessons (import_batch_id);

CREATE INDEX attendance_lessons_course_date_idx
    ON attendance_lessons (course_name, lesson_date);

CREATE INDEX attendance_lessons_status_idx
    ON attendance_lessons (status, is_ignored);


CREATE TABLE attendance_lesson_participants (
    id BIGSERIAL PRIMARY KEY,
    lesson_id BIGINT NOT NULL REFERENCES attendance_lessons(id) ON DELETE CASCADE,
    participant_key TEXT NOT NULL,
    canonical_full_name TEXT NOT NULL,
    raw_full_name TEXT,
    email TEXT,
    external_person_key TEXT,
    segment_count INTEGER NOT NULL DEFAULT 0,
    minutes_first_half NUMERIC(8,2) NOT NULL DEFAULT 0,
    minutes_second_half NUMERIC(8,2) NOT NULL DEFAULT 0,
    duration_first_half NUMERIC(8,2) NOT NULL DEFAULT 0,
    duration_second_half NUMERIC(8,2) NOT NULL DEFAULT 0,
    total_minutes NUMERIC(8,2) NOT NULL DEFAULT 0,
    calculated_presence_status TEXT NOT NULL,
    manual_override_presence_status TEXT,
    final_presence_status TEXT NOT NULL,
    flags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (segment_count >= 0),
    CHECK (minutes_first_half >= 0),
    CHECK (minutes_second_half >= 0),
    CHECK (duration_first_half >= 0),
    CHECK (duration_second_half >= 0),
    CHECK (total_minutes >= 0),
    CHECK (calculated_presence_status IN ('presente', 'prima_meta', 'seconda_meta', 'assente')),
    CHECK (manual_override_presence_status IS NULL OR manual_override_presence_status IN ('presente', 'prima_meta', 'seconda_meta', 'assente')),
    CHECK (final_presence_status IN ('presente', 'prima_meta', 'seconda_meta', 'assente')),
    UNIQUE (lesson_id, participant_key)
);

CREATE INDEX attendance_lesson_participants_lesson_idx
    ON attendance_lesson_participants (lesson_id);

CREATE INDEX attendance_lesson_participants_name_idx
    ON attendance_lesson_participants (canonical_full_name);

CREATE INDEX attendance_lesson_participants_final_status_idx
    ON attendance_lesson_participants (final_presence_status);


CREATE TABLE attendance_review_actions (
    id BIGSERIAL PRIMARY KEY,
    lesson_id BIGINT NOT NULL REFERENCES attendance_lessons(id) ON DELETE CASCADE,
    participant_id BIGINT REFERENCES attendance_lesson_participants(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_at TIMESTAMPTZ,
    is_applied BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT
);

CREATE INDEX attendance_review_actions_lesson_idx
    ON attendance_review_actions (lesson_id, created_at DESC);

CREATE INDEX attendance_review_actions_participant_idx
    ON attendance_review_actions (participant_id);

CREATE INDEX attendance_review_actions_action_type_idx
    ON attendance_review_actions (action_type);

COMMIT;
