from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.llm import DEFAULT_MODEL
from core.schemas import JokeRequest
from pipelines.conditions import PIPELINE_SPECS
from pipelines.simplified_ce import run_simplified_ce_pipeline


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TOPICS = BASE_DIR / "experiments" / "freek_style_topics_v2.json"
WRITE_LOCK = threading.Lock()


def load_topics(path: Path, limit: int) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    topics = payload["topics"]
    if len(topics) < limit:
        raise ValueError(f"Requested {limit} topics, but {path} contains {len(topics)}.")
    return topics[:limit]


def load_or_create_output(
    path: Path,
    *,
    model: str,
    topics_path: Path,
    topic_count: int,
) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "pipeline_implementation": "simplified_ce",
        "pipelines": ["C2", "E2"],
        "model": model,
        "topics_source": str(topics_path),
        "topic_count": topic_count,
        "requested_joke_count": topic_count * 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": [],
        "errors": [],
    }


def save(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def generate(job: tuple[dict[str, str], str], model: str) -> dict[str, Any]:
    topic, code = job
    result = run_simplified_ce_pipeline(
        PIPELINE_SPECS[code],
        JokeRequest(topic=topic["label"]),
        model=model,
    )
    return {
        "item_id": f'{topic["id"]}-{code}',
        "topic_id": topic["id"],
        "topic": topic["label"],
        "condition_code": code,
        "joke": result.joke,
        "warnings": result.warnings,
        "usage": asdict(result.usage) if result.usage else None,
        "semantic_plan": asdict(result.semantic_plan),
        "metadata": result.metadata,
        "prompt": result.prompt,
        "raw_response": json.loads(result.raw_response),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a resumable simplified C2/E2 batch.")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS)
    parser.add_argument("--topic-count", type=int, default=10)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    topics = load_topics(args.topics, args.topic_count)
    payload = load_or_create_output(
        args.output,
        model=args.model,
        topics_path=args.topics,
        topic_count=args.topic_count,
    )
    completed = {item["item_id"] for item in payload["items"]}
    jobs = [
        (topic, code)
        for topic in topics
        for code in ("C2", "E2")
        if f'{topic["id"]}-{code}' not in completed
    ]
    print(f"Starting {len(jobs)} remaining jobs with {args.workers} workers.", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(generate, job, args.model): job for job in jobs}
        for future in as_completed(futures):
            topic, code = futures[future]
            item_id = f'{topic["id"]}-{code}'
            with WRITE_LOCK:
                try:
                    item = future.result()
                    payload["items"].append(item)
                    payload["items"].sort(key=lambda value: value["item_id"])
                    print(f"Completed {item_id}: {item['joke']}", flush=True)
                except Exception as exc:
                    payload["errors"] = [
                        error for error in payload["errors"] if error["item_id"] != item_id
                    ]
                    payload["errors"].append(
                        {"item_id": item_id, "error": f"{type(exc).__name__}: {exc}"}
                    )
                    print(f"Failed {item_id}: {type(exc).__name__}: {exc}", flush=True)
                payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                save(args.output, payload)

    print(
        f"Saved {len(payload['items'])} jokes and {len(payload['errors'])} errors to {args.output}",
        flush=True,
    )


if __name__ == "__main__":
    main()
