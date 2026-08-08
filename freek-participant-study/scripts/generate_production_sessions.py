#!/usr/bin/env python3
"""Generate a private, balanced registry of real participant links."""

from __future__ import annotations

import argparse
import csv
import hashlib
import secrets
import sys
from collections import Counter
from collections.abc import Callable
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.sessions import REQUIRED_COLUMNS, load_sessions
from app.stimuli import load_stimuli

FIELDNAMES = (
    "session_id",
    "is_test",
    "active",
    "assignment_groups",
    "created_at",
    "notes",
)
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "private" / "sessions.production.csv"
DEFAULT_TEST_REGISTRY = PROJECT_ROOT / "data" / "sessions.staging.csv"


def _tie_breaker(index: int, group_id: str) -> str:
    return hashlib.sha256(f"pilot-1:{index}:{group_id}".encode()).hexdigest()


def generate_rows(
    *,
    real_count: int,
    test_rows: list[dict[str, str]],
    created_at: date,
    id_factory: Callable[[], str],
) -> list[dict[str, str]]:
    if real_count < 1:
        raise ValueError("real_count must be at least one.")
    group_ids = [f"G{number:02d}" for number in range(1, 13)]
    exposure = Counter(
        group_id
        for row in test_rows
        for group_id in row["assignment_groups"].split("|")
    )
    rows = [dict(row) for row in test_rows]
    used_ids = {row["session_id"] for row in rows}

    for index in range(1, real_count + 1):
        ranked = sorted(
            group_ids,
            key=lambda group_id: (
                exposure[group_id],
                _tie_breaker(index, group_id),
            ),
        )
        selected = ranked[:5]
        for group_id in selected:
            exposure[group_id] += 1

        session_id = id_factory()
        while session_id in used_ids:
            session_id = id_factory()
        used_ids.add(session_id)
        rows.append(
            {
                "session_id": session_id,
                "is_test": "false",
                "active": "true",
                "assignment_groups": "|".join(selected),
                "created_at": created_at.isoformat(),
                "notes": f"Production participant {index:02d}",
            }
        )
    return rows


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or ()) != REQUIRED_COLUMNS:
            raise ValueError("Test registry has an unexpected column contract.")
        return list(reader)


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing registry: {path}")
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate private production participant links."
    )
    parser.add_argument("--real-count", type=int, default=40)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--test-registry", type=Path, default=DEFAULT_TEST_REGISTRY)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = generate_rows(
        real_count=args.real_count,
        test_rows=read_rows(args.test_registry),
        created_at=date.today(),
        id_factory=lambda: f"participant-{secrets.token_urlsafe(16)}",
    )
    write_rows(args.output, rows)
    groups = load_stimuli()
    sessions = load_sessions({group.group_id for group in groups}, args.output)
    real_count = sum(not session.is_test for session in sessions.values())
    print(f"Created {real_count} private real sessions at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
