from __future__ import annotations

import json
import os

from openai import OpenAI

from core.pricing import active_model
from core.usage import usage_from_response


def build_openai_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=api_key) if api_key else None


def require_client(client: OpenAI | None = None) -> OpenAI:
    resolved_client = client or build_openai_client()
    if resolved_client is None:
        raise RuntimeError("OPENAI_API_KEY is required.")
    return resolved_client


def structured_call(client: OpenAI, prompt: str, payload: dict, response_format):
    response = client.responses.parse(
        model=active_model(),
        input=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        text_format=response_format,
    )
    if response.output_parsed is None:
        raise ValueError(f"OpenAI returned no structured output. Raw text: {response.output_text}")
    return response.output_parsed, usage_from_response(response)
