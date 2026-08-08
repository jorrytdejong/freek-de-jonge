#!/usr/bin/env python3
"""Validate static study inputs and deterministic assignment contracts."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.assignment import assignment_fingerprint, build_assignment
from app.exports import build_export_tables
from app.ratings import build_displayed_variants
from app.sessions import DEFAULT_SESSIONS_PATH, load_sessions
from app.stimuli import DEFAULT_STIMULI_PATH, load_stimuli


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate stimuli, sessions, and deterministic assignments."
    )
    parser.add_argument("--stimuli", type=Path, default=DEFAULT_STIMULI_PATH)
    parser.add_argument("--sessions", type=Path, default=DEFAULT_SESSIONS_PATH)
    parser.add_argument(
        "--require-test-only",
        action="store_true",
        help="Reject any non-test session in this registry.",
    )
    return parser.parse_args()


def validate_study(
    *,
    stimuli_path: Path,
    sessions_path: Path,
    require_test_only: bool,
) -> tuple[int, int, int]:
    groups = load_stimuli(stimuli_path)
    groups_by_id = {group.group_id: group for group in groups}
    sessions = load_sessions(set(groups_by_id), sessions_path)

    if require_test_only and any(not session.is_test for session in sessions.values()):
        raise ValueError("Staging registry contains a non-test session.")

    exposure = Counter(
        group_id
        for session in sessions.values()
        for group_id in session.assignment_groups
    )
    if set(exposure) != set(groups_by_id):
        raise ValueError("Session registry does not expose every joke group.")
    if max(exposure.values()) - min(exposure.values()) > 1:
        raise ValueError("Session registry group exposure is not balanced.")

    fingerprints: set[str] = set()
    for session in sessions.values():
        assignment = build_assignment(session, groups)
        fingerprint = assignment_fingerprint(assignment)
        if fingerprint in fingerprints:
            raise ValueError("Two sessions have the same complete assignment.")
        fingerprints.add(fingerprint)
        for assigned_group in assignment.groups:
            displayed = build_displayed_variants(
                assigned_group,
                groups_by_id[assigned_group.group_id],
            )
            if tuple(item.display_position for item in displayed) != tuple(range(1, 9)):
                raise ValueError("Displayed variant positions are not 1 through 8.")

    build_export_tables((), sessions, groups)
    return len(groups), len(sessions), sum(exposure.values())


def main() -> int:
    args = parse_args()
    group_count, session_count, assignment_count = validate_study(
        stimuli_path=args.stimuli,
        sessions_path=args.sessions,
        require_test_only=args.require_test_only,
    )
    print(
        f"Validated {group_count} groups, {session_count} sessions, and "
        f"{assignment_count} assigned group exposures."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
