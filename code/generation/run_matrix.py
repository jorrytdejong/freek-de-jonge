from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from core.llm import DEFAULT_MODEL, available_model_ids
from core.runner import run_matrix
from core.schemas import JokeRequest
from pipelines.conditions import PIPELINE_ORDER


def parse_args() -> argparse.Namespace:
    """Parse command-line options for the pipeline matrix.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Run the ACL final A1-E2 joke-generation matrix.")
    parser.add_argument("--topic", required=True, help="Topic for all selected pipelines.")
    parser.add_argument("--category", default=None, help="Humor category for B/D pipelines.")
    parser.add_argument("--audience", default="Dutch general audience")
    parser.add_argument("--format", default="short joke", dest="joke_format")
    parser.add_argument("--constraint", action="append", default=[], help="Extra constraint. Can be repeated.")
    parser.add_argument("--pipeline", action="append", choices=PIPELINE_ORDER, help="Pipeline code. Can be repeated.")
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=available_model_ids())
    parser.add_argument("--dry-run", action="store_true", help="Build prompts without calling the API.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> None:
    """Run selected conditions and emit their JSON results.

    Returns:
        None.
    """
    args = parse_args()
    request = JokeRequest(
        topic=args.topic,
        category=args.category,
        audience=args.audience,
        joke_format=args.joke_format,
        constraints=args.constraint,
    )
    results = run_matrix(
        request,
        pipeline_codes=args.pipeline,
        model=args.model,
        dry_run=args.dry_run,
    )
    payload = [asdict(result) for result in results]
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
