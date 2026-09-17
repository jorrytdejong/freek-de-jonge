#!/usr/bin/env python3
"""Print a compact summary of the public ACL evaluation data."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ratings", type=Path, default=Path("data/acl_human_evaluation_ratings.csv"))
    parser.add_argument("--stimuli", type=Path, default=Path("data/acl_jokes.csv"))
    args = parser.parse_args()

    with args.ratings.open(newline="", encoding="utf-8") as handle:
        ratings = list(csv.DictReader(handle))
    with args.stimuli.open(newline="", encoding="utf-8") as handle:
        stimuli = list(csv.DictReader(handle))

    participants = {row["participant_code"] for row in ratings}
    print(f"ratings: {len(ratings)} rows from {len(participants)} participants")
    print(f"stimuli: {len(stimuli)} items")
    print(f"conditions: {dict(sorted(Counter(row['condition_code'] for row in stimuli).items()))}")
    print(f"recruitment_source: {dict(sorted(Counter(row['recruitment_source'] for row in ratings).items()))}")


if __name__ == "__main__":
    main()
