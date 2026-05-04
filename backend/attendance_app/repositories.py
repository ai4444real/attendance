"""Repository contracts for attendance workflows."""

from __future__ import annotations

from typing import Protocol

from .models import ImportBatch, ImportBatchCreate, LessonDraft, PersistedDraftImport


class AttendanceDraftImportRepository(Protocol):
    """Persistence contract for draft attendance imports."""

    def save_draft_import(
        self,
        batch_data: ImportBatchCreate,
        lessons: list[LessonDraft],
    ) -> PersistedDraftImport:
        """Persist a full normalized draft import and return a summary."""
