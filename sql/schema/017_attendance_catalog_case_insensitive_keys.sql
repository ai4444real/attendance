BEGIN;

CREATE UNIQUE INDEX attendance_catalog_courses_code_lower_uidx
    ON attendance_catalog_courses (lower(code));

CREATE UNIQUE INDEX attendance_catalog_course_editions_key_lower_uidx
    ON attendance_catalog_course_editions (lower(edition_key));

COMMIT;
