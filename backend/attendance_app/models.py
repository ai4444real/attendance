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
class PersistedDraftImport:
    batch: ImportBatch
    lessons_created: int
    participants_created: int


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
    canonical_full_name: str
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
    flags: list[str]
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


@dataclass(frozen=True)
class DraftBatchDetail:
    batch: ImportBatchSummary
    lessons: list[DraftLessonView]
