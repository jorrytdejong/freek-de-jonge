from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, TypeVar

from pydantic import BaseModel

from core.categories import category_guidance, normalize_category
from core.category_guidance import build_freek_category_guidance_prompt, freek_category_context
from core.comic_guidance import COMIC_REALIZATION_GUIDANCE, COMIC_SELECTION_GUIDANCE
from core.freek_examples import freek_example_context
from core.llm import add_usage, generate_structured
from core.prompting import build_generation_prompt
from core.schemas import (
    CriticOutput,
    FreekCategoryGuidanceOutput,
    JokeRequest,
    JokeVariant,
    JokeVariantOutput,
    JokeVariantsOutput,
    PipelineResult,
    PipelineSpec,
    ScriptAOutput,
    ScriptBCandidatesOutput,
    ScriptBCandidate,
    ScriptBSelectionOutput,
    SemanticPlan,
    SemanticPlanOutput,
    UsageSummary,
)
from core.styles import style_guidance

StageOutput = TypeVar("StageOutput", bound=BaseModel)


def _structured_prompt(task: str, payload: dict[str, Any]) -> str:
    """Combine stage instructions and input into one prompt.

    Args:
        task: Instructions for the current pipeline stage.
        payload: Structured input supplied to the stage.

    Returns:
        Prompt containing the instructions and serialized payload.
    """
    return f"{task}\n\nInput:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\nReturn the requested structured fields."


def _base_payload(spec: PipelineSpec, request: JokeRequest) -> dict[str, Any]:
    """Build shared topic and style input.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.

    Returns:
        Base stage payload for the selected condition.
    """
    payload: dict[str, Any] = {
        "topic": request.topic,
        "style_guidance": style_guidance(spec.style_mode),
    }
    if spec.code == "C2":
        examples = freek_example_context()
        if examples:
            payload["freek_examples"] = examples
            payload["freek_example_instruction"] = (
                "Use these Freek de Jonge jokes as general stylistic context. "
                "Do not copy wording, names, or specific situations."
            )
    return payload


def _category_stage_context(
    spec: PipelineSpec,
    request: JokeRequest,
    freek_guidance: FreekCategoryGuidanceOutput | dict[str, object] | None,
) -> dict[str, object] | None:
    """Return category guidance for D stages after category-neutral Script A."""
    if spec.family != "category_script":
        return None
    if spec.code == "D2":
        if freek_guidance is None:
            raise ValueError("D2 requires guidance derived from category-matched Freek jokes.")
        return freek_category_context(request.category, freek_guidance)
    return category_guidance(request.category)


def _stage_payload(
    spec: PipelineSpec,
    request: JokeRequest,
    freek_guidance: FreekCategoryGuidanceOutput | dict[str, object] | None,
    **values: Any,
) -> dict[str, Any]:
    """Build a stage payload without leaking category fields into C conditions."""
    payload = {**_base_payload(spec, request), **values}
    category_context = _category_stage_context(spec, request, freek_guidance)
    if category_context is not None:
        payload["category_context"] = category_context
    return payload


def _stage_call(
    prompt: str,
    *,
    stage: str,
    model: str,
    response_model: type[StageOutput],
) -> tuple[StageOutput, str, UsageSummary]:
    """Run one structured stage with contextualized errors.

    Args:
        prompt: Complete stage prompt.
        stage: Stage name used in error messages.
        model: OpenAI model identifier.
        response_model: Pydantic output type for the stage.

    Returns:
        Parsed stage output, raw response text, and token usage.

    Raises:
        ValueError: If structured generation fails.
    """
    try:
        parsed, raw, usage = generate_structured(prompt, response_model, model=model)
    except ValueError as exc:
        raise ValueError(f"{stage} structured output failed: {exc}") from exc
    return parsed, raw, usage


def build_script_a_prompt(spec: PipelineSpec, request: JokeRequest) -> str:
    """Build the prompt that identifies the normal setup script.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.

    Returns:
        Script A stage prompt.
    """
    payload = _base_payload(spec, request)
    return _structured_prompt(
        """
You design jokes using script opposition.
Always write creative fields in Dutch.

Stage 1: Script A.
Given a topic and style mode:
1. ask how a general audience perceives this topic
2. ask how they usually feel about it
3. ask what their normal relationship to it is
4. compress those answers into one concise script_a

Script A must be the most normal, common-sense reading of the topic.
Return the script_a field.
""".strip(),
        payload,
    )


