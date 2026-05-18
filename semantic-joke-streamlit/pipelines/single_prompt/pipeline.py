from __future__ import annotations

import json
from time import perf_counter

from openai import OpenAI
from pydantic import BaseModel, Field

from core.llm import require_client
from core.pricing import active_model
from core.pipeline import PipelineDefinition
from core.usage import usage_from_response_with_duration
from pipelines.single_prompt.prompts import SINGLE_PROMPT_PIPELINE_PROMPT
from schemas import JokeRequest, JokeResult, JokeVariant, ScriptBCandidate, SemanticPlan


PIPELINE_ID = "single_prompt"
PIPELINE_NAME = "Single Prompt"
PIPELINE_DESCRIPTION = "One structured call that performs the same semantic stages internally."


class SinglePromptPipelinePayload(BaseModel):
    plan: SemanticPlan
    script_b_candidates: list[ScriptBCandidate] = Field(min_length=1)
    script_b_rationale: str
    variants: list[JokeVariant] = Field(min_length=1)
    best_joke: JokeVariant


def best_variant_from_payload(payload: SinglePromptPipelinePayload) -> JokeVariant:
    for variant in payload.variants:
        if variant.text == payload.best_joke.text and variant.angle == payload.best_joke.angle:
            return variant

    for variant in payload.variants:
        if variant.text == payload.best_joke.text:
            return variant

    raise ValueError("The single-prompt response selected a best joke outside the variants list.")


def run(request: JokeRequest, client: OpenAI | None = None) -> JokeResult:
    client = require_client(client)
    started_at = perf_counter()

    response = client.responses.parse(
        model=active_model(),
        input=[
            {"role": "system", "content": SINGLE_PROMPT_PIPELINE_PROMPT},
            {
                "role": "user",
                "content": json.dumps({"request": request.model_dump()}, ensure_ascii=False),
            },
        ],
        text_format=SinglePromptPipelinePayload,
    )

    payload = response.output_parsed
    if payload is None:
        raise ValueError(f"OpenAI returned no structured output. Raw text: {response.output_text}")

    return JokeResult(
        request=request,
        plan=payload.plan,
        script_b_candidates=payload.script_b_candidates,
        script_b_rationale=payload.script_b_rationale,
        variants=payload.variants,
        best_joke=best_variant_from_payload(payload),
        usage=usage_from_response_with_duration(response, perf_counter() - started_at),
    )


PIPELINE = PipelineDefinition(
    id=PIPELINE_ID,
    name=PIPELINE_NAME,
    description=PIPELINE_DESCRIPTION,
    runner=run,
)
