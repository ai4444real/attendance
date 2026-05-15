"""Repository contracts for attendance workflows."""

from __future__ import annotations

from typing import Protocol

from .models import (
    AttendanceIdentityAlias,
    DraftBatchDetail,
    DraftLessonSourceSegment,
    DraftLessonView,
    DraftReviewActionView,
    ImportBatchCreate,
    ImportBatchSummary,
    LessonDraft,
    ManualPresenceImportCreate,
    ManualPresenceImportResult,
    PersistedDraftImport,
    SkippedDuplicateLesson,
    SplitLessonResult,
)


class AttendanceDraftImportRepository(Protocol):
    """Persistence contract for draft attendance imports."""

    def save_draft_import(
        self,
        batch_data: ImportBatchCreate,
        lessons: list[LessonDraft],
        ) -> PersistedDraftImport:
        """Persist a full normalized draft import and return a summary."""


class AttendanceIdentityAliasRepository(Protocol):
    """Read and write participant identity aliases used during future imports."""

    def list_active_aliases(self) -> list[AttendanceIdentityAlias]:
        """Return active aliases ordered for deterministic application."""

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
        """Create or update one active alias rule."""

    def deactivate_alias(self, alias_id: int) -> None:
        """Deactivate one alias rule without deleting history."""


class AttendanceDraftQueryRepository(Protocol):
    """Read-only queries for draft attendance imports."""

    def list_batches(self, limit: int = 20) -> list[ImportBatchSummary]:
        """Return recent import batches with lightweight counters."""

    def get_batch_detail(self, batch_id: int) -> DraftBatchDetail:
        """Return one import batch with lightweight lesson summaries."""

    def get_lesson_detail(self, lesson_id: int) -> DraftLessonView:
        """Return one lesson with full participant detail."""

    def get_lesson_source_segments(self, lesson_id: int) -> list[DraftLessonSourceSegment]:
        """Return persisted raw/source segments for one lesson."""


class AttendanceReviewActionRepository(Protocol):
    """Write review actions for one draft lesson."""

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
        """Persist one review action and return the created row."""


class AttendanceDraftMutationRepository(Protocol):
    """Update one lesson draft after recomputation."""

    def update_lesson_after_recalculation(
        self,
        lesson: DraftLessonView,
        *,
        threshold_ratio: float,
        effective_start_at: str,
        break_point_at: str | None,
        effective_end_at: str,
        break_source: str,
        effective_start_source: str,
        effective_end_source: str,
        diagnostics: dict,
        participants: list[dict],
    ) -> None:
        """Persist recalculated lesson and participant values."""

    def set_lesson_ignored(self, lesson_id: int, *, is_ignored: bool) -> None:
        """Toggle one lesson between visible and ignored."""

    def set_lesson_status(self, lesson_id: int, *, status: str) -> None:
        """Promote or reopen one lesson draft state."""

    def replace_lesson_participants_after_identity_rebuild(
        self,
        lesson_id: int,
        *,
        diagnostics: dict,
        participants: list[dict],
    ) -> None:
        """Replace one lesson participant set after identity merge and remap review actions."""

    def ensure_lesson_source_segments(
        self,
        lesson_id: int,
        source_segments: list[DraftLessonSourceSegment],
    ) -> int:
        """Persist source segments for one lesson if missing, returning inserted rows."""

    def delete_lesson(self, lesson_id: int) -> None:
        """Delete one lesson and all dependent draft data."""

    def delete_batch(self, batch_id: int) -> None:
        """Delete one import batch and all dependent lessons and draft data."""

    def split_lesson(
        self,
        original_lesson_id: int,
        first_lesson: LessonDraft,
        first_source_segments: list[DraftLessonSourceSegment],
        second_lesson: LessonDraft,
        second_source_segments: list[DraftLessonSourceSegment],
    ) -> SplitLessonResult:
        """Create two replacement draft lessons and delete the original in one transaction."""

    def upsert_course_expected_lessons(
        self,
        course_name: str,
        expected_lessons_count: int | None,
    ) -> None:
        """Create or update the expected lesson count for one course."""

    def upsert_manual_presence_import(
        self,
        import_data: ManualPresenceImportCreate,
    ) -> ManualPresenceImportResult:
        """Create/update one manual lesson presence import in the canonical tables."""
