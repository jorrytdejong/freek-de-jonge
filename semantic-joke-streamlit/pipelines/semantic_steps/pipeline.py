from __future__ import annotations

from time import perf_counter

from openai import OpenAI

from core.llm import require_client, structured_call
from core.pipeline import PipelineDefinition
from core.usage import summarize_usage
from pipelines.semantic_steps.prompts import (
    CRITIC_PROMPT,
    GENERATOR_PROMPT,
    PLAN_CONTEXT_PROMPT,
    SCRIPT_A_PROMPT,
    SCRIPT_B_CANDIDATES_PROMPT,
    SCRIPT_B_RANKER_PROMPT,
)
from schemas import (
    JokeRequest,
    JokeResult,
    JokeVariant,
    JokeVariantsPayload,
    ScriptASeed,
    ScriptBCandidate,
    ScriptBCandidatesPayload,
    ScriptBSelection,
    SemanticPlan,
    SemanticPlanContext,
    UsageSummary,
)


PIPELINE_ID = "semantic_steps"
PIPELINE_NAME = "Script Opposition Pipeline"
PIPELINE_DESCRIPTION = "Six separate structured calls: script A, candidates, ranker, plan, variants, critic."


def assemble_plan(
    script_a_seed: ScriptASeed,
    script_b_selection: ScriptBSelection,
    plan_context: SemanticPlanContext,
) -> SemanticPlan:
    return SemanticPlan(
        script_a=script_a_seed.script_a,
        script_b=script_b_selection.script_b,
        opposition_type=plan_context.opposition_type,
        trigger=plan_context.trigger,
        setup_goal=plan_context.setup_goal,
        punch_goal=plan_context.punch_goal,
    )


def make_script_a(request: JokeRequest, client: OpenAI) -> tuple[ScriptASeed, UsageSummary | None]:
    script_a_seed, usage = structured_call(
        client,
        SCRIPT_A_PROMPT,
        {
            "topic": request.topic,
            "audience": request.audience,
            "voice": request.voice,
            "format": request.format,
            "constraints": request.constraints,
        },
        ScriptASeed,
    )
    return script_a_seed, usage


def generate_script_b_candidates(
    request: JokeRequest,
    script_a_seed: ScriptASeed,
    client: OpenAI,
) -> tuple[list[ScriptBCandidate], UsageSummary | None]:
    payload, usage = structured_call(
        client,
        SCRIPT_B_CANDIDATES_PROMPT,
        {
            "request": request.model_dump(),
            "script_a": script_a_seed.script_a,
        },
        ScriptBCandidatesPayload,
    )
    if not payload.candidates:
        raise ValueError("Script B generation returned no candidates.")
    return payload.candidates, usage


def rank_script_b_candidates(
    request: JokeRequest,
    script_a_seed: ScriptASeed,
    candidates: list[ScriptBCandidate],
    client: OpenAI,
) -> tuple[ScriptBSelection, UsageSummary | None]:
    if not candidates:
        raise ValueError("Script B ranking requires at least one candidate.")
    selection, usage = structured_call(
        client,
        SCRIPT_B_RANKER_PROMPT,
        {
            "request": request.model_dump(),
            "script_a": script_a_seed.script_a,
            "candidates": [candidate.model_dump() for candidate in candidates],
        },
        ScriptBSelection,
    )
    return selection, usage


def finalize_plan(
    request: JokeRequest,
    script_a_seed: ScriptASeed,
    script_b_selection: ScriptBSelection,
    client: OpenAI,
) -> tuple[SemanticPlan, UsageSummary | None]:
    payload, usage = structured_call(
        client,
        PLAN_CONTEXT_PROMPT,
        {
            "request": request.model_dump(),
            "script_a": script_a_seed.script_a,
            "script_b": script_b_selection.script_b,
        },
        SemanticPlanContext,
    )
    return assemble_plan(script_a_seed, script_b_selection, payload), usage


def generate_jokes(
    request: JokeRequest,
    plan: SemanticPlan,
    client: OpenAI,
) -> tuple[list[JokeVariant], UsageSummary | None]:
    payload, usage = structured_call(
        client,
        GENERATOR_PROMPT,
        {
            "request": request.model_dump(),
            "plan": plan.model_dump(),
        },
        JokeVariantsPayload,
    )
    if not payload.variants:
        raise ValueError("Joke generation returned no variants.")
    return payload.variants, usage


def pick_best(
    request: JokeRequest,
    plan: SemanticPlan,
    variants: list[JokeVariant],
    client: OpenAI,
) -> tuple[JokeVariant, UsageSummary | None]:
    if not variants:
        raise ValueError("Selection requires at least one joke variant.")
    best_joke, usage = structured_call(
        client,
        CRITIC_PROMPT,
        {
            "request": request.model_dump(),
            "plan": plan.model_dump(),
            "variants": [variant.model_dump() for variant in variants],
        },
        JokeVariant,
    )
    return best_joke, usage


def run(request: JokeRequest, client: OpenAI | None = None) -> JokeResult:
    client = require_client(client)
    started_at = perf_counter()
    usages: list[UsageSummary] = []

    script_a_seed, usage = make_script_a(request, client=client)
    if usage is not None:
        usages.append(usage)

    script_b_candidates, usage = generate_script_b_candidates(request, script_a_seed, client=client)
    if usage is not None:
        usages.append(usage)

    script_b_selection, usage = rank_script_b_candidates(request, script_a_seed, script_b_candidates, client=client)
    if usage is not None:
        usages.append(usage)

    plan, usage = finalize_plan(request, script_a_seed, script_b_selection, client=client)
    if usage is not None:
        usages.append(usage)

    variants, usage = generate_jokes(request, plan, client=client)
    if usage is not None:
        usages.append(usage)

    best_joke, usage = pick_best(request, plan, variants, client=client)
    if usage is not None:
        usages.append(usage)

    return JokeResult(
        request=request,
        plan=plan,
        script_b_candidates=script_b_candidates,
        script_b_rationale=script_b_selection.rationale,
        variants=variants,
        best_joke=best_joke,
        usage=summarize_usage(usages, started_at),
    )


PIPELINE = PipelineDefinition(
    id=PIPELINE_ID,
    name=PIPELINE_NAME,
    description=PIPELINE_DESCRIPTION,
    runner=run,
)
