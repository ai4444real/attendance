"""Application-layer models for attendance workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class ImportBatchCreate:
    source_system: str
    source_file_name: str
    source_file_path: Optional[str] = None
    source_file_sha256: Optional[str] = None
    imported_by: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class ImportBatch:
    id: int
    source_system: str
    source_file_name: str
    source_file_path: Optional[str]
    source_file_sha256: Optional[str]
    imported_by: Optional[str]
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LessonParticipantDraft:
    participant_key: str
    canonical_full_name: str
    raw_full_name: Optional[str]
    email: Optional[str]
    segment_count: int
    minutes_first_half: float
    minutes_second_half: float
    duration_first_half: float
    duration_second_half: float
    total_minutes: float
    calculated_presence_status: str
    final_presence_status: str
    flags: list[str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class LessonDraft:
    source_system: str
    source_meeting_id: str
    course_name: str
    lesson_date: str
    meeting_start_at: str
    meeting_end_at: str
    effective_start_at: str
    break_point_at: Optional[str]
    effective_end_at: str
    threshold_ratio: float
    break_source: str
    effective_start_source: str
    effective_end_source: str
    warnings: list[str]
    diagnostics: dict[str, Any]
    participants: list[LessonParticipantDraft]


@dataclass(frozen=True)
class SkippedDuplicateLesson:
    course_name: str
    source_meeting_id: str
    lesson_date: str
    existing_lesson_id: int
    existing_batch_id: int


@dataclass(frozen=True)
class ImportedLessonSummary:
    course_name: str
    source_meeting_id: str
    lesson_date: str


@dataclass(frozen=True)
class PersistedDraftImport:
    batch: ImportBatch | None
    lessons_created: int
    participants_created: int
    imported_lessons: list[ImportedLessonSummary] | None = None
    duplicate_lessons_skipped: int = 0
    skipped_duplicates: list[SkippedDuplicateLesson] | None = None


@dataclass(frozen=True)
class SplitLessonResult:
    original_lesson_id: int
    first_lesson_id: int
    second_lesson_id: int
    first_participants_count: int
    second_participants_count: int


@dataclass(frozen=True)
class AttendanceIdentityAlias:
    id: int
    canonical_full_name: str
    canonical_email: Optional[str]
    alias_value: str
    alias_type: str
    created_by: Optional[str]
    created_at: datetime
    is_active: bool
    notes: Optional[str]
    identity_id: Optional[int] = None


@dataclass(frozen=True)
class AttendanceIdentity:
    id: int
    identity_key: str
    display_name: str
    email: Optional[str]
    is_active: bool


@dataclass(frozen=True)
class AttendanceIdentityRebuildResult:
    source_identities: int
    rows_upserted: int
    identities_count: int


@dataclass(frozen=True)
class AttendanceAliasIdentitySyncResult:
    alias_id: int
    identity_id: int
    identity_key: str
    identity_created: bool
    alias_identity_id: Optional[int]
    alias_identity_deactivated: bool


@dataclass(frozen=True)
class ImportBatchSummary:
    id: int
    source_system: str
    source_file_name: str
    status: str
    created_at: datetime
    lessons_count: int
    participants_count: int


@dataclass(frozen=True)
class DraftLessonParticipantView:
    id: int
    participant_key: str
    canonical_full_name: str
    raw_full_name: Optional[str]
    email: Optional[str]
    segment_count: int
    minutes_first_half: float
    minutes_second_half: float
    duration_first_half: float
    duration_second_half: float
    total_minutes: float
    calculated_presence_status: str
    manual_override_presence_status: Optional[str]
    final_presence_status: str
    presence_source: str
    flags: list[str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DraftReviewActionView:
    id: int
    lesson_id: int
    participant_id: Optional[int]
    action_type: str
    payload: dict[str, Any]
    created_by: Optional[str]
    created_at: str
    applied_at: Optional[str]
    is_applied: bool
    notes: Optional[str]


@dataclass(frozen=True)
class DraftLessonSourceSegment:
    observed_full_name: str
    observed_email: Optional[str]
    join_time: str
    leave_time: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DraftLessonView:
    id: int
    course_name: str
    lesson_date: str
    source_meeting_id: str
    status: str
    is_ignored: bool
    threshold_ratio: float
    meeting_start_at: str
    meeting_end_at: str
    effective_start_at: str
    break_point_at: Optional[str]
    effective_end_at: str
    break_source: str
    effective_start_source: str
    effective_end_source: str
    warnings: list[str]
    diagnostics: dict[str, Any]
    summary: dict[str, int]
    participants: list[DraftLessonParticipantView]
    review_actions: list[DraftReviewActionView]
    import_batch_id: int = 0


@dataclass(frozen=True)
class DraftLessonSummary:
    id: int
    course_name: str
    lesson_date: str
    source_meeting_id: str
    status: str
    is_ignored: bool
    threshold_ratio: float
    summary: dict[str, int]


@dataclass(frozen=True)
class DraftBatchDetail:
    batch: ImportBatchSummary
    lessons: list[DraftLessonSummary]


@dataclass(frozen=True)
class SchoolAttendanceRecordView:
    lesson_id: int
    course_name: str
    lesson_date: str
    topic: Optional[str]
    canonical_full_name: str
    email: Optional[str]
    final_presence_status: str
    total_minutes: float
    expected_lessons_count: int
    expected_lessons_source: str


@dataclass(frozen=True)
class AttendanceIdentityCandidateView:
    canonical_full_name: str
    email: Optional[str]
    appearances_count: int
    lessons_count: int
    last_seen_at: str


@dataclass(frozen=True)
class SchoolCourseLessonView:
    lesson_id: int
    course_name: str
    lesson_date: str
    source_meeting_id: str
    total_records: int
    presente_count: int
    prima_meta_count: int
    seconda_meta_count: int
    assente_count: int
    external_lesson_id: Optional[str] = None
    topic: Optional[str] = None
    planned_event_title: Optional[str] = None
    planned_home_recipient_key: Optional[str] = None
    planned_match_method: Optional[str] = None


@dataclass(frozen=True)
class SchoolCourseOverviewView:
    course_name: str
    expected_lessons_count: int
    expected_lessons_source: str
    lessons: list[SchoolCourseLessonView]


@dataclass(frozen=True)
class SchoolStudentFollowupView:
    course_name: str
    canonical_full_name: str
    email: Optional[str]
    checked_lessons_count: int
    missed_lessons_count: int
    attended_lessons_count: int
    recent_lessons: list[dict[str, str | bool]]


@dataclass(frozen=True)
class ManualPresenceRecordCreate:
    full_name: str
    email: Optional[str]
    presence_status: str


@dataclass(frozen=True)
class ManualPresenceImportCreate:
    lesson_id: Optional[int]
    course_name: str
    lesson_date: str
    presence_source: str
    created_by: Optional[str]
    records: list[ManualPresenceRecordCreate]


@dataclass(frozen=True)
class ManualPresenceImportResult:
    lesson_id: int
    course_name: str
    lesson_date: str
    records_processed: int
    participants_upserted: int


@dataclass(frozen=True)
class AttendanceInstructor:
    id: int
    instructor_name: str
    alias_of_id: Optional[int]
    canonical_name: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
