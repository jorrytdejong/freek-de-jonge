from __future__ import annotations

from core.llm import build_openai_client, require_client
from core.pricing import DEFAULT_MODEL, MODEL_PRICING, active_model, estimate_cost
from core.registry import PIPELINES, run_pipeline, run_pipelines
from core.usage import summarize_usage, usage_from_response, usage_from_response_with_duration
from pipelines.semantic_steps.pipeline import run as run_semantic_steps
from pipelines.single_prompt.pipeline import run as run_single_prompt
from schemas import JokeRequest, JokeResult


def run(request: JokeRequest, client=None) -> JokeResult:
    return run_semantic_steps(request, client=client)
