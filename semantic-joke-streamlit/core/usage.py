from __future__ import annotations

from time import perf_counter

from core.pricing import active_model, estimate_cost
from schemas import UsageSummary


def usage_from_response(response) -> UsageSummary | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
    model = getattr(response, "model", active_model()) or active_model()
    return UsageSummary(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimate_cost(input_tokens, output_tokens, model=model),
    )


def usage_from_response_with_duration(response, duration_seconds: float) -> UsageSummary:
    usage = usage_from_response(response)
    if usage is None:
        model = getattr(response, "model", active_model()) or active_model()
        return UsageSummary(model=model, duration_seconds=duration_seconds)
    usage.duration_seconds = duration_seconds
    return usage


def summarize_usage(usages: list[UsageSummary], started_at: float) -> UsageSummary:
    duration = perf_counter() - started_at
    if not usages:
        return UsageSummary(model=active_model(), duration_seconds=duration)

    total_input_tokens = sum(item.input_tokens for item in usages)
    total_output_tokens = sum(item.output_tokens for item in usages)
    total_tokens = sum(item.total_tokens for item in usages)
    models = {item.model for item in usages}
    model = next(iter(models)) if len(models) == 1 else ", ".join(sorted(models))
    return UsageSummary(
        model=model,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimate_cost(total_input_tokens, total_output_tokens, model=model),
        duration_seconds=duration,
    )
