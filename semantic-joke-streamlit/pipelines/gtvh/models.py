from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class GTVHRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    audience: str = "Nederlands algemeen publiek"
    style_notes: str = "droog, observerend, bondig"


class SituationStage(BaseModel):
    setting: str
    characters: list[str]
    goal: str
    summary: str

    @field_validator("characters", mode="before")
    @classmethod
    def coerce_characters_to_list(cls, value):
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            return [text]
        return value


class ScriptOppositionStage(BaseModel):
    script_a: str
    script_b: str
    opposition_type: str
    why_they_conflict: str


class LogicalMechanismStage(BaseModel):
    mechanism: str
    twist_explanation: str


class NarrativeStrategyStage(BaseModel):
    format: str
    why_it_works: str


class LanguageStage(BaseModel):
    version_a: str
    version_b: str
    version_c: str


class TargetStage(BaseModel):
    needs_target: bool
    target: str | None = None
    neutral_version: str
    target_version: str | None = None
    rationale: str


class RefinementStage(BaseModel):
    best_version: str
    backup_version: str
    why_best_works: str


class GTVHPipelineResult(BaseModel):
    topic: str
    situation: SituationStage
    script_opposition: ScriptOppositionStage
    logical_mechanism: LogicalMechanismStage
    narrative_strategy: NarrativeStrategyStage
    language: LanguageStage
    target: TargetStage
    refinement: RefinementStage

