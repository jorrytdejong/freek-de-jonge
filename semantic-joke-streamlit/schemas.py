from typing import Any, Literal

from pydantic import BaseModel, Field


FormatType = Literal["one_liner", "short", "monologue"]


class JokeRequest(BaseModel):
    topic: str
    audience: str
    voice: str
    format: FormatType = "one_liner"
    constraints: list[str] = Field(default_factory=list)


class ScriptASeed(BaseModel):
    script_a: str


class ScriptBCandidate(BaseModel):
    script_b: str


class ScriptBCandidatesPayload(BaseModel):
    candidates: list[ScriptBCandidate]


class ScriptBSelection(BaseModel):
    script_b: str
    rationale: str


class SemanticPlanContext(BaseModel):
    opposition_type: str
    trigger: str
    setup_goal: str
    punch_goal: str


class SemanticPlan(BaseModel):
    script_a: str
    script_b: str
    opposition_type: str
    trigger: str
    setup_goal: str
    punch_goal: str


class JokeVariant(BaseModel):
    text: str
    angle: str


class JokeVariantsPayload(BaseModel):
    variants: list[JokeVariant]


class UsageSummary(BaseModel):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None
    duration_seconds: float | None = None


class JokeResult(BaseModel):
    request: JokeRequest
    plan: SemanticPlan
    script_b_candidates: list[ScriptBCandidate] = Field(default_factory=list)
    script_b_rationale: str = ""
    variants: list[JokeVariant]
    best_joke: JokeVariant
    usage: UsageSummary | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)