def build_script_b_candidates_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    script_a: str,
    freek_guidance: FreekCategoryGuidanceOutput | dict[str, object] | None = None,
) -> str:
    """Build the prompt that proposes opposing second scripts.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        script_a: Normal setup interpretation from the previous stage.

    Returns:
        Script B candidate-generation prompt.
    """
    payload = _stage_payload(spec, request, freek_guidance, script_a=script_a)
    return _structured_prompt(
        """
You generate conflicting second readings for a joke plan.
Always write creative fields in Dutch.

Stage 2: Script B candidates.
Generate 4 distinct script_b candidates.
Each candidate must be the opposite of script_a, not merely different.
Prefer clean opposition axes such as actual/non-actual, true/false, real/unreal,
normal/abnormal, possible/impossible, good/bad, life/death, non-sex/sex,
money/non-money, high-status/low-status, public/private, literal/social meaning.
The opposite script must still feel true, plausible, or recognizable.
Prefer candidates that could share a trigger word or phrase with script_a.

If a humor category is provided, use it to shape the kind of opposition.
Return the candidates as structured script_b fields.
""".strip(),
        payload,
    )


def build_script_b_ranker_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    script_a: str,
    candidates: list[ScriptBCandidate],
    freek_guidance: FreekCategoryGuidanceOutput | dict[str, object] | None = None,
) -> str:
    """Build the prompt that selects the strongest opposing script.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        script_a: Normal setup interpretation.
        candidates: Candidate opposing interpretations to rank.

    Returns:
        Script B ranking prompt.
    """
    payload = _stage_payload(
        spec,
        request,
        freek_guidance,
        script_a=script_a,
        candidates=[asdict(candidate) for candidate in candidates],
    )
    return _structured_prompt(
        """
You rank candidate second readings for a joke.
Always write creative fields in Dutch.

Stage 3: Script B ranking.
Select the single best script_b candidate based on:
- clearest opposite of script_a
- strongest truth-value opposition when available
- strongest single opposition axis
- strongest sense of being true or recognizable in its own right
- best shared-trigger potential
- best payoff potential for the requested style and category

Return the script_b and rationale fields.
""".strip(),
        payload,
    )


def build_plan_context_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    script_a: str,
    script_b: str,
    freek_guidance: FreekCategoryGuidanceOutput | dict[str, object] | None = None,
) -> str:
    """Build the prompt that completes the semantic joke plan.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        script_a: Normal setup interpretation.
        script_b: Selected opposing interpretation.

    Returns:
        Semantic plan stage prompt.
    """
    payload = _stage_payload(spec, request, freek_guidance, script_a=script_a, script_b=script_b)
    return _structured_prompt(
        """
You finalize a semantic joke plan from a chosen script opposition.
Always write creative fields in Dutch.

Stage 4: Semantic plan.
Given the request, script_a, selected script_b, and optional category:
1. name the opposition type
2. identify the trigger that supports both readings
3. define the setup goal
4. define the punch goal

Keep every field concise and specific.
Return opposition_type, trigger, setup_goal, and punch_goal.
""".strip(),
        payload,
    )


def build_generator_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    plan: SemanticPlan,
    freek_guidance: FreekCategoryGuidanceOutput | dict[str, object] | None = None,
) -> str:
    """Build the prompt that generates variants from a plan.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        plan: Completed semantic joke plan.

    Returns:
        Joke-variant generation prompt.
    """
    payload = _stage_payload(spec, request, freek_guidance, plan=asdict(plan))
    return _structured_prompt(
        f"""
You write jokes from a semantic plan.
Always write all joke variants in Dutch.

Stage 5: Joke generation.
Write three distinct joke variants that preserve the same script opposition.
Let the setup feel socially normal and recognizable before the punch reveals the opposite second reading.
Prefer a clear semantic reversal over shock value.
Do not merely state that both readings are true or summarize the social contradiction.
Make each joke concise and end on the strongest word or phrase.

{COMIC_REALIZATION_GUIDANCE}

Return structured variants with text and angle fields.
""".strip(),
        payload,
    )


