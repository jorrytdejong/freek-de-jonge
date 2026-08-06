"""Load private ACL session links with explicit 12-item assignments."""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

from app.acl_config import CONDITION_CODES, ITEMS_PER_PARTICIPANT
from app.acl_stimuli import JokeItem

REQUIRED_COLUMNS = {
    "session_id",
    "is_test",
    "active",
    "assigned_item_ids",
    "created_at",
    "notes",
}
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{12,64}$")
DEFAULT_SESSIONS_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "acl_sessions.csv"
)


class SessionValidationError(ValueError):
    """Raised when an ACL session registry violates its contract."""


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
    assigned_item_ids: tuple[str, ...]
    created_at: date
    notes: str


@dataclass(frozen=True)
class SessionAccess:
    status: SessionAccessStatus
    session: ParticipantSession | None = None


def _boolean(value: str, *, row_number: int, column: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise SessionValidationError(
        f"Rij {row_number} heeft een ongeldige boolean in {column}."
    )


def load_sessions(
    items: tuple[JokeItem, ...], path: Path = DEFAULT_SESSIONS_PATH
) -> dict[str, ParticipantSession]:
    if not path.is_file():
        raise SessionValidationError(f"Sessiebestand niet gevonden: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        return _load_rows(items, csv.DictReader(handle))


def load_sessions_csv_text(
    items: tuple[JokeItem, ...], csv_text: str
) -> dict[str, ParticipantSession]:
    return _load_rows(items, csv.DictReader(io.StringIO(csv_text, newline="")))


def _load_rows(
    items: tuple[JokeItem, ...], reader: csv.DictReader
) -> dict[str, ParticipantSession]:
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
    if missing:
        raise SessionValidationError(
            f"Ontbrekende sessiekolommen: {', '.join(sorted(missing))}"
        )
    items_by_id = {item.item_id: item for item in items}
    sessions: dict[str, ParticipantSession] = {}
    for row_number, row in enumerate(reader, start=2):
        values = {
            column: (row.get(column) or "").strip() for column in REQUIRED_COLUMNS
        }
        empty = sorted(
            column for column in REQUIRED_COLUMNS - {"notes"} if not values[column]
        )
        if empty:
            raise SessionValidationError(
                f"Rij {row_number} heeft lege velden: {', '.join(empty)}."
            )
        session_id = values["session_id"]
        if not SESSION_ID_PATTERN.fullmatch(session_id) or session_id in sessions:
            raise SessionValidationError(
                f"Ongeldige of dubbele sessie-ID: {session_id}."
            )
        assigned = tuple(values["assigned_item_ids"].split("|"))
        if len(assigned) != ITEMS_PER_PARTICIPANT or len(set(assigned)) != len(
            assigned
        ):
            raise SessionValidationError(
                f"Sessie {session_id} moet {ITEMS_PER_PARTICIPANT} unieke items hebben."
            )
        unknown = set(assigned) - set(items_by_id)
        if unknown:
            raise SessionValidationError(
                f"Sessie {session_id} bevat onbekende items: {sorted(unknown)}."
            )
        assigned_items = [items_by_id[item_id] for item_id in assigned]
        if len({item.topic_id for item in assigned_items}) != ITEMS_PER_PARTICIPANT:
            raise SessionValidationError(f"Sessie {session_id} herhaalt een topic.")
        condition_counts = Counter(item.condition_code for item in assigned_items)
        if condition_counts != Counter({condition: 2 for condition in CONDITION_CODES}):
            raise SessionValidationError(
                f"Sessie {session_id} heeft niet exact twee items per conditie."
            )
        try:
            created_at = date.fromisoformat(values["created_at"])
        except ValueError as error:
            raise SessionValidationError(
                f"Sessie {session_id} heeft een ongeldige datum."
            ) from error
        sessions[session_id] = ParticipantSession(
            session_id=session_id,
            is_test=_boolean(
                values["is_test"], row_number=row_number, column="is_test"
            ),
            active=_boolean(values["active"], row_number=row_number, column="active"),
            assigned_item_ids=assigned,
            created_at=created_at,
            notes=values["notes"],
        )
    if not sessions:
        raise SessionValidationError("Het sessieregister is leeg.")
    return sessions


def resolve_session(
    raw_session_id: str | None, sessions: dict[str, ParticipantSession]
) -> SessionAccess:
    if raw_session_id is None or not raw_session_id.strip():
        return SessionAccess(SessionAccessStatus.MISSING)
    session = sessions.get(raw_session_id.strip())
    if session is None:
        return SessionAccess(SessionAccessStatus.UNKNOWN)
    if not session.active:
        return SessionAccess(SessionAccessStatus.INACTIVE, session)
    return SessionAccess(SessionAccessStatus.VALID, session)
