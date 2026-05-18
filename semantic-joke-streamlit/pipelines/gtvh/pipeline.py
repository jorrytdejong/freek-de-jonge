from __future__ import annotations

from time import perf_counter
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from core.llm import require_client
from core.pipeline import PipelineDefinition
from core.pricing import active_model
from core.usage import summarize_usage, usage_from_response
from pipelines.gtvh.models import (
    GTVHRequest,
    GTVHPipelineResult,
    LanguageStage,
    LogicalMechanismStage,
    NarrativeStrategyStage,
    RefinementStage,
    ScriptOppositionStage,
    SituationStage,
    TargetStage,
)
from pipelines.gtvh.prompts import (
    language_prompt,
    logical_mechanism_prompt,
    narrative_strategy_prompt,
    refinement_prompt,
    script_opposition_prompt,
    situation_prompt,
    target_prompt,
)
from schemas import JokeRequest, JokeResult, JokeVariant, ScriptBCandidate, SemanticPlan, UsageSummary


PIPELINE_ID = "gtvh"
PIPELINE_NAME = "GTVH Pipeline"
PIPELINE_DESCRIPTION = "Seven-stage GTVH app pipeline: situation, opposition, mechanism, strategy, drafts, target, and refinement."

StageModel = TypeVar("StageModel", bound=BaseModel)


def request_to_gtvh(request: JokeRequest) -> GTVHRequest:
    style_parts = [request.voice]
    if request.format:
        style_parts.append(f"format: {request.format}")
    if request.constraints:
        style_parts.append("constraints: " + "; ".join(request.constraints))
    return GTVHRequest(
        topic=request.topic,
        audience=request.audience,
        style_notes=", ".join(part for part in style_parts if part),
    )


def run_stage(client: OpenAI, prompt: str, schema: type[StageModel], usages: list[UsageSummary]) -> StageModel:
    response = client.responses.parse(
        model=active_model(),
        input=prompt,
        text_format=schema,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise ValueError(f"OpenAI returned no structured output. Raw text: {response.output_text}")

    usage = usage_from_response(response)
    if usage is not None:
        usages.append(usage)
    return parsed


def variants_from_result(result: GTVHPipelineResult) -> list[JokeVariant]:
    variants = [
        JokeVariant(text=result.language.version_a, angle="Draft A"),
        JokeVariant(text=result.language.version_b, angle="Draft B"),
        JokeVariant(text=result.language.version_c, angle="Draft C"),
        JokeVariant(text=result.refinement.backup_version, angle="Backup refinement"),
    ]
    if result.target.target_version:
        variants.append(JokeVariant(text=result.target.target_version, angle=f"Targeted: {result.target.target or 'target'}"))
    return variants


def result_to_joke_result(request: JokeRequest, result: GTVHPipelineResult, usages: list[UsageSummary], started_at: float) -> JokeResult:
    best_joke = JokeVariant(text=result.refinement.best_version, angle=f"Best via {result.logical_mechanism.mechanism}")
    return JokeResult(
        request=request,
        plan=SemanticPlan(
            script_a=result.script_opposition.script_a,
            script_b=result.script_opposition.script_b,
            opposition_type=result.script_opposition.opposition_type,
            trigger=result.logical_mechanism.twist_explanation,
            setup_goal=result.situation.goal,
            punch_goal=result.narrative_strategy.why_it_works,
        ),
        script_b_candidates=[ScriptBCandidate(script_b=result.script_opposition.script_b)],
        script_b_rationale=result.script_opposition.why_they_conflict,
        variants=[best_joke, *variants_from_result(result)],
        best_joke=best_joke,
        usage=summarize_usage(usages, started_at),
        artifacts={"gtvh": result.model_dump()},
    )


def run(request: JokeRequest, client: OpenAI | None = None) -> JokeResult:
    client = require_client(client)
    started_at = perf_counter()
    usages: list[UsageSummary] = []
    gtvh_request = request_to_gtvh(request)

    situation = run_stage(client, situation_prompt(gtvh_request), SituationStage, usages)
    opposition = run_stage(client, script_opposition_prompt(gtvh_request, situation), ScriptOppositionStage, usages)
    mechanism = run_stage(client, logical_mechanism_prompt(gtvh_request, situation, opposition), LogicalMechanismStage, usages)
    strategy = run_stage(client, narrative_strategy_prompt(gtvh_request, situation, opposition, mechanism), NarrativeStrategyStage, usages)
    language = run_stage(client, language_prompt(gtvh_request, situation, opposition, mechanism, strategy), LanguageStage, usages)
    target = run_stage(client, target_prompt(gtvh_request, language), TargetStage, usages)
    refinement = run_stage(client, refinement_prompt(gtvh_request, language, target), RefinementStage, usages)

    result = GTVHPipelineResult(
        topic=gtvh_request.topic,
        situation=situation,
        script_opposition=opposition,
        logical_mechanism=mechanism,
        narrative_strategy=strategy,
        language=language,
        target=target,
        refinement=refinement,
    )
    return result_to_joke_result(request, result, usages, started_at)


PIPELINE = PipelineDefinition(
    id=PIPELINE_ID,
    name=PIPELINE_NAME,
    description=PIPELINE_DESCRIPTION,
    runner=run,
)
