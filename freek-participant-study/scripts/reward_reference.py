#!/usr/bin/env python3
"""Derive the pseudonymous allowlist reference for one private participant link."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rewards import participant_reward_reference


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate one Checkpoint 12 production-canary reward reference."
    )
    parser.add_argument("session_id", help="Private participant session ID")
    parser.add_argument("--study-version", default="acl-1")
    args = parser.parse_args()
    if not args.session_id.strip():
        parser.error("session_id must not be empty")
    print(participant_reward_reference(args.session_id, args.study_version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
