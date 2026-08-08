from __future__ import annotations

from core.categories import category_guidance
from core.category_guidance import freek_category_context
from core.comic_guidance import COMIC_REALIZATION_GUIDANCE
from core.freek_examples import freek_example_context
from core.schemas import FreekCategoryGuidanceOutput, JokeRequest, PipelineSpec, SemanticPlan
from core.styles import style_guidance


def condition_instructions(
    spec: PipelineSpec,
    plan: SemanticPlan,
    freek_guidance: FreekCategoryGuidanceOutput | dict[str, object] | None = None,
) -> str:
    """Build experiment-family instructions for a direct condition.

    Args:
        spec: Experiment condition specification.
        plan: Semantic plan containing optional category information.

    Returns:
        Condition-specific prompt instructions.

    Raises:
        ValueError: If the condition is not a direct-generation family.
    """
    if spec.family == "baseline":
        return """
Condition A: Baseline prompt.
Use only the topic.
""".strip()

    if spec.family == "category":
        context = (
            freek_category_context(plan.category, freek_guidance)
            if spec.code == "B2" and freek_guidance is not None
            else category_guidance(plan.category)
        )
        return f"""
Condition B: Category-guided generation.
Use the humor category as the main planning constraint.
Category context: {context}
Invent the setup, reversal, and wording for this topic during this run.
Do not explicitly explain the category in the joke.
""".strip()

    raise ValueError(f"Direct generation prompt is not available for family {spec.family!r}.")


def build_generation_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    plan: SemanticPlan,
    freek_guidance: FreekCategoryGuidanceOutput | dict[str, object] | None = None,
) -> str:
    """Build the direct-generation prompt for an A/B condition.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        plan: Semantic plan for the condition.

    Returns:
        Complete prompt for one structured model call.
    """
    freek_context = freek_example_context() if spec.code == "A2" else ""
    resolved_style_guidance = (
        "Write in Dutch. Deliver the joke as compact, performable cabaret material."
        if spec.code == "A1"
        else style_guidance(spec.style_mode)
    )
    prompt_pipeline_name = "Baseline Prompt" if spec.code == "A1" else spec.name
    sections = [
        f"""
You are generating one Dutch cabaret-style joke for an ACL humor-generation experiment.

Pipeline: {spec.code} - {prompt_pipeline_name}

Topic:
{request.topic}

Style mode:
{resolved_style_guidance}
""".strip()
    ]

    if spec.code == "A2" and freek_context:
        sections.append(
            f"""
A2 Freek example context:
{freek_context}
""".strip()
        )

    sections.append(
        f"""
Experimental condition:
{condition_instructions(spec, plan, freek_guidance)}

Output requirements:
- Write exactly one joke in Dutch.
{COMIC_REALIZATION_GUIDANCE}
- Keep it concise enough for blinded human evaluation.
- Return the joke in the text field and a concise description in the angle field.
- Do not include analysis or explanations inside the joke text.
""".strip()
    )
    return "\n\n".join(sections)
