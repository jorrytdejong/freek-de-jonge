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
    created_at: datetime
    updated_at: datetime


class ProgressStorage(Protocol):
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
        now: datetime | None = None,
    ) -> SavedProgress:
        """Atomically create or replace one anonymous session snapshot."""
