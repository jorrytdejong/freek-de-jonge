from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.categories import normalize_category


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATEGORY_SCRIPT_EXAMPLES_PATH = PROJECT_ROOT / "data" / "category_script_opposition_examples.json"

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


def load_category_script_opposition_examples(category: str | None, limit: int = 5) -> list[dict[str, Any]]:
    """Load normalized script-opposition examples for a category.

    Args:
        category: Category whose examples should be loaded.
        limit: Maximum number of source rows to inspect.

    Returns:
        Normalized script-opposition example dictionaries.
    """
    normalized = normalize_category(category)
    try:
        data = json.loads(CATEGORY_SCRIPT_EXAMPLES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    categories = data.get("categories", {})
    if not isinstance(categories, dict):
        return []

    raw_examples = categories.get(normalized, [])
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
