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
from app.acl_sessions import REQUIRED_COLUMNS, load_sessions
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
    if len(rows) != 90:
        raise ValueError(f"Expected 90 source items; found {len(rows)} in {source}.")
    return rows


def _topic_condition_offsets(seed: int) -> list[int]:
    """Return a fixed randomized condition offset for each of the 15 topics.

    Three alternating conditions receive three topics and the other three
    receive two. Rotating these offsets by participant makes total condition
    exposure differ by at most one at every recruitment prefix.
    """
    offsets = [*range(6), *range(6), 0, 2, 4]
    random.Random(seed).shuffle(offsets)
    return offsets


def _repeat_assignments(
    participant: int,
    *,
    seed: int,
    base_conditions: list[int],
    item_exposure: Counter[str],
) -> list[str]:
    """Choose nine second-topic items while filling every condition to four.

    Moving the nine-topic window by six positions balances topic repetition.
    A small dynamic program then chooses distinct conditions, preferring the
    least-exposed topic-condition items in the registry built so far.
    """
    selected_topics = [(participant * 6 + step) % 15 for step in range(9)]
    base_counts = Counter(base_conditions)
    initial_quotas = tuple(4 - base_counts[condition] for condition in range(6))
    selected_topics.sort(
        key=lambda topic: hashlib.sha256(
            f"{seed}:{participant}:{topic}:repeat-topic".encode()
        ).digest()
    )

    @lru_cache(maxsize=None)
    def solve(index: int, quotas: tuple[int, ...]) -> tuple[int, int, tuple[int, ...]]:
        if index == len(selected_topics):
            if any(quotas):
                raise ValueError("Could not fill the repeat-condition quotas.")
            return (0, 0, ())
        topic = selected_topics[index]
        candidates = []
        for condition, quota in enumerate(quotas):
            if quota == 0 or condition == base_conditions[topic]:
                continue
            next_quotas = list(quotas)
            next_quotas[condition] -= 1
            try:
                future_exposure, future_tie, future_choices = solve(
                    index + 1, tuple(next_quotas)
                )
            except ValueError:
                continue
            item_id = f"T{topic + 1:02d}-{CONDITION_CODES[condition]}"
            tie = int.from_bytes(
                hashlib.sha256(
                    f"{seed}:{participant}:{topic}:{condition}:repeat".encode()
                ).digest()[:4]
            )
            candidates.append(
                (
                    item_exposure[item_id] + future_exposure,
                    tie + future_tie,
                    (condition, *future_choices),
                )
            )
        if not candidates:
            raise ValueError("No valid repeat-condition assignment exists.")
        return min(candidates)

    _, _, choices = solve(0, initial_quotas)
    return [
        f"T{topic + 1:02d}-{CONDITION_CODES[condition]}"
        for topic, condition in zip(selected_topics, choices, strict=True)
    ]


def _display_order(item_ids: list[str], *, participant: int, seed: int) -> list[str]:
    """Return a deterministic shuffle with repeated topics well separated."""
    random_seed = int.from_bytes(
        hashlib.sha256(f"{seed}:{participant}:display".encode()).digest()[:8]
    )
    generator = random.Random(random_seed)
    for _ in range(10_000):
        candidate = item_ids.copy()
        generator.shuffle(candidate)
        positions: dict[str, list[int]] = {}
        for position, item_id in enumerate(candidate):
            positions.setdefault(item_id.split("-")[0], []).append(position)
        if all(
            len(topic_positions) == 1 or topic_positions[1] - topic_positions[0] >= 5
            for topic_positions in positions.values()
        ):
            return candidate
    raise ValueError("Could not separate repeated topics in the display order.")


