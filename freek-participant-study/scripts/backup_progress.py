#!/usr/bin/env python3
"""Download a validated raw progress backup from the configured backend."""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.storage import create_progress_storage
from app.storage.csv_storage import FIELDNAMES, serialize_progress_row

DEFAULT_BACKUP_DIRECTORY = PROJECT_ROOT / "data" / "private" / "backups"


def write_backup(path: Path) -> int:
    records = create_progress_storage(environ=os.environ, secrets={}).list_progress()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(serialize_progress_row(record) for record in records)
        temporary_path.replace(path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    return len(records)


def parse_args() -> argparse.Namespace:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser(description="Back up raw study progress.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_BACKUP_DIRECTORY / f"progress-{timestamp}.csv",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    count = write_backup(args.output)
    print(f"Backed up {count} session snapshots to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
