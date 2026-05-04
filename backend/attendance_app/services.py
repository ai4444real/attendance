"""Application services for attendance workflows."""

from __future__ import annotations

from collections import defaultdict

from backend.attendance_normalization.presence_rules import determine_presence_status
from backend.attendance_normalization.service import NormalizationResult

from .models import (
    DraftReviewActionView,
    ImportBatchCreate,
    LessonDraft,
    LessonParticipantDraft,
    PersistedDraftImport,
)
from .repositories import AttendanceDraftImportRepository, AttendanceReviewActionRepository


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
            participants_by_key: dict[str, LessonParticipantDraft] = {}

            for record in records_by_key.get(key, []):
                full_name = f"{record.first_name} {record.last_name}".strip()
                participant_key = record.email.strip().lower() or full_name.lower()
                participant_draft = LessonParticipantDraft(
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
                existing = participants_by_key.get(participant_key)
                if existing is None:
                    participants_by_key[participant_key] = participant_draft
                else:
                    participants_by_key[participant_key] = self._merge_participant_drafts(
                        existing,
                        participant_draft,
                        threshold=meeting.threshold,
                    )

            participants = sorted(
                participants_by_key.values(),
                key=lambda participant: participant.canonical_full_name.lower(),
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

    def _merge_participant_drafts(
        self,
        left: LessonParticipantDraft,
        right: LessonParticipantDraft,
        threshold: float,
    ) -> LessonParticipantDraft:
        canonical_full_name = (
            right.canonical_full_name
            if len(right.canonical_full_name) > len(left.canonical_full_name)
            else left.canonical_full_name
        )
        raw_full_name = (
            right.raw_full_name
            if (right.raw_full_name and len(right.raw_full_name) > len(left.raw_full_name or ""))
            else left.raw_full_name
        )
        email = left.email or right.email
        segment_count = left.segment_count + right.segment_count
        minutes_first_half = left.minutes_first_half + right.minutes_first_half
        minutes_second_half = left.minutes_second_half + right.minutes_second_half
        duration_first_half = max(left.duration_first_half, right.duration_first_half)
        duration_second_half = max(left.duration_second_half, right.duration_second_half)
        total_minutes = left.total_minutes + right.total_minutes
        calculated_presence_status = determine_presence_status(
            minutes_first_half=minutes_first_half,
            minutes_second_half=minutes_second_half,
            duration_first_half=duration_first_half,
            duration_second_half=duration_second_half,
            threshold=threshold,
        )
        merged_flags = sorted(set(left.flags + right.flags))
        merged_metadata = {**left.metadata, **right.metadata}
        merged_metadata["merged_duplicate_participant_key"] = True

        return LessonParticipantDraft(
            participant_key=left.participant_key,
            canonical_full_name=canonical_full_name,
            raw_full_name=raw_full_name,
            email=email,
            segment_count=segment_count,
            minutes_first_half=minutes_first_half,
            minutes_second_half=minutes_second_half,
            duration_first_half=duration_first_half,
            duration_second_half=duration_second_half,
            total_minutes=total_minutes,
            calculated_presence_status=calculated_presence_status,
            final_presence_status=calculated_presence_status,
            flags=merged_flags,
            metadata=merged_metadata,
        )


class AttendanceReviewActionService:
    """Use cases related to manual review actions on one lesson."""

    _ALLOWED_ACTIONS = {
        "set_threshold_ratio",
        "set_effective_start",
        "set_break_point",
        "set_effective_end",
    }

    def __init__(self, repository: AttendanceReviewActionRepository) -> None:
        self._repository = repository

    def create_lesson_review_action(
        self,
        lesson_id: int,
        action_type: str,
        payload: dict,
        *,
        created_by: str | None = None,
        notes: str | None = None,
        participant_id: int | None = None,
    ) -> DraftReviewActionView:
        if lesson_id <= 0:
            raise ValueError("lesson_id must be positive")
        if action_type not in self._ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported review action: {action_type}")
        if not isinstance(payload, dict) or not payload:
            raise ValueError("payload is required")
        self._validate_payload(action_type, payload)
        return self._repository.create_lesson_review_action(
            lesson_id,
            action_type,
            payload,
            created_by=created_by,
            notes=notes,
            participant_id=participant_id,
        )

    def _validate_payload(self, action_type: str, payload: dict) -> None:
        if action_type == "set_threshold_ratio":
            threshold = payload.get("threshold_ratio")
            if not isinstance(threshold, (int, float)) or threshold <= 0 or threshold > 1:
                raise ValueError("threshold_ratio must be a number between 0 and 1")
            return

        timestamp = payload.get("at")
        if not isinstance(timestamp, str) or "T" not in timestamp:
            raise ValueError("payload.at must be an ISO datetime string")
