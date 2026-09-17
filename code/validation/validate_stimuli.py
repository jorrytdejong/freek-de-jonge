#!/usr/bin/env python3
"""Validate the public 20-topic x 6-condition stimulus bank."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


EXPECTED_CONDITIONS = {"A1", "A2", "C1", "C2", "E1", "E2"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, nargs="?", default=Path("data/acl_jokes.csv"))
    args = parser.parse_args()

    with args.path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"item_id", "topic_id", "condition_code", "text"}
    missing = required.difference(rows[0] if rows else {})
    if missing:
        raise SystemExit(f"missing stimulus columns: {sorted(missing)}")
    item_ids = {row["item_id"] for row in rows}
    topics = {row["topic_id"] for row in rows}
    conditions = {row["condition_code"] for row in rows}
    if len(rows) != 120 or len(item_ids) != 120:
        raise SystemExit(f"expected 120 unique stimuli, found {len(rows)} rows and {len(item_ids)} IDs")
    if len(topics) != 20 or conditions != EXPECTED_CONDITIONS:
        raise SystemExit(f"unexpected design: {len(topics)} topics, {sorted(conditions)} conditions")
    if any(not row["text"].strip() for row in rows):
        raise SystemExit("stimulus bank contains empty joke text")
    print("Validated public stimuli: 20 topics, 6 conditions, 120 unique items.")


if __name__ == "__main__":
    main()
