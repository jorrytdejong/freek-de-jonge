from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel

from core.freek_examples import freek_example_context
from core.llm import add_usage, generate_structured
from core.joke_length import joke_length_instruction, joke_sentence_count, joke_word_count, validate_joke_length
from core.schemas import (
    AudienceExpectationOutput,
    GTVHCandidateOutput,
    GTVHCandidatesOutput,
    GTVHPlanOutput,
    JokeRepairVariantsOutput,
    JokeRequest,
    JokeVariant,
    PipelineResult,
    PipelineSpec,
    ScriptBCandidate,
    SemanticPlan,
    TheoryGateAssessmentOutput,
    TheoryGateOutput,
    UsageSummary,
    ValidatedCandidateSelectionOutput,
    ValidatedJokeVariantOutput,
    ValidatedJokeVariantsOutput,
)
from core.styles import style_guidance
from pipelines import plan_fidelity
from pipelines import shared_script_opposition as shared_so

StageOutput = TypeVar("StageOutput", bound=BaseModel)


def _structured_prompt(
    task: str,
    payload: dict[str, Any],
    *,
    condition_context: str = "",
) -> str:
    """Combine stage instructions and structured input."""
    sections = [task]
    if condition_context:
        sections.append(condition_context)
    sections.append(
        f"Input:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Return the requested structured fields."
    )
    return "\n\n".join(sections)


def _base_payload(spec: PipelineSpec, request: JokeRequest) -> dict[str, Any]:
    """Build the topic-only request payload."""
    return {"topic": request.topic}


def _condition_context(spec: PipelineSpec) -> str:
    """Build optional E2 guidance outside the structured JSON input."""
    if spec.style_mode != "freek":
        return ""
    sections = [f"Style guidance:\n{style_guidance(spec.style_mode)}"]
    examples = freek_example_context()
    if examples:
        sections.append(
            "Freek example context:\n"
            f"{examples}\n\n"
            "Use the examples only as structural context. Do not copy wording, names, or situations, "
            "and do not claim the result is an authentic Freek de Jonge joke."
        )
    return "\n\n".join(sections)


def _stage_call(
    prompt: str,
    *,
    stage: str,
    model: str,
    response_model: type[StageOutput],
) -> tuple[StageOutput, str, UsageSummary]:
    """Run and label one structured model call."""
    try:
        return generate_structured(prompt, response_model, model=model)
    except ValueError as exc:
        raise ValueError(f"{stage} structured output failed: {exc}") from exc


def _unique_ids(items: list[Any], attribute: str, *, stage: str) -> list[str]:
    """Return unique identifiers or reject malformed model output."""
    identifiers = [str(getattr(item, attribute)).strip() for item in items]
    if any(not identifier for identifier in identifiers):
        raise ValueError(f"{stage} returned an empty identifier.")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"{stage} returned duplicate identifiers: {identifiers}.")
    return identifiers


def _require_same_ids(expected: list[str], actual: list[str], *, stage: str) -> None:
    """Require an evaluator to return exactly one record per input item."""
    if set(expected) != set(actual) or len(expected) != len(actual):
        raise ValueError(f"{stage} identifiers must exactly match {expected}; received {actual}.")


def _passes_theory_gate(assessment: TheoryGateAssessmentOutput) -> bool:
    """Backward-compatible alias for the shared C/E SO gate."""
    return shared_so.passes_so_gate(assessment)


def build_audience_expectation_prompt(spec: PipelineSpec, request: JokeRequest) -> str:
    """Build the proposition-level Script A prompt."""
    return _structured_prompt(
        """
You analyze the default audience interpretation that a joke setup can activate.
Write all creative and analytical fields in Dutch.

Stage 1: Audience expectation and Script A.
For the supplied topic:
1. state the normal, common-sense Script A as a structured situation
2. identify participants and their default roles
3. identify the apparent goal, normal preconditions, and expected actions
4. identify the expected outcome
5. list 2-5 concrete propositions a general audience normally assumes
6. summarize the expectation a setup should activate

A script is not merely an attitude or opinion: it includes roles, a goal, conditions,
actions, and an outcome. Do not write a joke or invent an opposing script yet.
Return script_a, participants_and_roles, apparent_goal, preconditions,
expected_actions, expected_outcome, expected_propositions, and audience_expectation.
""".strip(),
        _base_payload(spec, request),
        condition_context=_condition_context(spec),
    )


