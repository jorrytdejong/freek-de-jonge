from __future__ import annotations

import os


DEFAULT_MODEL = "gpt-5.5"
MODEL = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5-nano": (0.05, 0.40),
}


def active_model() -> str:
    return os.getenv("OPENAI_MODEL", MODEL)


def estimate_cost(input_tokens: int, output_tokens: int, model: str | None = None) -> float:
    input_price, output_price = MODEL_PRICING.get(model or active_model(), MODEL_PRICING[DEFAULT_MODEL])
    return (input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)