def build_critic_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    plan: SemanticPlan,
    variants: list[JokeVariant],
    freek_guidance: FreekCategoryGuidanceOutput | dict[str, object] | None = None,
) -> str:
    """Build the prompt that selects the strongest variant.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        plan: Completed semantic joke plan.
        variants: Generated joke variants to evaluate.

    Returns:
        Critic selection prompt.
    """
    payload = _stage_payload(
        spec,
        request,
        freek_guidance,
        plan=asdict(plan),
        variants=[asdict(variant) for variant in variants],
    )
    return _structured_prompt(
        f"""
You select the best joke.
The winning joke must remain in Dutch.

Stage 6: Critic selection.
{COMIC_SELECTION_GUIDANCE}

After applying that eligibility test, pick the variant with:
1. the strongest immediate comic payoff
2. the clearest and latest punchline
3. the most concrete and performable wording
4. the best fit to the requested style mode
5. the strongest realization of the semantic plan

Return the text and angle fields.
The text must exactly match one generated variant.
""".strip(),
        payload,
    )


def dry_run_script_opposition_pipeline(spec: PipelineSpec, request: JokeRequest) -> PipelineResult:
    """Build all staged prompts without making model calls.

    Args:
        spec: Script-opposition condition specification.
        request: User-supplied joke request.

    Returns:
        Dry-run result containing every constructed stage prompt.
    """
    category = normalize_category(request.category) if spec.family == "category_script" else None
    script_a = "[generated during Script A stage]"
    script_b = "[generated during Script B selection]"
    freek_guidance: dict[str, object] | None = None
    if spec.code == "D2":
        freek_guidance = {
            "category_realization": "[derived from category-matched Freek jokes]",
            "tonal_tendencies": ["[derived during Freek category guidance stage]"],
            "generation_guidelines": ["[derived during Freek category guidance stage]"],
        }
    plan = SemanticPlan(
        category=category,
        setup_script=script_a,
        opposing_script=script_b,
        opposition_type="dry-run opposition",
        trigger="[generated during semantic planning]",
        setup_goal="activate the normal first reading",
        punch_goal="shift to the opposing second reading",
        style_mode=spec.style_mode,
    )
    prompts = [("script_a", build_script_a_prompt(spec, request))]
    if spec.code == "D2":
        prompts.append(("freek_category_guidance", build_freek_category_guidance_prompt(category)))
    prompts.extend([
        ("script_b_candidates", build_script_b_candidates_prompt(spec, request, script_a, freek_guidance)),
        (
            "script_b_ranker",
            build_script_b_ranker_prompt(
                spec,
                request,
                script_a,
                [ScriptBCandidate(script_b=script_b)],
                freek_guidance,
            ),
        ),
        ("plan_context", build_plan_context_prompt(spec, request, script_a, script_b, freek_guidance)),
        ("variants", build_generator_prompt(spec, request, plan, freek_guidance)),
        (
            "critic",
            build_critic_prompt(
                spec,
                request,
                plan,
                [JokeVariant(text="[dry run variant]", angle="dry run")],
                freek_guidance,
            ),
        ),
    ])
    prompt = "\n\n---\n\n".join(f"## {stage}\n{stage_prompt}" for stage, stage_prompt in prompts)
    variant = JokeVariant(text="[dry run] Staged script-opposition prompts built successfully.", angle="dry run")
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=spec.name,
        request=request,
        prompt=prompt,
        joke=variant.text,
        semantic_plan=plan,
        raw_response=prompt,
        script_b_candidates=[ScriptBCandidate(script_b=script_b)],
        script_b_rationale="Dry run used runtime-generation placeholders, not category semantic defaults.",
        variants=[variant],
        metadata={
            "family": spec.family,
            "style_mode": spec.style_mode,
            "category_context_source": (
                "freek_category_jokes" if spec.code == "D2" else "general_description" if spec.code == "D1" else None
            ),
            "stages": [stage for stage, _ in prompts],
        },
    )


