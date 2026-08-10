#!/usr/bin/env python3
"""Build the locked ACL stimuli and mathematically balanced session registries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import secrets
import sys
from collections import Counter
from collections.abc import Callable
from datetime import date
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.acl_config import (
    CONDITION_CODES,
    ITEMS_PER_PARTICIPANT,
    MAXIMUM_PARTICIPANTS,
    STUDY_VERSION,
)
from app.acl_sessions import OPTIONAL_COLUMNS, REQUIRED_COLUMNS, load_sessions
from app.acl_stimuli import REQUIRED_COLUMNS as STIMULUS_COLUMNS
from app.acl_stimuli import load_stimuli

SOURCE_ITEMS = (
    REPOSITORY_ROOT
    / "final ACL version"
    / "experiment_runs"
    / "acl_3x2_prompt_engineering_a7e5ec5"
    / "items"
)
DEFAULT_STIMULI = PROJECT_ROOT / "data" / "acl_jokes.csv"
DEFAULT_SESSIONS = PROJECT_ROOT / "data" / "acl_sessions.csv"
DEFAULT_STAGING_SESSIONS = PROJECT_ROOT / "data" / "acl_sessions.staging.csv"
STIMULUS_FIELDNAMES = (
    "study_version",
    "item_id",
    "topic_id",
    "topic",
    "condition_code",
    "pipeline_family",
    "freek_style",
    "text",
    "model",
    "result_sha256",
)
SESSION_FIELDNAMES = (
    "session_id",
    "is_test",
    "active",
    "reward_eligible",
    "assigned_item_ids",
    "created_at",
    "notes",
)


def stimulus_rows(source: Path) -> list[dict[str, str]]:
    rows = []
    for path in sorted(source.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = payload["result"]
        rows.append(
            {
                "study_version": STUDY_VERSION,
                "item_id": payload["job_id"],
                "topic_id": payload["topic_id"],
                "topic": payload["topic"],
                "condition_code": payload["condition_code"],
                "pipeline_family": payload["pipeline_family"],
                "freek_style": payload["style_mode"],
                "text": result["joke"].strip(),
                "model": payload["model"],
                "result_sha256": payload["result_sha256"],
            }
        )
    if len(rows) != 120:
        raise ValueError(f"Expected 120 source items; found {len(rows)} in {source}.")
    return rows


def _topic_condition_offsets(seed: int) -> list[int]:
    """Return a fixed randomized condition offset for each of the 20 topics.

    Two conditions receive four topics and the other four receive three. The
    offsets rotate by participant so every six-person block exposes every
    topic-condition item exactly once.
    """
    offsets = [*range(6), *range(6), *range(6), 0, 3]
    random.Random(seed).shuffle(offsets)
    return offsets


def _display_order(item_ids: list[str], *, participant: int, seed: int) -> list[str]:
    """Return a deterministic participant-specific display order."""
    random_seed = int.from_bytes(
        hashlib.sha256(f"{seed}:{participant}:display".encode()).digest()[:8]
    )
    candidate = item_ids.copy()
    random.Random(random_seed).shuffle(candidate)
    return candidate


@lru_cache(maxsize=None)
def _complete_assignment_matrix(seed: int) -> tuple[tuple[str, ...], ...]:
    """Build and cache the locked 50-person matrix before taking prefixes."""
    offsets = _topic_condition_offsets(seed)
    all_rows = []
    for participant in range(MAXIMUM_PARTICIPANTS):
        base_conditions = [(offset + participant) % 6 for offset in offsets]
        item_ids = [
            f"T{topic + 1:02d}-{CONDITION_CODES[condition]}"
            for topic, condition in enumerate(base_conditions)
        ]
        all_rows.append(
            tuple(_display_order(item_ids, participant=participant, seed=seed))
        )
    return tuple(all_rows)


def assignment_item_ids(participant_count: int, *, seed: int) -> list[list[str]]:
    if not 1 <= participant_count <= MAXIMUM_PARTICIPANTS:
        raise ValueError(
            f"participant_count must be between 1 and {MAXIMUM_PARTICIPANTS}."
        )
    all_rows = [list(row) for row in _complete_assignment_matrix(seed)]
    selected_rows = all_rows[:participant_count]
    validate_assignment_matrix(selected_rows)
    return selected_rows


def validate_assignment_matrix(rows: list[list[str]]) -> None:
    if not rows or len(rows) > MAXIMUM_PARTICIPANTS:
        raise ValueError("The registry must contain between 1 and 50 participants.")
    if any(
        len(row) != ITEMS_PER_PARTICIPANT or len(set(row)) != ITEMS_PER_PARTICIPANT
        for row in rows
    ):
        raise ValueError("Every participant must have 20 unique items.")
    topic_exposure = Counter()
    condition_exposure = Counter()
    item_exposure = Counter()
    for row in rows:
        topics = [item_id.split("-")[0] for item_id in row]
        conditions = [item_id.split("-")[1] for item_id in row]
        topic_counts = Counter(topics)
        if len(topic_counts) != 20 or set(topic_counts.values()) != {1}:
            raise ValueError("A participant must cover every topic exactly once.")
        frequencies = [Counter(conditions).get(code, 0) for code in CONDITION_CODES]
        if sorted(frequencies) != [3, 3, 3, 3, 4, 4]:
            raise ValueError(
                "A participant must receive three or four items per condition."
            )
        topic_exposure.update(topics)
        condition_exposure.update(conditions)
        item_exposure.update(row)
    if topic_exposure != Counter(
        {f"T{topic:02d}": len(rows) for topic in range(1, 21)}
    ):
        raise ValueError("Topic exposure is not exact.")
    condition_values = [condition_exposure[condition] for condition in CONDITION_CODES]
    if max(condition_values) - min(condition_values) > 1:
        raise ValueError("Condition exposure differs by more than one.")
    expected_items = {
        f"T{topic:02d}-{condition}"
        for topic in range(1, 21)
        for condition in CONDITION_CODES
    }
    complete_item_exposure = Counter({item_id: 0 for item_id in expected_items})
    complete_item_exposure.update(item_exposure)
    item_range = max(complete_item_exposure.values()) - min(
        complete_item_exposure.values()
    )
    if item_range > 1:
        raise ValueError("Individual item exposure differs by more than one.")
    for block_start in range(0, len(rows) - 5, 6):
        block = rows[block_start : block_start + 6]
        for topic in range(1, 21):
            topic_id = f"T{topic:02d}"
            conditions = {
                item_id.split("-")[1]
                for row in block
                for item_id in row
                if item_id.startswith(f"{topic_id}-")
            }
            if conditions != set(CONDITION_CODES):
                raise ValueError(
                    f"Six-person block does not rotate all conditions for {topic_id}."
                )


def session_rows(
    participant_count: int,
    *,
    is_test: bool,
    created_at: date,
    id_factory: Callable[[int], str],
    seed: int,
    reward_free_count: int = 0,
) -> list[dict[str, str]]:
    assignments = assignment_item_ids(participant_count, seed=seed)
    label = "Test session" if is_test else "Production participant"
    if reward_free_count < 0 or reward_free_count > participant_count:
        raise ValueError("reward_free_count must fit within participant_count.")
    return [
        {
            "session_id": id_factory(index),
            "is_test": str(is_test).lower(),
            "active": "true",
            "reward_eligible": str(index > reward_free_count).lower(),
            "assigned_item_ids": "|".join(item_ids),
            "created_at": created_at.isoformat(),
            "notes": f"{label} {index:02d}",
        }
        for index, item_ids in enumerate(assignments, start=1)
    ]


def _write_csv(
    path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_test_data(
    source: Path, stimuli_path: Path, sessions_paths: tuple[Path, ...]
) -> None:
    _write_csv(stimuli_path, STIMULUS_FIELDNAMES, stimulus_rows(source))
    stimuli = load_stimuli(stimuli_path)
    test_rows = session_rows(
        10,
        is_test=True,
        created_at=date.today(),
        id_factory=lambda index: (
            f"acl-test-{index:02d}-"
            + hashlib.sha256(f"acl-test-20-items-{index}".encode()).hexdigest()[:8]
        ),
        seed=20260806,
    )
    for path in sessions_paths:
        _write_csv(path, SESSION_FIELDNAMES, test_rows)
        load_sessions(stimuli, path)


def build_production(
    *,
    stimuli_path: Path,
    registry_path: Path,
    urls_path: Path,
    base_url: str,
) -> None:
    if registry_path.exists() or urls_path.exists():
        raise FileExistsError("Refusing to overwrite a private production registry.")
    stimuli = load_stimuli(stimuli_path)
    test_rows = session_rows(
        10,
        is_test=True,
        created_at=date.today(),
        id_factory=lambda index: (
            f"acl-test-{index:02d}-"
            + hashlib.sha256(f"acl-test-20-items-{index}".encode()).hexdigest()[:8]
        ),
        seed=20260806,
    )
    real_rows = session_rows(
        MAXIMUM_PARTICIPANTS,
        is_test=False,
        created_at=date.today(),
        id_factory=lambda _: f"participant-{secrets.token_urlsafe(16)}",
        seed=20260806,
        reward_free_count=10,
    )
    _write_csv(registry_path, SESSION_FIELDNAMES, [*test_rows, *real_rows])
    load_sessions(stimuli, registry_path)
    url_rows = [
        {
            "participant_number": f"P{index:02d}",
            "session_id": row["session_id"],
            "url": f"{base_url.rstrip('/')}?session={row['session_id']}",
            "reward_eligible": row["reward_eligible"],
            "assigned_item_ids": row["assigned_item_ids"],
        }
        for index, row in enumerate(real_rows, start=1)
    ]
    _write_csv(
        urls_path,
        (
            "participant_number",
            "session_id",
            "url",
            "reward_eligible",
            "assigned_item_ids",
        ),
        url_rows,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_ITEMS)
    parser.add_argument("--stimuli", type=Path, default=DEFAULT_STIMULI)
    parser.add_argument("--sessions", type=Path, default=DEFAULT_SESSIONS)
    parser.add_argument(
        "--staging-sessions", type=Path, default=DEFAULT_STAGING_SESSIONS
    )
    parser.add_argument("--production-registry", type=Path)
    parser.add_argument("--production-urls", type=Path)
    parser.add_argument(
        "--base-url", default="https://freek-participant-pilot.streamlit.app/"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if STIMULUS_COLUMNS != set(STIMULUS_FIELDNAMES) or (
        REQUIRED_COLUMNS | OPTIONAL_COLUMNS
    ) != set(SESSION_FIELDNAMES):
        raise RuntimeError("Builder columns no longer match the application contract.")
    build_test_data(
        args.source,
        args.stimuli,
        (args.sessions, args.staging_sessions),
    )
    print("Built 120 stimuli and two balanced 10-link test registries.")
    if bool(args.production_registry) != bool(args.production_urls):
        raise ValueError("Provide both production output paths or neither.")
    if args.production_registry and args.production_urls:
        build_production(
            stimuli_path=args.stimuli,
            registry_path=args.production_registry,
            urls_path=args.production_urls,
            base_url=args.base_url,
        )
        print(
            f"Built {MAXIMUM_PARTICIPANTS} private production URLs at "
            f"{args.production_urls}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
