from __future__ import annotations

from openai import OpenAI

from core.llm import require_client
from core.pipeline import PipelineDefinition
from schemas import JokeRequest, JokeResult


def run_pipeline(pipeline_id: str, request: JokeRequest, client: OpenAI | None = None) -> JokeResult:
    try:
        pipeline = PIPELINES[pipeline_id]
    except KeyError as exc:
        raise ValueError(f"Unknown pipeline: {pipeline_id}") from exc
    return pipeline.runner(request, client)


def run_pipelines(pipeline_ids: list[str], request: JokeRequest) -> dict[str, JokeResult]:
    client = require_client()
    return {pipeline_id: run_pipeline(pipeline_id, request, client=client) for pipeline_id in pipeline_ids}


from pipelines.semantic_steps.pipeline import PIPELINE as SEMANTIC_STEPS_PIPELINE  # noqa: E402
from pipelines.single_prompt.pipeline import PIPELINE as SINGLE_PROMPT_PIPELINE  # noqa: E402
from pipelines.osth_reverse.pipeline import PIPELINE as OSTH_REVERSE_PIPELINE  # noqa: E402
from pipelines.gtvh.pipeline import PIPELINE as GTVH_PIPELINE  # noqa: E402


PIPELINES: dict[str, PipelineDefinition] = {
    SEMANTIC_STEPS_PIPELINE.id: SEMANTIC_STEPS_PIPELINE,
    SINGLE_PROMPT_PIPELINE.id: SINGLE_PROMPT_PIPELINE,
    OSTH_REVERSE_PIPELINE.id: OSTH_REVERSE_PIPELINE,
    GTVH_PIPELINE.id: GTVH_PIPELINE,
}