def run_script_opposition_pipeline(spec: PipelineSpec, request: JokeRequest, *, model: str) -> PipelineResult:
    """Run the six-stage script-opposition pipeline.

    Args:
        spec: Script-opposition condition specification.
        request: User-supplied joke request.
        model: OpenAI model identifier.

    Returns:
        Generated joke, semantic trace, variants, and usage metadata.
    """
    raw_responses: dict[str, str] = {}
    usage: UsageSummary | None = None

    script_a_payload, raw, stage_usage = _stage_call(
        build_script_a_prompt(spec, request),
        stage="script_a",
        model=model,
        response_model=ScriptAOutput,
    )
    raw_responses["script_a"] = raw
    usage = add_usage(usage, stage_usage)
    script_a = script_a_payload.script_a

    freek_guidance: FreekCategoryGuidanceOutput | None = None
    if spec.code == "D2":
        freek_guidance, raw, stage_usage = _stage_call(
            build_freek_category_guidance_prompt(request.category),
            stage="freek_category_guidance",
            model=model,
            response_model=FreekCategoryGuidanceOutput,
        )
        raw_responses["freek_category_guidance"] = raw
        usage = add_usage(usage, stage_usage)

    candidates_payload, raw, stage_usage = _stage_call(
        build_script_b_candidates_prompt(spec, request, script_a, freek_guidance),
        stage="script_b_candidates",
        model=model,
        response_model=ScriptBCandidatesOutput,
    )
    raw_responses["script_b_candidates"] = raw
    usage = add_usage(usage, stage_usage)
    candidates = [ScriptBCandidate(script_b=candidate.script_b) for candidate in candidates_payload.candidates]

    selection_payload, raw, stage_usage = _stage_call(
        build_script_b_ranker_prompt(spec, request, script_a, candidates, freek_guidance),
        stage="script_b_ranker",
        model=model,
        response_model=ScriptBSelectionOutput,
    )
    raw_responses["script_b_ranker"] = raw
    usage = add_usage(usage, stage_usage)
    script_b = selection_payload.script_b
    rationale = selection_payload.rationale

    plan_payload, raw, stage_usage = _stage_call(
        build_plan_context_prompt(spec, request, script_a, script_b, freek_guidance),
        stage="plan_context",
        model=model,
        response_model=SemanticPlanOutput,
    )
    raw_responses["plan_context"] = raw
    usage = add_usage(usage, stage_usage)
    plan = SemanticPlan(
        category=normalize_category(request.category) if spec.family == "category_script" else None,
        setup_script=script_a,
        opposing_script=script_b,
        opposition_type=plan_payload.opposition_type,
        trigger=plan_payload.trigger,
        setup_goal=plan_payload.setup_goal,
        punch_goal=plan_payload.punch_goal,
        style_mode=spec.style_mode,
    )

    variants_payload, raw, stage_usage = _stage_call(
        build_generator_prompt(spec, request, plan, freek_guidance),
        stage="variants",
        model=model,
        response_model=JokeVariantsOutput,
    )
    raw_responses["variants"] = raw
    usage = add_usage(usage, stage_usage)
    variants = [
        JokeVariant(text=variant.text, angle=variant.angle)
        for variant in variants_payload.variants
    ]

    critic_payload, raw, stage_usage = _stage_call(
        build_critic_prompt(spec, request, plan, variants, freek_guidance),
        stage="critic",
        model=model,
        response_model=CriticOutput,
    )
    raw_responses["critic"] = raw
    usage = add_usage(usage, stage_usage)
    best = next(
        (variant for variant in variants if variant.text == critic_payload.text),
        JokeVariant(text=critic_payload.text, angle=critic_payload.angle),
    )

    prompts = [("script_a", build_script_a_prompt(spec, request))]
    if spec.code == "D2":
        prompts.append(("freek_category_guidance", build_freek_category_guidance_prompt(request.category)))
    prompts.extend(
        [
            ("script_b_candidates", build_script_b_candidates_prompt(spec, request, script_a, freek_guidance)),
            ("script_b_ranker", build_script_b_ranker_prompt(spec, request, script_a, candidates, freek_guidance)),
            ("plan_context", build_plan_context_prompt(spec, request, script_a, script_b, freek_guidance)),
            ("variants", build_generator_prompt(spec, request, plan, freek_guidance)),
            ("critic", build_critic_prompt(spec, request, plan, variants, freek_guidance)),
        ]
    )
    prompt = "\n\n---\n\n".join(f"## {stage}\n{stage_prompt}" for stage, stage_prompt in prompts)
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=spec.name,
        request=request,
        prompt=prompt,
        joke=best.text,
        semantic_plan=plan,
        raw_response=json.dumps(raw_responses, ensure_ascii=False, indent=2),
        script_b_candidates=candidates,
        script_b_rationale=rationale,
        variants=variants,
        usage=usage,
        metadata={
            "family": spec.family,
            "style_mode": spec.style_mode,
            "category_context_source": (
                "freek_category_jokes" if spec.code == "D2" else "general_description" if spec.code == "D1" else None
            ),
            "freek_category_guidance": freek_guidance.model_dump() if freek_guidance else None,
            "stages": list(raw_responses),
        },
    )


