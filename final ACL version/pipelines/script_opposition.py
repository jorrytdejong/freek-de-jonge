from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, TypeVar

from pydantic import BaseModel

from core.categories import category_defaults, normalize_category
from core.category_script_opposition_examples import load_category_script_opposition_examples
from core.freek_category_script_opposition_examples import load_freek_category_script_opposition_examples
from core.llm import add_usage, generate_structured
from core.prompting import build_generation_prompt
from core.schemas import (
    CriticOutput,
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
from core.script_opposition_examples import script_opposition_example_context
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
    """Build shared input with condition-specific examples.

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
        examples = script_opposition_example_context()
        if examples:
            payload["script_opposition_examples"] = examples
            payload["script_opposition_example_instruction"] = (
                "Use these Freek de Jonge examples as context for how script opposition can be analyzed. "
                "Do not copy wording, names, or specific situations."
            )
    if spec.code == "D1":
        category = normalize_category(request.category)
        examples = load_category_script_opposition_examples(category)
        if examples:
            payload["category_script_opposition_examples"] = examples
            payload["category_script_opposition_example_instruction"] = (
                "Use these examples as context for how the selected humor category can map to script opposition. "
                "Do not copy wording, names, or specific situations."
            )
    if spec.code == "D2":
        category = normalize_category(request.category)
        examples = load_freek_category_script_opposition_examples(category)
        if examples:
            payload["freek_category_script_opposition_examples"] = examples
            payload["freek_category_script_opposition_example_instruction"] = (
                "Use these Freek de Jonge examples as context for how the selected humor category can map to "
                "script opposition in Freek-style cabaret. Do not copy wording, names, or specific situations."
            )
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


def build_script_b_candidates_prompt(spec: PipelineSpec, request: JokeRequest, script_a: str) -> str:
    """Build the prompt that proposes opposing second scripts.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        script_a: Normal setup interpretation from the previous stage.

    Returns:
        Script B candidate-generation prompt.
    """
    category = normalize_category(request.category) if spec.family == "category_script" else None
    category_context = category_defaults(category) if category else None
    payload = {
        **_base_payload(spec, request),
        "script_a": script_a,
        "category": category,
        "category_context": category_context,
    }
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
    category = normalize_category(request.category) if spec.family == "category_script" else None
    payload = {
        **_base_payload(spec, request),
        "category": category,
        "script_a": script_a,
        "candidates": [asdict(candidate) for candidate in candidates],
    }
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
    category = normalize_category(request.category) if spec.family == "category_script" else None
    payload = {
        **_base_payload(spec, request),
        "category": category,
        "category_context": category_defaults(category) if category else None,
        "script_a": script_a,
        "script_b": script_b,
    }
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


def build_generator_prompt(spec: PipelineSpec, request: JokeRequest, plan: SemanticPlan) -> str:
    """Build the prompt that generates variants from a plan.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        plan: Completed semantic joke plan.

    Returns:
        Joke-variant generation prompt.
    """
    payload = {
        **_base_payload(spec, request),
        "plan": asdict(plan),
    }
    return _structured_prompt(
        """
You write jokes from a semantic plan.
Always write all joke variants in Dutch.

Stage 5: Joke generation.
Write three distinct joke variants that preserve the same script opposition.
Let the setup feel socially normal and recognizable before the punch reveals the opposite second reading.
Prefer a clear semantic reversal over shock value.
The second reading should feel surprisingly true, not merely fictional.
Make each joke concise and end on the strongest word or phrase.
Return structured variants with text and angle fields.
""".strip(),
        payload,
    )


def build_critic_prompt(spec: PipelineSpec, request: JokeRequest, plan: SemanticPlan, variants: list[JokeVariant]) -> str:
    """Build the prompt that selects the strongest variant.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        plan: Completed semantic joke plan.
        variants: Generated joke variants to evaluate.

    Returns:
        Critic selection prompt.
    """
    payload = {
        **_base_payload(spec, request),
        "plan": asdict(plan),
        "variants": [asdict(variant) for variant in variants],
    }
    return _structured_prompt(
        """
You select the best joke.
The winning joke must remain in Dutch.

Stage 6: Critic selection.
Pick the variant with:
- the clearest setup
- the strongest reinterpretation
- the best fit to the requested style mode
- the strongest realization of the semantic plan

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
    defaults = category_defaults(category)
    script_a = defaults["setup_script"]
    script_b = defaults["opposing_script"]
    plan = SemanticPlan(
        category=category,
        setup_script=script_a,
        opposing_script=script_b,
        opposition_type="dry-run opposition",
        trigger=defaults["trigger"],
        setup_goal="activate the normal first reading",
        punch_goal="shift to the opposing second reading",
        style_mode=spec.style_mode,
    )
    prompts = [
        ("script_a", build_script_a_prompt(spec, request)),
        ("script_b_candidates", build_script_b_candidates_prompt(spec, request, script_a)),
        (
            "script_b_ranker",
            build_script_b_ranker_prompt(spec, request, script_a, [ScriptBCandidate(script_b=script_b)]),
        ),
        ("plan_context", build_plan_context_prompt(spec, request, script_a, script_b)),
        ("variants", build_generator_prompt(spec, request, plan)),
        ("critic", build_critic_prompt(spec, request, plan, [JokeVariant(text="[dry run variant]", angle="dry run")])),
    ]
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
        script_b_rationale="Dry run used category/default script-opposition placeholders.",
        variants=[variant],
        metadata={"family": spec.family, "style_mode": spec.style_mode, "stages": [stage for stage, _ in prompts]},
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

    candidates_payload, raw, stage_usage = _stage_call(
        build_script_b_candidates_prompt(spec, request, script_a),
        stage="script_b_candidates",
        model=model,
        response_model=ScriptBCandidatesOutput,
    )
    raw_responses["script_b_candidates"] = raw
    usage = add_usage(usage, stage_usage)
    candidates = [ScriptBCandidate(script_b=candidate.script_b) for candidate in candidates_payload.candidates]

    selection_payload, raw, stage_usage = _stage_call(
        build_script_b_ranker_prompt(spec, request, script_a, candidates),
        stage="script_b_ranker",
        model=model,
        response_model=ScriptBSelectionOutput,
    )
    raw_responses["script_b_ranker"] = raw
    usage = add_usage(usage, stage_usage)
    script_b = selection_payload.script_b
    rationale = selection_payload.rationale

    plan_payload, raw, stage_usage = _stage_call(
        build_plan_context_prompt(spec, request, script_a, script_b),
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
        build_generator_prompt(spec, request, plan),
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
        build_critic_prompt(spec, request, plan, variants),
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

    prompt = "\n\n---\n\n".join(
        [
            f"## script_a\n{build_script_a_prompt(spec, request)}",
            f"## script_b_candidates\n{build_script_b_candidates_prompt(spec, request, script_a)}",
            f"## script_b_ranker\n{build_script_b_ranker_prompt(spec, request, script_a, candidates)}",
            f"## plan_context\n{build_plan_context_prompt(spec, request, script_a, script_b)}",
            f"## variants\n{build_generator_prompt(spec, request, plan)}",
            f"## critic\n{build_critic_prompt(spec, request, plan, variants)}",
        ]
    )
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
        metadata={"family": spec.family, "style_mode": spec.style_mode, "stages": list(raw_responses)},
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
        trigger=category_defaults(request.category)["trigger"] if spec.family == "category" else None,
        style_mode=spec.style_mode,
    )
    prompt = build_generation_prompt(spec, request, plan)
    if dry_run:
        joke = "[dry run] Prompt built successfully; no joke was generated."
        angle = "direct generation"
        raw_response = joke
        usage = None
    else:
        parsed, raw_response, usage = generate_structured(prompt, JokeVariantOutput, model=model)
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
        metadata={"family": spec.family, "style_mode": spec.style_mode, "stages": ["direct_generation"]},
    )
