"""Simplified alternatives for the C and E pipelines.

This module is deliberately separate from the experiment's original pipeline
files.  It keeps their central comparison while using fewer calls and smaller,
more readable prompts:

    shared: make two script oppositions -> check and choose one
    C:      write two jokes -> check and choose one
    E:      add the other GTVH resources -> write two jokes -> check and choose one

The prompts say "normal meaning" and "hidden meaning" where the original
implementation uses the more technical Script A and Script B terminology.  The
structured field names retain the theory labels so traces remain unambiguous.
"""

from __future__ import annotations

import json
from itertools import combinations
from typing import Literal

from pydantic import Field, model_validator

from core.joke_length import joke_length_instruction, validate_joke_length
from core.llm import add_usage, generate_structured
from core.schemas import (
    JokeRequest,
    JokeVariant,
    PipelineResult,
    PipelineSpec,
    ScriptBCandidate,
    SemanticPlan,
    StrictStageModel,
    UsageSummary,
)
from core.styles import style_guidance


VARIANT_IDS = ("V1", "V2")
CANDIDATE_IDS = ("B1", "B2")


DOCTOR_PATIENT_DEMONSTRATION = """Worked script-opposition example

Joke:
\"Is the doctor in?\" a patient asks in a bronchial whisper. The doctor's young wife
whispers that he is not, then says: \"Come right in.\"

Analysis:
- Script A is a medical consultation: a patient asks whether a physician is available.
- Script B is a secret affair: a visitor checks whether the husband is absent.
- The dominant abstract opposition is non-sex/sex.
- \"Doctor\", \"patient\", and \"bronchial\" make the medical reading dominant.
- Whispering overlaps both scripts: it can signal illness or secrecy.
- The doctor's absence blocks the medical goal but enables the affair goal.
- \"Come right in\" is anomalous under Script A but purposeful under Script B.
- The punch retrospectively changes the roles and meaning of earlier details.

Use this example to understand the mechanism only. Do not reuse medicine, doctors,
patients, spouses, affairs, whispering, the invitation phrase, or the non-sex/sex axis.""".strip()


class SimpleScriptA(StrictStageModel):
    """The audience's ordinary interpretation, generated independently."""

    script_a: str = Field(min_length=1)
    audience_expectation: str = Field(min_length=1)


class SimpleOpposition(StrictStageModel):
    """One compact Script A/Script B plan."""

    candidate_id: Literal["B1", "B2"]
    script_b: str = Field(min_length=1)
    opposition_axis: str = Field(min_length=1)
    shared_cues: list[str] = Field(min_length=1)
    switch_trigger: str = Field(min_length=1)
    role_reversal: str = Field(min_length=1)
    retrospective_reinterpretation: str = Field(min_length=1)


class SimpleOppositionSet(StrictStageModel):
    candidates: list[SimpleOpposition] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def require_candidate_ids(self) -> "SimpleOppositionSet":
        ids = tuple(candidate.candidate_id for candidate in self.candidates)
        if len(set(ids)) != 2 or set(ids) != set(CANDIDATE_IDS):
            raise ValueError("Candidates must be exactly B1 and B2.")
        return self


class SimpleOppositionAssessment(StrictStageModel):
    candidate_id: Literal["B1", "B2"]
    supports_both_meanings: bool
    meanings_really_conflict: bool
    normal_meaning_comes_first: bool
    hidden_meaning_is_clear_after_switch: bool
    earlier_words_gain_new_meaning: bool
    rationale: str = Field(min_length=1)


class SimpleOppositionAudit(StrictStageModel):
    assessments: list[SimpleOppositionAssessment] = Field(min_length=2, max_length=2)
    selected_candidate_id: Literal["B1", "B2"] | None = None
    selection_rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_assessment_ids(self) -> "SimpleOppositionAudit":
        ids = tuple(item.candidate_id for item in self.assessments)
        if len(set(ids)) != 2 or set(ids) != set(CANDIDATE_IDS):
            raise ValueError("Assessments must cover B1 and B2 once each.")
        return self


class SimpleGTVHPlan(StrictStageModel):
    logical_mechanism: str = Field(min_length=1)
    situation: str = Field(min_length=1)
    target: str | None = None
    narrative_strategy: str = Field(min_length=1)
    language: str = Field(min_length=1)


class SimpleVariant(StrictStageModel):
    variant_id: Literal["V1", "V2"]
    text: str = Field(min_length=1)
    angle: str = Field(min_length=1)


