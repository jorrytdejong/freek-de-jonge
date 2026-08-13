"""Small, testable Prolific integration helpers.

The study keeps its precomputed assignment token in ``session``.  Prolific adds
three pseudonymous identifiers to that URL.  We retain those identifiers only
inside the raw progress profile so a Taskflow replacement cannot inherit the
previous participant's autosaved answers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

PROLIFIC_PID_PARAM = "PROLIFIC_PID"
PROLIFIC_STUDY_PARAM = "STUDY_ID"
PROLIFIC_SUBMISSION_PARAM = "SESSION_ID"
PROLIFIC_PROFILE_KEY = "_prolific"
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


class ProlificContextError(ValueError):
    """Raised when a required Prolific launch context is absent or malformed."""


@dataclass(frozen=True)
class ProlificContext:
    participant_id: str
    study_id: str
    submission_id: str

    def query_params(self) -> dict[str, str]:
        return {
            PROLIFIC_PID_PARAM: self.participant_id,
            PROLIFIC_STUDY_PARAM: self.study_id,
            PROLIFIC_SUBMISSION_PARAM: self.submission_id,
        }

    def profile_metadata(
        self, *, replaced_submission_ids: tuple[str, ...] = ()
    ) -> dict[str, object]:
        return {
            "participant_id": self.participant_id,
            "study_id": self.study_id,
            "submission_id": self.submission_id,
            "replaced_submission_ids": list(replaced_submission_ids),
        }


def parse_prolific_context(
    query_params: Mapping[str, object], *, required: bool
) -> ProlificContext | None:
    raw_values = {
        key: query_params.get(key)
        for key in (
            PROLIFIC_PID_PARAM,
            PROLIFIC_STUDY_PARAM,
            PROLIFIC_SUBMISSION_PARAM,
        )
    }
    present = {
        key: value for key, value in raw_values.items() if value not in (None, "")
    }
    if not present:
        if required:
            raise ProlificContextError(
                "Open dit onderzoek vanuit je Prolific-deelnemerspagina."
            )
        return None
    if len(present) != len(raw_values):
        raise ProlificContextError("De Prolific-onderzoekslink is niet compleet.")

    normalized: dict[str, str] = {}
    for key, value in raw_values.items():
        if isinstance(value, (list, tuple)):
            value = value[0] if len(value) == 1 else None
        if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
            raise ProlificContextError("De Prolific-onderzoekslink is niet geldig.")
        normalized[key] = value
    return ProlificContext(
        participant_id=normalized[PROLIFIC_PID_PARAM],
        study_id=normalized[PROLIFIC_STUDY_PARAM],
        submission_id=normalized[PROLIFIC_SUBMISSION_PARAM],
    )


def read_profile_metadata(profile: object) -> dict[str, object] | None:
    if not isinstance(profile, dict):
        return None
    metadata = profile.get(PROLIFIC_PROFILE_KEY)
    return metadata if isinstance(metadata, dict) else None


def replaced_submission_ids(metadata: Mapping[str, object] | None) -> tuple[str, ...]:
    if metadata is None:
        return ()
    values = metadata.get("replaced_submission_ids", ())
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(
        value
        for value in values
        if isinstance(value, str) and _IDENTIFIER_PATTERN.fullmatch(value)
    )


def attach_prolific_metadata(
    profile: dict[str, object],
    context: ProlificContext,
    *,
    replaced: tuple[str, ...] = (),
) -> dict[str, object]:
    enriched = dict(profile)
    enriched[PROLIFIC_PROFILE_KEY] = context.profile_metadata(
        replaced_submission_ids=tuple(dict.fromkeys(replaced))
    )
    return enriched
