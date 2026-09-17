from __future__ import annotations

import json
from pathlib import Path


GENERATION_ROOT = Path(__file__).resolve().parents[1]
CATEGORY_JSON_DIR = GENERATION_ROOT / "data" / "source_examples"

EXAMPLE_SEGMENTS = [
    (
        "2005 - Freek de Jonge - Cordon Sanitaire (België)_laughter_with_humor_categories.json",
        1,
    ),
    (
        "2005 - Freek de Jonge - Cordon Sanitaire (België)_laughter_with_humor_categories.json",
        2,
    ),
    (
        "2010 - Freek de Jonge - Het Verlossende Woord_laughter_with_humor_categories.json",
        2,
    ),
    (
        "2010 - Freek de Jonge - Het Verlossende Woord_laughter_with_humor_categories.json",
        3,
    ),
    (
        "2014 - Freek de Jonge - Als je me nu nog niet kent - Deel 2 - Na de pauze_laughter_with_humor_categories.json",
        3,
    ),
    (
        "2014 - Freek de Jonge - Als je me nu nog niet kent - Deel 2 - Na de pauze_laughter_with_humor_categories.json",
        7,
    ),
    (
        "2020 - Freek de Jonge - Asociale afstand - Carre 5-7-2020_laughter_with_humor_categories.json",
        6,
    ),
    (
        "2020 - Freek de Jonge - Asociale afstand - Carre 5-7-2020_laughter_with_humor_categories.json",
        12,
    ),
    (
        "2025 - Freek de Jonge - Club Haug Rotterdam 22 april én KS Den Haag 23 april De Zeeuwse Jaren_laughter_with_humor_categories.json",
        18,
    ),
    (
        "2025 - Freek de Jonge - Club Haug Rotterdam 22 april én KS Den Haag 23 april De Zeeuwse Jaren_laughter_with_humor_categories.json",
        20,
    ),
]


def _segment_text(path: Path, index: int) -> str | None:
    """Read and normalize one transcript segment.

    Args:
        path: Path to a categorized transcript JSON file.
        index: Zero-based segment position to read.

    Returns:
        Normalized segment text, or ``None`` when it cannot be read.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        text = data["segments"][index].get("text", "")
    except (FileNotFoundError, IndexError, KeyError, TypeError, json.JSONDecodeError):
        return None
    text = " ".join(str(text).split())
    return text or None


def freek_example_context() -> str:
    """Build prompt context from selected Freek segments.

    Returns:
        Prompt-ready examples, or an empty string when none are available.
    """
    examples = []
    for filename, segment_index in EXAMPLE_SEGMENTS:
        text = _segment_text(CATEGORY_JSON_DIR / filename, segment_index)
        if text:
            examples.append(f"- {text}")

    if not examples:
        return ""

    return "\n".join(
        [
            "Simple Freek de Jonge context examples from real categorized segments:",
            *examples,
            "",
            "Use these only as lightweight tonal and contextual references. Do not copy wording, names, or specific situations.",
        ]
    )
