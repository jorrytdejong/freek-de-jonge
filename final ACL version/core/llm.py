from __future__ import annotations

import os
from typing import Any, TypeVar

from pydantic import BaseModel

from core.schemas import UsageSummary


DEFAULT_MODEL = "gpt-5.6-terra"
StructuredModel = TypeVar("StructuredModel", bound=BaseModel)
AVAILABLE_MODELS: tuple[dict[str, str], ...] = (
    {
        "id": "gpt-5.6-terra",
        "label": "GPT-5.6 Terra",
        "description": "Best-quality default for complex humor generation, semantic planning, and evaluation.",
    },
    {
        "id": "gpt-5.5",
        "label": "GPT-5.5",
        "description": "High-quality fallback for complex humor generation and evaluation.",
    },
    {
        "id": "gpt-5.4-mini",
        "label": "GPT-5.4 mini",
        "description": "Strong, faster alternative when running the full experiment matrix.",
    },
    {
        "id": "gpt-5.4-nano",
        "label": "GPT-5.4 nano",
        "description": "Fastest option for dry runs, prompt checks, and inexpensive baselines.",
    },
)


def available_model_ids() -> list[str]:
    """Return model identifiers supported by the application.

    Returns:
        Model identifiers in display order.
    """
    return [model["id"] for model in AVAILABLE_MODELS]


def model_label(model_id: str) -> str:
    """Return a human-readable label for a model.

    Args:
        model_id: Model identifier to look up.

    Returns:
        The configured label and identifier, or the identifier itself.
    """
    for model in AVAILABLE_MODELS:
        if model["id"] == model_id:
            return f'{model["label"]} ({model["id"]})'
    return model_id


def model_description(model_id: str) -> str:
    """Return the configured description for a model.

    Args:
        model_id: Model identifier to look up.

    Returns:
        The configured description or a generic fallback.
    """
    for model in AVAILABLE_MODELS:
        if model["id"] == model_id:
            return model["description"]
    return "Custom model."


class MissingAPIKeyError(RuntimeError):
    """Raised when generation needs OpenAI access but no API key is configured."""


def _usage_from_response(response: Any, model: str) -> UsageSummary:
    """Extract normalized token usage from an OpenAI response.

    Args:
        response: OpenAI response containing optional usage metadata.
        model: Model identifier associated with the response.

    Returns:
        Normalized input, output, and total token counts.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return UsageSummary(model=model)

    input_tokens = int(getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or input_tokens + output_tokens)
    return UsageSummary(model=model, input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)


def add_usage(left: UsageSummary | None, right: UsageSummary | None) -> UsageSummary | None:
    """Combine two optional token-usage summaries.

    Args:
        left: Previously accumulated usage, if any.
        right: Usage from the newest stage, if any.

    Returns:
        Combined usage, one original value, or ``None``.
    """
    if left is None:
        return right
    if right is None:
        return left
    return UsageSummary(
        model=right.model or left.model,
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
        total_tokens=left.total_tokens + right.total_tokens,
    )


def generate_structured(
    prompt: str,
    response_model: type[StructuredModel],
    *,
    model: str = DEFAULT_MODEL,
) -> tuple[StructuredModel, str, UsageSummary]:
    """Generate and validate a structured model response.

    Args:
        prompt: Complete text prompt sent to the model.
        response_model: Pydantic model used to parse the response.
        model: OpenAI model identifier.

    Returns:
        Parsed output, raw response text, and normalized usage.

    Raises:
        MissingAPIKeyError: If ``OPENAI_API_KEY`` is not configured.
        ValueError: If the response contains no parsed structured output.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise MissingAPIKeyError("Set OPENAI_API_KEY to generate jokes with the ACL final pipelines.")

    from openai import OpenAI

    client = OpenAI()
    response = client.responses.parse(
        model=model,
        input=prompt,
        text_format=response_model,
    )
    if response.output_parsed is None:
        raise ValueError(f"OpenAI returned no {response_model.__name__} output. Raw text: {response.output_text}")
    raw_text = response.output_text or response.output_parsed.model_dump_json()
    return response.output_parsed, raw_text, _usage_from_response(response, model)
