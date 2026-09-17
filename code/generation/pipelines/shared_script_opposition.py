from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, TypeVar

from pydantic import BaseModel

from core.llm import add_usage, generate_structured
from core.script_opposition_examples import script_opposition_example_context
from core.schemas import (
    AudienceExpectationOutput,
    GTVHCandidateOutput,
    GTVHCandidatesOutput,
    JokeRequest,
    PipelineSpec,
    TheoryGateAssessmentOutput,
    TheoryGateOutput,
    UsageSummary,
    ValidatedCandidateSelectionOutput,
)
from core.styles import style_guidance


StageOutput = TypeVar("StageOutput", bound=BaseModel)


@dataclass
class SharedScriptOppositionResult:
    """The common Script Opposition result consumed by both C and E."""

    audience: AudienceExpectationOutput
    candidates: list[GTVHCandidateOutput]
    assessments: list[TheoryGateAssessmentOutput]
    approved: list[GTVHCandidateOutput]
    selected: GTVHCandidateOutput
    selection_rationale: str
    prompts: list[tuple[str, str]]
    raw_responses: dict[str, str]
    usage: UsageSummary | None
    candidate_attempts: list[list[dict[str, Any]]]
    theory_gate_attempts: list[list[dict[str, Any]]]


def _structured_prompt(
    task: str,
    payload: dict[str, Any],
    *,
    condition_context: str = "",
) -> str:
    sections = [task]
    if condition_context:
        sections.append(condition_context)
    sections.append(
        f"Input:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Return the requested structured fields."
    )
    return "\n\n".join(sections)


def _condition_context(spec: PipelineSpec) -> str:
    """Use identical condition context in the shared C/E SO stages."""
    if spec.style_mode != "freek":
        return ""
    sections = [f"Style guidance:\n{style_guidance(spec.style_mode)}"]
    examples = script_opposition_example_context()
    if examples:
        serialized_examples = json.dumps(examples, ensure_ascii=False, indent=2)
        sections.append(
            "Annotated Freek Script Opposition examples:\n"
            f"{serialized_examples}\n\n"
            "Use these examples only as structural context for analyzing Script Opposition. "
            "Do not copy wording, names, or situations, and do not claim the result is an "
            "authentic Freek de Jonge joke."
        )
    return "\n\n".join(sections)


def build_audience_expectation_prompt(spec: PipelineSpec, request: JokeRequest) -> str:
    return _structured_prompt(
        """
You construct the audience's default interpretation, Script A, for the supplied topic.
Write all creative and analytical fields in Dutch.

Treat the topic as a broad starting point, not a literal assignment. Use it to find
a recognizable situation, but do not force the joke to mention or enact the topic
literally.

Stage 1: Audience expectation and Script A.
For the supplied topic:
1. identify the participants and their default roles
2. state the apparent goal, normal preconditions, expected actions, and expected outcome
3. list 2-5 concrete propositions a general audience normally assumes
4. compress the structured situation into one concise script_a
5. summarize the expectation a setup should activate

Script A must be a structured, normal, common-sense situation rather than merely an
attitude or opinion. Do not write a joke or introduce Script B.
Return script_a, participants_and_roles, apparent_goal, preconditions,
expected_actions, expected_outcome, expected_propositions, and audience_expectation.
""".strip(),
        {"topic": request.topic},
        condition_context=_condition_context(spec),
    )


def build_opposition_candidates_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    audience: AudienceExpectationOutput,
) -> str:
    return _structured_prompt(
        """
You construct opposing Script B candidates for the supplied Script A.
Write all fields in Dutch except candidate_id.

Stage 2: Opposition candidates.
Generate exactly 4 candidates with candidate_id B1 through B4.
Treat the topic as a broad starting point rather than a literal assignment; the
candidate may use an adjacent recognizable situation.
For every candidate:
- state a coherent and recognizable script_b with roles_b and goal_b
- tie it to one opposed_proposition copied from Script A
- identify one dominant opposition_axis; local incompatibility is sufficient and
  literal logical negation is not required
- describe reading_a and reading_b of the shared semantic material
- specify role_remapping between the scripts
- provide one concise shared_anchor plus shared_cues that can occur under both readings
- distinguish the late switch_trigger from earlier shared cues
- propose a hinge_event that is anomalous or inappropriate under Script A
- explain the anomaly_under_a and why it becomes purposeful in resolution_under_b
- keep Script A dominant before the trigger and Script B latent but recoverable

Do not specify a Logical Mechanism or any other GTVH Knowledge Resource here. Those
are added only by E after the common Script Opposition has been selected.
Return candidate_id, script_b, opposition_axis, opposed_proposition, shared_anchor,
reading_a, reading_b, roles_b, goal_b, role_remapping, shared_cues, switch_trigger,
hinge_event, anomaly_under_a, and resolution_under_b for each candidate.
""".strip(),
        {
            "topic": request.topic,
            "script_a": audience.model_dump(),
        },
        condition_context=_condition_context(spec),
    )


