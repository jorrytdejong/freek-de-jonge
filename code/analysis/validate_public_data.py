#!/usr/bin/env python3
"""Validate the public ACL paper data package.

The checks deliberately operate only on files shipped with the paper. They
do not require Supabase, participant registries, deployment configuration, or
network access.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


EXPECTED_CONDITIONS = {"A1", "A2", "C1", "C2", "E1", "E2"}
EXPECTED_TOPICS = {f"T{i:02d}" for i in range(1, 21)}
FORBIDDEN_RATING_COLUMNS = {
    "session_id",
    "participant_id",
    "prolific_id",
    "email",
    "ip_address",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path} is empty")
    return rows


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_ratings(path: Path, stimulus_ids: set[str]) -> list[str]:
    rows = read_csv(path)
    columns = set(rows[0])
    required = {
        "participant_code",
        "study_version",
        "recruitment_source",
        "item_id",
        "topic_id",
        "condition_code",
        "pipeline_family",
        "funniness",
        "coherence",
        "freek_similarity",
    }
    require(required <= columns, f"ratings missing columns: {sorted(required - columns)}")
    require(not (columns & FORBIDDEN_RATING_COLUMNS), "ratings contain identifying columns")
    require(len(rows) == 840, f"expected 840 ratings, found {len(rows)}")

    participants = {row["participant_code"] for row in rows}
    items = {row["item_id"] for row in rows}
    topics = {row["topic_id"] for row in rows}
    conditions = {row["condition_code"] for row in rows}
    require(len(participants) == 42, f"expected 42 participants, found {len(participants)}")
    require(len(items) == 120, f"expected 120 rated items, found {len(items)}")
    require(topics == EXPECTED_TOPICS, "ratings do not cover exactly T01-T20")
    require(conditions == EXPECTED_CONDITIONS, "ratings do not contain exactly the six paper conditions")
    require(items == stimulus_ids, "ratings and stimulus item IDs do not match")

    keys = [(row["participant_code"], row["item_id"]) for row in rows]
    require(len(keys) == len(set(keys)), "duplicate participant-item rating rows")
    per_participant = Counter(row["participant_code"] for row in rows)
    require(set(per_participant.values()) == {20}, "each participant must have exactly 20 ratings")
    per_item = Counter(row["item_id"] for row in rows)
    require(min(per_item.values()) == 6 and max(per_item.values()) == 8, "unexpected item exposure range")

    sources = Counter(row["recruitment_source"] for row in rows)
    require(set(sources) == {"network", "prolific"}, "unexpected recruitment source")
    require(sources == {"prolific": 520, "network": 320}, f"unexpected source counts: {sources}")

    for row in rows:
        require(row["condition_code"] in EXPECTED_CONDITIONS, "unexpected condition code")
        require(row["item_id"].startswith(row["topic_id"] + "-"), "item/topic mismatch")
        for outcome in ("funniness", "coherence", "freek_similarity"):
            require(row[outcome] in {"1", "2", "3", "4", "5"}, f"invalid {outcome} score")

    return sorted(items)


def validate_stimuli(path: Path) -> set[str]:
    rows = read_csv(path)
    required = {
        "item_id",
        "topic_id",
        "condition_code",
        "pipeline_family",
        "text",
        "model",
        "result_sha256",
    }
    columns = set(rows[0])
    require(required <= columns, f"stimuli missing columns: {sorted(required - columns)}")
    require(len(rows) == 120, f"expected 120 stimuli, found {len(rows)}")
    item_ids = {row["item_id"] for row in rows}
    require(len(item_ids) == 120, "stimulus item IDs are not unique")
    require({row["topic_id"] for row in rows} == EXPECTED_TOPICS, "stimuli do not cover T01-T20")
    require({row["condition_code"] for row in rows} == EXPECTED_CONDITIONS, "stimuli do not contain six conditions")
    require(all(row["model"] == "gpt-5.6-terra" for row in rows), "stimuli use unexpected models")
    require(all(row["text"].strip() for row in rows), "stimulus text is empty")
    return item_ids


def validate_corpus(path: Path) -> None:
    rows = read_csv(path)
    required = {
        "source_audio",
        "start",
        "end",
        "text",
        "categories_json",
        "script_opposition_json",
    }
    columns = set(rows[0])
    require(required <= columns, f"corpus annotations missing columns: {sorted(required - columns)}")
    require(len(rows) == 69, f"expected 69 corpus annotations, found {len(rows)}")
    require(len({row["source_audio"] for row in rows}) == 5, "expected five corpus source records")
    require(all(row["text"].strip() for row in rows), "corpus annotation contains empty text")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ratings", type=Path, default=Path("data/acl_human_evaluation_ratings.csv"))
    parser.add_argument("--stimuli", type=Path, default=Path("data/acl_jokes.csv"))
    parser.add_argument("--corpus", type=Path, default=Path("data/acl_corpus_annotations_69.csv"))
    args = parser.parse_args()

    stimulus_ids = validate_stimuli(args.stimuli)
    validate_ratings(args.ratings, stimulus_ids)
    validate_corpus(args.corpus)
    print("Validated public ACL data: 20 topics, 6 conditions, 120 stimuli, 69 corpus annotations, 840 ratings, 42 participants.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
