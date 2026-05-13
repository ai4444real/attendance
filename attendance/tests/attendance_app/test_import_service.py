from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timezone

from backend.attendance_app.models import (
    AttendanceIdentityAlias,
    DraftLessonSourceSegment,
    DraftLessonParticipantView,
    DraftLessonView,
    DraftReviewActionView,
    ImportBatch,
    ImportBatchCreate,
    ImportedLessonSummary,
    ManualPresenceImportResult,
    PersistedDraftImport,
    SkippedDuplicateLesson,
)
from backend.attendance_app.services import (
    AttendanceCourseConfigService,
    AttendanceDraftRecalculationService,
    AttendanceLessonIdentityRebuildService,
    AttendanceIdentityAliasService,
    AttendanceImportService,
    AttendanceLessonStateService,
    AttendanceManualPresenceService,
    AttendanceReviewActionService,
)
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
            imported_lessons=[
                ImportedLessonSummary(
                    course_name=lesson.course_name,
                    source_meeting_id=lesson.source_meeting_id,
                    lesson_date=lesson.lesson_date,
                )
                for lesson in lessons
            ],
            duplicate_lessons_skipped=0,
            skipped_duplicates=[],
        )


class FakeAttendanceReviewActionRepository:
    def __init__(self) -> None:
        self.calls = []

    def create_lesson_review_action(self, lesson_id, action_type, payload, **kwargs):
        self.calls.append((lesson_id, action_type, payload, kwargs))
        return DraftReviewActionView(
            id=99,
            lesson_id=lesson_id,
            participant_id=None,
            action_type=action_type,
            payload=payload,
            created_by=kwargs.get("created_by"),
            created_at="2026-05-04T12:00:00+00:00",
            applied_at=None,
            is_applied=False,
            notes=kwargs.get("notes"),
        )


class FakeAttendanceDraftQueryRepository:
    def __init__(self, lesson: DraftLessonView) -> None:
        self.lesson = lesson
        self.source_segments: list[DraftLessonSourceSegment] = []

    def get_lesson_detail(self, lesson_id: int) -> DraftLessonView:
        return self.lesson

    def get_lesson_source_segments(self, lesson_id: int) -> list[DraftLessonSourceSegment]:
        return list(self.source_segments)


class FakeAttendanceDraftMutationRepository:
    def __init__(self) -> None:
        self.last_update = None
        self.ignored_calls = []
        self.status_calls = []
        self.last_identity_rebuild = None
        self.source_segments_inserted = []
        self.deleted_lessons = []
        self.deleted_batches = []
        self.course_expected_lessons = []
        self.manual_imports = []

    def update_lesson_after_recalculation(self, lesson, **kwargs) -> None:
        self.last_update = kwargs

    def set_lesson_ignored(self, lesson_id: int, *, is_ignored: bool) -> None:
        self.ignored_calls.append((lesson_id, is_ignored))

    def set_lesson_status(self, lesson_id: int, *, status: str) -> None:
        self.status_calls.append((lesson_id, status))

    def replace_lesson_participants_after_identity_rebuild(self, lesson_id: int, *, diagnostics: dict, participants: list[dict]) -> None:
        self.last_identity_rebuild = {
            "lesson_id": lesson_id,
            "diagnostics": diagnostics,
            "participants": participants,
        }

    def ensure_lesson_source_segments(self, lesson_id: int, source_segments: list[DraftLessonSourceSegment]) -> int:
        self.source_segments_inserted.append((lesson_id, list(source_segments)))
        return len(source_segments)

    def delete_lesson(self, lesson_id: int) -> None:
        self.deleted_lessons.append(lesson_id)

    def delete_batch(self, batch_id: int) -> None:
        self.deleted_batches.append(batch_id)

    def upsert_course_expected_lessons(self, course_name: str, expected_lessons_count: int | None) -> None:
        self.course_expected_lessons.append((course_name, expected_lessons_count))

    def upsert_manual_presence_import(self, import_data):
        self.manual_imports.append(import_data)
        return ManualPresenceImportResult(
            lesson_id=77,
            course_name=import_data.course_name,
            lesson_date=import_data.lesson_date,
            records_processed=len(import_data.records),
            participants_upserted=len(import_data.records),
        )


class AttendanceImportServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeAttendanceDraftImportRepository()
        self.alias_repository = FakeAttendanceIdentityAliasRepository()
        self.service = AttendanceImportService(self.repository, self.alias_repository)
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

    def test_persist_normalization_result_applies_identity_aliases_from_repository(self) -> None:
        self.alias_repository.aliases = [
            AttendanceIdentityAlias(
                id=1,
                canonical_full_name="Mario Rossi",
                canonical_email=None,
                alias_value="Mario R. Rossi",
                alias_type="full_name",
                created_by="test",
                created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
                is_active=True,
                notes=None,
            )
        ]
        aliased = replace(
            self.result,
            records=[
                replace(
                    self.result.records[0],
                    first_name="Mario",
                    last_name="R. Rossi",
                    email="",
                )
            ],
        )

        persisted = self.service.persist_normalization_result(self.batch, aliased)

        self.assertEqual(1, persisted.participants_created)
        participant = self.repository.last_lessons[0].participants[0]
        self.assertEqual("Mario Rossi", participant.canonical_full_name)
        self.assertEqual("mario rossi", participant.participant_key)

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

    def test_import_result_can_represent_no_batch_when_everything_is_skipped(self) -> None:
        persisted = PersistedDraftImport(
            batch=None,
            lessons_created=0,
            participants_created=0,
            imported_lessons=[],
            duplicate_lessons_skipped=3,
            skipped_duplicates=[
                SkippedDuplicateLesson(
                    course_name="PRACTITIONER",
                    source_meeting_id="891 9285 7355",
                    lesson_date="2026-01-28",
                    existing_lesson_id=147,
                    existing_batch_id=9,
                )
            ],
        )

        self.assertIsNone(persisted.batch)
        self.assertEqual(0, persisted.lessons_created)
        self.assertEqual(3, persisted.duplicate_lessons_skipped)


class AttendanceReviewActionServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeAttendanceReviewActionRepository()
        self.service = AttendanceReviewActionService(self.repository)

    def test_create_lesson_review_action_accepts_threshold_action(self) -> None:
        action = self.service.create_lesson_review_action(
            12,
            "set_threshold_ratio",
            {"threshold_ratio": 0.75},
            created_by="test-ui",
        )

        self.assertEqual("set_threshold_ratio", action.action_type)
        self.assertEqual(1, len(self.repository.calls))

    def test_create_lesson_review_action_rejects_unknown_action(self) -> None:
        with self.assertRaises(ValueError):
            self.service.create_lesson_review_action(12, "explode_lesson", {"foo": "bar"})

    def test_create_lesson_review_action_accepts_manual_presence_override(self) -> None:
        action = self.service.create_lesson_review_action(
            12,
            "set_manual_presence_status",
            {"presence_status": "presente"},
            participant_id=44,
        )

        self.assertEqual("set_manual_presence_status", action.action_type)
        self.assertEqual(1, len(self.repository.calls))


