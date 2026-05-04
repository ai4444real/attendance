from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timezone

from backend.attendance_app.models import ImportBatch, ImportBatchCreate, PersistedDraftImport
from backend.attendance_app.services import AttendanceImportService
from backend.attendance_normalization.service import (
    MeetingDiagnostic,
    NormalizationResult,
    NormalizedAttendanceRecord,
    TimelinePoint,
)


class FakeAttendanceDraftImportRepository:
    def __init__(self) -> None:
        self.last_batch_data: ImportBatchCreate | None = None
        self.last_lessons = None

    def save_draft_import(self, batch_data, lessons):
        self.last_batch_data = batch_data
        self.last_lessons = lessons
        now = datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc)
        return PersistedDraftImport(
            batch=ImportBatch(
                id=1,
                source_system=batch_data.source_system,
                source_file_name=batch_data.source_file_name,
                source_file_path=batch_data.source_file_path,
                source_file_sha256=batch_data.source_file_sha256,
                imported_by=batch_data.imported_by,
                status="draft",
                notes=batch_data.notes,
                created_at=now,
                updated_at=now,
            ),
            lessons_created=len(lessons),
            participants_created=sum(len(lesson.participants) for lesson in lessons),
        )


class AttendanceImportServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeAttendanceDraftImportRepository()
        self.service = AttendanceImportService(self.repository)
        self.batch = ImportBatchCreate(
            source_system="zoom",
            source_file_name="report-zoom-2026-05.csv",
            source_file_path="attendance/data/report-zoom-2026-05.csv",
            imported_by="simone",
        )
        self.result = NormalizationResult(
            source_path="attendance/data/report-zoom-2026-05.csv",
            threshold=0.8,
            total_meetings_found=1,
            selected_courses=["BIAS"],
            selected_meetings_count=1,
            warnings=[],
            meetings=[
                MeetingDiagnostic(
                    course="BIAS",
                    meeting_id="123",
                    date="2026-05-04",
                    meeting_start="2026-05-04T19:00:00+00:00",
                    meeting_end="2026-05-04T21:00:00+00:00",
                    effective_start="2026-05-04T19:05:00+00:00",
                    break_point="2026-05-04T20:00:00+00:00",
                    effective_end="2026-05-04T20:55:00+00:00",
                    break_source="midpoint",
                    threshold=0.8,
                    trim_start_minutes=5.0,
                    trim_end_minutes=5.0,
                    effective_start_source="auto_suggest",
                    effective_end_source="auto_suggest",
                    suggested_effective_start="2026-05-04T19:05:00+00:00",
                    suggested_effective_end="2026-05-04T20:55:00+00:00",
                    suggestion_confidence="high",
                    participant_count=1,
                    peak_active_count=10,
                    sampled_every_minutes=10.0,
                    timeline=[TimelinePoint(timestamp="2026-05-04T19:00:00+00:00", active_count=10)],
                )
            ],
            records=[
                NormalizedAttendanceRecord(
                    course="BIAS",
                    meeting_id="123",
                    date="2026-05-04",
                    first_name="Mario",
                    last_name="Rossi",
                    email="mario@example.com",
                    calculated_presence_status="presente",
                    minutes_first_half=44.0,
                    minutes_second_half=45.0,
                    duration_first_half=55.0,
                    duration_second_half=55.0,
                    total_minutes=89.0,
                    segment_count=2,
                    break_source="midpoint",
                    effective_start="2026-05-04T19:05:00+00:00",
                    break_point="2026-05-04T20:00:00+00:00",
                    effective_end="2026-05-04T20:55:00+00:00",
                    threshold=0.8,
                    trim_start_minutes=5.0,
                    trim_end_minutes=5.0,
                )
            ],
        )

    def test_persist_normalization_result_builds_lesson_drafts(self) -> None:
        persisted = self.service.persist_normalization_result(self.batch, self.result)

        self.assertEqual(1, persisted.lessons_created)
        self.assertEqual(1, persisted.participants_created)
        self.assertEqual(self.batch, self.repository.last_batch_data)
        self.assertEqual(1, len(self.repository.last_lessons))
        lesson = self.repository.last_lessons[0]
        self.assertEqual("BIAS", lesson.course_name)
        self.assertEqual("123", lesson.source_meeting_id)
        self.assertEqual(1, len(lesson.participants))
        self.assertEqual("Mario Rossi", lesson.participants[0].canonical_full_name)

    def test_persist_normalization_result_rejects_blank_source_system(self) -> None:
        with self.assertRaises(ValueError):
            self.service.persist_normalization_result(replace(self.batch, source_system="   "), self.result)

    def test_persist_normalization_result_rejects_blank_source_file_name(self) -> None:
        with self.assertRaises(ValueError):
            self.service.persist_normalization_result(replace(self.batch, source_file_name="  "), self.result)

    def test_persist_normalization_result_merges_duplicate_participant_keys_in_same_lesson(self) -> None:
        duplicated = replace(
            self.result,
            records=[
                self.result.records[0],
                replace(
                    self.result.records[0],
                    first_name="Mario Andrea",
                    minutes_first_half=1.0,
                    minutes_second_half=0.5,
                    total_minutes=1.5,
                    segment_count=1,
                ),
            ],
        )

        persisted = self.service.persist_normalization_result(self.batch, duplicated)

        self.assertEqual(1, persisted.lessons_created)
        self.assertEqual(1, persisted.participants_created)
        lesson = self.repository.last_lessons[0]
        self.assertEqual(1, len(lesson.participants))
        participant = lesson.participants[0]
        self.assertEqual("mario@example.com", participant.participant_key)
        self.assertEqual("Mario Andrea Rossi", participant.canonical_full_name)
        self.assertEqual(45.0, participant.minutes_first_half)
        self.assertEqual(45.5, participant.minutes_second_half)
        self.assertEqual(90.5, participant.total_minutes)
        self.assertEqual(3, participant.segment_count)
        self.assertEqual("presente", participant.final_presence_status)
        self.assertTrue(participant.metadata["merged_duplicate_participant_key"])


if __name__ == "__main__":
    unittest.main()
