from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.categories import normalize_category
from core.category_examples import FREEK_LABELS_BY_CATEGORY


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FREEK_CATEGORY_SCRIPT_EXAMPLES_PATH = PROJECT_ROOT / "data" / "freek_category_script_opposition_examples.json"

PROMPT_FIELDS = (
    "text",
    "category_label",
    "category_score",
    "script_a",
    "script_b",
    "opposition_type",
    "trigger",
    "setup_reading",
    "punch_reinterpretation",
    "ambiguity_type",
    "script_confidence",
)


def load_freek_category_script_opposition_examples(category: str | None, limit: int = 5) -> list[dict[str, Any]]:
    """Load top Freek script-opposition examples for a category.

    Args:
        category: Category whose Freek examples should be loaded.
        limit: Maximum number of ranked examples to return.

    Returns:
        Examples ranked by category score and script confidence.
    """
    normalized = normalize_category(category)
    labels = FREEK_LABELS_BY_CATEGORY.get(normalized, (normalized,))
    try:
        data = json.loads(FREEK_CATEGORY_SCRIPT_EXAMPLES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    humor_types = data.get("humor_types", {})
    if not isinstance(humor_types, dict):
        return []

    examples = []
    seen_texts = set()
    for label in labels:
        raw_examples = humor_types.get(label, [])
        if not isinstance(raw_examples, list):
            continue
        for raw_example in raw_examples:
            if not isinstance(raw_example, dict):
                continue
            text = " ".join(str(raw_example.get("text", "")).split())
            if not text or text in seen_texts:
                continue
            example = {
                field: " ".join(str(raw_example.get(field, "")).split())
                for field in PROMPT_FIELDS
                if field not in {"category_score", "script_confidence"}
            }
            try:
                example["category_score"] = float(raw_example.get("category_score", 0.0))
            except (TypeError, ValueError):
                example["category_score"] = 0.0
            try:
                example["script_confidence"] = float(raw_example.get("script_confidence", 0.0))
            except (TypeError, ValueError):
                example["script_confidence"] = 0.0
            seen_texts.add(text)
            examples.append(example)

    examples.sort(
        key=lambda example: (
            float(example["category_score"]),
            float(example["script_confidence"]),
        ),
        reverse=True,
    )
    return examples[:limit]