class AttendanceDraftRecalculationServiceTest(unittest.TestCase):
    def test_recalculate_lesson_accepts_naive_segment_datetimes_with_aware_markers(self) -> None:
        lesson = DraftLessonView(
            id=50,
            course_name="MASTER",
            lesson_date="2026-02-09",
            source_meeting_id="886 5440 3922",
            status="draft",
            is_ignored=False,
            threshold_ratio=0.8,
            meeting_start_at="2026-02-09T19:54:00+00:00",
            meeting_end_at="2026-02-09T23:06:00+00:00",
            effective_start_at="2026-02-09T20:00:00+00:00",
            break_point_at="2026-02-09T21:33:00+00:00",
            effective_end_at="2026-02-09T23:06:00+00:00",
            break_source="midpoint",
            effective_start_source="snap",
            effective_end_source="meeting_end",
            warnings=[],
            diagnostics={},
            summary={"presente": 1, "prima_meta": 0, "seconda_meta": 0, "assente": 0},
            participants=[
                DraftLessonParticipantView(
                    id=1,
                    participant_key="mario@example.com",
                    canonical_full_name="Mario Rossi",
                    raw_full_name="Mario Rossi",
                    email="mario@example.com",
                    segment_count=1,
                    minutes_first_half=0.0,
                    minutes_second_half=0.0,
                    duration_first_half=0.0,
                    duration_second_half=0.0,
                    total_minutes=0.0,
                    calculated_presence_status="assente",
                    manual_override_presence_status=None,
                    final_presence_status="assente",
                    presence_source="zoom",
                    flags=[],
                    metadata={
                        "first_name": "Mario",
                        "last_name": "Rossi",
                        "segments": [["2026-02-09T20:00:00", "2026-02-09T22:40:00"]],
                    },
                )
            ],
            review_actions=[],
        )
        query = FakeAttendanceDraftQueryRepository(lesson)
        mutation = FakeAttendanceDraftMutationRepository()
        service = AttendanceDraftRecalculationService(query, mutation)

        service.recalculate_lesson(50)

        self.assertIsNotNone(mutation.last_update)
        self.assertEqual(1, len(mutation.last_update["participants"]))

    def test_recalculate_lesson_applies_latest_manual_presence_override(self) -> None:
        lesson = DraftLessonView(
            id=51,
            course_name="MASTER",
            lesson_date="2026-02-09",
            source_meeting_id="886 5440 3922",
            status="draft",
            is_ignored=False,
            threshold_ratio=0.8,
            meeting_start_at="2026-02-09T19:54:00+00:00",
            meeting_end_at="2026-02-09T23:06:00+00:00",
            effective_start_at="2026-02-09T20:00:00+00:00",
            break_point_at="2026-02-09T21:33:00+00:00",
            effective_end_at="2026-02-09T23:06:00+00:00",
            break_source="midpoint",
            effective_start_source="snap",
            effective_end_source="meeting_end",
            warnings=[],
            diagnostics={},
            summary={"presente": 0, "prima_meta": 1, "seconda_meta": 0, "assente": 0},
            participants=[
                DraftLessonParticipantView(
                    id=2,
                    participant_key="mario@example.com",
                    canonical_full_name="Mario Rossi",
                    raw_full_name="Mario Rossi",
                    email="mario@example.com",
                    segment_count=1,
                    minutes_first_half=40.0,
                    minutes_second_half=20.0,
                    duration_first_half=50.0,
                    duration_second_half=50.0,
                    total_minutes=60.0,
                    calculated_presence_status="prima_meta",
                    manual_override_presence_status=None,
                    final_presence_status="prima_meta",
                    presence_source="zoom",
                    flags=[],
                    metadata={"segments": []},
                )
            ],
            review_actions=[
                DraftReviewActionView(
                    id=1,
                    lesson_id=51,
                    participant_id=2,
                    action_type="set_manual_presence_status",
                    payload={"presence_status": "presente"},
                    created_by="test",
                    created_at="2026-05-05T10:00:00+00:00",
                    applied_at=None,
                    is_applied=False,
                    notes=None,
                )
            ],
        )
        query = FakeAttendanceDraftQueryRepository(lesson)
        mutation = FakeAttendanceDraftMutationRepository()
        service = AttendanceDraftRecalculationService(query, mutation)

        service.recalculate_lesson(51)

        participant_update = mutation.last_update["participants"][0]
        self.assertEqual("presente", participant_update["manual_override_presence_status"])
        self.assertEqual("presente", participant_update["final_presence_status"])

    def test_recalculate_lesson_applies_identity_aliases_to_source_segments(self) -> None:
        lesson = DraftLessonView(
            id=52,
            course_name="PRACTITIONER",
            lesson_date="2026-01-28",
            source_meeting_id="891 9285 7355",
            status="draft",
            is_ignored=False,
            threshold_ratio=0.8,
            meeting_start_at="2026-01-28T19:25:00+00:00",
            meeting_end_at="2026-01-28T23:47:00+00:00",
            effective_start_at="2026-01-28T20:04:00+00:00",
            break_point_at="2026-01-28T20:59:00+00:00",
            effective_end_at="2026-01-28T21:54:00+00:00",
            break_source="midpoint",
            effective_start_source="snap",
            effective_end_source="meeting_end",
            warnings=[],
            diagnostics={},
            summary={"presente": 0, "prima_meta": 0, "seconda_meta": 1, "assente": 0},
            participants=[
                DraftLessonParticipantView(
                    id=21,
                    participant_key="apfacchi@gmail.com",
                    canonical_full_name="Andrea Facchi",
                    raw_full_name="Andrea Facchi",
                    email="apfacchi@gmail.com",
                    segment_count=2,
                    minutes_first_half=13.0,
                    minutes_second_half=55.0,
                    duration_first_half=55.0,
                    duration_second_half=55.0,
                    total_minutes=68.0,
                    calculated_presence_status="seconda_meta",
                    manual_override_presence_status=None,
                    final_presence_status="seconda_meta",
                    presence_source="zoom",
                    flags=[],
                    metadata={
                        "identity_sources": [
                            {
                                "raw_full_name": "Andrea Facchi",
                                "email": "apfacchi@gmail.cim",
                                "segments": [["2026-01-28T20:19:00+00:00", "2026-01-28T21:25:00+00:00"]],
                            },
                            {
                                "raw_full_name": "Andrea Facchi",
                                "email": "apfacchi@gmail.com",
                                "segments": [["2026-01-28T21:25:00+00:00", "2026-01-28T23:13:00+00:00"]],
                            },
                        ],
                        "segments": [["2026-01-28T20:19:00+00:00", "2026-01-28T21:54:00+00:00"]],
                    },
                )
            ],
            review_actions=[],
        )
        query = FakeAttendanceDraftQueryRepository(lesson)
        query.source_segments = [
            DraftLessonSourceSegment(
                observed_full_name="Andrea Facchi",
                observed_email="apfacchi@gmail.cim",
                join_time="2026-01-28T20:19:00+00:00",
                leave_time="2026-01-28T21:25:00+00:00",
                metadata={},
            ),
            DraftLessonSourceSegment(
                observed_full_name="Andrea Facchi",
                observed_email="apfacchi@gmail.com",
                join_time="2026-01-28T21:25:00+00:00",
                leave_time="2026-01-28T23:13:00+00:00",
                metadata={},
            ),
        ]
        mutation = FakeAttendanceDraftMutationRepository()
        alias_repo = FakeAttendanceIdentityAliasRepository()
        alias_repo.aliases = [
            AttendanceIdentityAlias(
                id=2,
                canonical_full_name="Andrea Facchi",
                canonical_email="apfacchi@gmail.com",
                alias_value="apfacchi@gmail.cim",
                alias_type="email",
                created_by="test",
                created_at=datetime(2026, 5, 6, 9, 0, tzinfo=timezone.utc),
                is_active=True,
                notes=None,
            )
        ]
        service = AttendanceDraftRecalculationService(query, mutation, alias_repo)

        service.recalculate_lesson(52)

        participant_update = mutation.last_update["participants"][0]
        self.assertEqual(40.0, participant_update["minutes_first_half"])
        self.assertEqual(55.0, participant_update["minutes_second_half"])
        self.assertEqual(55.0, participant_update["duration_first_half"])
        self.assertEqual(55.0, participant_update["duration_second_half"])
        self.assertEqual("seconda_meta", participant_update["calculated_presence_status"])