def build_opposition_candidates_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    audience: AudienceExpectationOutput,
) -> str:
    """Build theory-explicit opposing-script candidates."""
    payload = {
        **_base_payload(spec, request),
        "script_a": audience.script_a,
        "expected_propositions": audience.expected_propositions,
        "audience_expectation": audience.audience_expectation,
    }
    return _structured_prompt(
        """
You construct candidate script oppositions under SSTH/GTVH.
Write all fields in Dutch except candidate_id.

Stage 2: Opposition candidates.
Generate exactly 4 candidates with candidate_id B1 through B4.
A script is a structured situation containing participants, roles, a goal,
preconditions, expected actions, and an outcome. Script B must be a coherent
alternative situation, not merely a surprising opinion, metaphor, exaggeration,
or darker description of Script A.

Every candidate must:
- oppose or functionally reverse one explicit Script A expectation; the scripts must
  be locally incompatible but need not be literal logical negations
- identify one dominant opposition axis
- state Script B's participants or roles and goal
- specify how roles change between the scripts
- use a concrete shared word, phrase, object, role, condition, or situation as an anchor
- explain how that anchor supports reading_a and reading_b
- list shared cues that can appear before the punch and remain compatible with both scripts
- distinguish those shared cues from a late switch trigger that makes Script B preferred
- propose a hinge event that is anomalous, useless, or inappropriate under Script A
- explain why the same hinge event is purposeful or appropriate under Script B
- provide a precise logical mechanism that enables the switch
- keep Script A dominant before the trigger and Script B recognizable afterward

Prefer candidates in which the same condition blocks Script A's goal but enables
Script B's goal. Do not write the completed joke yet.

Diversify the axes and logical mechanisms. Do not rank the candidates.
Return candidate_id, script_b, opposition_axis, opposed_proposition,
shared_anchor, reading_a, reading_b, roles_b, goal_b, role_remapping, shared_cues,
switch_trigger, hinge_event, anomaly_under_a, resolution_under_b, and
logical_mechanism for each candidate.
""".strip(),
        payload,
        condition_context=_condition_context(spec),
    )


def build_theory_gate_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    audience: AudienceExpectationOutput,
    candidates: list[GTVHCandidateOutput],
) -> str:
    """Build the independent non-compensatory theory audit."""
    payload = {
        **_base_payload(spec, request),
        "script_a": audience.model_dump(),
        "candidates": [candidate.model_dump() for candidate in candidates],
    }
    return _structured_prompt(
        """
You are a strict SSTH/GTVH validity auditor, not a creativity judge.
Write rationales in Dutch.

Stage 3: Theory gate.
Assess every candidate independently. Return exactly one assessment for every candidate_id.
Set each criterion to true only when it is explicitly supported:
- dual_compatibility: one realizable joke text could be compatible with both scripts
- genuine_opposition: the scripts are locally incompatible on the named axis; literal
  propositional negation is not required
- single_axis: the opposition has one clear dominant axis
- anchor_supports_both: the proposed anchor naturally supports both readings
- recognizable_second_reading: Script B is plausible or socially recognizable
- setup_dominance: without the trigger, a normal reader would prefer Script A
- latent_second_reading: at least one pre-trigger cue already supports Script B
- anomaly_resolved: the hinge event is specifically anomalous under A and purposeful under B
- retrospective_reinterpretation: Script B changes the function or meaning of an earlier detail
- functional_reversal: one condition blocks A's goal but enables B's goal; record this
  separately as a preference, not a mandatory condition

This is a non-compensatory gate: do not pass a weak criterion because the candidate is creative.
At least two candidates should pass only if the supplied candidates genuinely justify it.
""".strip(),
        payload,
        condition_context=_condition_context(spec),
    )


