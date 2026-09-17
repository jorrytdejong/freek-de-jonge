from __future__ import annotations

from core.categories import category_defaults
from core.category_examples import category_example_context, freek_category_example_context
from core.freek_examples import freek_example_context
from core.joke_length import joke_length_instruction
from core.schemas import JokeRequest, PipelineSpec, SemanticPlan
from core.styles import style_guidance


def condition_instructions(spec: PipelineSpec, plan: SemanticPlan) -> str:
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
Use only the topic.
""".strip()

    if spec.family == "category":
        return f"""
Use the humor category as the main planning constraint.
Humor category: {plan.category}
Likely setup pattern: {category_defaults(plan.category)["setup_script"]}
Likely turn pattern: {category_defaults(plan.category)["opposing_script"]}
Likely trigger type: {category_defaults(plan.category)["trigger"]}
Do not explicitly explain the category in the joke.
""".strip()

    raise ValueError(f"Direct generation prompt is not available for family {spec.family!r}.")


def build_generation_prompt(spec: PipelineSpec, request: JokeRequest, plan: SemanticPlan) -> str:
    """Build the direct-generation prompt for an A/B condition.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        plan: Semantic plan for the condition.

    Returns:
        Complete prompt for one structured model call.
    """
    freek_context = freek_example_context() if spec.code == "A2" else ""
    category_context = category_example_context(request.category) if spec.code == "B1" else ""
    freek_category_context = freek_category_example_context(request.category) if spec.code == "B2" else ""
    sections = [
        f"""
You are generating one Dutch cabaret-style joke:

Topic:
{request.topic}
""".strip()
    ]

    if spec.style_mode == "freek" and spec.code != "A2":
        sections.append(
            f"""
Style mode:
{style_guidance(spec.style_mode)}
""".strip()
        )

    if spec.code == "A2" and freek_context:
        sections.append(
            f"""
Style examples:
{freek_context}
""".strip()
        )

    if spec.code == "B1" and category_context:
        sections.append(
            f"""
Category examples:
{category_context}
""".strip()
        )

    if spec.code == "B2" and freek_category_context:
        sections.append(
            f"""
Style-and-category examples:
{freek_category_context}
""".strip()
        )

    sections.append(
        f"""
Generation guidance:
{condition_instructions(spec, plan)}

Output requirements:
- Write exactly one joke in Dutch.
- {joke_length_instruction()}
- Write for spoken delivery by one comedian: include a recognizable setup, a clear
  turn or misdirection, and a final punchline that creates the laugh.
- Do not write an observation, explanation, summary, moral, slogan, or policy statement.
- Do not end with an abstract conclusion; the final sentence must be the punchline.
- Read the joke aloud mentally and rewrite it if it does not sound performable.
- Return the joke in the text field and a concise description in the angle field.
- Do not include analysis or explanations inside the joke text.
""".strip()
    )
    return "\n\n".join(sections)