class AttendanceLessonIdentityRebuildServiceTest(unittest.TestCase):
    def test_rebuild_lesson_with_current_aliases_merges_duplicate_identity_rows(self) -> None:
        lesson = DraftLessonView(
            id=128,
            course_name="PRACTITIONER",
            lesson_date="2026-01-28",
            source_meeting_id="891 9285 7355",
            status="draft",
            is_ignored=False,
            threshold_ratio=0.8,
            meeting_start_at="2026-01-28T19:25:00+00:00",
            meeting_end_at="2026-01-28T23:47:00+00:00",
            effective_start_at="2026-01-28T20:04:00+00:00",
            break_point_at="2026-01-28T20:59:00+00:00",
            effective_end_at="2026-01-28T21:54:00+00:00",
            break_source="midpoint",
            effective_start_source="snap",
            effective_end_source="meeting_end",
            warnings=[],
            diagnostics={},
            summary={"presente": 0, "prima_meta": 0, "seconda_meta": 0, "assente": 2},
            participants=[
                DraftLessonParticipantView(
                    id=11,
                    participant_key="apfacchi@gmail.cim",
                    canonical_full_name="Andrea Facchi",
                    raw_full_name="Andrea Facchi",
                    email="apfacchi@gmail.cim",
                    segment_count=1,
                    minutes_first_half=39.0,
                    minutes_second_half=26.0,
                    duration_first_half=55.0,
                    duration_second_half=55.0,
                    total_minutes=65.0,
                    calculated_presence_status="assente",
                    manual_override_presence_status=None,
                    final_presence_status="assente",
                    presence_source="zoom",
                    flags=[],
                    metadata={
                        "segments": [["2026-01-28T20:15:00", "2026-01-28T21:30:00"]],
                    },
                ),
                DraftLessonParticipantView(
                    id=12,
                    participant_key="apfacchi@gmail.com",
                    canonical_full_name="Andrea Facchi",
                    raw_full_name="Andrea Facchi",
                    email="apfacchi@gmail.com",
                    segment_count=1,
                    minutes_first_half=0.0,
                    minutes_second_half=29.0,
                    duration_first_half=55.0,
                    duration_second_half=55.0,
                    total_minutes=29.0,
                    calculated_presence_status="assente",
                    manual_override_presence_status=None,
                    final_presence_status="assente",
                    presence_source="zoom",
                    flags=[],
                    metadata={
                        "segments": [["2026-01-28T21:25:00", "2026-01-28T21:54:00"]],
                    },
                ),
            ],
            review_actions=[],
        )
        query = FakeAttendanceDraftQueryRepository(lesson)
        mutation = FakeAttendanceDraftMutationRepository()
        alias_repo = FakeAttendanceIdentityAliasRepository()
        alias_repo.aliases = [
            AttendanceIdentityAlias(
                id=1,
                canonical_full_name="Andrea Facchi",
                canonical_email="apfacchi@gmail.com",
                alias_value="apfacchi@gmail.cim",
                alias_type="email",
                created_by="test",
                created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
                is_active=True,
                notes=None,
            )
        ]
        service = AttendanceLessonIdentityRebuildService(query, mutation, alias_repo)

        service.rebuild_lesson_with_current_aliases(128)

        self.assertIsNotNone(mutation.last_identity_rebuild)
        participants = mutation.last_identity_rebuild["participants"]
        self.assertEqual(1, len(participants))
        self.assertEqual(11, participants[0]["survivor_id"])
        self.assertEqual([12], participants[0]["obsolete_ids"])
        self.assertEqual("apfacchi@gmail.com", participants[0]["participant_key"])