class SimpleVariants(StrictStageModel):
    variants: list[SimpleVariant] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def require_variant_ids(self) -> "SimpleVariants":
        ids = tuple(variant.variant_id for variant in self.variants)
        if len(set(ids)) != 2 or set(ids) != set(VARIANT_IDS):
            raise ValueError("Variants must be exactly V1 and V2.")
        return self


class SimpleVariantAssessment(StrictStageModel):
    variant_id: Literal["V1", "V2"]
    preserves_script_opposition: bool
    preserves_logical_mechanism: bool | None = None
    preserves_situation: bool | None = None
    preserves_target: bool | None = None
    preserves_narrative_strategy: bool | None = None
    preserves_language_plan: bool | None = None
    clear_switch: bool
    punchline_lands: bool
    humor_score: int = Field(ge=1, le=5)
    rationale: str = Field(min_length=1)


class SimpleComparison(StrictStageModel):
    left_variant_id: Literal["V1", "V2"]
    right_variant_id: Literal["V1", "V2"]
    winner_variant_id: Literal["V1", "V2"]
    rationale: str = Field(min_length=1)


class SimpleFinalEvaluation(StrictStageModel):
    assessments: list[SimpleVariantAssessment] = Field(min_length=2, max_length=2)
    comparisons: list[SimpleComparison] = Field(min_length=1, max_length=1)
    selected_variant_id: Literal["V1", "V2"]
    selection_rationale: str = Field(min_length=1)


def _json(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump()  # type: ignore[union-attr]
    return json.dumps(value, ensure_ascii=False, indent=2)


def _is_e(spec: PipelineSpec) -> bool:
    if spec.code not in {"C1", "C2", "E1", "E2"}:
        raise ValueError("The simplified pipeline supports only C1, C2, E1, and E2.")
    return spec.code.startswith("E")


def _passes_opposition(item: SimpleOppositionAssessment) -> bool:
    return all(
        (
            item.supports_both_meanings,
            item.meanings_really_conflict,
            item.normal_meaning_comes_first,
            item.hidden_meaning_is_clear_after_switch,
            item.earlier_words_gain_new_meaning,
        )
    )


def build_script_a_prompt(request: JokeRequest) -> str:
    """Build the independent Script A prompt."""
    return f"""For this topic, describe the ordinary situation an audience expects:
{request.topic}

Return:
- script_a: the normal situation in one sentence
- audience_expectation: what the audience expects to happen

Do not write a joke or introduce a hidden meaning."""


def build_opposition_prompt(request: JokeRequest, script_a: SimpleScriptA) -> str:
    """Build the shared C/E Script B proposal prompt."""
    return f"""We need a short Dutch joke about this topic:
{request.topic}

Normal situation:
{_json(script_a)}

Here is a semantic example. Use its structure, not its subject matter:

{DOCTOR_PATIENT_DEMONSTRATION}

Suggest exactly two different hidden meanings, B1 and B2.

For each hidden meaning:
- say what the hidden situation is
- name the main contrast with the normal situation
- give a few words or details that fit both meanings
- give the late clue that reveals the hidden meaning
- explain how the roles change
- explain how the reveal changes the meaning of something heard earlier

Do not write jokes yet.
Do not add other humor theory terms or GTVH resources."""


def build_opposition_audit_prompt(
    request: JokeRequest,
    proposals: SimpleOppositionSet,
) -> str:
    """Build the independent shared SO check-and-selection prompt."""
    return f"""Check these two plans for a Dutch joke about {request.topic}.

{_json(proposals)}

For each plan, answer these questions:
1. Could one joke support both the normal and hidden meaning?
2. Do the two meanings really conflict?
3. Would readers believe the normal meaning first?
4. Does the late clue make the hidden meaning clear?
5. Does that clue give earlier words a new meaning?

A plan passes only if every answer is true. Choose the strongest passing plan.
If none passes, return no selected_candidate_id. Judge the plans; do not rewrite them."""


def build_repair_prompt(
    request: JokeRequest,
    script_a: SimpleScriptA,
    proposals: SimpleOppositionSet,
    audit: SimpleOppositionAudit,
) -> str:
    """Build the one exceptional repair prompt."""
    return f"""None of these joke plans worked well enough.

Topic: {request.topic}
Frozen normal situation:
{_json(script_a)}

Original plans:
{_json(proposals)}

Review feedback:
{_json(audit)}

Keep the normal situation exactly the same. Replace B1 and B2
with two genuinely new plans that solve the problems in the feedback.
Use the same fields as before.
Do not write jokes yet."""


def build_gtvh_prompt(
    request: JokeRequest,
    script_a: str,
    selected: SimpleOpposition,
) -> str:
    """Build the E-only enrichment prompt while freezing the selected SO."""
    return f"""Add five practical choices to this approved joke plan.

Topic: {request.topic}
Normal meaning: {script_a}
Hidden meaning:
{_json(selected)}

Do not change either meaning, the contrast, or the reveal. Only add:
- logical_mechanism: how the misunderstanding or reversal works
- situation: the people, place, objects, and activity
- target: who or what is mocked, or null if nobody is
- narrative_strategy: the form of the joke, such as a short story or dialogue
- language: the key wording that carries the double meaning

Write the answers in Dutch."""


def build_generation_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    script_a: str,
    selected: SimpleOpposition,
    gtvh: SimpleGTVHPlan | None,
) -> str:
    """Build the C or E generation prompt."""
    extra = (
        "Use these extra choices too:\n" + _json(gtvh)
        if gtvh is not None
        else "Use only the normal and hidden meanings above as the humor plan."
    )
    return f"""Write exactly two different Dutch jokes, V1 and V2.

Topic: {request.topic}
Normal meaning: {script_a}
Hidden meaning:
{_json(selected)}

{extra}

Each joke must make the normal meaning believable, reveal the hidden meaning late,
and end when the punchline lands. Do not explain the joke afterward.
{joke_length_instruction()}

Style:
{style_guidance(spec.style_mode)}"""


