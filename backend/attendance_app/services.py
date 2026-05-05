"""Application services for attendance workflows."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from backend.attendance_normalization.aggregator import ZoomMeeting, ZoomSegment, aggregate_meeting
from backend.attendance_normalization.presence_rules import determine_presence_status
from backend.attendance_normalization.service import NormalizationResult

from .models import (
    AttendanceIdentityAlias,
    DraftLessonView,
    DraftReviewActionView,
    ImportBatchCreate,
    LessonDraft,
    LessonParticipantDraft,
    PersistedDraftImport,
)
from .repositories import (
    AttendanceDraftImportRepository,
    AttendanceIdentityAliasRepository,
    AttendanceDraftMutationRepository,
    AttendanceDraftQueryRepository,
    AttendanceReviewActionRepository,
)


class AttendanceImportService:
    """Use cases related to attendance imports."""

    def __init__(
        self,
        repository: AttendanceDraftImportRepository,
        identity_alias_repository: AttendanceIdentityAliasRepository | None = None,
    ) -> None:
        self._repository = repository
        self._identity_alias_repository = identity_alias_repository

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
        alias_map = self._build_identity_alias_map()
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
                canonical_full_name = self._apply_identity_alias(full_name, alias_map)
                first_name, last_name = self._split_full_name(canonical_full_name)
                participant_key = record.email.strip().lower() or canonical_full_name.lower()
                participant_draft = LessonParticipantDraft(
                    participant_key=participant_key,
                    canonical_full_name=canonical_full_name,
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
                    metadata={
                        "first_name": first_name,
                        "last_name": last_name,
                        "segments": list(record.segments),
                        "canonicalized_by_identity_alias": canonical_full_name != full_name,
                    },
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

    def _build_identity_alias_map(self) -> dict[str, str]:
        if self._identity_alias_repository is None:
            return {}
        aliases = self._identity_alias_repository.list_active_aliases()
        return {
            self._normalize_identity_key(alias.alias_full_name): alias.canonical_full_name
            for alias in aliases
        }

    def _apply_identity_alias(self, full_name: str, alias_map: dict[str, str]) -> str:
        normalized = self._normalize_identity_key(full_name)
        return alias_map.get(normalized, full_name)

    def _normalize_identity_key(self, value: str) -> str:
        return " ".join((value or "").strip().casefold().split())

    def _split_full_name(self, full_name: str) -> tuple[str, str]:
        parts = [part for part in (full_name or "").split(" ") if part]
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

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
        left_segments = list(left.metadata.get("segments", []))
        right_segments = list(right.metadata.get("segments", []))
        merged_metadata["segments"] = left_segments + right_segments
        merged_metadata["first_name"] = merged_metadata.get("first_name") or left.canonical_full_name.split(" ")[0]
        merged_metadata["last_name"] = merged_metadata.get("last_name") or " ".join(left.canonical_full_name.split(" ")[1:])

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
        "set_manual_presence_status",
        "clear_manual_presence_status",
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
        if not isinstance(payload, dict):
            raise ValueError("payload is required")
        if action_type != "clear_manual_presence_status" and not payload:
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
        if action_type == "set_manual_presence_status":
            presence_status = payload.get("presence_status")
            if presence_status not in {"presente", "prima_meta", "seconda_meta", "assente"}:
                raise ValueError("presence_status must be one of presente, prima_meta, seconda_meta, assente")
            return

        if action_type == "clear_manual_presence_status":
            return

        if action_type == "set_threshold_ratio":
            threshold = payload.get("threshold_ratio")
            if not isinstance(threshold, (int, float)) or threshold <= 0 or threshold > 1:
                raise ValueError("threshold_ratio must be a number between 0 and 1")
            return

        timestamp = payload.get("at")
        if not isinstance(timestamp, str) or "T" not in timestamp:
            raise ValueError("payload.at must be an ISO datetime string")


class AttendanceDraftRecalculationService:
    """Recompute one draft lesson from persisted segments and review actions."""

    def __init__(
        self,
        query_repository: AttendanceDraftQueryRepository,
        mutation_repository: AttendanceDraftMutationRepository,
    ) -> None:
        self._query_repository = query_repository
        self._mutation_repository = mutation_repository

    def recalculate_lesson(self, lesson_id: int) -> DraftLessonView:
        lesson = self._query_repository.get_lesson_detail(lesson_id)
        action_sequence = sorted(lesson.review_actions, key=lambda item: (item.created_at, item.id))

        threshold_ratio = lesson.threshold_ratio
        effective_start_at = lesson.effective_start_at
        break_point_at = lesson.break_point_at
        effective_end_at = lesson.effective_end_at
        break_source = lesson.break_source
        effective_start_source = lesson.effective_start_source
        effective_end_source = lesson.effective_end_source
        manual_overrides = {
            participant.id: participant.manual_override_presence_status
            for participant in lesson.participants
        }

        for action in action_sequence:
            payload = action.payload or {}
            if action.action_type == "set_threshold_ratio":
                threshold_ratio = float(payload["threshold_ratio"])
            elif action.action_type == "set_effective_start":
                effective_start_at = str(payload["at"])
                effective_start_source = "review_action"
            elif action.action_type == "set_break_point":
                break_point_at = str(payload["at"])
                break_source = "manual"
            elif action.action_type == "set_effective_end":
                effective_end_at = str(payload["at"])
                effective_end_source = "review_action"
            elif action.action_type == "set_manual_presence_status" and action.participant_id is not None:
                manual_overrides[action.participant_id] = str(payload["presence_status"])
            elif action.action_type == "clear_manual_presence_status" and action.participant_id is not None:
                manual_overrides[action.participant_id] = None

        participants_have_segments = all(
            isinstance(participant.metadata.get("segments"), list) and participant.metadata.get("segments")
            for participant in lesson.participants
        )

        if participants_have_segments:
            participants = self._recalculate_from_segments(
                lesson,
                threshold_ratio=threshold_ratio,
                effective_start_at=effective_start_at,
                break_point_at=break_point_at,
                effective_end_at=effective_end_at,
                manual_overrides=manual_overrides,
            )
        else:
            participants = self._recalculate_threshold_only(
                lesson,
                threshold_ratio=threshold_ratio,
                manual_overrides=manual_overrides,
            )

        diagnostics = dict(lesson.diagnostics or {})
        diagnostics["threshold_ratio"] = threshold_ratio
        diagnostics["effective_start"] = effective_start_at
        diagnostics["break_point"] = break_point_at
        diagnostics["effective_end"] = effective_end_at
        diagnostics["recalculated_from_review_actions"] = True
        diagnostics["recalculation_mode"] = "segments" if participants_have_segments else "threshold_only"

        self._mutation_repository.update_lesson_after_recalculation(
            lesson,
            threshold_ratio=threshold_ratio,
            effective_start_at=effective_start_at,
            break_point_at=break_point_at,
            effective_end_at=effective_end_at,
            break_source=break_source,
            effective_start_source=effective_start_source,
            effective_end_source=effective_end_source,
            diagnostics=diagnostics,
            participants=participants,
        )

        return self._query_repository.get_lesson_detail(lesson_id)

    def _recalculate_from_segments(
        self,
        lesson: DraftLessonView,
        *,
        threshold_ratio: float,
        effective_start_at: str,
        break_point_at: str | None,
        effective_end_at: str,
        manual_overrides: dict[int, str | None],
    ) -> list[dict]:
        meeting = self._build_zoom_meeting(lesson)
        effective_start = datetime.fromisoformat(effective_start_at)
        effective_end = datetime.fromisoformat(effective_end_at)
        break_point = datetime.fromisoformat(break_point_at) if break_point_at else None
        break_point = self._resolve_break_point(effective_start, effective_end, break_point)

        aggregated = aggregate_meeting(
            meeting=meeting,
            effective_start=effective_start,
            break_point=break_point,
            effective_end=effective_end,
        )
        records_by_key = {
            (record.email.strip().lower() or record.full_name.lower()): record
            for record in aggregated
        }

        updates: list[dict] = []
        for participant in lesson.participants:
            participant_key = participant.email.strip().lower() if participant.email else participant.canonical_full_name.lower()
            record = records_by_key.get(participant_key)
            if record is None:
                continue
            calculated = determine_presence_status(
                minutes_first_half=record.minutes_first_half,
                minutes_second_half=record.minutes_second_half,
                duration_first_half=record.duration_first_half,
                duration_second_half=record.duration_second_half,
                threshold=threshold_ratio,
            )
            manual_override_presence_status = manual_overrides.get(participant.id)
            final = manual_override_presence_status or calculated
            updates.append(
                {
                    "id": participant.id,
                    "minutes_first_half": record.minutes_first_half,
                    "minutes_second_half": record.minutes_second_half,
                    "duration_first_half": record.duration_first_half,
                    "duration_second_half": record.duration_second_half,
                    "total_minutes": record.total_minutes,
                    "calculated_presence_status": calculated,
                    "manual_override_presence_status": manual_override_presence_status,
                    "final_presence_status": final,
                }
            )
        return updates

    def _recalculate_threshold_only(
        self,
        lesson: DraftLessonView,
        *,
        threshold_ratio: float,
        manual_overrides: dict[int, str | None],
    ) -> list[dict]:
        updates: list[dict] = []
        for participant in lesson.participants:
            calculated = determine_presence_status(
                minutes_first_half=participant.minutes_first_half,
                minutes_second_half=participant.minutes_second_half,
                duration_first_half=participant.duration_first_half,
                duration_second_half=participant.duration_second_half,
                threshold=threshold_ratio,
            )
            manual_override_presence_status = manual_overrides.get(participant.id)
            final = manual_override_presence_status or calculated
            updates.append(
                {
                    "id": participant.id,
                    "minutes_first_half": participant.minutes_first_half,
                    "minutes_second_half": participant.minutes_second_half,
                    "duration_first_half": participant.duration_first_half,
                    "duration_second_half": participant.duration_second_half,
                    "total_minutes": participant.total_minutes,
                    "calculated_presence_status": calculated,
                    "manual_override_presence_status": manual_override_presence_status,
                    "final_presence_status": final,
                }
            )
        return updates

    def _build_zoom_meeting(self, lesson: DraftLessonView) -> ZoomMeeting:
        segments: list[ZoomSegment] = []
        lesson_start = datetime.fromisoformat(lesson.meeting_start_at)
        lesson_end = datetime.fromisoformat(lesson.meeting_end_at)
        target_tz = lesson_start.tzinfo
        for participant in lesson.participants:
            participant_segments = participant.metadata.get("segments") or []
            first_name = participant.metadata.get("first_name") or participant.canonical_full_name.split(" ")[0]
            last_name = participant.metadata.get("last_name") or " ".join(participant.canonical_full_name.split(" ")[1:])
            for segment in participant_segments:
                if not isinstance(segment, (list, tuple)) or len(segment) != 2:
                    continue
                segments.append(
                    ZoomSegment(
                        first_name=first_name,
                        last_name=last_name,
                        email=participant.email or "",
                        full_name=participant.canonical_full_name,
                        join_time=self._coerce_segment_datetime(segment[0], target_tz),
                        leave_time=self._coerce_segment_datetime(segment[1], target_tz),
                    )
                )
        return ZoomMeeting(
            course=lesson.course_name,
            meeting_id=lesson.source_meeting_id,
            start_time=lesson_start,
            end_time=lesson_end,
            duration_minutes=(lesson_end - lesson_start).total_seconds() / 60,
            segments=segments,
        )

    def _resolve_break_point(
        self,
        effective_start: datetime,
        effective_end: datetime,
        break_point: datetime | None,
    ) -> datetime:
        candidate = break_point or (effective_start + (effective_end - effective_start) / 2)
        min_break = effective_start + timedelta(minutes=5)
        max_break = effective_end - timedelta(minutes=5)
        if max_break <= min_break:
            return effective_start + (effective_end - effective_start) / 2
        if candidate < min_break:
            return min_break
        if candidate > max_break:
            return max_break
        return candidate

    def _coerce_segment_datetime(self, value: str, target_tz) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None and target_tz is not None:
            return parsed.replace(tzinfo=target_tz)
        if parsed.tzinfo is not None and target_tz is None:
            return parsed.replace(tzinfo=None)
        return parsed


class AttendanceLessonStateService:
    """Change lesson state flags that are orthogonal to attendance recalculation."""

    _ALLOWED_STATUSES = {"draft", "official"}

    def __init__(self, mutation_repository: AttendanceDraftMutationRepository) -> None:
        self._mutation_repository = mutation_repository

    def set_lesson_ignored(self, lesson_id: int, *, is_ignored: bool) -> None:
        if lesson_id <= 0:
            raise ValueError("lesson_id must be positive")
        self._mutation_repository.set_lesson_ignored(lesson_id, is_ignored=is_ignored)

    def set_lesson_status(self, lesson_id: int, *, status: str) -> None:
        if lesson_id <= 0:
            raise ValueError("lesson_id must be positive")
        if status not in self._ALLOWED_STATUSES:
            raise ValueError(f"Unsupported lesson status: {status}")
        self._mutation_repository.set_lesson_status(lesson_id, status=status)


class AttendanceIdentityAliasService:
    """Manage persistent identity aliases used by future imports."""

    def __init__(self, repository: AttendanceIdentityAliasRepository) -> None:
        self._repository = repository

    def create_alias(
        self,
        *,
        canonical_full_name: str,
        alias_full_name: str,
        created_by: str | None = None,
        notes: str | None = None,
    ) -> AttendanceIdentityAlias:
        canonical = " ".join((canonical_full_name or "").strip().split())
        alias = " ".join((alias_full_name or "").strip().split())
        if not canonical:
            raise ValueError("canonical_full_name is required")
        if not alias:
            raise ValueError("alias_full_name is required")
        if canonical.casefold() == alias.casefold():
            raise ValueError("canonical_full_name and alias_full_name must differ")
        return self._repository.create_alias(
            canonical_full_name=canonical,
            alias_full_name=alias,
            created_by=created_by,
            notes=notes,
        )
