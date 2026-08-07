from __future__ import annotations

import json

from core.categories import category_guidance, normalize_category
from core.category_examples import load_freek_category_examples
from core.schemas import FreekCategoryGuidanceOutput


def build_freek_category_guidance_prompt(category: str | None) -> str:
    """Build a prompt that derives guidance from category-matched Freek jokes."""
    normalized = normalize_category(category)
    examples = load_freek_category_examples(normalized)
    if not examples:
        raise ValueError(
            f"No Freek de Jonge jokes tagged with {normalized!r} are available. "
            "B2 and D2 require category-matched Freek examples and will not use a generic fallback."
        )

    payload = {
        "category_guidance": category_guidance(normalized),
        "freek_jokes_tagged_with_category": examples,
    }
    return f"""
You analyze Freek de Jonge jokes that have been tagged with one humor category.
Derive fresh, high-level guidance for realizing that category in a newly generated joke.

Rules:
- Ground every observation in recurring properties of the supplied jokes.
- Describe tone, rhetoric, perspective, pacing, and category realization.
- Do not propose a setup script, opposing script, semantic trigger, topic, punchline, or new joke.
- Do not repeat names, situations, or distinctive wording from an example.
- Do not claim that the generated joke was written by Freek de Jonge.

Input:
{json.dumps(payload, ensure_ascii=False, indent=2)}

Return category_realization, tonal_tendencies, and generation_guidelines.
""".strip()


def freek_category_context(
    category: str | None,
    guidance: FreekCategoryGuidanceOutput | dict[str, object],
) -> dict[str, object]:
    """Combine the general category definition with freshly derived Freek guidance."""
    profile = guidance.model_dump() if isinstance(guidance, FreekCategoryGuidanceOutput) else guidance
    return {
        **category_guidance(category),
        "context_source": "Freek de Jonge jokes tagged with the selected category",
        "derived_freek_category_guidance": profile,
    }