def build_evaluation_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    script_a: str,
    selected: SimpleOpposition,
    variants: SimpleVariants,
    gtvh: SimpleGTVHPlan | None,
) -> str:
    """Build the shared one-call fidelity and pairwise evaluation prompt."""
    resource_instruction = (
        f"Also check whether each joke keeps every extra E choice:\n{_json(gtvh)}"
        if gtvh is not None
        else "The five E-only preservation fields must be null because this is pipeline C."
    )
    return f"""Judge two Dutch jokes about {request.topic}.

Approved normal meaning: {script_a}
Approved hidden meaning:
{_json(selected)}

{resource_instruction}

Jokes:
{_json(variants)}

For each joke, check whether it keeps the approved two meanings, has a clear late
switch, and ends with a real punchline. Give humor a score from 1 to 5.

Compare V1 with V2. A joke that preserves all required plan choices must beat one
that does not. Otherwise prefer the funnier, clearer joke. Return one final winner.
Do not rewrite the jokes."""


def _validate_audit(
    proposals: SimpleOppositionSet,
    audit: SimpleOppositionAudit,
) -> SimpleOpposition:
    assessments = {item.candidate_id: item for item in audit.assessments}
    passing = {candidate_id for candidate_id, item in assessments.items() if _passes_opposition(item)}
    if not passing:
        raise ValueError("No simplified Script Opposition candidate passed the gate.")
    if audit.selected_candidate_id not in passing:
        raise ValueError("The SO auditor did not select a passing candidate.")
    return next(
        item for item in proposals.candidates if item.candidate_id == audit.selected_candidate_id
    )


def _variant_passes(item: SimpleVariantAssessment, *, is_e: bool) -> bool:
    required = [item.preserves_script_opposition, item.clear_switch, item.punchline_lands]
    if is_e:
        required.extend(
            [
                item.preserves_logical_mechanism,
                item.preserves_situation,
                item.preserves_narrative_strategy,
                item.preserves_language_plan,
            ]
        )
        if item.preserves_target is not None:
            required.append(item.preserves_target)
    return all(value is True for value in required)


def _validate_evaluation(
    evaluation: SimpleFinalEvaluation,
    *,
    is_e: bool,
) -> tuple[list[str], list[str]]:
    assessment_ids = [item.variant_id for item in evaluation.assessments]
    if len(set(assessment_ids)) != 2 or set(assessment_ids) != set(VARIANT_IDS):
        raise ValueError("The final evaluation must assess V1 and V2 once each.")

    expected_pairs = {frozenset(pair) for pair in combinations(VARIANT_IDS, 2)}
    actual_pairs: set[frozenset[str]] = set()
    for comparison in evaluation.comparisons:
        pair = frozenset((comparison.left_variant_id, comparison.right_variant_id))
        if len(pair) != 2 or comparison.winner_variant_id not in pair:
            raise ValueError("Each comparison must name two variants and choose one of them.")
        actual_pairs.add(pair)
    if actual_pairs != expected_pairs:
        raise ValueError("The final evaluation must compare every variant pair exactly once.")

    passing = [
        item.variant_id for item in evaluation.assessments if _variant_passes(item, is_e=is_e)
    ]
    if passing and evaluation.selected_variant_id not in passing:
        raise ValueError("The final evaluator selected a variant that failed required fidelity.")
    warnings = []
    if not passing:
        warnings.append(
            "No variant preserved every required choice; the best unsuccessful joke was returned."
        )
    return passing, warnings


