"""Scope progress records to a Prolific submission within one assignment URL."""

from __future__ import annotations

import hashlib

from app.prolific import PROLIFIC_PROFILE_KEY
from app.storage.base import ProgressStorage, SavedProgress


class ProlificScopedProgressStorage:
    """Give each Prolific submission its own row while retaining the URL token.

    ``session_id`` remains the assignment token in the URL.  The physical key
    adds a short digest of the Prolific study and submission IDs, allowing a
    replacement participant to use the same URL without overwriting or being
    blocked by the previous participant's record.
    """

    def __init__(
        self,
        backend: ProgressStorage,
        *,
        assignment_session_id: str,
        study_id: str,
        submission_id: str,
    ) -> None:
        self.backend = backend
        self.assignment_session_id = assignment_session_id
        self.study_id = study_id
        self.submission_id = submission_id
        digest = hashlib.sha256(
            f"{study_id}\x00{submission_id}".encode("utf-8")
        ).hexdigest()[:12]
        self.scoped_session_id = f"{assignment_session_id}--p-{digest}"
        self._active_key = self.scoped_session_id

    def _use_legacy_record_for_same_submission(
        self, record: SavedProgress | None
    ) -> bool:
        if record is None or not isinstance(record.profile, dict):
            return False
        metadata = record.profile.get(PROLIFIC_PROFILE_KEY)
        return (
            isinstance(metadata, dict)
            and metadata.get("submission_id") == self.submission_id
        )

    def list_progress(self) -> tuple[SavedProgress, ...]:
        return self.backend.list_progress()

    def load_progress(self, session_id: str) -> SavedProgress | None:
        if session_id != self.assignment_session_id:
            return self.backend.load_progress(session_id)
        scoped = self.backend.load_progress(self.scoped_session_id)
        if scoped is not None:
            self._active_key = self.scoped_session_id
            return scoped
        legacy = self.backend.load_progress(self.assignment_session_id)
        if legacy is not None and self._use_legacy_record_for_same_submission(legacy):
            self._active_key = self.assignment_session_id
            return legacy
        self._active_key = self.scoped_session_id
        return None

    def save_progress(self, *, session_id: str, **kwargs: object) -> SavedProgress:
        key = self._active_key if session_id == self.assignment_session_id else session_id
        return self.backend.save_progress(session_id=key, **kwargs)

    def submit_response(self, *, session_id: str, **kwargs: object) -> SavedProgress:
        key = self._active_key if session_id == self.assignment_session_id else session_id
        return self.backend.submit_response(session_id=key, **kwargs)