def run_direct_condition(spec: PipelineSpec, request: JokeRequest, *, model: str, dry_run: bool) -> PipelineResult:
    """Run or dry-run a direct generation condition.

    Args:
        spec: Direct-generation condition specification.
        request: User-supplied joke request.
        model: OpenAI model identifier.
        dry_run: Whether to build the prompt without a model call.

    Returns:
        Direct-generation or dry-run pipeline result.
    """
    plan = SemanticPlan(
        category=normalize_category(request.category) if spec.family == "category" else None,
        style_mode=spec.style_mode,
    )
    freek_guidance: FreekCategoryGuidanceOutput | dict[str, object] | None = None
    guidance_prompt = None
    if spec.code == "B2":
        guidance_prompt = build_freek_category_guidance_prompt(request.category)

    if dry_run:
        if spec.code == "B2":
            freek_guidance = {
                "category_realization": "[derived from category-matched Freek jokes]",
                "tonal_tendencies": ["[derived during Freek category guidance stage]"],
                "generation_guidelines": ["[derived during Freek category guidance stage]"],
            }
        generation_prompt = build_generation_prompt(spec, request, plan, freek_guidance)
        prompt = (
            f"## freek_category_guidance\n{guidance_prompt}\n\n---\n\n## direct_generation\n{generation_prompt}"
            if guidance_prompt
            else generation_prompt
        )
        joke = "[dry run] Prompt built successfully; no joke was generated."
        angle = "direct generation"
        raw_response = joke
        usage = None
    else:
        raw_responses: dict[str, str] = {}
        usage = None
        if guidance_prompt:
            freek_guidance, raw, stage_usage = _stage_call(
                guidance_prompt,
                stage="freek_category_guidance",
                model=model,
                response_model=FreekCategoryGuidanceOutput,
            )
            raw_responses["freek_category_guidance"] = raw
            usage = add_usage(usage, stage_usage)
        generation_prompt = build_generation_prompt(spec, request, plan, freek_guidance)
        prompt = (
            f"## freek_category_guidance\n{guidance_prompt}\n\n---\n\n## direct_generation\n{generation_prompt}"
            if guidance_prompt
            else generation_prompt
        )
        parsed, raw, stage_usage = generate_structured(generation_prompt, JokeVariantOutput, model=model)
        raw_responses["direct_generation"] = raw
        usage = add_usage(usage, stage_usage)
        raw_response = json.dumps(raw_responses, ensure_ascii=False, indent=2)
        joke = parsed.text
        angle = parsed.angle
    variant = JokeVariant(text=joke, angle=angle)
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=spec.name,
        request=request,
        prompt=prompt,
        joke=joke,
        semantic_plan=plan,
        raw_response=raw_response,
        variants=[variant],
        usage=usage,
        metadata={
            "family": spec.family,
            "style_mode": spec.style_mode,
            "category_context_source": (
                "freek_category_jokes" if spec.code == "B2" else "general_description" if spec.code == "B1" else None
            ),
            "freek_category_guidance": (
                freek_guidance.model_dump() if isinstance(freek_guidance, FreekCategoryGuidanceOutput) else None
            ),
            "stages": ["freek_category_guidance", "direct_generation"] if spec.code == "B2" else ["direct_generation"],
        },
    )