def run_simplified_ce_pipeline(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    model: str,
) -> PipelineResult:
    """Run the simplified C or E pipeline without touching the original runners."""
    is_e = _is_e(spec)
    prompts: list[tuple[str, str]] = []
    raw_responses: dict[str, str] = {}
    usage: UsageSummary | None = None

    def call(stage: str, prompt: str, response_model: type[StrictStageModel]):
        nonlocal usage
        parsed, raw, stage_usage = generate_structured(prompt, response_model, model=model)
        prompts.append((stage, prompt))
        raw_responses[stage] = raw
        usage = add_usage(usage, stage_usage)
        return parsed

    script_a = call(
        "script_a",
        build_script_a_prompt(request),
        SimpleScriptA,
    )
    assert isinstance(script_a, SimpleScriptA)

    proposals = call(
        "opposition_proposals",
        build_opposition_prompt(request, script_a),
        SimpleOppositionSet,
    )
    assert isinstance(proposals, SimpleOppositionSet)

    audit = call(
        "opposition_audit",
        build_opposition_audit_prompt(request, proposals),
        SimpleOppositionAudit,
    )
    assert isinstance(audit, SimpleOppositionAudit)

    try:
        selected = _validate_audit(proposals, audit)
    except ValueError:
        repaired = call(
            "opposition_repair",
            build_repair_prompt(request, script_a, proposals, audit),
            SimpleOppositionSet,
        )
        assert isinstance(repaired, SimpleOppositionSet)
        proposals = repaired
        audit = call(
            "opposition_reaudit",
            build_opposition_audit_prompt(request, proposals),
            SimpleOppositionAudit,
        )
        assert isinstance(audit, SimpleOppositionAudit)
        selected = _validate_audit(proposals, audit)

    gtvh: SimpleGTVHPlan | None = None
    if is_e:
        gtvh = call(
            "gtvh_enrichment",
            build_gtvh_prompt(request, script_a.script_a, selected),
            SimpleGTVHPlan,
        )
        assert isinstance(gtvh, SimpleGTVHPlan)

    variants = call(
        "variants",
        build_generation_prompt(spec, request, script_a.script_a, selected, gtvh),
        SimpleVariants,
    )
    assert isinstance(variants, SimpleVariants)
    for variant in variants.variants:
        validate_joke_length(variant.text, label=variant.variant_id)

    evaluation = call(
        "evaluation_and_selection",
        build_evaluation_prompt(
            spec,
            request,
            script_a.script_a,
            selected,
            variants,
            gtvh,
        ),
        SimpleFinalEvaluation,
    )
    assert isinstance(evaluation, SimpleFinalEvaluation)
    passing_ids, warnings = _validate_evaluation(evaluation, is_e=is_e)
    variants_by_id = {variant.variant_id: variant for variant in variants.variants}
    best = variants_by_id[evaluation.selected_variant_id]

    combined_prompt = "\n\n---\n\n".join(
        f"## {stage}\n{prompt}" for stage, prompt in prompts
    )
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=f"Simplified {spec.name}",
        request=request,
        prompt=combined_prompt,
        joke=best.text,
        semantic_plan=SemanticPlan(
            setup_script=script_a.script_a,
            opposing_script=selected.script_b,
            opposition_type=selected.opposition_axis,
            trigger=selected.switch_trigger,
            shared_cues=selected.shared_cues,
            role_remapping=[selected.role_reversal],
            style_mode=spec.style_mode,
        ),
        raw_response=json.dumps(raw_responses, ensure_ascii=False, indent=2),
        warnings=warnings,
        script_b_candidates=[
            ScriptBCandidate(
                candidate_id=item.candidate_id,
                script_b=item.script_b,
                opposition_axis=item.opposition_axis,
                role_remapping=[item.role_reversal],
                shared_cues=item.shared_cues,
                switch_trigger=item.switch_trigger,
                resolution_under_b=item.retrospective_reinterpretation,
            )
            for item in proposals.candidates
        ],
        script_b_rationale=audit.selection_rationale,
        variants=[JokeVariant(text=item.text, angle=item.angle) for item in variants.variants],
        usage=usage,
        metadata={
            "implementation": "simplified_ce",
            "normal_path_calls": 6 if is_e else 5,
            "selected_candidate_id": selected.candidate_id,
            "gtvh_plan": gtvh.model_dump() if gtvh else None,
            "passing_variant_ids": passing_ids,
            "selected_variant_id": evaluation.selected_variant_id,
            "evaluation": evaluation.model_dump(),
        },
    )
