from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_OPPOSITION_EXAMPLES_PATH = PROJECT_ROOT / "data" / "freek_script_opposition_examples.json"

PROMPT_FIELDS = (
    "text",
    "script_a",
    "script_b",
    "opposition_type",
    "trigger",
    "setup_reading",
    "punch_reinterpretation",
    "ambiguity_type",
    "confidence",
)


def load_script_opposition_examples(limit: int = 5) -> list[dict[str, Any]]:
    """Load normalized Freek script-opposition examples.

    Args:
        limit: Maximum number of source examples to inspect.

    Returns:
        Normalized example dictionaries.
    """
    try:
        data = json.loads(SCRIPT_OPPOSITION_EXAMPLES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    raw_examples = data.get("examples", [])
    if not isinstance(raw_examples, list):
        return []

    examples = []
    for raw_example in raw_examples[:limit]:
        if not isinstance(raw_example, dict):
            continue
        example = {
            field: " ".join(str(raw_example.get(field, "")).split())
            for field in PROMPT_FIELDS
            if field != "confidence"
        }
        try:
            example["confidence"] = float(raw_example.get("confidence", 0.0))
        except (TypeError, ValueError):
            example["confidence"] = 0.0
        examples.append(example)
    return examples


def script_opposition_example_context() -> list[dict[str, Any]]:
    """Return Freek examples for prompt construction.

    Returns:
        Script-opposition example dictionaries.
    """
    return load_script_opposition_examples()