@lru_cache(maxsize=None)
def _complete_assignment_matrix(seed: int) -> tuple[tuple[str, ...], ...]:
    """Build and cache the locked 50-person matrix before taking prefixes."""
    offsets = _topic_condition_offsets(seed)
    item_exposure: Counter[str] = Counter()
    base_conditions_by_participant: list[list[int]] = []
    repeat_pairs: list[list[list[int]]] = []
    for participant in range(MAXIMUM_PARTICIPANTS):
        base_conditions = [(offset + participant) % 6 for offset in offsets]
        base_conditions_by_participant.append(base_conditions)
        base_ids = [
            f"T{topic + 1:02d}-{CONDITION_CODES[condition]}"
            for topic, condition in enumerate(base_conditions)
        ]
        repeat_ids = _repeat_assignments(
            participant,
            seed=seed,
            base_conditions=base_conditions,
            item_exposure=item_exposure,
        )
        repeat_pairs.append(
            [
                [int(item_id[1:3]) - 1, CONDITION_CODES.index(item_id[4:])]
                for item_id in repeat_ids
            ]
        )
        item_exposure.update([*base_ids, *repeat_ids])

    # Swapping two repeat-condition labels within one participant preserves
    # that person's four-per-condition quota and their selected topics. Use
    # those swaps to make every recruitment prefix from 25 onward differ by
    # at most two item ratings, while making the final 50-person registry
    # optimal: 60 items receive 13 ratings and 30 receive 14.
    prefix_exposure: list[Counter[tuple[int, int]]] = []
    running_exposure: Counter[tuple[int, int]] = Counter()
    for base_conditions, participant_pairs in zip(
        base_conditions_by_participant, repeat_pairs, strict=True
    ):
        running_exposure.update(enumerate(base_conditions))
        running_exposure.update(tuple(pair) for pair in participant_pairs)
        prefix_exposure.append(running_exposure.copy())
    final_minimum = 60 * 13**2 + 30 * 14**2
    objective = sum(
        prefix_exposure[-1][topic, condition] ** 2
        for topic in range(15)
        for condition in range(6)
    )
    generator = random.Random(seed ^ 0x24A11C)
    for _ in range(200_000):
        if objective == final_minimum:
            break
        participant = generator.randrange(MAXIMUM_PARTICIPANTS)
        first, second = generator.sample(range(9), 2)
        topic_1, condition_1 = repeat_pairs[participant][first]
        topic_2, condition_2 = repeat_pairs[participant][second]
        base_conditions = base_conditions_by_participant[participant]
        if (
            condition_1 == condition_2
            or condition_2 == base_conditions[topic_1]
            or condition_1 == base_conditions[topic_2]
        ):
            continue
        changes = (
            ((topic_1, condition_1), -1),
            ((topic_2, condition_2), -1),
            ((topic_1, condition_2), 1),
            ((topic_2, condition_1), 1),
        )
        old_cost = sum(prefix_exposure[-1][key] ** 2 for key, _ in changes)
        new_cost = sum(
            (prefix_exposure[-1][key] + change) ** 2 for key, change in changes
        )
        if new_cost > old_cost:
            continue
        valid_prefixes = True
        for prefix_index in range(max(24, participant), MAXIMUM_PARTICIPANTS):
            changed = {
                key: prefix_exposure[prefix_index][key] + change
                for key, change in changes
            }
            values = [
                changed.get(
                    (topic, condition),
                    prefix_exposure[prefix_index][topic, condition],
                )
                for topic in range(15)
                for condition in range(6)
            ]
            if max(values) - min(values) > 2:
                valid_prefixes = False
                break
        if not valid_prefixes:
            continue
        for key, change in changes:
            for prefix_index in range(participant, MAXIMUM_PARTICIPANTS):
                prefix_exposure[prefix_index][key] += change
        repeat_pairs[participant][first][1] = condition_2
        repeat_pairs[participant][second][1] = condition_1
        objective += new_cost - old_cost
    if objective != final_minimum:
        raise ValueError("Could not balance item exposure across 50 sessions.")

    all_rows = []
    for participant, (base_conditions, participant_pairs) in enumerate(
        zip(base_conditions_by_participant, repeat_pairs, strict=True)
    ):
        row = [
            f"T{topic + 1:02d}-{CONDITION_CODES[condition]}"
            for topic, condition in enumerate(base_conditions)
        ]
        row.extend(
            f"T{topic + 1:02d}-{CONDITION_CODES[condition]}"
            for topic, condition in participant_pairs
        )
        all_rows.append(tuple(_display_order(row, participant=participant, seed=seed)))
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
        raise ValueError("Every participant must have 24 unique items.")
    topic_exposure = Counter()
    condition_exposure = Counter()
    item_exposure = Counter()
    for row in rows:
        topics = [item_id.split("-")[0] for item_id in row]
        conditions = [item_id.split("-")[1] for item_id in row]
        topic_counts = Counter(topics)
        if sorted(topic_counts.values()) != [1] * 6 + [2] * 9:
            raise ValueError("A participant must cover all topics and repeat nine.")
        frequencies = [Counter(conditions).get(code, 0) for code in CONDITION_CODES]
        if frequencies != [4] * 6:
            raise ValueError("A participant must receive four items per condition.")
        topic_positions: dict[str, list[int]] = {}
        for position, topic in enumerate(topics):
            topic_positions.setdefault(topic, []).append(position)
        if any(
            len(positions) == 2 and positions[1] - positions[0] < 5
            for positions in topic_positions.values()
        ):
            raise ValueError("Repeated topics are too close in the display order.")
        topic_exposure.update(topics)
        condition_exposure.update(conditions)
        item_exposure.update(row)
    if max(topic_exposure.values()) - min(topic_exposure.values()) > 1:
        raise ValueError("Topic exposure differs by more than one.")
    if condition_exposure != Counter(
        {condition: len(rows) * 4 for condition in CONDITION_CODES}
    ):
        raise ValueError("Condition exposure is not exact.")
    expected_items = {
        f"T{topic:02d}-{condition}"
        for topic in range(1, 16)
        for condition in CONDITION_CODES
    }
    complete_item_exposure = Counter({item_id: 0 for item_id in expected_items})
    complete_item_exposure.update(item_exposure)
    item_range = max(complete_item_exposure.values()) - min(
        complete_item_exposure.values()
    )
    if len(rows) >= 25 and item_range > 2:
        raise ValueError("Individual item exposure differs by more than two.")
    if len(rows) == MAXIMUM_PARTICIPANTS and item_range > 1:
        raise ValueError("Final individual item exposure differs by more than one.")
    for block_start in range(0, len(rows) - 5, 6):
        block = rows[block_start : block_start + 6]
        for topic in range(1, 16):
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
) -> list[dict[str, str]]:
    assignments = assignment_item_ids(participant_count, seed=seed)
    label = "Test session" if is_test else "Production participant"
    return [
        {
            "session_id": id_factory(index),
            "is_test": str(is_test).lower(),
            "active": "true",
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
            + hashlib.sha256(f"acl-test-24-items-{index}".encode()).hexdigest()[:8]
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
            + hashlib.sha256(f"acl-test-24-items-{index}".encode()).hexdigest()[:8]
        ),
        seed=20260806,
    )
    real_rows = session_rows(
        MAXIMUM_PARTICIPANTS,
        is_test=False,
        created_at=date.today(),
        id_factory=lambda _: f"participant-{secrets.token_urlsafe(16)}",
        seed=20260806,
    )
    _write_csv(registry_path, SESSION_FIELDNAMES, [*test_rows, *real_rows])
    load_sessions(stimuli, registry_path)
    url_rows = [
        {
            "participant_number": f"P{index:02d}",
            "session_id": row["session_id"],
            "url": f"{base_url.rstrip('/')}?session={row['session_id']}",
            "assigned_item_ids": row["assigned_item_ids"],
        }
        for index, row in enumerate(real_rows, start=1)
    ]
    _write_csv(
        urls_path,
        ("participant_number", "session_id", "url", "assigned_item_ids"),
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
    if STIMULUS_COLUMNS != set(STIMULUS_FIELDNAMES) or REQUIRED_COLUMNS != set(
        SESSION_FIELDNAMES
    ):
        raise RuntimeError("Builder columns no longer match the application contract.")
    build_test_data(
        args.source,
        args.stimuli,
        (args.sessions, args.staging_sessions),
    )
    print("Built 90 stimuli and two balanced 10-link test registries.")
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
