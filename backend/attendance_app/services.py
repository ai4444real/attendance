"""Application services for attendance workflows."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from backend.attendance_normalization.identity_rules import load_identity_rules
from backend.attendance_normalization.presence_rules import determine_presence_status
from backend.attendance_normalization.service import NormalizationResult

MAX_RECONNECT_GAP_MINUTES = 5.0

from .models import (
    AttendanceIdentityAlias,
    DraftLessonSourceSegment,
    DraftLessonView,
    DraftReviewActionView,
    ImportBatchCreate,
    LessonDraft,
    LessonParticipantDraft,
    ManualPresenceImportCreate,
    ManualPresenceImportResult,
    ManualPresenceRecordCreate,
    PersistedDraftImport,
    SplitLessonResult,
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
        name_alias_map, email_alias_map = _load_identity_alias_maps(self._identity_alias_repository)
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
                canonical_full_name, canonical_email = self._apply_identity_alias(
                    full_name,
                    record.email or None,
                    name_alias_map,
                    email_alias_map,
                )
                first_name, last_name = self._split_full_name(canonical_full_name)
                participant_key = (canonical_email or "").strip().lower() or canonical_full_name.lower()
                participant_draft = LessonParticipantDraft(
                    participant_key=participant_key,
                    canonical_full_name=canonical_full_name,
                    raw_full_name=full_name,
                    email=canonical_email,
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
                        "identity_sources": [
                            {
                                "raw_full_name": full_name,
                                "email": record.email or "",
                                "segments": list(record.segments),
                            }
                        ],
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
                        effective_start_at=meeting.effective_start,
                        break_point_at=meeting.break_point,
                        effective_end_at=meeting.effective_end,
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

    def _apply_identity_alias(
        self,
        full_name: str,
        email: str | None,
        name_alias_map: dict[str, AttendanceIdentityAlias],
        email_alias_map: dict[str, AttendanceIdentityAlias],
    ) -> tuple[str, str | None]:
        return _apply_identity_alias_maps(full_name, email, name_alias_map, email_alias_map)

    def _split_full_name(self, full_name: str) -> tuple[str, str]:
        return _split_full_name(full_name)

    def _merge_participant_drafts(
        self,
        left: LessonParticipantDraft,
        right: LessonParticipantDraft,
        threshold: float,
        effective_start_at: str,
        break_point_at: str,
        effective_end_at: str,
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
        merged_flags = sorted(set(left.flags + right.flags))
        merged_metadata = {**left.metadata, **right.metadata}
        merged_metadata["merged_duplicate_participant_key"] = True
        left_segments = list(left.metadata.get("segments", []))
        right_segments = list(right.metadata.get("segments", []))
        merged_metadata["first_name"] = merged_metadata.get("first_name") or left.canonical_full_name.split(" ")[0]
        merged_metadata["last_name"] = merged_metadata.get("last_name") or " ".join(left.canonical_full_name.split(" ")[1:])
        merged_metadata["identity_sources"] = _merge_identity_sources(
            left.metadata.get("identity_sources"),
            right.metadata.get("identity_sources"),
            fallback_left_name=left.raw_full_name or left.canonical_full_name,
            fallback_left_email=left.email,
            fallback_left_segments=left_segments,
            fallback_right_name=right.raw_full_name or right.canonical_full_name,
            fallback_right_email=right.email,
            fallback_right_segments=right_segments,
        )
        if _identity_sources_have_any_segments(merged_metadata["identity_sources"]):
            rebuilt = _aggregate_identity_sources_as_one(
                merged_metadata["identity_sources"],
                canonical_full_name=canonical_full_name,
                canonical_email=email,
                effective_start_at=effective_start_at,
                break_point_at=break_point_at,
                effective_end_at=effective_end_at,
                threshold=threshold,
            )
            merged_metadata["segments"] = rebuilt["segments"]
        else:
            rebuilt = {
                "segment_count": left.segment_count + right.segment_count,
                "minutes_first_half": _round1(left.minutes_first_half + right.minutes_first_half),
                "minutes_second_half": _round1(left.minutes_second_half + right.minutes_second_half),
                "duration_first_half": max(left.duration_first_half, right.duration_first_half),
                "duration_second_half": max(left.duration_second_half, right.duration_second_half),
                "total_minutes": _round1(left.total_minutes + right.total_minutes),
            }
            rebuilt["calculated_presence_status"] = determine_presence_status(
                minutes_first_half=rebuilt["minutes_first_half"],
                minutes_second_half=rebuilt["minutes_second_half"],
                duration_first_half=rebuilt["duration_first_half"],
                duration_second_half=rebuilt["duration_second_half"],
                threshold=threshold,
            )
            merged_metadata["segments"] = left_segments + right_segments

        return LessonParticipantDraft(
            participant_key=left.participant_key,
            canonical_full_name=canonical_full_name,
            raw_full_name=raw_full_name,
            email=email,
            segment_count=rebuilt["segment_count"],
            minutes_first_half=rebuilt["minutes_first_half"],
            minutes_second_half=rebuilt["minutes_second_half"],
            duration_first_half=rebuilt["duration_first_half"],
            duration_second_half=rebuilt["duration_second_half"],
            total_minutes=rebuilt["total_minutes"],
            calculated_presence_status=rebuilt["calculated_presence_status"],
            final_presence_status=rebuilt["calculated_presence_status"],
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

    def delete_lesson_review_action(self, action_id: int) -> int:
        if action_id <= 0:
            raise ValueError("action_id must be positive")
        return self._repository.delete_lesson_review_action(action_id)

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
        identity_alias_repository: AttendanceIdentityAliasRepository | None = None,
    ) -> None:
        self._query_repository = query_repository
        self._mutation_repository = mutation_repository
        self._identity_alias_repository = identity_alias_repository

    def recalculate_lesson(
        self,
        lesson_id: int,
        *,
        use_current_markers: bool = False,
        apply_marker_action_ids: set[int] | None = None,
        prefer_original_baseline: bool = False,
    ) -> DraftLessonView:
        lesson = self._query_repository.get_lesson_detail(lesson_id)
        action_sequence = sorted(lesson.review_actions, key=lambda item: (item.created_at, item.id))
        apply_marker_action_ids = apply_marker_action_ids or set()

        diagnostics = dict(lesson.diagnostics or {})
        marker_action_types = {
            "set_threshold_ratio",
            "set_effective_start",
            "set_break_point",
            "set_effective_end",
        }
        has_marker_actions = any(action.action_type in marker_action_types for action in action_sequence)
        baseline = self._build_recalculation_baseline(
            lesson,
            diagnostics,
            use_current_markers=use_current_markers,
            prefer_original_baseline=prefer_original_baseline or has_marker_actions,
        )
        # Marker corrections are event-sourced: baseline + surviving actions.
        # The use_current_markers path is kept only for legacy incremental callers.
        if (
            use_current_markers
            and apply_marker_action_ids
            and not isinstance(diagnostics.get("review_action_baseline"), dict)
            and any(action.id in apply_marker_action_ids and action.action_type in marker_action_types for action in action_sequence)
        ):
            diagnostics["review_action_baseline"] = dict(baseline)
        threshold_ratio = baseline["threshold_ratio"]
        effective_start_at = baseline["effective_start_at"]
        break_point_at = baseline["break_point_at"]
        effective_end_at = baseline["effective_end_at"]
        break_source = baseline["break_source"]
        effective_start_source = baseline["effective_start_source"]
        effective_end_source = baseline["effective_end_source"]
        manual_overrides = {
            participant.id: None
            for participant in lesson.participants
        }

        for action in action_sequence:
            payload = action.payload or {}
            if use_current_markers and action.action_type in marker_action_types and action.id not in apply_marker_action_ids:
                continue
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

        source_segments = self._query_repository.get_lesson_source_segments(lesson.id)
        effective_start = datetime.fromisoformat(str(effective_start_at))
        effective_end = datetime.fromisoformat(str(effective_end_at))
        meeting_start_at = lesson.meeting_start_at
        meeting_end_at = lesson.meeting_end_at
        bounds_were_expanded = False
        source_bounds = self._source_segment_bounds(source_segments, effective_start.tzinfo)
        if source_bounds is not None:
            source_start, source_end = source_bounds
            meeting_start = datetime.fromisoformat(lesson.meeting_start_at)
            meeting_end = datetime.fromisoformat(lesson.meeting_end_at)
            if source_start < meeting_start:
                meeting_start_at = source_start.isoformat()
                bounds_were_expanded = True
                if effective_start < source_start:
                    effective_start = source_start
                    effective_start_at = effective_start.isoformat()
                    effective_start_source = "source_segments"
            if source_end > meeting_end:
                meeting_end_at = source_end.isoformat()
                bounds_were_expanded = True
                if effective_end <= meeting_end:
                    effective_end = source_end
                    effective_end_at = effective_end.isoformat()
                    effective_end_source = "source_segments"

        meeting_end_candidate = datetime.fromisoformat(str(meeting_end_at))
        if effective_end <= effective_start:
            if source_bounds is not None and source_bounds[1] > effective_start:
                effective_end = source_bounds[1]
                effective_end_source = "recalculate_resolved"
            elif meeting_end_candidate > effective_start:
                effective_end = meeting_end_candidate
                effective_end_source = "recalculate_resolved"
            else:
                effective_end = effective_start + timedelta(minutes=10)
                effective_end_source = "recalculate_resolved"
            effective_end_at = effective_end.isoformat()

        requested_break_point = datetime.fromisoformat(str(break_point_at)) if break_point_at else None
        if bounds_were_expanded and break_source in {"midpoint", "recalculate_resolved"}:
            requested_break_point = None
        if requested_break_point is not None and (
            requested_break_point <= effective_start or requested_break_point >= effective_end
        ):
            requested_break_point = None
        resolved_break_point = self._resolve_break_point(effective_start, effective_end, requested_break_point)
        if requested_break_point is None or resolved_break_point != requested_break_point:
            break_source = "recalculate_resolved"
        break_point_at = resolved_break_point.isoformat()

        participants_have_segments = bool(source_segments) or all(
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
                source_segments=source_segments,
            )
        else:
            participants = self._recalculate_threshold_only(
                lesson,
                threshold_ratio=threshold_ratio,
                manual_overrides=manual_overrides,
            )

        if not use_current_markers:
            diagnostics["review_action_baseline"] = baseline
        diagnostics["threshold_ratio"] = threshold_ratio
        diagnostics["effective_start"] = effective_start_at
        diagnostics["break_point"] = break_point_at
        diagnostics["effective_end"] = effective_end_at
        diagnostics["recalculated_from_review_actions"] = True
        diagnostics["recalculated_from_current_markers"] = use_current_markers
        diagnostics["recalculation_mode"] = "segments" if participants_have_segments else "threshold_only"
        if source_segments:
            diagnostics["timeline"] = self._build_timeline_from_source_segments(
                source_segments,
                datetime.fromisoformat(str(meeting_start_at)),
                datetime.fromisoformat(str(meeting_end_at)),
            )
            diagnostics["peak_active_count"] = max(
                [int(point.get("active_count") or 0) for point in diagnostics["timeline"] if isinstance(point, dict)] or [0]
            )
            diagnostics["sampled_every_minutes"] = 10.0

        self._mutation_repository.update_lesson_after_recalculation(
            lesson,
            threshold_ratio=threshold_ratio,
            meeting_start_at=meeting_start_at,
            meeting_end_at=meeting_end_at,
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

    def _source_segment_bounds(
        self,
        source_segments: list[DraftLessonSourceSegment],
        target_tz,
    ) -> tuple[datetime, datetime] | None:
        if not source_segments:
            return None
        starts = []
        ends = []
        for segment in source_segments:
            try:
                starts.append(_coerce_segment_datetime(segment.join_time, target_tz))
                ends.append(_coerce_segment_datetime(segment.leave_time, target_tz))
            except ValueError:
                continue
        if not starts or not ends:
            return None
        return min(starts), max(ends)

    def _build_timeline_from_source_segments(
        self,
        source_segments: list[DraftLessonSourceSegment],
        window_start: datetime,
        window_end: datetime,
        step_minutes: float = 10.0,
    ) -> list[dict]:
        if window_end <= window_start:
            return [{"timestamp": window_start.isoformat(), "active_count": 0}]
        step = timedelta(minutes=step_minutes)
        current = window_start
        points = []
        while current < window_end:
            points.append({
                "timestamp": current.isoformat(),
                "active_count": self._count_active_source_segments(source_segments, current, window_end),
            })
            current += step
        points.append({
            "timestamp": window_end.isoformat(),
            "active_count": self._count_active_source_segments(source_segments, window_end, window_end),
        })
        return points

    def _count_active_source_segments(
        self,
        source_segments: list[DraftLessonSourceSegment],
        probe_time: datetime,
        window_end: datetime,
    ) -> int:
        adjusted_probe = probe_time if probe_time < window_end else window_end - timedelta(seconds=1)
        active = set()
        for segment in source_segments:
            try:
                join_time = _coerce_segment_datetime(segment.join_time, adjusted_probe.tzinfo)
                leave_time = _coerce_segment_datetime(segment.leave_time, adjusted_probe.tzinfo)
            except ValueError:
                continue
            if join_time <= adjusted_probe < leave_time:
                active.add(segment.observed_email or segment.observed_full_name)
        return len(active)

    def _build_recalculation_baseline(
        self,
        lesson: DraftLessonView,
        diagnostics: dict,
        *,
        use_current_markers: bool = False,
        prefer_original_baseline: bool = False,
    ) -> dict:
        if use_current_markers:
            return self._current_lesson_baseline(lesson)
        existing = diagnostics.get("review_action_baseline")
        if isinstance(existing, dict):
            return {
                "threshold_ratio": float(existing.get("threshold_ratio", lesson.threshold_ratio)),
                "effective_start_at": str(existing.get("effective_start_at") or lesson.effective_start_at),
                "break_point_at": existing.get("break_point_at"),
                "effective_end_at": str(existing.get("effective_end_at") or lesson.effective_end_at),
                "break_source": str(existing.get("break_source") or lesson.break_source),
                "effective_start_source": str(existing.get("effective_start_source") or lesson.effective_start_source),
                "effective_end_source": str(existing.get("effective_end_source") or lesson.effective_end_source),
            }
        if prefer_original_baseline:
            return self._infer_recalculation_baseline(lesson, diagnostics)
        return self._current_lesson_baseline(lesson)

    def _current_lesson_baseline(self, lesson: DraftLessonView) -> dict:
        return {
            "threshold_ratio": lesson.threshold_ratio,
            "effective_start_at": lesson.effective_start_at,
            "break_point_at": lesson.break_point_at,
            "effective_end_at": lesson.effective_end_at,
            "break_source": lesson.break_source,
            "effective_start_source": lesson.effective_start_source,
            "effective_end_source": lesson.effective_end_source,
        }

    def _infer_recalculation_baseline(self, lesson: DraftLessonView, diagnostics: dict) -> dict:
        suggested_start = diagnostics.get("suggested_effective_start")
        suggested_end = diagnostics.get("suggested_effective_end")
        confidence = diagnostics.get("suggestion_confidence")
        effective_start_at = (
            str(suggested_start)
            if confidence == "high" and suggested_start
            else str(lesson.effective_start_at)
        )
        effective_start_source = (
            "auto_suggest"
            if confidence == "high" and suggested_start
            else str(lesson.effective_start_source or "recalculate_resolved")
        )

        effective_end_at = (
            str(suggested_end)
            if confidence == "high" and suggested_end
            else str(diagnostics.get("meeting_end") or lesson.meeting_end_at)
        )
        effective_end_source = (
            "auto_suggest"
            if confidence == "high" and suggested_end
            else "meeting_end"
        )

        break_point_at = lesson.break_point_at
        break_source = str(lesson.break_source or "recalculate_resolved")
        if break_source == "manual":
            break_point_at = None
            break_source = "recalculate_resolved"

        return {
            "threshold_ratio": lesson.threshold_ratio,
            "effective_start_at": effective_start_at,
            "break_point_at": break_point_at,
            "effective_end_at": effective_end_at,
            "break_source": break_source,
            "effective_start_source": effective_start_source,
            "effective_end_source": effective_end_source,
        }

    def _recalculate_from_segments(
        self,
        lesson: DraftLessonView,
        *,
        threshold_ratio: float,
        effective_start_at: str,
        break_point_at: str | None,
        effective_end_at: str,
        manual_overrides: dict[int, str | None],
        source_segments: list[DraftLessonSourceSegment] | None = None,
    ) -> list[dict]:
        effective_start = datetime.fromisoformat(effective_start_at)
        effective_end = datetime.fromisoformat(effective_end_at)
        break_point = datetime.fromisoformat(break_point_at) if break_point_at else None
        break_point = self._resolve_break_point(effective_start, effective_end, break_point)
        if not source_segments:
            source_segments = _extract_source_segments_from_lesson(lesson)

        name_alias_map, email_alias_map = _load_identity_alias_maps(self._identity_alias_repository)
        aggregated = _aggregate_source_segments_by_final_identity(
            source_segments,
            effective_start=effective_start,
            break_point=break_point,
            effective_end=effective_end,
            threshold=threshold_ratio,
            name_alias_map=name_alias_map,
            email_alias_map=email_alias_map,
            forced_identity_pairs=set(),
            forced_canonical_full_name=None,
            forced_canonical_email=None,
        )

        updates: list[dict] = []
        for participant in lesson.participants:
            participant_key = participant.email.strip().lower() if participant.email else participant.canonical_full_name.lower()
            record = aggregated.get(participant_key)
            if record is None:
                continue
            manual_override_presence_status = manual_overrides.get(participant.id)
            final = manual_override_presence_status or record["calculated_presence_status"]
            updates.append(
                {
                    "id": participant.id,
                    "minutes_first_half": record["minutes_first_half"],
                    "minutes_second_half": record["minutes_second_half"],
                    "duration_first_half": record["duration_first_half"],
                    "duration_second_half": record["duration_second_half"],
                    "total_minutes": record["total_minutes"],
                    "calculated_presence_status": record["calculated_presence_status"],
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

    def _resolve_break_point(
        self,
        effective_start: datetime,
        effective_end: datetime,
        break_point: datetime | None,
    ) -> datetime:
        candidate = break_point or (effective_start + (effective_end - effective_start) / 2)
        midpoint = effective_start + (effective_end - effective_start) / 2
        min_break = effective_start + timedelta(minutes=5)
        max_break = effective_end - timedelta(minutes=5)
        if max_break <= min_break:
            return midpoint
        if candidate <= effective_start or candidate >= effective_end:
            return midpoint
        if candidate < min_break:
            return min_break
        if candidate > max_break:
            return max_break
        return candidate


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

    def delete_lesson(self, lesson_id: int) -> None:
        if lesson_id <= 0:
            raise ValueError("lesson_id must be positive")
        self._mutation_repository.delete_lesson(lesson_id)

    def delete_batch(self, batch_id: int) -> None:
        if batch_id <= 0:
            raise ValueError("batch_id must be positive")
        self._mutation_repository.delete_batch(batch_id)


class AttendanceLessonSplitService:
    """Split one untouched draft lesson into two normal draft lessons."""

    def __init__(
        self,
        query_repository: AttendanceDraftQueryRepository,
        mutation_repository: AttendanceDraftMutationRepository,
        identity_alias_repository: AttendanceIdentityAliasRepository | None = None,
    ) -> None:
        self._query_repository = query_repository
        self._mutation_repository = mutation_repository
        self._identity_alias_repository = identity_alias_repository

    def split_lesson(
        self,
        lesson_id: int,
        *,
        first_end_at: str,
        second_start_at: str,
    ) -> SplitLessonResult:
        if lesson_id <= 0:
            raise ValueError("lesson_id must be positive")
        lesson = self._query_repository.get_lesson_detail(lesson_id)
        self._validate_split_allowed(lesson)

        meeting_start = datetime.fromisoformat(lesson.meeting_start_at)
        meeting_end = datetime.fromisoformat(lesson.meeting_end_at)
        effective_start = datetime.fromisoformat(lesson.effective_start_at)
        effective_end = datetime.fromisoformat(lesson.effective_end_at)
        first_end = _coerce_segment_datetime(first_end_at, meeting_start.tzinfo)
        second_start = _coerce_segment_datetime(second_start_at, meeting_start.tzinfo)
        if not (meeting_start < first_end < second_start < meeting_end):
            raise ValueError("Lo split deve stare dentro la lezione: inizio Zoom < fine mattina < inizio pomeriggio < fine Zoom.")

        source_segments = self._query_repository.get_lesson_source_segments(lesson_id)
        if not source_segments:
            source_segments = _extract_source_segments_from_lesson(lesson)
        if not source_segments:
            raise ValueError("Questa lezione non ha segmenti grezzi sufficienti per lo split.")

        first_sources = self._split_source_segments(source_segments, meeting_start, first_end, "1")
        second_sources = self._split_source_segments(source_segments, second_start, meeting_end, "2")
        if not first_sources or not second_sources:
            raise ValueError("Lo split produrrebbe una delle due lezioni senza segmenti: correggi gli orari.")

        name_alias_map, email_alias_map = _load_identity_alias_maps(self._identity_alias_repository)
        first_effective_start = self._clamp_start(effective_start, meeting_start, first_end)
        first_effective_end = first_end
        first_break = self._midpoint(first_effective_start, first_effective_end)
        second_effective_start = second_start
        second_effective_end = meeting_end
        second_break = self._midpoint(second_effective_start, second_effective_end)

        first_lesson = self._build_split_lesson(
            lesson,
            part="1",
            source_segments=first_sources,
            meeting_start=meeting_start,
            meeting_end=first_end,
            effective_start=first_effective_start,
            break_point=first_break,
            effective_end=first_effective_end,
            name_alias_map=name_alias_map,
            email_alias_map=email_alias_map,
        )
        second_lesson = self._build_split_lesson(
            lesson,
            part="2",
            source_segments=second_sources,
            meeting_start=second_start,
            meeting_end=meeting_end,
            effective_start=second_effective_start,
            break_point=second_break,
            effective_end=second_effective_end,
            name_alias_map=name_alias_map,
            email_alias_map=email_alias_map,
        )
        return self._mutation_repository.split_lesson(
            lesson.id,
            first_lesson,
            first_sources,
            second_lesson,
            second_sources,
        )

    def _validate_split_allowed(self, lesson: DraftLessonView) -> None:
        if lesson.status != "draft":
            raise ValueError("Lo split e' consentito solo su lezioni draft.")
        if lesson.is_ignored:
            raise ValueError("Lo split non e' consentito su lezioni ignorate.")
        if lesson.review_actions:
            raise ValueError("Lo split e' consentito solo prima di qualsiasi correzione.")

    def _split_source_segments(
        self,
        source_segments: list[DraftLessonSourceSegment],
        window_start: datetime,
        window_end: datetime,
        part: str,
    ) -> list[DraftLessonSourceSegment]:
        result: list[DraftLessonSourceSegment] = []
        for segment in source_segments:
            segment_start = _coerce_segment_datetime(segment.join_time, window_start.tzinfo)
            segment_end = _coerce_segment_datetime(segment.leave_time, window_start.tzinfo)
            clipped_start = max(segment_start, window_start)
            clipped_end = min(segment_end, window_end)
            if clipped_end <= clipped_start:
                continue
            metadata = dict(segment.metadata or {})
            metadata["split_part"] = part
            result.append(
                DraftLessonSourceSegment(
                    observed_full_name=segment.observed_full_name,
                    observed_email=segment.observed_email,
                    join_time=clipped_start.isoformat(),
                    leave_time=clipped_end.isoformat(),
                    metadata=metadata,
                )
            )
        return result

    def _build_split_lesson(
        self,
        lesson: DraftLessonView,
        *,
        part: str,
        source_segments: list[DraftLessonSourceSegment],
        meeting_start: datetime,
        meeting_end: datetime,
        effective_start: datetime,
        break_point: datetime,
        effective_end: datetime,
        name_alias_map: dict[str, AttendanceIdentityAlias],
        email_alias_map: dict[str, AttendanceIdentityAlias],
    ) -> LessonDraft:
        participants = self._build_participants_from_sources(
            source_segments,
            effective_start=effective_start,
            break_point=break_point,
            effective_end=effective_end,
            threshold=lesson.threshold_ratio,
            name_alias_map=name_alias_map,
            email_alias_map=email_alias_map,
        )
        diagnostics = dict(lesson.diagnostics or {})
        diagnostics["split_from_lesson_id"] = lesson.id
        diagnostics["split_part"] = part
        diagnostics["split_created_from"] = {
            "source_meeting_id": lesson.source_meeting_id,
            "meeting_start_at": lesson.meeting_start_at,
            "meeting_end_at": lesson.meeting_end_at,
        }
        diagnostics["meeting_start"] = meeting_start.isoformat()
        diagnostics["meeting_end"] = meeting_end.isoformat()
        diagnostics["effective_start"] = effective_start.isoformat()
        diagnostics["break_point"] = break_point.isoformat()
        diagnostics["effective_end"] = effective_end.isoformat()
        diagnostics["break_source"] = "split_midpoint"
        diagnostics["effective_start_source"] = "split"
        diagnostics["effective_end_source"] = "split"
        diagnostics["suggested_effective_start"] = None
        diagnostics["suggested_effective_end"] = None
        diagnostics["suggestion_confidence"] = None
        diagnostics["trim_start_minutes"] = 0.0
        diagnostics["trim_end_minutes"] = 0.0
        diagnostics.pop("review_action_baseline", None)
        diagnostics["timeline"] = self._filter_timeline(diagnostics.get("timeline"), meeting_start, meeting_end)
        diagnostics["peak_active_count"] = max(
            [int(point.get("active_count") or 0) for point in diagnostics["timeline"] if isinstance(point, dict)] or [0]
        )
        diagnostics["participant_count"] = len(participants)
        return LessonDraft(
            source_system="zoom",
            source_meeting_id=f"{lesson.source_meeting_id}#split-{part}",
            course_name=lesson.course_name,
            lesson_date=lesson.lesson_date,
            meeting_start_at=meeting_start.isoformat(),
            meeting_end_at=meeting_end.isoformat(),
            effective_start_at=effective_start.isoformat(),
            break_point_at=break_point.isoformat(),
            effective_end_at=effective_end.isoformat(),
            threshold_ratio=lesson.threshold_ratio,
            break_source="split_midpoint",
            effective_start_source="split",
            effective_end_source="split",
            warnings=[*lesson.warnings, f"Split parte {part} da lesson #{lesson.id}"],
            diagnostics=diagnostics,
            participants=participants,
        )

    def _build_participants_from_sources(
        self,
        source_segments: list[DraftLessonSourceSegment],
        *,
        effective_start: datetime,
        break_point: datetime,
        effective_end: datetime,
        threshold: float,
        name_alias_map: dict[str, AttendanceIdentityAlias],
        email_alias_map: dict[str, AttendanceIdentityAlias],
    ) -> list[LessonParticipantDraft]:
        aggregated = _aggregate_source_segments_by_final_identity(
            source_segments,
            effective_start=effective_start,
            break_point=break_point,
            effective_end=effective_end,
            threshold=threshold,
            name_alias_map=name_alias_map,
            email_alias_map=email_alias_map,
            forced_identity_pairs=set(),
            forced_canonical_full_name=None,
            forced_canonical_email=None,
        )
        source_groups = self._group_identity_sources(source_segments, name_alias_map, email_alias_map)
        participants: list[LessonParticipantDraft] = []
        for participant_key, record in aggregated.items():
            identity_sources = source_groups.get(participant_key, [])
            raw_full_name = self._pick_raw_name(identity_sources, record["canonical_full_name"])
            first_name, last_name = _split_full_name(record["canonical_full_name"])
            metadata = {
                "first_name": first_name,
                "last_name": last_name,
                "segments": record["segments"],
                "identity_sources": identity_sources,
                "canonicalized_by_identity_alias": raw_full_name != record["canonical_full_name"],
            }
            participants.append(
                LessonParticipantDraft(
                    participant_key=participant_key,
                    canonical_full_name=record["canonical_full_name"],
                    raw_full_name=raw_full_name,
                    email=record["canonical_email"],
                    segment_count=record["segment_count"],
                    minutes_first_half=record["minutes_first_half"],
                    minutes_second_half=record["minutes_second_half"],
                    duration_first_half=record["duration_first_half"],
                    duration_second_half=record["duration_second_half"],
                    total_minutes=record["total_minutes"],
                    calculated_presence_status=record["calculated_presence_status"],
                    final_presence_status=record["calculated_presence_status"],
                    flags=[],
                    metadata=metadata,
                )
            )
        return sorted(participants, key=lambda item: item.canonical_full_name.lower())

    def _group_identity_sources(
        self,
        source_segments: list[DraftLessonSourceSegment],
        name_alias_map: dict[str, AttendanceIdentityAlias],
        email_alias_map: dict[str, AttendanceIdentityAlias],
    ) -> dict[str, list[dict]]:
        grouped: dict[str, dict[tuple[str, str], dict]] = {}
        for segment in source_segments:
            canonical_full_name, canonical_email = _apply_identity_alias_maps(
                segment.observed_full_name,
                segment.observed_email,
                name_alias_map,
                email_alias_map,
            )
            participant_key = (canonical_email or "").strip().lower() or canonical_full_name.lower()
            raw_name = (segment.observed_full_name or "").strip()
            raw_email = (segment.observed_email or "").strip()
            source_key = (raw_name.casefold(), raw_email.casefold())
            entry = grouped.setdefault(participant_key, {}).setdefault(
                source_key,
                {
                    "raw_full_name": raw_name,
                    "email": raw_email,
                    "segments": [],
                },
            )
            entry["segments"].append([segment.join_time, segment.leave_time])
        return {
            participant_key: list(sources.values())
            for participant_key, sources in grouped.items()
        }

    def _pick_raw_name(self, identity_sources: list[dict], fallback: str) -> str:
        names = [str(source.get("raw_full_name") or "").strip() for source in identity_sources]
        names = [name for name in names if name]
        return max(names, key=len) if names else fallback

    def _filter_timeline(self, timeline, window_start: datetime, window_end: datetime) -> list[dict]:
        if not isinstance(timeline, list):
            return []
        filtered = []
        for point in timeline:
            if not isinstance(point, dict):
                continue
            timestamp = point.get("timestamp")
            if not isinstance(timestamp, str):
                continue
            try:
                point_time = _coerce_segment_datetime(timestamp, window_start.tzinfo)
            except ValueError:
                continue
            if window_start <= point_time <= window_end:
                filtered.append({
                    "timestamp": point_time.isoformat(),
                    "active_count": int(point.get("active_count") or 0),
                })
        return filtered

    def _clamp_start(self, value: datetime, minimum: datetime, maximum: datetime) -> datetime:
        if value <= minimum or value >= maximum:
            return minimum
        return value

    def _midpoint(self, start: datetime, end: datetime) -> datetime:
        return start + (end - start) / 2


class AttendanceCourseConfigService:
    """Manage lightweight course configuration used by school reports."""

    def __init__(self, mutation_repository: AttendanceDraftMutationRepository) -> None:
        self._mutation_repository = mutation_repository

    def set_expected_lessons_count(
        self,
        course_name: str,
        expected_lessons_count: int | None,
    ) -> None:
        normalized_course_name = " ".join((course_name or "").strip().split())
        if not normalized_course_name:
            raise ValueError("course_name is required")
        if expected_lessons_count is not None and expected_lessons_count <= 0:
            raise ValueError("expected_lessons_count must be positive")
        self._mutation_repository.upsert_course_expected_lessons(
            normalized_course_name,
            expected_lessons_count,
        )


class AttendanceManualPresenceService:
    """Import already-aggregated attendance rows into the canonical model."""

    _ALLOWED_STATUSES = {"presente", "prima_meta", "seconda_meta", "assente"}
    _ALLOWED_SOURCES = {"manual", "qr_form", "csv_manual"}

    def __init__(
        self,
        mutation_repository: AttendanceDraftMutationRepository,
        identity_alias_repository: AttendanceIdentityAliasRepository | None = None,
    ) -> None:
        self._mutation_repository = mutation_repository
        self._identity_alias_repository = identity_alias_repository

    def import_manual_presence(
        self,
        *,
        lesson_id: int | None = None,
        course_name: str,
        lesson_date: str,
        presence_source: str = "manual",
        created_by: str | None = None,
        records: list[dict],
    ) -> ManualPresenceImportResult:
        normalized_course_name = " ".join((course_name or "").strip().split())
        normalized_lesson_date = (lesson_date or "").strip()
        if lesson_id is None and not normalized_course_name:
            raise ValueError("course_name is required")
        if lesson_id is None and not normalized_lesson_date:
            raise ValueError("lesson_date is required")
        if normalized_lesson_date:
            try:
                date.fromisoformat(normalized_lesson_date)
            except ValueError as exc:
                raise ValueError("lesson_date must be YYYY-MM-DD") from exc
        if presence_source not in self._ALLOWED_SOURCES:
            raise ValueError(f"Unsupported presence_source: {presence_source}")

        name_alias_map, email_alias_map = _load_identity_alias_maps(self._identity_alias_repository)
        normalized_records: list[ManualPresenceRecordCreate] = []
        seen_keys: set[str] = set()
        for record in records:
            raw_name = " ".join(str(record.get("full_name") or "").strip().split())
            raw_email = str(record.get("email") or "").strip() or None
            status = str(record.get("presence_status") or "").strip()
            if not raw_name:
                continue
            if status not in self._ALLOWED_STATUSES:
                raise ValueError(f"Unsupported presence status: {status}")
            canonical_full_name, canonical_email = _apply_identity_alias_maps(
                raw_name,
                raw_email,
                name_alias_map,
                email_alias_map,
            )
            dedupe_key = (canonical_email or "").strip().lower() or canonical_full_name.lower()
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            normalized_records.append(
                ManualPresenceRecordCreate(
                    full_name=canonical_full_name,
                    email=canonical_email,
                    presence_status=status,
                )
            )

        if not normalized_records:
            raise ValueError("At least one valid manual presence record is required")

        return self._mutation_repository.upsert_manual_presence_import(
            ManualPresenceImportCreate(
                lesson_id=lesson_id,
                course_name=normalized_course_name,
                lesson_date=normalized_lesson_date,
                presence_source=presence_source,
                created_by=created_by,
                records=normalized_records,
            )
        )


class AttendanceIdentityAliasService:
    """Manage persistent identity aliases used by future imports."""

    def __init__(self, repository: AttendanceIdentityAliasRepository) -> None:
        self._repository = repository

    def create_alias(
        self,
        *,
        canonical_full_name: str,
        canonical_email: str | None = None,
        alias_value: str,
        alias_type: str = "full_name",
        created_by: str | None = None,
        notes: str | None = None,
    ) -> AttendanceIdentityAlias:
        canonical = " ".join((canonical_full_name or "").strip().split())
        alias = " ".join((alias_value or "").strip().split()) if alias_type == "full_name" else (alias_value or "").strip()
        if not canonical:
            raise ValueError("canonical_full_name is required")
        if not alias:
            raise ValueError("alias_value is required")
        if alias_type not in {"full_name", "email"}:
            raise ValueError("alias_type must be full_name or email")
        if alias_type == "full_name" and canonical.casefold() == alias.casefold():
            raise ValueError("canonical_full_name and alias_full_name must differ")
        return self._repository.create_alias(
            canonical_full_name=canonical,
            canonical_email=(canonical_email or "").strip() or None,
            alias_value=alias,
            alias_type=alias_type,
            created_by=created_by,
            notes=notes,
        )

    def merge_participants(
        self,
        *,
        canonical_full_name: str,
        canonical_email: str | None,
        alias_full_name: str,
        alias_email: str | None,
        created_by: str | None = None,
        notes: str | None = None,
    ) -> AttendanceIdentityAlias:
        same_name = canonical_full_name.strip().casefold() == alias_full_name.strip().casefold()
        canonical_email_norm = (canonical_email or "").strip().casefold()
        alias_email_norm = (alias_email or "").strip().casefold()
        if same_name and canonical_email_norm and alias_email_norm and canonical_email_norm != alias_email_norm:
            return self.create_alias(
                canonical_full_name=canonical_full_name,
                canonical_email=canonical_email,
                alias_value=alias_email,
                alias_type="email",
                created_by=created_by,
                notes=notes,
            )
        return self.create_alias(
            canonical_full_name=canonical_full_name,
            canonical_email=canonical_email,
            alias_value=alias_full_name,
            alias_type="full_name",
            created_by=created_by,
            notes=notes,
        )

    def bootstrap_from_legacy_rules(self, path: str | None = None) -> int:
        rules = load_identity_rules(path)
        created = 0
        for rule in rules.rules:
            for alias in rule.aliases:
                self._repository.create_alias(
                    canonical_full_name=rule.canonical_full_name,
                    alias_value=alias,
                    alias_type="full_name",
                    created_by="legacy-bootstrap",
                    notes="Importato da attendance/config/identity_rules.json",
                )
                created += 1
        return created

    def deactivate_alias(self, alias_id: int) -> None:
        if alias_id <= 0:
            raise ValueError("alias_id must be positive")
        self._repository.deactivate_alias(alias_id)


class AttendanceLessonIdentityRebuildService:
    """Rebuild one draft lesson participant set using the current identity alias rules."""

    def __init__(
        self,
        query_repository: AttendanceDraftQueryRepository,
        mutation_repository: AttendanceDraftMutationRepository,
        identity_alias_repository: AttendanceIdentityAliasRepository,
    ) -> None:
        self._query_repository = query_repository
        self._mutation_repository = mutation_repository
        self._identity_alias_repository = identity_alias_repository

    def rebuild_lesson_with_current_aliases(self, lesson_id: int) -> DraftLessonView:
        return self.rebuild_lesson_with_current_aliases_and_hint(lesson_id)

    def rebuild_all_lessons_with_current_aliases(self) -> dict:
        lesson_ids = self._query_repository.list_lesson_ids_for_identity_rebuild()
        rebuilt = []
        skipped = []
        errors = []
        for lesson_id in lesson_ids:
            try:
                before = self._query_repository.get_lesson_detail(lesson_id)
                before_count = len(before.participants)
                after = self.rebuild_lesson_with_current_aliases(lesson_id)
                rebuilt.append(
                    {
                        "lesson_id": lesson_id,
                        "course_name": after.course_name,
                        "lesson_date": after.lesson_date,
                        "before_participants": before_count,
                        "after_participants": len(after.participants),
                    }
                )
            except ValueError as exc:
                skipped.append({"lesson_id": lesson_id, "reason": str(exc)})
            except Exception as exc:
                errors.append({"lesson_id": lesson_id, "reason": str(exc)})
        return {
            "candidate_lessons": len(lesson_ids),
            "rebuilt_lessons": len(rebuilt),
            "skipped_lessons": len(skipped),
            "error_lessons": len(errors),
            "rebuilt": rebuilt,
            "skipped": skipped,
            "errors": errors,
        }

    def rebuild_lesson_with_current_aliases_and_hint(
        self,
        lesson_id: int,
        *,
        canonical_participant_id: int | None = None,
        alias_participant_id: int | None = None,
        forced_canonical_full_name: str | None = None,
        forced_canonical_email: str | None = None,
    ) -> DraftLessonView:
        lesson = self._query_repository.get_lesson_detail(lesson_id)
        if not lesson.participants:
            return lesson
        source_segments = self._query_repository.get_lesson_source_segments(lesson_id)
        if not source_segments:
            source_segments = _extract_source_segments_from_lesson(lesson)
            if not source_segments:
                raise ValueError("Questa lezione non ha segmenti grezzi sufficienti per il re-merge identità.")
            self._mutation_repository.ensure_lesson_source_segments(lesson.id, source_segments)
            source_segments = self._query_repository.get_lesson_source_segments(lesson_id) or source_segments

        name_alias_map, email_alias_map = _load_identity_alias_maps(self._identity_alias_repository)
        effective_start = datetime.fromisoformat(lesson.effective_start_at)
        effective_end = datetime.fromisoformat(lesson.effective_end_at)
        break_point = datetime.fromisoformat(lesson.break_point_at) if lesson.break_point_at else None
        break_point = self._resolve_break_point(effective_start, effective_end, break_point)

        forced_merge = None
        if canonical_participant_id is not None and alias_participant_id is not None:
            forced_merge = {
                "canonical_participant_id": canonical_participant_id,
                "alias_participant_id": alias_participant_id,
                "canonical_full_name": forced_canonical_full_name or "",
                "canonical_email": forced_canonical_email or "",
            }

        aggregated = _aggregate_source_segments_by_final_identity(
            source_segments,
            effective_start=effective_start,
            break_point=break_point,
            effective_end=effective_end,
            threshold=lesson.threshold_ratio,
            name_alias_map=name_alias_map,
            email_alias_map=email_alias_map,
            forced_identity_pairs=self._build_forced_identity_pairs(lesson, forced_merge),
            forced_canonical_full_name=(forced_merge or {}).get("canonical_full_name"),
            forced_canonical_email=(forced_merge or {}).get("canonical_email"),
        )
        action_sequence = sorted(lesson.review_actions, key=lambda item: (item.created_at, item.id))

        old_to_target_key: dict[int, str] = {}
        grouped_participants: dict[str, list] = defaultdict(list)
        for participant in lesson.participants:
            rebuilt_key = self._participant_target_key(
                participant,
                name_alias_map,
                email_alias_map,
                forced_merge=forced_merge,
            )
            old_to_target_key[participant.id] = rebuilt_key
            grouped_participants[rebuilt_key].append(participant)

        remapped_overrides = self._build_manual_override_map(action_sequence, lesson.participants, old_to_target_key)

        rebuilt_participants: list[dict] = []
        missing_target_keys: list[str] = []
        for target_key, participants in grouped_participants.items():
            record = aggregated.get(target_key)
            if record is None:
                missing_target_keys.append(target_key)
                continue
            survivor = min(participants, key=lambda participant: participant.id)
            obsolete_ids = [participant.id for participant in participants if participant.id != survivor.id]
            canonical_full_name = record["canonical_full_name"]
            raw_full_name = self._pick_raw_full_name(participants)
            canonical_email = (record["canonical_email"] or "").strip() or None
            calculated = record["calculated_presence_status"]
            manual_override_presence_status = remapped_overrides.get(survivor.id)
            final = manual_override_presence_status or calculated
            identity_sources = self._merge_identity_sources_from_participants(participants)
            first_name, last_name = _split_full_name(canonical_full_name)
            metadata = dict(survivor.metadata or {})
            metadata["segments"] = record["segments"]
            metadata["identity_sources"] = identity_sources
            metadata["first_name"] = first_name
            metadata["last_name"] = last_name
            metadata["canonicalized_by_identity_alias"] = canonical_full_name != (raw_full_name or canonical_full_name)
            metadata["rebuilt_from_identity_aliases"] = True
            rebuilt_participants.append(
                {
                    "survivor_id": survivor.id,
                    "obsolete_ids": obsolete_ids,
                    "participant_key": target_key,
                    "canonical_full_name": canonical_full_name,
                    "raw_full_name": raw_full_name,
                    "email": canonical_email,
                    "segment_count": record["segment_count"],
                    "minutes_first_half": record["minutes_first_half"],
                    "minutes_second_half": record["minutes_second_half"],
                    "duration_first_half": record["duration_first_half"],
                    "duration_second_half": record["duration_second_half"],
                    "total_minutes": record["total_minutes"],
                    "calculated_presence_status": calculated,
                    "manual_override_presence_status": manual_override_presence_status,
                    "final_presence_status": final,
                    "flags": sorted({flag for participant in participants for flag in participant.flags}),
                    "metadata": metadata,
                }
            )

        if missing_target_keys:
            raise ValueError(
                "Impossibile ricostruire completamente la lezione dopo l'unione: "
                f"mancano record aggregati per {len(missing_target_keys)} identità."
            )

        diagnostics = dict(lesson.diagnostics or {})
        diagnostics["remerged_from_identity_aliases"] = True
        diagnostics["remerged_at"] = datetime.now().isoformat()
        diagnostics["remerged_participants_count"] = len(rebuilt_participants)
        self._mutation_repository.replace_lesson_participants_after_identity_rebuild(
            lesson.id,
            diagnostics=diagnostics,
            participants=rebuilt_participants,
        )
        return self._query_repository.get_lesson_detail(lesson_id)

    def _participant_target_key(
        self,
        participant,
        name_alias_map: dict[str, AttendanceIdentityAlias],
        email_alias_map: dict[str, AttendanceIdentityAlias],
        *,
        forced_merge: dict | None = None,
    ) -> str:
        if forced_merge and participant.id in {forced_merge["canonical_participant_id"], forced_merge["alias_participant_id"]}:
            canonical_full_name = forced_merge["canonical_full_name"] or participant.canonical_full_name
            canonical_email = forced_merge["canonical_email"] or participant.email or None
            return (canonical_email or "").strip().lower() or canonical_full_name.lower()
        primary_source = _get_identity_sources(participant)[0]
        source_name = str(primary_source.get("raw_full_name") or participant.raw_full_name or participant.canonical_full_name).strip()
        source_email = str(primary_source.get("email") or participant.email or "").strip()
        canonical_full_name, canonical_email = _apply_identity_alias_maps(
            source_name,
            source_email or None,
            name_alias_map,
            email_alias_map,
        )
        return (canonical_email or "").strip().lower() or canonical_full_name.lower()

    def _build_forced_identity_pairs(self, lesson: DraftLessonView, forced_merge: dict | None) -> set[tuple[str, str]]:
        if not forced_merge:
            return set()
        pairs: set[tuple[str, str]] = set()
        for participant in lesson.participants:
            if participant.id not in {forced_merge["canonical_participant_id"], forced_merge["alias_participant_id"]}:
                continue
            for source in _get_identity_sources(participant):
                source_name = str(source.get("raw_full_name") or participant.raw_full_name or participant.canonical_full_name).strip()
                source_email = str(source.get("email") or participant.email or "").strip()
                pairs.add((source_name.casefold(), source_email.casefold()))
        return pairs

    def _build_manual_override_map(self, action_sequence, participants, old_to_target_key: dict[int, str]) -> dict[int, str | None]:
        target_to_survivor = {
            old_to_target_key[participant.id]: min(
                participant_group.id
                for participant_group in participants
                if old_to_target_key[participant_group.id] == old_to_target_key[participant.id]
            )
            for participant in participants
        }
        overrides = {}
        for action in action_sequence:
            if action.participant_id is None:
                continue
            target_key = old_to_target_key.get(action.participant_id)
            if target_key is None:
                continue
            survivor_id = target_to_survivor[target_key]
            if action.action_type == "set_manual_presence_status":
                overrides[survivor_id] = str((action.payload or {}).get("presence_status"))
            elif action.action_type == "clear_manual_presence_status":
                overrides[survivor_id] = None
        return overrides

    def _pick_raw_full_name(self, participants) -> str:
        candidates = [((participant.raw_full_name or "").strip()) for participant in participants]
        candidates = [candidate for candidate in candidates if candidate]
        if not candidates:
            return participants[0].canonical_full_name
        return max(candidates, key=len)

    def _merge_identity_sources_from_participants(self, participants) -> list[dict]:
        merged_sources: list[dict] = []
        for participant in participants:
            for source in _get_identity_sources(participant):
                raw_full_name = str(source.get("raw_full_name") or participant.raw_full_name or participant.canonical_full_name).strip()
                email = str(source.get("email") or participant.email or "").strip()
                segments = list(source.get("segments") or [])
                merged_sources.append(
                    {
                        "raw_full_name": raw_full_name,
                        "email": email,
                        "segments": segments,
                    }
                )
        return _dedupe_identity_sources(merged_sources)

    def _extract_source_segments_from_lesson(self, lesson: DraftLessonView) -> list[DraftLessonSourceSegment]:
        source_segments: list[DraftLessonSourceSegment] = []
        for participant in lesson.participants:
            for source in _get_identity_sources(participant):
                source_name = str(source.get("raw_full_name") or participant.raw_full_name or participant.canonical_full_name).strip()
                source_email = str(source.get("email") or participant.email or "").strip() or None
                for segment in list(source.get("segments") or []):
                    if not isinstance(segment, (list, tuple)) or len(segment) != 2:
                        continue
                    source_segments.append(
                        DraftLessonSourceSegment(
                            observed_full_name=source_name,
                            observed_email=source_email,
                            join_time=str(segment[0]),
                            leave_time=str(segment[1]),
                            metadata={},
                        )
                    )
        return source_segments

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


def _load_identity_alias_maps(
    identity_alias_repository: AttendanceIdentityAliasRepository | None,
) -> tuple[dict[str, AttendanceIdentityAlias], dict[str, AttendanceIdentityAlias]]:
    if identity_alias_repository is None:
        return {}, {}
    aliases = identity_alias_repository.list_active_aliases()
    name_alias_map = {
        _normalize_identity_key(alias.alias_value): alias
        for alias in aliases
        if alias.alias_type == "full_name"
    }
    email_alias_map = {
        (alias.alias_value or "").strip().casefold(): alias
        for alias in aliases
        if alias.alias_type == "email"
    }
    return name_alias_map, email_alias_map


def _apply_identity_alias_maps(
    full_name: str,
    email: str | None,
    name_alias_map: dict[str, AttendanceIdentityAlias],
    email_alias_map: dict[str, AttendanceIdentityAlias],
) -> tuple[str, str | None]:
    normalized_email = (email or "").strip().casefold()
    if normalized_email and normalized_email in email_alias_map:
        alias = email_alias_map[normalized_email]
        return alias.canonical_full_name, alias.canonical_email or email
    normalized_name = _normalize_identity_key(full_name)
    if normalized_name in name_alias_map:
        alias = name_alias_map[normalized_name]
        return alias.canonical_full_name, alias.canonical_email or email
    return full_name, email


def _normalize_identity_key(value: str) -> str:
    return " ".join((value or "").strip().casefold().split())


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in (full_name or "").split(" ") if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _merge_identity_sources(
    left_sources,
    right_sources,
    *,
    fallback_left_name: str,
    fallback_left_email: str | None,
    fallback_left_segments,
    fallback_right_name: str,
    fallback_right_email: str | None,
    fallback_right_segments,
) -> list[dict]:
    merged = []
    merged.extend(left_sources or [{
        "raw_full_name": fallback_left_name,
        "email": fallback_left_email or "",
        "segments": fallback_left_segments,
    }])
    merged.extend(right_sources or [{
        "raw_full_name": fallback_right_name,
        "email": fallback_right_email or "",
        "segments": fallback_right_segments,
    }])
    return _dedupe_identity_sources(merged)


def _get_identity_sources(participant) -> list[dict]:
    sources = participant.metadata.get("identity_sources")
    if isinstance(sources, list) and sources:
        return [dict(source) for source in sources if isinstance(source, dict)]
    raw_full_name = (participant.raw_full_name or participant.canonical_full_name).strip()
    return [{
        "raw_full_name": raw_full_name,
        "email": participant.email or "",
        "segments": list(participant.metadata.get("segments") or []),
    }]


def _dedupe_identity_sources(sources: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    for source in sources:
        raw_full_name = str(source.get("raw_full_name") or "").strip()
        email = str(source.get("email") or "").strip()
        key = (raw_full_name.casefold(), email.casefold())
        entry = merged.setdefault(
            key,
            {
                "raw_full_name": raw_full_name,
                "email": email,
                "segments": [],
            },
        )
        entry["segments"].extend(list(source.get("segments") or []))
    return list(merged.values())


def _identity_sources_have_any_segments(identity_sources: list[dict]) -> bool:
    return any(
        isinstance(segment, (list, tuple)) and len(segment) == 2
        for source in identity_sources
        for segment in list(source.get("segments") or [])
    )


def _aggregate_identity_sources_as_one(
    identity_sources: list[dict],
    *,
    canonical_full_name: str,
    canonical_email: str | None,
    effective_start_at: str,
    break_point_at: str,
    effective_end_at: str,
    threshold: float,
) -> dict:
    source_segments = [
        DraftLessonSourceSegment(
            observed_full_name=str(source.get("raw_full_name") or canonical_full_name).strip(),
            observed_email=str(source.get("email") or canonical_email or "").strip() or None,
            join_time=str(segment[0]),
            leave_time=str(segment[1]),
            metadata={},
        )
        for source in identity_sources
        for segment in list(source.get("segments") or [])
        if isinstance(segment, (list, tuple)) and len(segment) == 2
    ]
    aggregated = _aggregate_source_segments_by_final_identity(
        source_segments,
        effective_start=datetime.fromisoformat(effective_start_at),
        break_point=datetime.fromisoformat(break_point_at),
        effective_end=datetime.fromisoformat(effective_end_at),
        threshold=threshold,
        name_alias_map={},
        email_alias_map={},
        forced_identity_pairs={
            (
                (segment.observed_full_name or "").strip().casefold(),
                ((segment.observed_email or "").strip().casefold()),
            )
            for segment in source_segments
        },
        forced_canonical_full_name=canonical_full_name,
        forced_canonical_email=canonical_email,
    )
    key = (canonical_email or "").strip().lower() or canonical_full_name.lower()
    return aggregated[key]


def _aggregate_source_segments_by_final_identity(
    source_segments: list[DraftLessonSourceSegment],
    *,
    effective_start: datetime,
    break_point: datetime,
    effective_end: datetime,
    threshold: float,
    name_alias_map: dict[str, AttendanceIdentityAlias],
    email_alias_map: dict[str, AttendanceIdentityAlias],
    forced_identity_pairs: set[tuple[str, str]],
    forced_canonical_full_name: str | None,
    forced_canonical_email: str | None,
) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    target_tz = effective_start.tzinfo
    for source_segment in source_segments:
        source_name = (source_segment.observed_full_name or "").strip()
        source_email = (source_segment.observed_email or "").strip()
        if (source_name.casefold(), source_email.casefold()) in forced_identity_pairs:
            canonical_full_name = forced_canonical_full_name or source_name
            canonical_email = forced_canonical_email or source_email or None
        else:
            canonical_full_name, canonical_email = _apply_identity_alias_maps(
                source_name,
                source_email or None,
                name_alias_map,
                email_alias_map,
            )
        target_key = (canonical_email or "").strip().lower() or canonical_full_name.lower()
        bucket = grouped.setdefault(
            target_key,
            {
                "canonical_full_name": canonical_full_name,
                "canonical_email": canonical_email,
                "intervals": [],
            },
        )
        bucket["intervals"].append(
            (
                _coerce_segment_datetime(source_segment.join_time, target_tz),
                _coerce_segment_datetime(source_segment.leave_time, target_tz),
            )
        )

    results: dict[str, dict] = {}
    for target_key, bucket in grouped.items():
        merged_intervals = _merge_overlapping_intervals(bucket["intervals"])
        minutes_first_half = _round1(sum(_overlap_minutes(start, end, effective_start, break_point) for start, end in merged_intervals))
        minutes_second_half = _round1(sum(_overlap_minutes(start, end, break_point, effective_end) for start, end in merged_intervals))
        duration_first_half = _round1((break_point - effective_start).total_seconds() / 60)
        duration_second_half = _round1((effective_end - break_point).total_seconds() / 60)
        calculated_presence_status = determine_presence_status(
            minutes_first_half=minutes_first_half,
            minutes_second_half=minutes_second_half,
            duration_first_half=duration_first_half,
            duration_second_half=duration_second_half,
            threshold=threshold,
        )
        results[target_key] = {
            "canonical_full_name": bucket["canonical_full_name"],
            "canonical_email": bucket["canonical_email"],
            "segment_count": len(merged_intervals),
            "minutes_first_half": minutes_first_half,
            "minutes_second_half": minutes_second_half,
            "duration_first_half": duration_first_half,
            "duration_second_half": duration_second_half,
            "total_minutes": _round1(minutes_first_half + minutes_second_half),
            "calculated_presence_status": calculated_presence_status,
            "segments": [(start.isoformat(), end.isoformat()) for start, end in merged_intervals],
        }
    return results


def _extract_source_segments_from_lesson(lesson: DraftLessonView) -> list[DraftLessonSourceSegment]:
    source_segments: list[DraftLessonSourceSegment] = []
    for participant in lesson.participants:
        for source in _get_identity_sources(participant):
            source_name = str(source.get("raw_full_name") or participant.raw_full_name or participant.canonical_full_name).strip()
            source_email = str(source.get("email") or participant.email or "").strip() or None
            for segment in list(source.get("segments") or []):
                if not isinstance(segment, (list, tuple)) or len(segment) != 2:
                    continue
                source_segments.append(
                    DraftLessonSourceSegment(
                        observed_full_name=source_name,
                        observed_email=source_email,
                        join_time=str(segment[0]),
                        leave_time=str(segment[1]),
                        metadata={},
                    )
                )
    return source_segments


def _merge_overlapping_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not intervals:
        return []
    max_gap = timedelta(minutes=MAX_RECONNECT_GAP_MINUTES)
    ordered = sorted(intervals, key=lambda item: (item[0], item[1]))
    merged: list[list[datetime]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        last = merged[-1]
        if start <= last[1] + max_gap:
            if end > last[1]:
                last[1] = end
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _overlap_minutes(segment_start: datetime, segment_end: datetime, range_start: datetime, range_end: datetime) -> float:
    start = max(segment_start, range_start)
    end = min(segment_end, range_end)
    return max(0.0, (end - start).total_seconds() / 60)


def _coerce_segment_datetime(value: str, target_tz) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None and target_tz is not None:
        return parsed.replace(tzinfo=target_tz)
    if parsed.tzinfo is not None and target_tz is None:
        return parsed.replace(tzinfo=None)
    return parsed


def _round1(value: float) -> float:
    return round(value, 1)
