-- Attendance admin/debug queries
-- Database target: rebekko
--
-- Esempio d'uso:
--   sudo -u postgres psql -d rebekko -f sql/queries/attendance_admin_queries.sql
--
-- Oppure copia/incolla una query singola in psql.


-- 1. Ultimi import batch
SELECT
    id,
    source_system,
    source_file_name,
    status,
    imported_by,
    created_at,
    updated_at
FROM attendance_import_batches
ORDER BY created_at DESC
LIMIT 20;


-- 2. Ultime lezioni importate
SELECT
    l.id,
    l.import_batch_id,
    l.course_name,
    l.lesson_date,
    l.source_meeting_id,
    l.status,
    l.is_ignored,
    l.threshold_ratio,
    l.effective_start_at,
    l.break_point_at,
    l.effective_end_at,
    l.created_at
FROM attendance_lessons AS l
ORDER BY l.created_at DESC
LIMIT 30;


-- 3. Conteggio partecipanti per lezione
SELECT
    l.id AS lesson_id,
    l.course_name,
    l.lesson_date,
    COUNT(p.id) AS participant_count,
    COUNT(*) FILTER (WHERE p.final_presence_status = 'presente') AS presenti,
    COUNT(*) FILTER (WHERE p.final_presence_status = 'prima_meta') AS prima_meta,
    COUNT(*) FILTER (WHERE p.final_presence_status = 'seconda_meta') AS seconda_meta,
    COUNT(*) FILTER (WHERE p.final_presence_status = 'assente') AS assenti
FROM attendance_lessons AS l
LEFT JOIN attendance_lesson_participants AS p
    ON p.lesson_id = l.id
GROUP BY l.id, l.course_name, l.lesson_date
ORDER BY l.lesson_date DESC, l.course_name ASC
LIMIT 30;


-- 4. Partecipanti di una lezione specifica
-- Sostituisci 123 con il vero lesson_id.
SELECT
    p.id,
    p.lesson_id,
    p.canonical_full_name,
    p.email,
    p.segment_count,
    p.minutes_first_half,
    p.minutes_second_half,
    p.duration_first_half,
    p.duration_second_half,
    p.calculated_presence_status,
    p.manual_override_presence_status,
    p.final_presence_status,
    p.flags_json
FROM attendance_lesson_participants AS p
WHERE p.lesson_id = 123
ORDER BY p.canonical_full_name ASC;


-- 5. Review actions recenti
SELECT
    ra.id,
    ra.lesson_id,
    ra.participant_id,
    ra.action_type,
    ra.is_applied,
    ra.created_by,
    ra.created_at,
    ra.applied_at
FROM attendance_review_actions AS ra
ORDER BY ra.created_at DESC
LIMIT 30;
