#!/usr/bin/env python3
"""Validate ACL stimuli, sessions, balancing, and deterministic assignments."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.acl_assignment import assignment_fingerprint, build_assignment
from app.acl_sessions import DEFAULT_SESSIONS_PATH, load_sessions
from app.acl_stimuli import DEFAULT_STIMULI_PATH, load_stimuli
from scripts.build_acl_study_data import validate_assignment_matrix


def validate_study(
    *, stimuli_path: Path, sessions_path: Path, require_test_only: bool
) -> tuple[int, int, int]:
    stimuli = load_stimuli(stimuli_path)
    sessions = load_sessions(stimuli, sessions_path)
    if require_test_only and any(not session.is_test for session in sessions.values()):
        raise ValueError("Staging registry contains a non-test session.")
    relevant = list(sessions.values())
    strata = (
        [session for session in relevant if session.is_test],
        [session for session in relevant if not session.is_test],
    )
    total_exposure = 0
    for stratum in strata:
        if not stratum:
            continue
        matrix = [list(session.assigned_item_ids) for session in stratum]
        validate_assignment_matrix(matrix)
        fingerprints = {
            assignment_fingerprint(build_assignment(session, stimuli))
            for session in stratum
        }
        if len(fingerprints) != len(stratum):
            raise ValueError("Two sessions in one stratum share an assignment.")
        exposure = Counter(item_id for row in matrix for item_id in row)
        if set(exposure) != {item.item_id for item in stimuli}:
            raise ValueError("A registry stratum does not expose all 120 items.")
        total_exposure += sum(exposure.values())
    return len(stimuli), len(relevant), total_exposure


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stimuli", type=Path, default=DEFAULT_STIMULI_PATH)
    parser.add_argument("--sessions", type=Path, default=DEFAULT_SESSIONS_PATH)
    parser.add_argument("--require-test-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_study(
        stimuli_path=args.stimuli,
        sessions_path=args.sessions,
        require_test_only=args.require_test_only,
    )
    print(
        f"Validated {result[0]} items, {result[1]} sessions, "
        f"and {result[2]} assigned exposures."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
