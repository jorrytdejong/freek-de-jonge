"""Storage contract for resumable participant progress."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class SavedProgress:
    session_id: str
    study_version: str
    is_test: bool
    current_page: str
    profile: dict[str, object] | None
    responses: dict[str, dict[str, object]]
    drafts: dict[str, dict[str, object]]
    status: str
    final_comment: str
    submissions: tuple[dict[str, object], ...]
    created_at: datetime
    updated_at: datetime


class ProgressStorage(Protocol):
    def list_progress(self) -> tuple[SavedProgress, ...]:
        """Return all saved sessions in stable session-ID order."""

    def load_progress(self, session_id: str) -> SavedProgress | None:
        """Return saved state for one anonymous session."""

    def save_progress(
        self,
        *,
        session_id: str,
        study_version: str,
        is_test: bool,
        current_page: str,
        profile: dict[str, object] | None,
        responses: dict[str, dict[str, object]],
        drafts: dict[str, dict[str, object]],
        final_comment: str = "",
        submissions: tuple[dict[str, object], ...] = (),
        now: datetime | None = None,
    ) -> SavedProgress:
        """Atomically create or replace one anonymous session snapshot."""

    def submit_response(
        self,
        *,
        session_id: str,
        study_version: str,
        is_test: bool,
        profile: dict[str, object],
        responses: dict[str, dict[str, object]],
        final_comment: str,
        now: datetime | None = None,
    ) -> SavedProgress:
        """Append one atomic immutable submission event."""
