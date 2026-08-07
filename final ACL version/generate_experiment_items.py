#!/usr/bin/env python3
"""Generate the locked 3 x 2 ACL stimulus bank with resumable checkpoints.

Each topic-condition result is written atomically to its own JSON file. Running
the command again skips valid completed files and continues with missing jobs.
The first valid result is retained; this prevents manual outcome selection.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.llm import DEFAULT_MODEL
from core.runner import run_pipeline
from core.schemas import JokeRequest
from pipelines.conditions import PIPELINE_SPECS


STUDY_ID = "acl_3x2_items_v1"
SCHEMA_VERSION = 1
PROMPT_VERSION = "repository_state_at_generation"
CONDITION_CODES = ("A1", "A2", "C1", "C2", "E1", "E2")
SCHEDULE_SEED = 20260806
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TOPICS = BASE_DIR / "experiments" / "freek_style_topics_v1.json"
DEFAULT_OUTPUT_DIR = BASE_DIR / "experiment_runs" / STUDY_ID


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_topics(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    topics = payload.get("topics")
    if not isinstance(topics, list) or len(topics) != 15:
        raise ValueError("The locked topic manifest must contain exactly 15 topics.")
    ids = [item.get("id") for item in topics]
    labels = [item.get("label") for item in topics]
    if len(set(ids)) != 15 or len(set(labels)) != 15 or not all(ids) or not all(labels):
        raise ValueError("Topic IDs and labels must be present and unique.")
    return payload


def build_jobs(topics: list[dict[str, str]]) -> list[dict[str, str]]:
    jobs = [
        {
            "job_id": f"{topic['id']}-{condition}",
            "topic_id": topic["id"],
            "topic": topic["label"],
            "condition_code": condition,
        }
        for topic in topics
        for condition in CONDITION_CODES
    ]
    random.Random(SCHEDULE_SEED).shuffle(jobs)
    return jobs


def item_path(output_dir: Path, job_id: str) -> Path:
    return output_dir / "items" / f"{job_id}.json"


def validate_item(
    payload: dict[str, Any], job: dict[str, str], *, model: str, dry_run: bool
) -> tuple[bool, str]:
    expected = {
        "schema_version": SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "job_id": job["job_id"],
        "topic_id": job["topic_id"],
        "topic": job["topic"],
        "condition_code": job["condition_code"],
        "model": model,
        "dry_run": dry_run,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            return False, f"{key} mismatch"
    result = payload.get("result")
    if not isinstance(result, dict):
        return False, "missing result object"
    if result.get("pipeline_code") != job["condition_code"]:
        return False, "pipeline code mismatch"
    if result.get("request", {}).get("topic") != job["topic"]:
        return False, "request topic mismatch"
    if not dry_run and not str(result.get("joke", "")).strip():
        return False, "empty joke"
    stored_hash = payload.get("result_sha256")
    if stored_hash != sha256(result):
        return False, "result hash mismatch"
    return True, "valid"


def read_valid_item(
    path: Path, job: dict[str, str], *, model: str, dry_run: bool
) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"unreadable: {exc}"
    valid, reason = validate_item(payload, job, model=model, dry_run=dry_run)
    return (payload if valid else None), reason


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_run_manifest(
    output_dir: Path,
    *,
    topics_payload: dict[str, Any],
    topics_path: Path,
    model: str,
    dry_run: bool,
    jobs: list[dict[str, str]],
) -> None:
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "design": "3 pipeline families x 2 Freek-style modes",
        "conditions": [
            {
                "code": code,
                "family": PIPELINE_SPECS[code].family,
                "style_mode": PIPELINE_SPECS[code].style_mode,
                "name": PIPELINE_SPECS[code].name,
            }
            for code in CONDITION_CODES
        ],
        "model": model,
        "dry_run": dry_run,
        "prompt_version": PROMPT_VERSION,
        "topic_manifest": str(topics_path.resolve()),
        "topic_manifest_sha256": sha256(topics_payload),
        "schedule_seed": SCHEDULE_SEED,
        "acceptance_rule": "Retain the first structurally valid output; retry only failed or invalid jobs.",
        "number_of_topics": len(topics_payload["topics"]),
        "number_of_conditions": len(CONDITION_CODES),
        "number_of_jobs": len(jobs),
        "generation_order": [job["job_id"] for job in jobs],
    }
    path = output_dir / "run_manifest.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != manifest:
            raise RuntimeError(
                f"Run manifest conflict at {path}. Use a new output directory for a changed setup."
            )
    else:
        atomic_write_json(path, manifest)


def append_failure(output_dir: Path, job: dict[str, str], attempt: int, exc: Exception) -> None:
    failure = {
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "job": job,
        "attempt": attempt,
        "exception_type": type(exc).__name__,
        "message": str(exc),
    }
    failure_dir = output_dir / "failures"
    failure_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    atomic_write_json(failure_dir / f"{job['job_id']}-{stamp}.json", failure)


def completed_items(
    output_dir: Path, jobs: list[dict[str, str]], *, model: str, dry_run: bool
) -> list[dict[str, Any]]:
    completed: list[dict[str, Any]] = []
    for job in jobs:
        payload, _ = read_valid_item(
            item_path(output_dir, job["job_id"]), job, model=model, dry_run=dry_run
        )
        if payload is not None:
            completed.append(payload)
    return completed


def write_registry(output_dir: Path, items: list[dict[str, Any]]) -> None:
    registry_path = output_dir / "stimulus_registry.csv"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = registry_path.with_suffix(".csv.tmp")
    fields = [
        "job_id",
        "topic_id",
        "topic",
        "condition_code",
        "pipeline_family",
        "style_mode",
        "model",
        "generated_at",
        "joke",
        "warnings",
        "result_sha256",
        "item_file",
    ]
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in sorted(items, key=lambda value: value["job_id"]):
            writer.writerow(
                {
                    "job_id": item["job_id"],
                    "topic_id": item["topic_id"],
                    "topic": item["topic"],
                    "condition_code": item["condition_code"],
                    "pipeline_family": item["pipeline_family"],
                    "style_mode": item["style_mode"],
                    "model": item["model"],
                    "generated_at": item["generated_at"],
                    "joke": item["result"]["joke"],
                    "warnings": " | ".join(item["result"].get("warnings", [])),
                    "result_sha256": item["result_sha256"],
                    "item_file": f"items/{item['job_id']}.json",
                }
            )
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, registry_path)


def generate(args: argparse.Namespace) -> int:
    topics_path = args.topics.resolve()
    output_dir = args.output_dir.resolve()
    topics_payload = load_topics(topics_path)
    jobs = build_jobs(topics_payload["topics"])
    write_run_manifest(
        output_dir,
        topics_payload=topics_payload,
        topics_path=topics_path,
        model=args.model,
        dry_run=args.dry_run,
        jobs=jobs,
    )

    done_before = completed_items(output_dir, jobs, model=args.model, dry_run=args.dry_run)
    print(f"Run {STUDY_ID}: {len(done_before)}/{len(jobs)} valid checkpoints already present.", flush=True)
    if args.status:
        write_registry(output_dir, done_before)
        return 0

    generated_now = 0
    failures_now = 0
    for position, job in enumerate(jobs, start=1):
        path = item_path(output_dir, job["job_id"])
        existing, reason = read_valid_item(path, job, model=args.model, dry_run=args.dry_run)
        if existing is not None:
            continue
        if path.exists():
            raise RuntimeError(f"Refusing to overwrite invalid checkpoint {path}: {reason}")
        if args.max_items is not None and generated_now >= args.max_items:
            break

        spec = PIPELINE_SPECS[job["condition_code"]]
        attempt = 1 + len(list((output_dir / "failures").glob(f"{job['job_id']}-*.json")))
        print(
            f"[{position:02d}/{len(jobs)}] generating {job['job_id']} "
            f"({spec.family}, style={spec.style_mode}, model={args.model})",
            flush=True,
        )
        try:
            request = JokeRequest(topic=job["topic"], category=None)
            result = run_pipeline(
                job["condition_code"], request, model=args.model, dry_run=args.dry_run
            )
            result_payload = asdict(result)
            item = {
                "schema_version": SCHEMA_VERSION,
                "study_id": STUDY_ID,
                **job,
                "pipeline_family": spec.family,
                "style_mode": spec.style_mode,
                "model": args.model,
                "prompt_version": PROMPT_VERSION,
                "dry_run": args.dry_run,
                "attempt": attempt,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "result": result_payload,
                "result_sha256": sha256(result_payload),
            }
            valid, validation_reason = validate_item(
                item, job, model=args.model, dry_run=args.dry_run
            )
            if not valid:
                raise ValueError(f"Generated result failed validation: {validation_reason}")
            atomic_write_json(path, item)
            generated_now += 1
            print(f"  checkpointed {path.name}", flush=True)
        except Exception as exc:  # preserve progress and record enough context to retry
            failures_now += 1
            append_failure(output_dir, job, attempt, exc)
            print(f"  FAILED {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            if args.stop_on_error:
                break

    completed = completed_items(output_dir, jobs, model=args.model, dry_run=args.dry_run)
    write_registry(output_dir, completed)
    print(
        f"Progress: {len(completed)}/{len(jobs)} complete; "
        f"{generated_now} generated and {failures_now} failed in this invocation.",
        flush=True,
    )
    return 1 if failures_now else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    args = parser.parse_args()
    if args.max_items is not None and args.max_items < 1:
        parser.error("--max-items must be at least 1")
    return args


if __name__ == "__main__":
    raise SystemExit(generate(parse_args()))
