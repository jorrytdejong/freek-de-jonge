from __future__ import annotations

from core.llm import DEFAULT_MODEL
from core.schemas import JokeRequest, PipelineResult
from pipelines.conditions import PIPELINE_ORDER, PIPELINE_SPECS
from pipelines.script_opposition import dry_run_script_opposition_pipeline, run_direct_condition, run_script_opposition_pipeline
from pipelines.validated_gtvh import dry_run_validated_gtvh_pipeline, run_validated_gtvh_pipeline
from pipelines import shared_script_opposition as shared_so


def run_pipeline(
    pipeline_code: str,
    request: JokeRequest,
    *,
    model: str = DEFAULT_MODEL,
    dry_run: bool = False,
    shared_result: shared_so.SharedScriptOppositionResult | None = None,
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
            return dry_run_validated_gtvh_pipeline(
                spec,
                request,
                shared_result=shared_result,
            )
        return run_validated_gtvh_pipeline(
            spec,
            request,
            model=model,
            shared_result=shared_result,
        )

    if spec.family in {"script_opposition", "category_script"}:
        if dry_run:
            return dry_run_script_opposition_pipeline(
                spec,
                request,
                shared_result=shared_result,
            )
        return run_script_opposition_pipeline(
            spec,
            request,
            model=model,
            shared_result=shared_result,
        )

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
    shared_by_style: dict[str, shared_so.SharedScriptOppositionResult] = {}
    results: list[PipelineResult] = []
    for code in codes:
        spec = PIPELINE_SPECS[code.upper()]
        shared_result = None
        if spec.family in {"script_opposition", "validated_gtvh"}:
            style_key = spec.style_mode
            if style_key not in shared_by_style:
                if dry_run:
                    shared_by_style[style_key] = shared_so.dry_run_shared_script_opposition(
                        spec,
                        request,
                    )
                else:
                    shared_by_style[style_key] = shared_so.run_shared_script_opposition(
                        spec,
                        request,
                        model=model,
                    )
            shared_result = shared_by_style[style_key]
        results.append(
            run_pipeline(
                code,
                request,
                model=model,
                dry_run=dry_run,
                shared_result=shared_result,
            )
        )
    return results
