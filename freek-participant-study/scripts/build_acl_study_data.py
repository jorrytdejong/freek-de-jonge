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
from collections import Counter, deque
from collections.abc import Callable
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.acl_config import CONDITION_CODES, STUDY_VERSION
from app.acl_sessions import REQUIRED_COLUMNS, load_sessions
from app.acl_stimuli import REQUIRED_COLUMNS as STIMULUS_COLUMNS
from app.acl_stimuli import load_stimuli

SOURCE_ITEMS = (
    REPOSITORY_ROOT
    / "final ACL version"
    / "experiment_runs"
    / "acl_3x2_items_v1"
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


class _Dinic:
    def __init__(self, node_count: int) -> None:
        self.graph: list[list[list[object]]] = [[] for _ in range(node_count)]

    def add_edge(self, source: int, target: int, capacity: int, tag=None) -> None:
        forward: list[object] = [target, capacity, len(self.graph[target]), tag]
        backward: list[object] = [source, 0, len(self.graph[source]), None]
        self.graph[source].append(forward)
        self.graph[target].append(backward)

    def max_flow(self, source: int, sink: int) -> int:
        total = 0
        while True:
            level = [-1] * len(self.graph)
            level[source] = 0
            queue = deque([source])
            while queue:
                node = queue.popleft()
                for target, capacity, _, _ in self.graph[node]:
                    target = int(target)
                    if int(capacity) and level[target] < 0:
                        level[target] = level[node] + 1
                        queue.append(target)
            if level[sink] < 0:
                return total
            cursor = [0] * len(self.graph)

            def send(node: int, amount: int) -> int:
                if node == sink:
                    return amount
                while cursor[node] < len(self.graph[node]):
                    edge = self.graph[node][cursor[node]]
                    target, capacity, reverse, _ = edge
                    target = int(target)
                    if int(capacity) and level[target] == level[node] + 1:
                        pushed = send(target, min(amount, int(capacity)))
                        if pushed:
                            edge[1] = int(edge[1]) - pushed
                            reverse_edge = self.graph[target][int(reverse)]
                            reverse_edge[1] = int(reverse_edge[1]) + pushed
                            return pushed
                    cursor[node] += 1
                return 0

            while pushed := send(source, 10**9):
                total += pushed


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


def _selected_topics(participant_count: int) -> list[set[int]]:
    if participant_count % 5:
        raise ValueError("Balanced participant counts must be a multiple of five.")
    selected = []
    for participant in range(participant_count):
        omitted = {
            participant % 15,
            (participant + 5) % 15,
            (participant + 10) % 15,
        }
        selected.append(set(range(15)) - omitted)
    exposure = Counter(topic for topics in selected for topic in topics)
    if len(exposure) != 15 or len(set(exposure.values())) != 1:
        raise RuntimeError("Topic selection construction is not balanced.")
    return selected


def _condition_targets(participant_count: int) -> dict[tuple[int, int], int]:
    base = (2 * participant_count) // 15
    return {
        (topic, condition): base + (condition in {2 * (topic % 3), 2 * (topic % 3) + 1})
        for topic in range(15)
        for condition in range(6)
    }


def _assign_conditions(
    participant_count: int, selected: list[set[int]], seed: int
) -> dict[tuple[int, int], int]:
    targets = _condition_targets(participant_count)
    for attempt in range(100):
        randomizer = random.Random(seed + attempt)
        remaining = {
            (participant, topic)
            for participant, topics in enumerate(selected)
            for topic in topics
        }
        assignments: dict[tuple[int, int], int] = {}
        condition_order = list(range(6))
        randomizer.shuffle(condition_order)
        solved = True
        for condition in condition_order[:-1]:
            source = 0
            participant_offset = 1
            topic_offset = participant_offset + participant_count
            sink = topic_offset + 15
            network = _Dinic(sink + 1)
            for participant in range(participant_count):
                network.add_edge(source, participant_offset + participant, 2)
            edges = list(remaining)
            randomizer.shuffle(edges)
            for participant, topic in edges:
                network.add_edge(
                    participant_offset + participant,
                    topic_offset + topic,
                    1,
                    (participant, topic),
                )
            for topic in range(15):
                network.add_edge(
                    topic_offset + topic,
                    sink,
                    targets[topic, condition],
                )
            if network.max_flow(source, sink) != 2 * participant_count:
                solved = False
                break
            used = []
            for participant in range(participant_count):
                for edge in network.graph[participant_offset + participant]:
                    if edge[3] is not None and int(edge[1]) == 0:
                        used.append(edge[3])
            for edge in used:
                assignments[edge] = condition
                remaining.remove(edge)
        if not solved:
            continue
        final_condition = condition_order[-1]
        if not all(
            sum(participant == candidate for participant, _ in remaining) == 2
            for candidate in range(participant_count)
        ):
            continue
        if not all(
            sum(topic == candidate for _, topic in remaining)
            == targets[candidate, final_condition]
            for candidate in range(15)
        ):
            continue
        assignments.update({edge: final_condition for edge in remaining})
        return assignments
    raise RuntimeError("Could not construct the balanced condition assignment.")


def assignment_item_ids(participant_count: int, *, seed: int) -> list[list[str]]:
    selected = _selected_topics(participant_count)
    assignments = _assign_conditions(participant_count, selected, seed)
    all_rows: list[list[str]] = []
    for participant in range(participant_count):
        topics_by_condition: dict[int, list[int]] = {
            condition: [] for condition in range(6)
        }
        for topic in selected[participant]:
            topics_by_condition[assignments[participant, topic]].append(topic)
        condition_sequence = [
            (base_condition + participant) % 6
            for base_condition in (*range(6), *range(6))
        ]
        row: list[str] = []
        for position, condition in enumerate(condition_sequence):
            topics = topics_by_condition[condition]
            topics.sort(
                key=lambda topic: hashlib.sha256(
                    f"{seed}:{participant}:{condition}:{topic}".encode()
                ).digest()
            )
            topic = topics.pop()
            row.append(f"T{topic + 1:02d}-{CONDITION_CODES[condition]}")
        all_rows.append(row)
    validate_assignment_matrix(all_rows)
    return all_rows


def validate_assignment_matrix(rows: list[list[str]]) -> None:
    if not rows or any(len(row) != 12 or len(set(row)) != 12 for row in rows):
        raise ValueError("Every participant must have 12 unique items.")
    topic_exposure = Counter()
    condition_exposure = Counter()
    item_exposure = Counter()
    position_condition = Counter()
    for row in rows:
        topics = [item_id.split("-")[0] for item_id in row]
        conditions = [item_id.split("-")[1] for item_id in row]
        if len(set(topics)) != 12:
            raise ValueError("A participant has a repeated topic.")
        if Counter(conditions) != Counter(
            {condition: 2 for condition in CONDITION_CODES}
        ):
            raise ValueError("A participant does not have two items per condition.")
        topic_exposure.update(topics)
        condition_exposure.update(conditions)
        item_exposure.update(row)
        position_condition.update(enumerate(conditions, start=1))
    if len(set(topic_exposure.values())) != 1:
        raise ValueError("Topic exposure is not exact.")
    if len(set(condition_exposure.values())) != 1:
        raise ValueError("Condition exposure is not exact.")
    if max(item_exposure.values()) - min(item_exposure.values()) > 1:
        raise ValueError("Individual item exposure differs by more than one.")
    for position in range(1, 13):
        values = [
            position_condition[position, condition] for condition in CONDITION_CODES
        ]
        if max(values) - min(values) > 1:
            raise ValueError(f"Condition order is imbalanced at position {position}.")


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
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
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
            + hashlib.sha256(f"acl-test-{index}".encode()).hexdigest()[:8]
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
            + hashlib.sha256(f"acl-test-{index}".encode()).hexdigest()[:8]
        ),
        seed=20260806,
    )
    real_rows = session_rows(
        25,
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
        print(f"Built 25 private production URLs at {args.production_urls}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