class AttendanceLessonStateServiceTest(unittest.TestCase):
    def test_set_lesson_ignored_delegates_to_repository(self) -> None:
        mutation = FakeAttendanceDraftMutationRepository()
        service = AttendanceLessonStateService(mutation)

        service.set_lesson_ignored(12, is_ignored=True)

        self.assertEqual([(12, True)], mutation.ignored_calls)

    def test_set_lesson_status_rejects_unknown_status(self) -> None:
        mutation = FakeAttendanceDraftMutationRepository()
        service = AttendanceLessonStateService(mutation)

        with self.assertRaises(ValueError):
            service.set_lesson_status(12, status="processing")

    def test_delete_lesson_delegates_to_repository(self) -> None:
        mutation = FakeAttendanceDraftMutationRepository()
        service = AttendanceLessonStateService(mutation)

        service.delete_lesson(33)

        self.assertEqual([33], mutation.deleted_lessons)

    def test_delete_batch_delegates_to_repository(self) -> None:
        mutation = FakeAttendanceDraftMutationRepository()
        service = AttendanceLessonStateService(mutation)

        service.delete_batch(10)

        self.assertEqual([10], mutation.deleted_batches)


class AttendanceCourseConfigServiceTest(unittest.TestCase):
    def test_set_expected_lessons_count_delegates_to_repository(self) -> None:
        mutation = FakeAttendanceDraftMutationRepository()
        service = AttendanceCourseConfigService(mutation)

        service.set_expected_lessons_count(" Practitioner ", 32)

        self.assertEqual([("Practitioner", 32)], mutation.course_expected_lessons)

    def test_set_expected_lessons_count_accepts_none_for_fallback(self) -> None:
        mutation = FakeAttendanceDraftMutationRepository()
        service = AttendanceCourseConfigService(mutation)

        service.set_expected_lessons_count("Practitioner", None)

        self.assertEqual([("Practitioner", None)], mutation.course_expected_lessons)


