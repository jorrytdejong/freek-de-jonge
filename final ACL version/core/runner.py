from __future__ import annotations

from core.llm import DEFAULT_MODEL
from core.schemas import JokeRequest, PipelineResult
from pipelines.conditions import PIPELINE_ORDER, PIPELINE_SPECS
from pipelines.script_opposition import dry_run_script_opposition_pipeline, run_direct_condition, run_script_opposition_pipeline
from pipelines.validated_gtvh import dry_run_validated_gtvh_pipeline, run_validated_gtvh_pipeline


def run_pipeline(
    pipeline_code: str,
    request: JokeRequest,
    *,
    model: str = DEFAULT_MODEL,
    dry_run: bool = False,
) -> PipelineResult:
    """Run one experiment condition for a joke request.

    Args:
        pipeline_code: Matrix code identifying the condition.
        request: Joke-generation request shared with the condition.
        model: OpenAI model identifier.
        dry_run: Whether to build prompts without model calls.

    Returns:
        The generated or dry-run pipeline result.

    Raises:
        ValueError: If ``pipeline_code`` is not registered.
    """
    try:
        spec = PIPELINE_SPECS[pipeline_code.upper()]
    except KeyError as exc:
        known = ", ".join(PIPELINE_ORDER)
        raise ValueError(f"Unknown pipeline {pipeline_code!r}. Choose one of: {known}.") from exc

    if spec.family == "validated_gtvh":
        if dry_run:
            return dry_run_validated_gtvh_pipeline(spec, request)
        return run_validated_gtvh_pipeline(spec, request, model=model)

    if spec.family in {"script_opposition", "category_script"}:
        if dry_run:
            return dry_run_script_opposition_pipeline(spec, request)
        return run_script_opposition_pipeline(spec, request, model=model)

    return run_direct_condition(spec, request, model=model, dry_run=dry_run)


def run_matrix(
    request: JokeRequest,
    *,
    pipeline_codes: list[str] | None = None,
    model: str = DEFAULT_MODEL,
    dry_run: bool = False,
) -> list[PipelineResult]:
    """Run requested experiment conditions in matrix order.

    Args:
        request: Joke-generation request shared by all conditions.
        pipeline_codes: Conditions to run, or ``None`` for the full matrix.
        model: OpenAI model identifier.
        dry_run: Whether to build prompts without model calls.

    Returns:
        Pipeline results in the requested order.
    """
    codes = pipeline_codes or PIPELINE_ORDER
    return [run_pipeline(code, request, model=model, dry_run=dry_run) for code in codes]