def build_opposition_repair_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    audience: AudienceExpectationOutput,
    candidates: list[GTVHCandidateOutput],
    assessments: list[TheoryGateAssessmentOutput],
) -> str:
    """Build a targeted regeneration prompt from failed gate feedback."""
    payload = {
        **_base_payload(spec, request),
        "script_a": audience.model_dump(),
        "failed_candidates": [candidate.model_dump() for candidate in candidates],
        "gate_feedback": [assessment.model_dump() for assessment in assessments],
    }
    return _structured_prompt(
        """
You repair a set of Script B candidates that all failed a strict SSTH/GTVH gate.
Write all fields in Dutch except candidate_id.

Stage 3b: Opposition repair.
Replace the failed set with exactly 4 substantially revised candidates using
candidate_id B1 through B4. Use the gate feedback diagnostically.

For every replacement:
- identify one explicit Script A expectation in opposed_proposition
- make script_b a coherent alternative situation that opposes or functionally reverses
  that expectation; do not require a superficial X/not-X paraphrase
- use one dominant opposition axis
- supply Script B roles and goal plus an explicit role remapping
- choose a concrete anchor and earlier shared cues that support both readings
- distinguish the late switch trigger from the shared cues
- state a hinge event, its anomaly under A, and its resolution under B
- state the precise logical mechanism that makes the late switch resolvable
- keep Script A dominant before the trigger and Script B plausible afterward

Do not preserve a failed idea merely by rephrasing it. Do not rank candidates.
Return a complete replacement candidate set.
""".strip(),
        payload,
        condition_context=_condition_context(spec),
    )


def build_candidate_selection_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    audience: AudienceExpectationOutput,
    approved_candidates: list[GTVHCandidateOutput],
) -> str:
    """Build ID-only selection among candidates that passed the hard gate."""
    payload = {
        **_base_payload(spec, request),
        "script_a": audience.model_dump(),
        "approved_candidates": [candidate.model_dump() for candidate in approved_candidates],
    }
    return _structured_prompt(
        """
You select the strongest theory-valid script opposition.
Write the rationale in Dutch.

Stage 4: Validated candidate selection.
Choose only from approved_candidates using:
- clearest and most economical opposition
- strongest setup test: Script A dominates without the trigger
- strongest switch test: the hinge event creates a specific anomaly under Script A
- strongest retrospective test: Script B resolves the anomaly and reinterprets an earlier cue
- strongest functional reversal when available
- clearest separation of shared cues and late switch trigger
- most coherent logical mechanism
- best topic specificity
- best payoff potential

Return selected_candidate_id and rationale.
Do not repeat or rewrite Script B.
""".strip(),
        payload,
        condition_context=_condition_context(spec),
    )


def build_gtvh_plan_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    audience: AudienceExpectationOutput,
    candidate: GTVHCandidateOutput,
) -> str:
    """Build a plan covering all six GTVH knowledge resources."""
    payload = {
        **_base_payload(spec, request),
        "script_a": audience.model_dump(),
        "selected_candidate": candidate.model_dump(),
    }
    return _structured_prompt(
        """
You extend an immutable validated Script Opposition with the remaining GTVH resources.
Write all fields in Dutch.

Stage 5: GTVH extension.
Specify:
- opposition_type: copy the selected candidate's opposition_axis verbatim
- logical_mechanism: the GTVH Logical Mechanism applied to the selected SO
- situation: participants, activity, objects, and setting
- target: the person, institution, convention, or idea being targeted; null if none
- narrative_strategy: how setup and punchline are organized
- lexical_anchor: the primary concrete surface expression used as a hinge; it need not
  carry the entire opposition by itself
- supporting_dual_cues: copy the selected candidate's shared_cues verbatim
- switch_trigger: copy the selected candidate's switch_trigger verbatim
- hinge_event: copy the selected candidate's hinge_event verbatim
- anomaly_under_a: copy the selected candidate's anomaly_under_a verbatim
- resolution_under_b: copy the selected candidate's resolution_under_b verbatim
- role_remapping: copy the selected candidate's role_remapping verbatim
- setup_goal: how Script A becomes the dominant expectation
- punch_goal: how Script B reinterprets the setup
- punch_final_word: the strongest intended final word or short phrase

The selected candidate is authoritative. Do not replace, reinterpret, or improve
any Script Opposition field. Add Logical Mechanism, Situation, Target, Narrative
Strategy, and Language without changing the selected SO. Return the complete
GTVHPlanOutput shape, with the SO fields copied exactly.
""".strip(),
        payload,
        condition_context=_condition_context(spec),
    )