class FakeAttendanceIdentityAliasRepository:
    def __init__(self) -> None:
        self.aliases: list[AttendanceIdentityAlias] = []
        self.last_created = None

    def list_active_aliases(self) -> list[AttendanceIdentityAlias]:
        return list(self.aliases)

    def create_alias(self, **kwargs) -> AttendanceIdentityAlias:
        self.last_created = kwargs
        return AttendanceIdentityAlias(
            id=10,
            canonical_full_name=kwargs["canonical_full_name"],
            canonical_email=kwargs.get("canonical_email"),
            alias_value=kwargs["alias_value"],
            alias_type=kwargs.get("alias_type", "full_name"),
            created_by=kwargs.get("created_by"),
            created_at=datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc),
            is_active=True,
            notes=kwargs.get("notes"),
        )


class AttendanceManualPresenceServiceTest(unittest.TestCase):
    def test_import_manual_presence_canonicalizes_and_delegates(self) -> None:
        mutation = FakeAttendanceDraftMutationRepository()
        aliases = FakeAttendanceIdentityAliasRepository()
        aliases.aliases = [
            AttendanceIdentityAlias(
                id=1,
                canonical_full_name="Mario Rossi",
                canonical_email="mario@example.com",
                alias_value="Mario R.",
                alias_type="full_name",
                created_by="test",
                created_at=datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc),
                is_active=True,
                notes=None,
            )
        ]
        service = AttendanceManualPresenceService(mutation, aliases)

        result = service.import_manual_presence(
            course_name=" Practitioner ",
            lesson_date="2026-05-13",
            presence_source="manual",
            created_by="test-ui",
            records=[
                {"full_name": "Mario R.", "presence_status": "presente"},
                {"full_name": "Mario Rossi", "email": "mario@example.com", "presence_status": "presente"},
            ],
        )

        self.assertEqual(77, result.lesson_id)
        self.assertEqual(1, result.records_processed)
        saved = mutation.manual_imports[0]
        self.assertEqual("Practitioner", saved.course_name)
        self.assertEqual("manual", saved.presence_source)
        self.assertEqual("Mario Rossi", saved.records[0].full_name)
        self.assertEqual("mario@example.com", saved.records[0].email)
        self.assertEqual("presente", saved.records[0].presence_status)

    def test_import_manual_presence_accepts_existing_lesson_without_course_or_date(self) -> None:
        mutation = FakeAttendanceDraftMutationRepository()
        service = AttendanceManualPresenceService(mutation)

        service.import_manual_presence(
            lesson_id=123,
            course_name="",
            lesson_date="",
            records=[{"full_name": "Mario Rossi", "presence_status": "presente"}],
        )

        saved = mutation.manual_imports[0]
        self.assertEqual(123, saved.lesson_id)
        self.assertEqual("", saved.course_name)
        self.assertEqual("", saved.lesson_date)

    def test_import_manual_presence_rejects_unknown_status(self) -> None:
        mutation = FakeAttendanceDraftMutationRepository()
        service = AttendanceManualPresenceService(mutation)

        with self.assertRaises(ValueError):
            service.import_manual_presence(
                course_name="Practitioner",
                lesson_date="2026-05-13",
                records=[{"full_name": "Mario Rossi", "presence_status": "forse"}],
            )


class AttendanceIdentityAliasServiceTest(unittest.TestCase):
    def test_create_alias_trims_and_delegates(self) -> None:
        repository = FakeAttendanceIdentityAliasRepository()
        service = AttendanceIdentityAliasService(repository)

        alias = service.create_alias(
            canonical_full_name=" Mario Rossi ",
            alias_value=" Mario R. Rossi ",
            created_by="drafts-ui",
        )

        self.assertEqual("Mario Rossi", alias.canonical_full_name)
        self.assertEqual("Mario R. Rossi", alias.alias_value)
        self.assertEqual("Mario Rossi", repository.last_created["canonical_full_name"])

    def test_create_alias_rejects_same_identity(self) -> None:
        repository = FakeAttendanceIdentityAliasRepository()
        service = AttendanceIdentityAliasService(repository)

        with self.assertRaises(ValueError):
            service.create_alias(
                canonical_full_name="Mario Rossi",
                alias_value="mario rossi",
            )

    def test_bootstrap_from_legacy_rules_imports_all_aliases(self) -> None:
        repository = FakeAttendanceIdentityAliasRepository()
        service = AttendanceIdentityAliasService(repository)

        created = service.bootstrap_from_legacy_rules("attendance/config/identity_rules.json")

        self.assertEqual(8, created)


if __name__ == "__main__":
    unittest.main()
