from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from openai import OpenAI

from schemas import JokeRequest, JokeResult


@dataclass(frozen=True)
class PipelineDefinition:
    id: str
    name: str
    description: str
    runner: Callable[[JokeRequest, OpenAI | None], JokeResult]