def build_validated_variants_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    audience: AudienceExpectationOutput,
    candidate: GTVHCandidateOutput,
    plan: GTVHPlanOutput,
) -> str:
    """Build setup/punchline-separated joke generation."""
    payload = {
        **_base_payload(spec, request),
        "script_a": audience.model_dump(),
        "selected_candidate": candidate.model_dump(),
        "gtvh_plan": plan.model_dump(),
    }
    return _structured_prompt(
        f"""
You realize a validated GTVH plan as concise Dutch jokes.

Treat the topic as broad inspiration rather than a literal assignment. The joke
may use an adjacent situation and need not mention the topic explicitly.

Stage 6: Controlled joke generation.
Write exactly three variants with variant_id V1, V2, and V3.
{joke_length_instruction()}
Write each variant as a joke intended to be spoken aloud by one comedian to a Dutch
audience. Each must have a recognizable setup, a clear turn or misdirection, and a
final punchline that creates the laugh.
For every variant:
- preserve the supplied shared Script Opposition exactly; do not invent a new
  Script A, Script B, opposition axis, cue, or switch
- setup makes Script A dominant but not exclusive
- one or two supporting dual cues appear ordinary under Script A and gain a second
  function under Script B
- punchline introduces the smallest possible switch trigger late
- a preceding action or condition becomes anomalous under Script A but immediately
  purposeful under Script B
- full_text contains the exact setup and punchline
- a concrete anchor_surface_form occurs verbatim in full_text
- earlier wording remains interpretable under both scripts after the punchline
- the switch is surprising but quickly understandable
- the joke is specific to the supplied topic
- full_text ends as close as possible to the planned strongest word or phrase

Do not explain Script B, name the opposition, or append an unrelated surprise that
was not latent in the setup.
Do not write an observation, explanation, summary, moral, slogan, or policy statement.
Do not end with an abstract conclusion; the final sentence must be the punchline.
Mentally read each variant aloud and rewrite it if it does not sound performable.

Return variant_id, setup, punchline, full_text, angle, and anchor_surface_form.
""".strip(),
        payload,
        condition_context=_condition_context(spec),
    )


def _validate_variants(variants: list[ValidatedJokeVariantOutput]) -> list[str]:
    """Apply deterministic surface-form requirements."""
    identifiers = _unique_ids(variants, "variant_id", stage="variants")
    expected_ids = {"V1", "V2", "V3"}
    if set(identifiers) != expected_ids or len(identifiers) != len(expected_ids):
        raise ValueError(f"Variants must use exactly V1, V2, and V3; received {identifiers}.")
    for variant in variants:
        validate_joke_length(variant.full_text, label=f"Variant {variant.variant_id}")
        if variant.setup not in variant.full_text or variant.punchline not in variant.full_text:
            raise ValueError(
                f"Variant {variant.variant_id} full_text must contain its exact setup and punchline."
            )
        if variant.anchor_surface_form.casefold() not in variant.full_text.casefold():
            raise ValueError(
                f"Variant {variant.variant_id} does not contain anchor_surface_form "
                f"{variant.anchor_surface_form!r}."
            )
    return identifiers


def _validate_candidate_set(candidates: list[GTVHCandidateOutput], *, stage: str) -> list[str]:
    """Require the complete immutable B1-B4 candidate set."""
    identifiers = _unique_ids(candidates, "candidate_id", stage=stage)
    expected_ids = {f"B{index}" for index in range(1, 5)}
    if set(identifiers) != expected_ids or len(identifiers) != len(expected_ids):
        raise ValueError(
            f"{stage} must use exactly B1 through B4; received {identifiers}."
        )
    return identifiers


def _gate_failure_summary(assessments: list[TheoryGateAssessmentOutput]) -> str:
    """Summarize which mandatory criteria rejected the candidate set."""
    criteria = (
        "dual_compatibility",
        "genuine_opposition",
        "single_axis",
        "anchor_supports_both",
        "recognizable_second_reading",
        "setup_dominance",
        "latent_second_reading",
        "anomaly_resolved",
        "retrospective_reinterpretation",
    )
    failures = {
        criterion: sum(not bool(getattr(assessment, criterion)) for assessment in assessments)
        for criterion in criteria
    }
    return ", ".join(f"{criterion}={count}" for criterion, count in failures.items() if count)


