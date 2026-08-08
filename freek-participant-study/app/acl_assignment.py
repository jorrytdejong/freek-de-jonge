"""Resolve the explicit, balanced item order encoded by a session link."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.acl_sessions import ParticipantSession
from app.acl_stimuli import JokeItem


@dataclass(frozen=True)
class AssignedItem:
    item_id: str
    display_position: int


@dataclass(frozen=True)
class ParticipantAssignment:
    session_id: str
    items: tuple[AssignedItem, ...]


def build_assignment(
    session: ParticipantSession, stimuli: tuple[JokeItem, ...]
) -> ParticipantAssignment:
    available = {item.item_id for item in stimuli}
    unknown = set(session.assigned_item_ids) - available
    if unknown:
        raise ValueError(f"Assignment contains unknown items: {sorted(unknown)}")
    return ParticipantAssignment(
        session_id=session.session_id,
        items=tuple(
            AssignedItem(item_id=item_id, display_position=position)
            for position, item_id in enumerate(session.assigned_item_ids, start=1)
        ),
    )


def assignment_fingerprint(assignment: ParticipantAssignment) -> str:
    payload = "|".join(item.item_id for item in assignment.items)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]
