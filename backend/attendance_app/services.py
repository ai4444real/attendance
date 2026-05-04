"""Application services for attendance workflows."""

from __future__ import annotations

from collections import defaultdict

from backend.attendance_normalization.service import NormalizationResult

from .models import (
    ImportBatchCreate,
    LessonDraft,
    LessonParticipantDraft,
    PersistedDraftImport,
)
from .repositories import AttendanceDraftImportRepository


class AttendanceImportService:
    """Use cases related to attendance imports."""

    def __init__(self, repository: AttendanceDraftImportRepository) -> None:
        self._repository = repository

    def persist_normalization_result(
        self,
        batch_data: ImportBatchCreate,
        normalization_result: NormalizationResult,
    ) -> PersistedDraftImport:
        if not batch_data.source_system.strip():
            raise ValueError("source_system is required")
        if not batch_data.source_file_name.strip():
            raise ValueError("source_file_name is required")

        lessons = self._build_lesson_drafts(normalization_result)
        return self._repository.save_draft_import(batch_data, lessons)

    def _build_lesson_drafts(self, normalization_result: NormalizationResult) -> list[LessonDraft]:
        records_by_key = defaultdict(list)
        meeting_by_key = {}

        for meeting in normalization_result.meetings:
            key = (meeting.course, meeting.meeting_id, meeting.date)
            meeting_by_key[key] = meeting

        for record in normalization_result.records:
            key = (record.course, record.meeting_id, record.date[:10])
            records_by_key[key].append(record)

        lesson_drafts: list[LessonDraft] = []
        for key, meeting in meeting_by_key.items():
            course, meeting_id, lesson_date = key
            participants = []

            for record in records_by_key.get(key, []):
                full_name = f"{record.first_name} {record.last_name}".strip()
                participant_key = record.email.strip().lower() or full_name.lower()
                participants.append(
                    LessonParticipantDraft(
                        participant_key=participant_key,
                        canonical_full_name=full_name,
                        raw_full_name=full_name,
                        email=record.email or None,
                        segment_count=record.segment_count,
                        minutes_first_half=record.minutes_first_half,
                        minutes_second_half=record.minutes_second_half,
                        duration_first_half=record.duration_first_half,
                        duration_second_half=record.duration_second_half,
                        total_minutes=record.total_minutes,
                        calculated_presence_status=record.calculated_presence_status,
                        final_presence_status=record.calculated_presence_status,
                        flags=[],
                        metadata={},
                    )
                )

            lesson_drafts.append(
                LessonDraft(
                    source_system="zoom",
                    source_meeting_id=meeting_id,
                    course_name=course,
                    lesson_date=lesson_date,
                    meeting_start_at=meeting.meeting_start,
                    meeting_end_at=meeting.meeting_end,
                    effective_start_at=meeting.effective_start,
                    break_point_at=meeting.break_point,
                    effective_end_at=meeting.effective_end,
                    threshold_ratio=meeting.threshold,
                    break_source=meeting.break_source,
                    effective_start_source=meeting.effective_start_source,
                    effective_end_source=meeting.effective_end_source,
                    warnings=[],
                    diagnostics={
                        "meeting_start": meeting.meeting_start,
                        "meeting_end": meeting.meeting_end,
                        "participant_count": meeting.participant_count,
                        "peak_active_count": meeting.peak_active_count,
                        "sampled_every_minutes": meeting.sampled_every_minutes,
                        "trim_start_minutes": meeting.trim_start_minutes,
                        "trim_end_minutes": meeting.trim_end_minutes,
                        "effective_start_source": meeting.effective_start_source,
                        "effective_end_source": meeting.effective_end_source,
                        "suggested_effective_start": meeting.suggested_effective_start,
                        "suggested_effective_end": meeting.suggested_effective_end,
                        "suggestion_confidence": meeting.suggestion_confidence,
                        "timeline": [
                            {
                                "timestamp": point.timestamp,
                                "active_count": point.active_count,
                            }
                            for point in meeting.timeline
                        ],
                    },
                    participants=participants,
                )
            )

        return sorted(lesson_drafts, key=lambda lesson: (lesson.lesson_date, lesson.course_name, lesson.source_meeting_id))