def _dry_run_fixtures() -> tuple[
    AudienceExpectationOutput,
    list[GTVHCandidateOutput],
    list[TheoryGateAssessmentOutput],
    GTVHCandidateOutput,
    GTVHPlanOutput,
    list[ValidatedJokeVariantOutput],
]:
    """Create coherent placeholders used only to expose every dry-run prompt."""
    audience = AudienceExpectationOutput(
        script_a="Een publieke voorziening levert bezoekers een dienst.",
        participants_and_roles=[
            "de instelling als dienstverlener",
            "de bezoeker als ontvanger",
        ],
        apparent_goal="De bezoeker ontvangt hulp.",
        preconditions=["De instelling stelt een voorziening beschikbaar."],
        expected_actions=["De instelling helpt de bezoeker."],
        expected_outcome="De bezoeker houdt de controle en vertrekt geholpen.",
        expected_propositions=[
            "De instelling geeft iets aan de bezoeker.",
            "De bezoeker houdt de controle.",
        ],
        audience_expectation="De plek helpt de bezoeker volgens normale regels.",
    )
    candidates = [
        GTVHCandidateOutput(
            candidate_id=f"B{index}",
            script_b=f"De bezoeker levert iets in bij de instelling ({index}).",
            opposition_axis="geven/nemen",
            opposed_proposition="De instelling geeft iets aan de bezoeker.",
            shared_anchor="voorziening",
            reading_a="De instelling voorziet de bezoeker.",
            reading_b="De bezoeker voorziet de instelling.",
            roles_b=[
                "de instelling als ontvanger",
                "de bezoeker als middel",
            ],
            goal_b="De instelling gebruikt wat de bezoeker inlevert.",
            role_remapping=[
                "de instelling: gever -> ontvanger",
                "de bezoeker: ontvanger -> middel",
            ],
            shared_cues=["voorziening", "inleveren"],
            switch_trigger="jezelf inleveren",
            hinge_event="De bezoeker moet iets inleveren om geholpen te worden.",
            anomaly_under_a="De bezoeker verliest juist iets bij een behulpzame voorziening.",
            resolution_under_b="De instelling is de werkelijke ontvanger van de transactie.",
        )
        for index in range(1, 5)
    ]
    gates = [
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
            rationale="Dry-run kandidaat voldoet aan alle poortcriteria.",
        )
        for candidate in candidates
    ]
    plan = GTVHPlanOutput(
        opposition_type="geven/nemen",
        logical_mechanism="omkering van gever en ontvanger",
        situation="een bezoeker bij een publieke instelling",
        target="institutionele taal",
        narrative_strategy="normale setup gevolgd door late rolomkering",
        lexical_anchor="voorziening",
        supporting_dual_cues=["voorziening", "inleveren"],
        switch_trigger="jezelf inleveren",
        hinge_event="De bezoeker moet iets inleveren.",
        anomaly_under_a="Hulp kost de bezoeker zijn autonomie.",
        resolution_under_b="De instelling gebruikt de bezoeker als haar voorziening.",
        role_remapping=[
            "de instelling: helper -> ontvanger",
            "de bezoeker: ontvanger -> middel",
        ],
        setup_goal="Activeer de verwachting dat de instelling iets geeft.",
        punch_goal="Onthul dat de bezoeker juist iets moet afstaan.",
        punch_final_word="jezelf",
    )
    variants = [
        ValidatedJokeVariantOutput(
            variant_id=f"V{index}",
            setup=f"Deze voorziening helpt iedereen, versie {index}.",
            punchline="Je hoeft alleen jezelf in te leveren.",
            full_text=f"Deze voorziening helpt iedereen, versie {index}. Je hoeft alleen jezelf in te leveren.",
            angle="omkering van geven en nemen",
            anchor_surface_form="voorziening",
        )
        for index in range(1, 4)
    ]
    return audience, candidates, gates, candidates[0], plan, variants


def _required_gtvh_resources(plan: GTVHPlanOutput) -> list[str]:
    resources = ["SO", "LM", "SI"]
    if plan.target is not None:
        resources.append("TA")
    resources.extend(["NS", "LA"])
    return resources


