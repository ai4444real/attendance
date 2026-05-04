"""Repository contracts for attendance workflows."""

from __future__ import annotations

from typing import Protocol

from .models import (
    DraftBatchDetail,
    DraftLessonView,
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


class AttendanceDraftQueryRepository(Protocol):
    """Read-only queries for draft attendance imports."""

    def list_batches(self, limit: int = 20) -> list[ImportBatchSummary]:
        """Return recent import batches with lightweight counters."""

    def get_batch_detail(self, batch_id: int) -> DraftBatchDetail:
        """Return one import batch with lightweight lesson summaries."""

    def get_lesson_detail(self, lesson_id: int) -> DraftLessonView:
        """Return one lesson with full participant detail."""