def build_theory_gate_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    audience: AudienceExpectationOutput,
    candidates: list[GTVHCandidateOutput],
) -> str:
    return _structured_prompt(
        """
You are a strict Script Opposition validity auditor, not a creativity judge.
Write rationales in Dutch.

Stage 3: Theory gate.
Assess every candidate independently and return exactly one assessment per candidate_id.
Set each criterion to true only when explicitly supported:
- dual_compatibility: one realizable joke text could support both scripts
- genuine_opposition: the scripts are locally incompatible on the stated axis
- single_axis: one opposition is clearly dominant
- anchor_supports_both: the shared material naturally supports both readings
- recognizable_second_reading: Script B is coherent and socially recognizable
- setup_dominance: a normal reader would initially prefer Script A
- latent_second_reading: Script B can remain available before the trigger
- anomaly_resolved: the hinge anomaly under A becomes purposeful under B
- retrospective_reinterpretation: Script B changes the function or meaning of earlier material
- functional_reversal: note whether one condition blocks A's goal while enabling B's goal;
  this is desirable but not mandatory for passage

This gate evaluates Script Opposition only. Do not invent or assess a Logical Mechanism.
""".strip(),
        {
            "topic": request.topic,
            "script_a": audience.model_dump(),
            "candidates": [candidate.model_dump() for candidate in candidates],
        },
        condition_context=_condition_context(spec),
    )


def build_opposition_repair_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    audience: AudienceExpectationOutput,
    candidates: list[GTVHCandidateOutput],
    assessments: list[TheoryGateAssessmentOutput],
) -> str:
    return _structured_prompt(
        """
You repair a complete candidate set that failed the Script Opposition gate.
Write all fields in Dutch except candidate_id.

Stage 3b: Opposition repair.
Replace the failed set with exactly 4 substantially revised candidates using B1 through B4.
Use the gate feedback diagnostically. Each replacement must provide every field used in
the original candidate stage, preserve Script A, and improve dual compatibility, local
opposition, setup dominance, latent Script B, and retrospective reinterpretation.

Do not add a Logical Mechanism or another GTVH Knowledge Resource. Do not preserve a
failed idea merely by rephrasing it and do not rank candidates.
""".strip(),
        {
            "topic": request.topic,
            "script_a": audience.model_dump(),
            "failed_candidates": [candidate.model_dump() for candidate in candidates],
            "gate_feedback": [assessment.model_dump() for assessment in assessments],
        },
        condition_context=_condition_context(spec),
    )


def build_candidate_selection_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    audience: AudienceExpectationOutput,
    approved_candidates: list[GTVHCandidateOutput],
) -> str:
    return _structured_prompt(
        """
You select the strongest Script Opposition from candidates that passed the gate.
Write the rationale in Dutch.

Stage 4: Candidate selection.
Choose only from approved_candidates using opposition clarity, dual compatibility,
setup dominance, latent second-reading support, retrospective reinterpretation, topic
specificity, economy, and payoff potential.

Return selected_candidate_id and rationale. Select by ID only and do not rewrite Script B.
""".strip(),
        {
            "topic": request.topic,
            "script_a": audience.model_dump(),
            "approved_candidates": [candidate.model_dump() for candidate in approved_candidates],
        },
        condition_context=_condition_context(spec),
    )


def _unique_ids(items: list[Any], attribute: str, *, stage: str) -> list[str]:
    identifiers = [str(getattr(item, attribute)).strip() for item in items]
    if any(not identifier for identifier in identifiers):
        raise ValueError(f"{stage} returned an empty identifier.")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"{stage} returned duplicate identifiers: {identifiers}.")
    return identifiers


def _validate_candidate_set(candidates: list[GTVHCandidateOutput], *, stage: str) -> list[str]:
    identifiers = _unique_ids(candidates, "candidate_id", stage=stage)
    expected = {f"B{index}" for index in range(1, 5)}
    if set(identifiers) != expected or len(identifiers) != len(expected):
        raise ValueError(f"{stage} must use exactly B1 through B4; received {identifiers}.")
    return identifiers


