#!/usr/bin/env python3
"""Generate validated local analysis CSV files from saved study progress."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.acl_exports import (
    DEFAULT_EXPORT_DIRECTORY,
    build_export_tables,
    write_export_files,
)
from app.acl_sessions import DEFAULT_SESSIONS_PATH, load_sessions
from app.acl_stimuli import DEFAULT_STIMULI_PATH, load_stimuli
from app.storage import CSVProgressStorage

DEFAULT_PROGRESS_PATH = PROJECT_ROOT / "data" / "runtime" / "acl_progress.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export validated participant and rating tables."
    )
    parser.add_argument("--progress", type=Path, default=DEFAULT_PROGRESS_PATH)
    parser.add_argument("--sessions", type=Path, default=DEFAULT_SESSIONS_PATH)
    parser.add_argument("--stimuli", type=Path, default=DEFAULT_STIMULI_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_EXPORT_DIRECTORY)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stimuli = load_stimuli(args.stimuli)
    sessions = load_sessions(stimuli, args.sessions)
    records = CSVProgressStorage(args.progress).list_progress()
    tables = build_export_tables(records, sessions, stimuli)
    participants_path, ratings_path = write_export_files(tables, args.output)
    print(
        f"Exported {len(tables.participants)} participants and "
        f"{len(tables.ratings)} ratings."
    )
    print(participants_path.resolve())
    print(ratings_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
