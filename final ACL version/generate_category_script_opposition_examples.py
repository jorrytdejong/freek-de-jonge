from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import Field

from core.categories import CATEGORY_INVENTORY
from core.llm import DEFAULT_MODEL, MissingAPIKeyError, add_usage, generate_structured
from core.schemas import StrictStageModel, UsageSummary


PROJECT_ROOT = Path(__file__).resolve().parent
CATEGORY_EXAMPLES_PATH = PROJECT_ROOT / "data" / "category_examples.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "category_script_opposition_examples.json"


class ScriptOppositionExample(StrictStageModel):
    script_a: str = Field(min_length=1)
    script_b: str = Field(min_length=1)
    opposition_type: str = Field(min_length=1)
    trigger: str = Field(min_length=1)
    setup_reading: str = Field(min_length=1)
    punch_reinterpretation: str = Field(min_length=1)
    ambiguity_type: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


def build_prompt(category: str, joke_text: str) -> str:
    """Build a structured script-opposition analysis prompt.

    Args:
        category: Canonical humor category for the joke.
        joke_text: Dutch joke to analyze.

    Returns:
        Complete structured-analysis prompt.
    """
    category_info = CATEGORY_INVENTORY[category]
    payload = {
        "category": category,
        "category_description": category_info["description"],
        "category_setup_pattern": category_info["setup_script"],
        "category_opposing_pattern": category_info["opposing_script"],
        "category_trigger_pattern": category_info["trigger"],
        "joke_text": joke_text,
    }
    return f"""
You analyze a short Dutch joke example for a category-conditioned script-opposition prompt.

Return a compact Raskin-style script-opposition analysis. Use Dutch for creative fields
when natural, but keep technical labels concise.

Definitions:
- script_a: the normal, common-sense setup reading.
- script_b: the competing reading that makes the joke work.
- opposition_type: the main opposition axis, such as literal/figurative, normal/abnormal,
  polite/impolite, serious/trivial, high status/low status, possible/impossible, true/false.
- trigger: the concrete word, phrase, or move in the joke that lets script_b appear.
- setup_reading: how the audience is led into script_a.
- punch_reinterpretation: how the joke text flips or clashes with script_a.
- ambiguity_type: the mechanism, such as lexical ambiguity, presupposition shift,
  social norm violation, irony, category shift, taboo shift, or none/unclear.
- confidence: how strong the script-opposition analysis is.

Input:
{json.dumps(payload, ensure_ascii=False, indent=2)}

Return only the requested structured fields.
""".strip()


def load_category_examples() -> dict[str, list[str]]:
    """Load and normalize all source jokes grouped by category.

    Returns:
        Mapping from category names to normalized joke texts.
    """
    data = json.loads(CATEGORY_EXAMPLES_PATH.read_text(encoding="utf-8"))
    return {
        category: [" ".join(str(text).split()) for text in examples]
        for category, examples in data.items()
    }


def load_existing() -> dict:
    """Load previously generated analyses.

    Returns:
        Existing output data, or an empty dictionary when absent.
    """
    if not OUTPUT_PATH.exists():
        return {}
    return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))


def write_output(categories: dict[str, list[dict]], usage: UsageSummary | None) -> None:
    """Persist generated analyses and cumulative usage metadata.

    Args:
        categories: Generated analyses grouped by category.
        usage: Cumulative model usage, if model calls were made.

    Returns:
        None.
    """
    payload = {
        "metadata": {
            "source_file": str(CATEGORY_EXAMPLES_PATH.relative_to(PROJECT_ROOT)),
            "selection": "All category_examples.json jokes analyzed for script opposition.",
            "examples_per_category": 5,
            "analysis_model": usage.model if usage else None,
            "usage": None if usage is None else {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
            },
        },
        "categories": categories,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    """Generate missing category script-opposition analyses.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser(description="Generate script-opposition analyses for category examples.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    source = load_category_examples()
    existing = load_existing()
    categories: dict[str, list[dict]] = existing.get("categories", {})
    usage: UsageSummary | None = None

    for category, jokes in source.items():
        category_rows = categories.setdefault(category, [])
        existing_texts = {row.get("text") for row in category_rows}
        for joke_text in jokes:
            if joke_text in existing_texts:
                continue
            parsed, raw, stage_usage = generate_structured(
                build_prompt(category, joke_text),
                ScriptOppositionExample,
                model=args.model,
            )
            usage = add_usage(usage, stage_usage)
            row = {
                "text": joke_text,
                **parsed.model_dump(),
                "raw_response": raw,
            }
            category_rows.append(row)
            write_output(categories, usage)
            print(f"{category}: {len(category_rows)}/5")

    write_output(categories, usage)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except MissingAPIKeyError as exc:
        raise SystemExit(str(exc)) from exc
