from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ConditionFamily = Literal[
    "baseline",
    "category",
    "script_opposition",
    "category_script",
    "validated_gtvh",
]
StyleMode = Literal["none", "freek"]


class StrictStageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FreekCategoryGuidanceOutput(StrictStageModel):
    category_realization: str = Field(min_length=1)
    tonal_tendencies: list[str] = Field(min_length=1)
    generation_guidelines: list[str] = Field(min_length=1)


class ScriptAOutput(StrictStageModel):
    script_a: str = Field(min_length=1)


class ScriptBCandidateOutput(StrictStageModel):
    script_b: str = Field(min_length=1)


class ScriptBCandidatesOutput(StrictStageModel):
    candidates: list[ScriptBCandidateOutput] = Field(min_length=1)


class ScriptBSelectionOutput(StrictStageModel):
    script_b: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class SemanticPlanOutput(StrictStageModel):
    opposition_type: str = Field(min_length=1)
    trigger: str = Field(min_length=1)
    setup_goal: str = Field(min_length=1)
    punch_goal: str = Field(min_length=1)


class JokeVariantOutput(StrictStageModel):
    text: str = Field(min_length=1)
    angle: str = Field(min_length=1)


class JokeVariantsOutput(StrictStageModel):
    variants: list[JokeVariantOutput] = Field(min_length=1)


class CriticOutput(StrictStageModel):
    text: str = Field(min_length=1)
    angle: str = Field(min_length=1)


class AudienceExpectationOutput(StrictStageModel):
    script_a: str = Field(min_length=1)
    expected_propositions: list[str] = Field(min_length=2)
    audience_expectation: str = Field(min_length=1)


class GTVHCandidateOutput(StrictStageModel):
    candidate_id: str = Field(min_length=1)
    script_b: str = Field(min_length=1)
    opposition_axis: str = Field(min_length=1)
    opposed_proposition: str = Field(min_length=1)
    shared_anchor: str = Field(min_length=1)
    reading_a: str = Field(min_length=1)
    reading_b: str = Field(min_length=1)
    logical_mechanism: str = Field(min_length=1)


class GTVHCandidatesOutput(StrictStageModel):
    candidates: list[GTVHCandidateOutput] = Field(min_length=4)


class TheoryGateAssessmentOutput(StrictStageModel):
    candidate_id: str = Field(min_length=1)
    dual_compatibility: bool
    genuine_opposition: bool
    single_axis: bool
    anchor_supports_both: bool
    coherent_logical_mechanism: bool
    recognizable_second_reading: bool
    rationale: str = Field(min_length=1)


class TheoryGateOutput(StrictStageModel):
    assessments: list[TheoryGateAssessmentOutput] = Field(min_length=1)


class ValidatedCandidateSelectionOutput(StrictStageModel):
    selected_candidate_id: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class GTVHPlanOutput(StrictStageModel):
    opposition_type: str = Field(min_length=1)
    logical_mechanism: str = Field(min_length=1)
    situation: str = Field(min_length=1)
    target: Optional[str] = None
    narrative_strategy: str = Field(min_length=1)
    lexical_anchor: str = Field(min_length=1)
    setup_goal: str = Field(min_length=1)
    punch_goal: str = Field(min_length=1)
    punch_final_word: str = Field(min_length=1)


class ValidatedJokeVariantOutput(StrictStageModel):
    variant_id: str = Field(min_length=1)
    setup: str = Field(min_length=1)
    punchline: str = Field(min_length=1)
    full_text: str = Field(min_length=1)
    angle: str = Field(min_length=1)
    anchor_surface_form: str = Field(min_length=1)


class ValidatedJokeVariantsOutput(StrictStageModel):
    variants: list[ValidatedJokeVariantOutput] = Field(min_length=3)


class BlindReconstructionAssessmentOutput(StrictStageModel):
    variant_id: str = Field(min_length=1)
    recovered_script_a: str = Field(min_length=1)
    recovered_script_b: str = Field(min_length=1)
    recovered_anchor: str = Field(min_length=1)
    opposition_axis: str = Field(min_length=1)
    dual_reading_valid: bool
    resolution_valid: bool
    topic_specific: bool
    rationale: str = Field(min_length=1)


class BlindReconstructionOutput(StrictStageModel):
    assessments: list[BlindReconstructionAssessmentOutput] = Field(min_length=1)


class PairwiseComparisonOutput(StrictStageModel):
    left_variant_id: str = Field(min_length=1)
    right_variant_id: str = Field(min_length=1)
    winner_variant_id: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class PairwiseSelectionOutput(StrictStageModel):
    comparisons: list[PairwiseComparisonOutput] = Field(min_length=1)
    selected_variant_id: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


@dataclass(frozen=True)
class PipelineSpec:
    code: str
    family: ConditionFamily
    style_mode: StyleMode
    name: str
    description: str


@dataclass
class JokeRequest:
    topic: str
    category: str | None = None
    audience: str = "Dutch general audience"
    joke_format: str = "short joke"
    constraints: list[str] = field(default_factory=list)


@dataclass
class ScriptASeed:
    script_a: str


@dataclass
class ScriptBCandidate:
    script_b: str


@dataclass
class ScriptBSelection:
    script_b: str
    rationale: str


@dataclass
class SemanticPlan:
    category: str | None = None
    setup_script: str | None = None
    opposing_script: str | None = None
    opposition_type: str | None = None
    trigger: str | None = None
    setup_goal: str | None = None
    punch_goal: str | None = None
    style_mode: StyleMode = "none"


@dataclass
class JokeVariant:
    text: str
    angle: str


@dataclass
class UsageSummary:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class PipelineResult:
    pipeline_code: str
    pipeline_name: str
    request: JokeRequest
    prompt: str
    joke: str
    semantic_plan: SemanticPlan
    raw_response: str
    warnings: list[str] = field(default_factory=list)
    script_b_candidates: list[ScriptBCandidate] = field(default_factory=list)
    script_b_rationale: str = ""
    variants: list[JokeVariant] = field(default_factory=list)
    usage: UsageSummary | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
