"""Write-through shadow storage used during migration rehearsals."""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.storage.base import ProgressStorage, SavedProgress

LOGGER = logging.getLogger(__name__)


class ShadowProgressStorage:
    """Keep the primary store authoritative while mirroring writes best-effort."""

    def __init__(self, primary: ProgressStorage, shadow: ProgressStorage) -> None:
        self.primary = primary
        self.shadow = shadow

    def list_progress(self) -> tuple[SavedProgress, ...]:
        return self.primary.list_progress()

    def load_progress(self, session_id: str) -> SavedProgress | None:
        return self.primary.load_progress(session_id)

    def _mirror(self, operation: Callable[[], object], session_id: str) -> None:
        try:
            operation()
        except Exception:
            LOGGER.exception("Supabase shadow write failed for session %s", session_id)

    def save_progress(self, **kwargs: object) -> SavedProgress:
        saved = self.primary.save_progress(**kwargs)  # type: ignore[arg-type]
        self._mirror(lambda: self.shadow.save_progress(**kwargs), saved.session_id)  # type: ignore[arg-type]
        return saved

    def submit_response(self, **kwargs: object) -> SavedProgress:
        saved = self.primary.submit_response(**kwargs)  # type: ignore[arg-type]
        self._mirror(lambda: self.shadow.submit_response(**kwargs), saved.session_id)  # type: ignore[arg-type]
        return saved