def _require_same_ids(expected: list[str], actual: list[str], *, stage: str) -> None:
    if set(expected) != set(actual) or len(expected) != len(actual):
        raise ValueError(f"{stage} identifiers must exactly match {expected}; received {actual}.")


def passes_so_gate(assessment: TheoryGateAssessmentOutput) -> bool:
    """Require the common SO criteria; functional reversal remains diagnostic."""
    return all(
        (
            assessment.dual_compatibility,
            assessment.genuine_opposition,
            assessment.single_axis,
            assessment.anchor_supports_both,
            assessment.recognizable_second_reading,
            assessment.setup_dominance,
            assessment.latent_second_reading,
            assessment.anomaly_resolved,
            assessment.retrospective_reinterpretation,
        )
    )


def _stage_call(
    prompt: str,
    *,
    stage: str,
    model: str,
    response_model: type[StageOutput],
) -> tuple[StageOutput, str, UsageSummary]:
    try:
        return generate_structured(prompt, response_model, model=model)
    except ValueError as exc:
        raise ValueError(f"{stage} structured output failed: {exc}") from exc


def run_shared_script_opposition(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    model: str,
) -> SharedScriptOppositionResult:
    """Run the identical SO construction, gate, repair, and selection for C and E."""
    prompts: list[tuple[str, str]] = []
    raw_responses: dict[str, str] = {}
    usage: UsageSummary | None = None

    def call(stage: str, prompt: str, response_model: type[StageOutput]) -> StageOutput:
        nonlocal usage
        parsed, raw, stage_usage = _stage_call(
            prompt,
            stage=stage,
            model=model,
            response_model=response_model,
        )
        prompts.append((stage, prompt))
        raw_responses[stage] = raw
        usage = add_usage(usage, stage_usage)
        return parsed

    audience = call(
        "audience_expectation",
        build_audience_expectation_prompt(spec, request),
        AudienceExpectationOutput,
    )
    assert isinstance(audience, AudienceExpectationOutput)

    candidate_payload = call(
        "opposition_candidates",
        build_opposition_candidates_prompt(spec, request, audience),
        GTVHCandidatesOutput,
    )
    assert isinstance(candidate_payload, GTVHCandidatesOutput)
    candidates = candidate_payload.candidates
    candidate_ids = _validate_candidate_set(candidates, stage="opposition_candidates")
    candidate_attempts = [[candidate.model_dump() for candidate in candidates]]

    gate_payload = call(
        "theory_gate",
        build_theory_gate_prompt(spec, request, audience, candidates),
        TheoryGateOutput,
    )
    assert isinstance(gate_payload, TheoryGateOutput)
    gate_ids = _unique_ids(gate_payload.assessments, "candidate_id", stage="theory_gate")
    _require_same_ids(candidate_ids, gate_ids, stage="theory_gate")
    theory_gate_attempts = [
        [assessment.model_dump() for assessment in gate_payload.assessments]
    ]

    by_id = {assessment.candidate_id: assessment for assessment in gate_payload.assessments}
    approved = [candidate for candidate in candidates if passes_so_gate(by_id[candidate.candidate_id])]
    if not approved:
        repaired_payload = call(
            "opposition_repair",
            build_opposition_repair_prompt(
                spec,
                request,
                audience,
                candidates,
                gate_payload.assessments,
            ),
            GTVHCandidatesOutput,
        )
        assert isinstance(repaired_payload, GTVHCandidatesOutput)
        candidates = repaired_payload.candidates
        candidate_ids = _validate_candidate_set(candidates, stage="opposition_repair")
        candidate_attempts.append([candidate.model_dump() for candidate in candidates])

        gate_payload = call(
            "theory_gate_repaired",
            build_theory_gate_prompt(spec, request, audience, candidates),
            TheoryGateOutput,
        )
        assert isinstance(gate_payload, TheoryGateOutput)
        gate_ids = _unique_ids(
            gate_payload.assessments,
            "candidate_id",
            stage="theory_gate_repaired",
        )
        _require_same_ids(candidate_ids, gate_ids, stage="theory_gate_repaired")
        theory_gate_attempts.append(
            [assessment.model_dump() for assessment in gate_payload.assessments]
        )
        by_id = {
            assessment.candidate_id: assessment for assessment in gate_payload.assessments
        }
        approved = [
            candidate for candidate in candidates if passes_so_gate(by_id[candidate.candidate_id])
        ]
        if not approved:
            raise ValueError(
                "No Script B candidate passed every mandatory shared SO criterion "
                "after one targeted repair attempt."
            )

    selection = call(
        "candidate_selection",
        build_candidate_selection_prompt(spec, request, audience, approved),
        ValidatedCandidateSelectionOutput,
    )
    assert isinstance(selection, ValidatedCandidateSelectionOutput)
    approved_by_id = {candidate.candidate_id: candidate for candidate in approved}
    if selection.selected_candidate_id not in approved_by_id:
        raise ValueError(
            "Candidate selector chose an ID that did not pass the shared SO gate: "
            f"{selection.selected_candidate_id!r}."
        )

    return SharedScriptOppositionResult(
        audience=audience,
        candidates=candidates,
        assessments=gate_payload.assessments,
        approved=approved,
        selected=approved_by_id[selection.selected_candidate_id],
        selection_rationale=selection.rationale,
        prompts=prompts,
        raw_responses=raw_responses,
        usage=usage,
        candidate_attempts=candidate_attempts,
        theory_gate_attempts=theory_gate_attempts,
    )


