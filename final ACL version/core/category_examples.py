from __future__ import annotations

import json
from pathlib import Path

from core.categories import normalize_category


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATEGORY_EXAMPLES_PATH = PROJECT_ROOT / "data" / "category_examples.json"
FREEK_CATEGORY_EXAMPLES_PATH = PROJECT_ROOT / "data" / "freek_category_examples.json"

FREEK_LABELS_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    "Domheid": ("Stupidity",),
    "Zelfspot": ("Self-mockery",),
    "Primitieve humor": ("Primitive humor",),
    "Zwarte humor": ("Black humor", "Dark humor"),
    "Ironie": ("Irony",),
    "Leedvermaak": ("Schadenfreude",),
    "Taalhumor": ("Language humor",),
    "Overdrijving": ("Exaggeration",),
    "Understatement": ("Understatement",),
    "De slimme observatie": ("Clever observation", "Observational humor"),
    "De plotselinge ommezwaai": ("Sudden twist",),
    "De verkeerde opmerking": ("Inappropriate remark",),
    "Cirkelhumor": ("Circular humor",),
    "Antihumor": ("Anti-humor", "Antihumor"),
}


def load_category_examples(category: str | None) -> list[str]:
    """Load and normalize generic examples for a humor category.

    Args:
        category: Category name, supported alias, or ``None``.

    Returns:
        Normalized example texts, or an empty list if loading fails.
    """
    normalized = normalize_category(category)
    try:
        data = json.loads(CATEGORY_EXAMPLES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    examples = data.get(normalized, [])
    if not isinstance(examples, list):
        return []

    return [" ".join(str(example).split()) for example in examples if str(example).strip()]


def category_example_context(category: str | None) -> str:
    """Format generic category examples as prompt context.

    Args:
        category: Category whose examples should be formatted.

    Returns:
        Prompt-ready example context, or an empty string when unavailable.
    """
    examples = load_category_examples(category)
    if not examples:
        return ""

    return "\n".join(
        [
            f"Example jokes for category {normalize_category(category)}:",
            *(f"- {example}" for example in examples),
            "",
            "Use these only as category examples. Do not copy wording, names, or situations.",
        ]
    )


def load_freek_category_examples(category: str | None, *, limit: int = 5) -> list[dict[str, str | float]]:
    """Load the highest-scoring Freek examples for a category.

    Args:
        category: Category whose Freek examples should be loaded.
        limit: Maximum number of examples to return.

    Returns:
        Example dictionaries sorted by descending score.
    """
    normalized = normalize_category(category)
    labels = FREEK_LABELS_BY_CATEGORY.get(normalized, (normalized,))
    try:
        data = json.loads(FREEK_CATEGORY_EXAMPLES_PATH.read_text(encoding="utf-8"))
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
            try:
                score = float(raw_example.get("score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            seen_texts.add(text)
            examples.append({"text": text, "score": score})

    examples.sort(key=lambda example: float(example["score"]), reverse=True)
    return examples[:limit]


def freek_category_example_context(category: str | None) -> str:
    """Format Freek category examples as prompt context.

    Args:
        category: Category whose Freek examples should be formatted.

    Returns:
        Prompt-ready example context, or an empty string when unavailable.
    """
    examples = load_freek_category_examples(category)
    if not examples:
        return ""

    normalized = normalize_category(category)
    return "\n".join(
        [
            f"Freek de Jonge examples for category {normalized}:",
            *(f"- [{example['score']:.2f}] {example['text']}" for example in examples),
            "",
            "Use these as Freek-style examples for the selected humor category. Do not copy wording, names, or situations.",
        ]
    )
