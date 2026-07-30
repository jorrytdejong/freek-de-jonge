"""Load, validate, and resolve anonymous participant sessions."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

EXPECTED_GROUPS_PER_SESSION = 5
EXPECTED_TEST_SESSIONS = 10
REQUIRED_COLUMNS = {
    "session_id",
    "is_test",
    "active",
    "assignment_groups",
    "created_at",
    "notes",
}
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{12,64}$")
DEFAULT_SESSIONS_PATH = Path(__file__).resolve().parents[1] / "data" / "sessions.csv"


class SessionValidationError(ValueError):
    """Raised when the fixed session registry violates its contract."""


class SessionAccessStatus(StrEnum):
    VALID = "valid"
    MISSING = "missing"
    UNKNOWN = "unknown"
    INACTIVE = "inactive"


@dataclass(frozen=True)
class ParticipantSession:
    session_id: str
    is_test: bool
    active: bool
    assignment_groups: tuple[str, ...]
    created_at: date
    notes: str


@dataclass(frozen=True)
class SessionAccess:
    status: SessionAccessStatus
    session: ParticipantSession | None = None


def _parse_boolean(value: str, *, row_number: int, column: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise SessionValidationError(
        f"Rij {row_number} heeft ongeldige boolean {value!r} in {column}."
    )


def load_sessions(
    valid_group_ids: set[str],
    path: Path = DEFAULT_SESSIONS_PATH,
) -> dict[str, ParticipantSession]:
    """Load the fixed registry and validate every assignment."""
    if not path.is_file():
        raise SessionValidationError(f"Sessiebestand niet gevonden: {path}")

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing_columns = REQUIRED_COLUMNS - fieldnames
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise SessionValidationError(f"Ontbrekende sessiekolommen: {missing}")
        rows = list(reader)

    sessions: dict[str, ParticipantSession] = {}
    for row_number, row in enumerate(rows, start=2):
        values = {
            column: (row.get(column) or "").strip() for column in REQUIRED_COLUMNS
        }
        required_nonempty = REQUIRED_COLUMNS - {"notes"}
        empty_columns = [
            column for column in required_nonempty if not values[column]
        ]
        if empty_columns:
            empty = ", ".join(sorted(empty_columns))
            raise SessionValidationError(
                f"Rij {row_number} heeft lege verplichte velden: {empty}"
            )

        session_id = values["session_id"]
        if not SESSION_ID_PATTERN.fullmatch(session_id):
            raise SessionValidationError(
                f"Rij {row_number} heeft ongeldig session_id {session_id!r}."
            )
        if session_id in sessions:
            raise SessionValidationError(f"Dubbel session_id: {session_id}.")

        assignment_groups = tuple(values["assignment_groups"].split("|"))
        if len(assignment_groups) != EXPECTED_GROUPS_PER_SESSION:
            raise SessionValidationError(
                f"Sessie {session_id} heeft {len(assignment_groups)} groepen; "
                f"verwacht {EXPECTED_GROUPS_PER_SESSION}."
            )
        if len(set(assignment_groups)) != len(assignment_groups):
            raise SessionValidationError(
                f"Sessie {session_id} bevat dubbele toegewezen groepen."
            )
        unknown_groups = set(assignment_groups) - valid_group_ids
        if unknown_groups:
            unknown = ", ".join(sorted(unknown_groups))
            raise SessionValidationError(
                f"Sessie {session_id} verwijst naar onbekende groepen: {unknown}."
            )

        try:
            created_at = date.fromisoformat(values["created_at"])
        except ValueError as error:
            raise SessionValidationError(
                f"Rij {row_number} heeft ongeldige created_at "
                f"{values['created_at']!r}."
            ) from error

        sessions[session_id] = ParticipantSession(
            session_id=session_id,
            is_test=_parse_boolean(
                values["is_test"],
                row_number=row_number,
                column="is_test",
            ),
            active=_parse_boolean(
                values["active"],
                row_number=row_number,
                column="active",
            ),
            assignment_groups=assignment_groups,
            created_at=created_at,
            notes=values["notes"],
        )

    test_count = sum(session.is_test for session in sessions.values())
    if test_count != EXPECTED_TEST_SESSIONS:
        raise SessionValidationError(
            f"Verwacht {EXPECTED_TEST_SESSIONS} testsessies; "
            f"gevonden {test_count}."
        )

    return sessions


def resolve_session(
    raw_session_id: str | None,
    sessions: dict[str, ParticipantSession],
) -> SessionAccess:
    """Resolve a URL session value without revealing unknown registry entries."""
    if raw_session_id is None or not raw_session_id.strip():
        return SessionAccess(status=SessionAccessStatus.MISSING)

    session = sessions.get(raw_session_id.strip())
    if session is None:
        return SessionAccess(status=SessionAccessStatus.UNKNOWN)
    if not session.active:
        return SessionAccess(
            status=SessionAccessStatus.INACTIVE,
            session=session,
        )
    return SessionAccess(status=SessionAccessStatus.VALID, session=session)
