"""Repository contracts for attendance workflows."""

from __future__ import annotations

from typing import Protocol

from .models import (
    AttendanceIdentityAlias,
    DraftBatchDetail,
    DraftLessonView,
    DraftReviewActionView,
    ImportBatchCreate,
    ImportBatchSummary,
    LessonDraft,
    PersistedDraftImport,
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
        alias_full_name: str,
        created_by: str | None = None,
        notes: str | None = None,
    ) -> AttendanceIdentityAlias:
        """Create or update one active alias rule."""


class AttendanceDraftQueryRepository(Protocol):
    """Read-only queries for draft attendance imports."""

    def list_batches(self, limit: int = 20) -> list[ImportBatchSummary]:
        """Return recent import batches with lightweight counters."""

    def get_batch_detail(self, batch_id: int) -> DraftBatchDetail:
        """Return one import batch with lightweight lesson summaries."""

    def get_lesson_detail(self, lesson_id: int) -> DraftLessonView:
        """Return one lesson with full participant detail."""


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