def _validate_gtvh_preserves_so(
    plan: GTVHPlanOutput,
    selected: GTVHCandidateOutput,
) -> None:
    """Reject an E extension that changes any selected SO field."""
    expected = {
        "opposition_type": selected.opposition_axis,
        "supporting_dual_cues": selected.shared_cues,
        "switch_trigger": selected.switch_trigger,
        "hinge_event": selected.hinge_event,
        "anomaly_under_a": selected.anomaly_under_a,
        "resolution_under_b": selected.resolution_under_b,
        "role_remapping": selected.role_remapping,
    }
    actual = {field: getattr(plan, field) for field in expected}
    if actual != expected:
        mismatches = {
            field: {"expected": expected[field], "actual": actual[field]}
            for field in expected
            if expected[field] != actual[field]
        }
        raise ValueError(
            "E GTVH extension changed immutable Script Opposition fields: "
            f"{mismatches}"
        )


def _gtvh_intended_plan(
    audience: AudienceExpectationOutput,
    selected: GTVHCandidateOutput,
    plan: GTVHPlanOutput,
) -> dict[str, Any]:
    return {
        "script_a": audience.model_dump(),
        "selected_script_opposition": selected.model_dump(),
        "gtvh_plan": plan.model_dump(),
    }


def dry_run_validated_gtvh_pipeline(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    shared_result: shared_so.SharedScriptOppositionResult | None = None,
) -> PipelineResult:
    """Build every validated-GTVH prompt without model calls."""
    shared = shared_result or shared_so.dry_run_shared_script_opposition(spec, request)
    audience = shared.audience
    candidates = shared.candidates
    gates = shared.assessments
    selected = shared.selected
    _, _, _, _, plan, variants = _dry_run_fixtures()
    fidelity_variants = [
        plan_fidelity.FidelityVariant(
            variant_id=variant.variant_id,
            text=variant.full_text,
            angle=variant.angle,
        )
        for variant in variants
    ]
    required_resources = _required_gtvh_resources(plan)
    evaluation = plan_fidelity.dry_run_plan_fidelity_selection(
        spec,
        request,
        required_resources=required_resources,
        intended_plan=_gtvh_intended_plan(audience, selected, plan),
        variants=fidelity_variants,
    )
    prompts = [
        *shared.prompts,
        ("gtvh_plan", build_gtvh_plan_prompt(spec, request, audience, selected)),
        ("variants", build_validated_variants_prompt(spec, request, audience, selected, plan)),
        *evaluation.prompts,
    ]
    combined_prompt = "\n\n---\n\n".join(f"## {stage}\n{prompt}" for stage, prompt in prompts)
    semantic_plan = SemanticPlan(
        setup_script=audience.script_a,
        opposing_script=selected.script_b,
        opposition_type=plan.opposition_type,
        trigger=plan.switch_trigger,
        setup_goal=plan.setup_goal,
        punch_goal=plan.punch_goal,
        shared_cues=plan.supporting_dual_cues,
        hinge_event=plan.hinge_event,
        anomaly_under_a=plan.anomaly_under_a,
        resolution_under_b=plan.resolution_under_b,
        role_remapping=plan.role_remapping,
        style_mode=spec.style_mode,
    )
    joke = variants[0].full_text
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=spec.name,
        request=request,
        prompt=combined_prompt,
        joke=joke,
        semantic_plan=semantic_plan,
        raw_response=combined_prompt,
        script_b_candidates=[
            ScriptBCandidate(
                script_b=candidate.script_b,
                candidate_id=candidate.candidate_id,
                opposition_axis=candidate.opposition_axis,
                opposed_expectation=candidate.opposed_proposition,
                roles_b=candidate.roles_b,
                goal_b=candidate.goal_b,
                role_remapping=candidate.role_remapping,
                shared_cues=candidate.shared_cues,
                switch_trigger=candidate.switch_trigger,
                hinge_event=candidate.hinge_event,
                anomaly_under_a=candidate.anomaly_under_a,
                resolution_under_b=candidate.resolution_under_b,
            )
            for candidate in candidates
        ],
        script_b_rationale="Dry run selected candidate B1 after the theory gate.",
        variants=[JokeVariant(text=variant.full_text, angle=variant.angle) for variant in variants],
        metadata={
            "family": spec.family,
            "style_mode": spec.style_mode,
            "stages": [stage for stage, _ in prompts],
            "gtvh_trace": {
                "audience_expectation": audience.model_dump(),
                "candidates": [candidate.model_dump() for candidate in candidates],
                "candidate_attempts": shared.candidate_attempts,
                "theory_gate": [gate.model_dump() for gate in gates],
                "theory_gate_attempts": shared.theory_gate_attempts,
                "approved_candidate_ids": [candidate.candidate_id for candidate in candidates],
                "selected_candidate_id": selected.candidate_id,
                "gtvh_plan": plan.model_dump(),
                "detailed_variants": [variant.model_dump() for variant in variants],
                "plan_fidelity": [
                    assessment.model_dump() for assessment in evaluation.assessments
                ],
                "passing_variant_ids": evaluation.passing_variant_ids,
                "selected_variant_id": evaluation.selected_variant_id,
            },
        },
    )