def dry_run_shared_script_opposition(
    spec: PipelineSpec,
    request: JokeRequest,
) -> SharedScriptOppositionResult:
    audience = AudienceExpectationOutput(
        script_a="Een publieke instelling helpt een bezoeker.",
        participants_and_roles=[
            "de instelling als helper",
            "de bezoeker als ontvanger",
        ],
        apparent_goal="De bezoeker ontvangt hulp.",
        preconditions=["De instelling is beschikbaar."],
        expected_actions=["De instelling verleent een dienst."],
        expected_outcome="De bezoeker vertrekt geholpen.",
        expected_propositions=[
            "De instelling geeft iets aan de bezoeker.",
            "De bezoeker behoudt de controle.",
        ],
        audience_expectation="De instelling helpt de bezoeker volgens normale regels.",
    )
    candidates = [
        GTVHCandidateOutput(
            candidate_id=f"B{index}",
            script_b=f"De instelling gebruikt de bezoeker ({index}).",
            opposition_axis="geven/nemen",
            opposed_proposition="De instelling geeft iets aan de bezoeker.",
            shared_anchor="voorziening",
            reading_a="De instelling voorziet de bezoeker.",
            reading_b="De bezoeker voorziet de instelling.",
            roles_b=["de instelling als ontvanger", "de bezoeker als middel"],
            goal_b="De instelling ontvangt iets van de bezoeker.",
            role_remapping=["helper -> ontvanger", "ontvanger -> middel"],
            shared_cues=["voorziening"],
            switch_trigger="zichzelf inleveren",
            hinge_event="De bezoeker moet zichzelf inleveren.",
            anomaly_under_a="De hulp kost de bezoeker zichzelf.",
            resolution_under_b="De instelling is de werkelijke ontvanger.",
        )
        for index in range(1, 5)
    ]
    assessments = [
        TheoryGateAssessmentOutput(
            candidate_id=candidate.candidate_id,
            dual_compatibility=True,
            genuine_opposition=True,
            single_axis=True,
            anchor_supports_both=True,
            recognizable_second_reading=True,
            setup_dominance=True,
            latent_second_reading=True,
            anomaly_resolved=True,
            retrospective_reinterpretation=True,
            functional_reversal=True,
            rationale="De kandidaat voldoet aan de gedeelde SO-criteria.",
        )
        for candidate in candidates
    ]
    prompts = [
        ("audience_expectation", build_audience_expectation_prompt(spec, request)),
        (
            "opposition_candidates",
            build_opposition_candidates_prompt(spec, request, audience),
        ),
        (
            "theory_gate",
            build_theory_gate_prompt(spec, request, audience, candidates),
        ),
        (
            "candidate_selection",
            build_candidate_selection_prompt(spec, request, audience, candidates),
        ),
    ]
    return SharedScriptOppositionResult(
        audience=audience,
        candidates=candidates,
        assessments=assessments,
        approved=candidates,
        selected=candidates[0],
        selection_rationale="Dry run selected B1.",
        prompts=prompts,
        raw_responses={},
        usage=None,
        candidate_attempts=[[candidate.model_dump() for candidate in candidates]],
        theory_gate_attempts=[
            [assessment.model_dump() for assessment in assessments]
        ],
    )
