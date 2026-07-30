"""Create stable per-session group and variant ordering."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, TypeVar

from app.sessions import ParticipantSession
from app.stimuli import JokeGroup

Item = TypeVar("Item")


@dataclass(frozen=True)
class AssignedGroup:
    group_id: str
    variant_ids: tuple[str, ...]


@dataclass(frozen=True)
class ParticipantAssignment:
    session_id: str
    groups: tuple[AssignedGroup, ...]


def _stable_order(items: Iterable[Item], *, seed: str) -> tuple[Item, ...]:
    """Sort items by a SHA-256 key so order is stable across Python processes."""

    def order_key(item: Item) -> bytes:
        payload = f"{seed}|{item}".encode()
        return hashlib.sha256(payload).digest()

    return tuple(sorted(items, key=order_key))


def build_assignment(
    session: ParticipantSession,
    groups: tuple[JokeGroup, ...],
) -> ParticipantAssignment:
    """Build the immutable assignment encoded by one fixed session record."""
    groups_by_id = {group.group_id: group for group in groups}
    ordered_group_ids = _stable_order(
        session.assignment_groups,
        seed=f"{session.session_id}|groups",
    )

    assigned_groups = []
    for group_id in ordered_group_ids:
        group = groups_by_id[group_id]
        variant_ids = _stable_order(
            (variant.variant_id for variant in group.variants),
            seed=f"{session.session_id}|{group_id}|variants",
        )
        assigned_groups.append(
            AssignedGroup(
                group_id=group_id,
                variant_ids=variant_ids,
            )
        )

    return ParticipantAssignment(
        session_id=session.session_id,
        groups=tuple(assigned_groups),
    )


def assignment_fingerprint(assignment: ParticipantAssignment) -> str:
    """Return a short identifier useful for tests and operational diagnostics."""
    payload = "|".join(
        f"{group.group_id}:{','.join(group.variant_ids)}"
        for group in assignment.groups
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]

