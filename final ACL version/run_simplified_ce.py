from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from core.llm import DEFAULT_MODEL
from core.schemas import JokeRequest
from pipelines.conditions import PIPELINE_SPECS
from pipelines.simplified_ce import run_simplified_ce_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a separate, plain-language simplified C or E pipeline."
    )
    parser.add_argument("--pipeline", choices=("C1", "C2", "E1", "E2"), required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    result = run_simplified_ce_pipeline(
        PIPELINE_SPECS[args.pipeline],
        JokeRequest(topic=args.topic),
        model=args.model,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