def run_validated_gtvh_pipeline(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    model: str,
    shared_result: shared_so.SharedScriptOppositionResult | None = None,
) -> PipelineResult:
    """Run E by extending the exact shared C/E Script Opposition result."""
    shared = shared_result or shared_so.run_shared_script_opposition(spec, request, model=model)
    raw_responses = dict(shared.raw_responses)
    prompts = list(shared.prompts)
    usage = shared.usage

    def call(
        stage: str,
        prompt: str,
        response_model: type[StageOutput],
    ) -> StageOutput:
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

    audience = shared.audience
    candidates = shared.candidates
    approved = shared.approved
    selected = shared.selected
    candidate_attempts = shared.candidate_attempts
    gate_attempts = shared.theory_gate_attempts

    plan = call(
        "gtvh_plan",
        build_gtvh_plan_prompt(spec, request, audience, selected),
        GTVHPlanOutput,
    )
    assert isinstance(plan, GTVHPlanOutput)
    _validate_gtvh_preserves_so(plan, selected)

    variants_payload = call(
        "variants",
        build_validated_variants_prompt(spec, request, audience, selected, plan),
        ValidatedJokeVariantsOutput,
    )
    assert isinstance(variants_payload, ValidatedJokeVariantsOutput)
    variants = variants_payload.variants
    length_repair_prompt: str | None = None
    if any(
        not 20 <= joke_word_count(variant.full_text) <= 45
        or joke_sentence_count(variant.full_text) > 3
        for variant in variants
    ):
        fidelity_variants = [
            plan_fidelity.FidelityVariant(
                variant_id=variant.variant_id,
                text=variant.full_text,
                angle=variant.angle,
            )
            for variant in variants
        ]
        length_repair_prompt = plan_fidelity.build_length_repair_prompt(
            request,
            intended_plan=_gtvh_intended_plan(audience, selected, plan),
            variants=fidelity_variants,
        )
        repaired_payload, repair_raw, repair_usage = _stage_call(
            length_repair_prompt,
            stage="length_repair",
            model=model,
            response_model=JokeRepairVariantsOutput,
        )
        original_by_id = {variant.variant_id: variant for variant in variants}
        repaired_by_id = {item.variant_id: item for item in repaired_payload.variants}
        if set(repaired_by_id) != {"V1", "V2", "V3"}:
            raise ValueError("Length repair must return exactly V1, V2, and V3.")
        variants = [
            ValidatedJokeVariantOutput(
                variant_id=f"V{index}",
                setup=repaired_by_id[f"V{index}"].setup or original_by_id[f"V{index}"].setup,
                punchline=repaired_by_id[f"V{index}"].punchline or original_by_id[f"V{index}"].punchline,
                full_text=repaired_by_id[f"V{index}"].text,
                angle=repaired_by_id[f"V{index}"].angle,
                anchor_surface_form=(
                    repaired_by_id[f"V{index}"].anchor_surface_form
                    or original_by_id[f"V{index}"].anchor_surface_form
                ),
            )
            for index in range(1, 4)
        ]
        raw_responses["length_repair"] = repair_raw
        usage = add_usage(usage, repair_usage)
    variant_ids = _validate_variants(variants)

    required_resources = _required_gtvh_resources(plan)
    fidelity_variants = [
        plan_fidelity.FidelityVariant(
            variant_id=variant.variant_id,
            text=variant.full_text,
            angle=variant.angle,
        )
        for variant in variants
    ]
    evaluation = plan_fidelity.run_plan_fidelity_selection(
        spec,
        request,
        model=model,
        required_resources=required_resources,
        intended_plan=_gtvh_intended_plan(audience, selected, plan),
        variants=fidelity_variants,
    )
    prompts.extend(evaluation.prompts)
    if length_repair_prompt:
        prompts.insert(len(shared.prompts) + 2, ("length_repair", length_repair_prompt))
    raw_responses.update(evaluation.raw_responses)
    usage = add_usage(usage, evaluation.usage)
    final_variants = evaluation.variants
    selected_variant = next(
        item for item in final_variants
        if item.variant_id == evaluation.selected_variant_id
    )
    best = JokeVariant(text=selected_variant.text, angle=selected_variant.angle)

    semantic_plan = SemanticPlan(
        setup_script=audience.script_a,
        opposing_script=selected.script_b,
        opposition_type=plan.opposition_type,
        trigger=plan.switch_trigger,
        setup_goal=plan.setup_goal,
        punch_goal=plan.punch_goal,
        shared_cues=plan.supporting_dual_cues,
        hinge_event=plan.hinge_event,
        anomaly_under_a=plan.anomaly_under_a,
        resolution_under_b=plan.resolution_under_b,
        role_remapping=plan.role_remapping,
        style_mode=spec.style_mode,
    )
    combined_prompt = "\n\n---\n\n".join(
        f"## {stage}\n{prompt}" for stage, prompt in prompts
    )
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=spec.name,
        request=request,
        prompt=combined_prompt,
        joke=best.text,
        semantic_plan=semantic_plan,
        raw_response=json.dumps(raw_responses, ensure_ascii=False, indent=2),
        warnings=evaluation.warnings,
        script_b_candidates=[
            ScriptBCandidate(
                script_b=candidate.script_b,
                candidate_id=candidate.candidate_id,
                opposition_axis=candidate.opposition_axis,
                opposed_expectation=candidate.opposed_proposition,
                roles_b=candidate.roles_b,
                goal_b=candidate.goal_b,
                role_remapping=candidate.role_remapping,
                shared_cues=candidate.shared_cues,
                switch_trigger=candidate.switch_trigger,
                hinge_event=candidate.hinge_event,
                anomaly_under_a=candidate.anomaly_under_a,
                resolution_under_b=candidate.resolution_under_b,
            )
            for candidate in candidates
        ],
        script_b_rationale=shared.selection_rationale,
        variants=[
            JokeVariant(text=variant.text, angle=variant.angle)
            for variant in final_variants
        ],
        usage=usage,
        metadata={
            "family": spec.family,
            "style_mode": spec.style_mode,
            "stages": list(raw_responses),
            "gtvh_trace": {
                "audience_expectation": audience.model_dump(),
                "candidates": [candidate.model_dump() for candidate in candidates],
                "candidate_attempts": candidate_attempts,
                "theory_gate": [
                    assessment.model_dump() for assessment in shared.assessments
                ],
                "theory_gate_attempts": gate_attempts,
                "approved_candidate_ids": [
                    candidate.candidate_id for candidate in approved
                ],
                "selected_candidate_id": selected.candidate_id,
                "gtvh_plan": plan.model_dump(),
                "detailed_variants": [variant.model_dump() for variant in variants],
                "evaluated_variants": [
                    {"variant_id": item.variant_id, "text": item.text, "angle": item.angle}
                    for item in evaluation.variants
                ],
                "joke_repaired": evaluation.repaired,
                "required_resources": required_resources,
                "plan_fidelity": [
                    {
                        **assessment.model_dump(),
                        "passes_required_plan": plan_fidelity.passes_required_plan(
                            assessment,
                            required_resources,
                        ),
                    }
                    for assessment in evaluation.assessments
                ],
                "passing_variant_ids": evaluation.passing_variant_ids,
                "pairwise_comparisons": [
                    comparison.model_dump()
                    for comparison in evaluation.selection.comparisons
                ],
                "selected_variant_id": evaluation.selected_variant_id,
                "selection_rationale": evaluation.selection.rationale,
            },
        },
    )
