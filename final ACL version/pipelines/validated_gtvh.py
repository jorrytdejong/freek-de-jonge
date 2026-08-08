from __future__ import annotations

import itertools
import json
from typing import Any, TypeVar

from pydantic import BaseModel

from core.freek_examples import freek_example_context
from core.comic_guidance import COMIC_REALIZATION_GUIDANCE, COMIC_SELECTION_GUIDANCE
from core.llm import add_usage, generate_structured
from core.schemas import (
    AudienceExpectationOutput,
    BlindReconstructionAssessmentOutput,
    BlindReconstructionOutput,
    GTVHCandidateOutput,
    GTVHCandidatesOutput,
    GTVHPlanOutput,
    JokeRequest,
    JokeVariant,
    PairwiseComparisonOutput,
    PairwiseSelectionOutput,
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

StageOutput = TypeVar("StageOutput", bound=BaseModel)


def _structured_prompt(task: str, payload: dict[str, Any]) -> str:
    """Combine stage instructions and structured input."""
    return f"{task}\n\nInput:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\nReturn the requested structured fields."


def _base_payload(spec: PipelineSpec, request: JokeRequest) -> dict[str, Any]:
    """Build request context without changing any legacy pipeline payload."""
    payload: dict[str, Any] = {
        "topic": request.topic,
        "audience": request.audience,
        "joke_format": request.joke_format,
        "constraints": request.constraints,
        "style_guidance": style_guidance(spec.style_mode),
    }
    if spec.style_mode == "freek":
        examples = freek_example_context()
        if examples:
            payload["freek_example_context"] = examples
            payload["example_instruction"] = (
                "Use the examples only as structural context. Do not copy wording, names, or situations, "
                "and do not claim the result is an authentic Freek de Jonge joke."
            )
    return payload


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
    """Apply the non-compensatory SSTH/GTVH gate."""
    return all(
        (
            assessment.dual_compatibility,
            assessment.genuine_opposition,
            assessment.single_axis,
            assessment.anchor_supports_both,
            assessment.coherent_logical_mechanism,
            assessment.recognizable_second_reading,
        )
    )


def build_audience_expectation_prompt(spec: PipelineSpec, request: JokeRequest) -> str:
    """Build the proposition-level Script A prompt."""
    return _structured_prompt(
        """
You analyze the default audience interpretation that a joke setup can activate.
Write all creative and analytical fields in Dutch.

Stage 1: Audience expectation and Script A.
For the supplied topic:
1. state the normal, common-sense Script A
2. list 2-5 concrete propositions a general audience normally assumes
3. summarize the expectation a setup should activate

Do not write a joke and do not invent an opposing script yet.
Return script_a, expected_propositions, and audience_expectation.
""".strip(),
        _base_payload(spec, request),
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
Generate exactly 8 candidates with candidate_id B1 through B8.
Every candidate must:
- contradict one explicit Script A proposition, not merely add a metaphor or darker description
- identify one dominant opposition axis
- use a concrete shared word, phrase, object, role, or situation as an anchor
- explain how that anchor supports reading_a and reading_b
- provide a coherent logical mechanism that enables the switch
- remain recognizable or plausible under Script B

Diversify the axes and logical mechanisms. Do not rank the candidates.
Return candidate_id, script_b, opposition_axis, opposed_proposition,
shared_anchor, reading_a, reading_b, and logical_mechanism for each candidate.
""".strip(),
        payload,
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
- genuine_opposition: Script B contradicts Script A rather than merely reframing it
- single_axis: the opposition has one clear dominant axis
- anchor_supports_both: the proposed anchor naturally supports both readings
- coherent_logical_mechanism: the audience can resolve the switch
- recognizable_second_reading: Script B is plausible or socially recognizable

This is a non-compensatory gate: do not pass a weak criterion because the candidate is creative.
At least two candidates should pass only if the supplied candidates genuinely justify it.
""".strip(),
        payload,
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
Replace the failed set with exactly 8 substantially revised candidates using
candidate_id B1 through B8. Use the gate feedback diagnostically.

For every replacement:
- copy one expected Script A proposition verbatim into opposed_proposition
- make script_b a concise proposition that directly contradicts it
- use one dominant opposition axis expressible as X/not-X or a clear scalar reversal
- choose a concrete anchor that can genuinely occur in a joke and support both readings
- state reading_a and reading_b as two interpretations of that same anchor
- state the precise logical mechanism that makes the late switch resolvable
- keep the second reading plausible or socially recognizable

Do not preserve a failed idea merely by rephrasing it. Do not rank candidates.
Return a complete replacement candidate set.
""".strip(),
        payload,
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
- strongest shared-anchor potential
- most coherent logical mechanism
- best topic specificity
- best payoff potential

Return selected_candidate_id and rationale.
Do not repeat or rewrite Script B.
""".strip(),
        payload,
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
You turn a validated script opposition into a complete GTVH joke plan.
Write all fields in Dutch.

Stage 5: GTVH plan.
Specify:
- opposition_type: the Script Opposition
- logical_mechanism: how the incongruity becomes retrospectively understandable
- situation: participants, activity, objects, and setting
- target: the person, institution, convention, or idea being targeted; null if none
- narrative_strategy: how setup and punchline are organized
- lexical_anchor: a concrete surface expression capable of supporting both readings
- setup_goal: how Script A becomes the dominant expectation
- punch_goal: how Script B reinterprets the setup
- punch_final_word: the strongest intended final word or short phrase

Preserve the selected opposition. Do not replace it with a merely related contrast.
""".strip(),
        payload,
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

Stage 6: Controlled joke generation.
Write exactly three variants with variant_id V1, V2, and V3.
The GTVH plan is a constraint, not finished joke copy.
For every variant:
- setup primarily activates Script A
- punchline activates Script B late
- full_text contains the exact setup and punchline
- a concrete anchor_surface_form occurs verbatim in full_text
- earlier wording remains interpretable under both scripts after the punchline
- the switch is surprising but quickly understandable
- the joke is specific to the supplied topic
- full_text ends as close as possible to the planned strongest word or phrase

{COMIC_REALIZATION_GUIDANCE}

Discard and replace any draft for which no exact audience laugh moment can be identified.
Return variant_id, setup, punchline, full_text, angle, and anchor_surface_form.
""".strip(),
        payload,
    )


def build_blind_reconstruction_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    variants: list[ValidatedJokeVariantOutput],
) -> str:
    """Build a plan-blind realization audit."""
    payload = {
        "topic": request.topic,
        "audience": request.audience,
        "variants": [
            {"variant_id": variant.variant_id, "full_text": variant.full_text}
            for variant in variants
        ],
    }
    return _structured_prompt(
        """
You independently analyze completed jokes without access to their intended plans.
Write all analytical fields in Dutch except variant_id.

Stage 7: Blind script reconstruction.
For every variant_id, recover:
- the initially activated Script A
- the punchline-activated Script B
- the exact word, phrase, object, role, or situation anchoring both readings
- the dominant opposition axis

Then determine:
- dual_reading_valid: the text itself supports both recovered scripts
- resolution_valid: the punch makes the earlier setup retrospectively understandable
- topic_specific: the joke materially depends on the supplied topic

Return exactly one assessment per variant. Do not reward intended structure that is absent from the text.
""".strip(),
        payload,
    )


def build_pairwise_selection_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    variants: list[ValidatedJokeVariantOutput],
    reconstructions: list[BlindReconstructionAssessmentOutput],
) -> str:
    """Build ID-only pairwise final selection."""
    pairs = [
        {"left_variant_id": left.variant_id, "right_variant_id": right.variant_id}
        for left, right in itertools.combinations(variants, 2)
    ]
    payload = {
        **_base_payload(spec, request),
        "eligible_variants": [variant.model_dump() for variant in variants],
        "blind_reconstructions": [assessment.model_dump() for assessment in reconstructions],
        "required_pairs": pairs,
    }
    return _structured_prompt(
        f"""
You are the final comparative joke evaluator.
Write rationales in Dutch.

Stage 8: Pairwise selection.
Judge every required pair and return exactly one comparison for each.
For each pair, winner_variant_id must equal its left_variant_id or right_variant_id.

{COMIC_SELECTION_GUIDANCE}

For every pair, compare funniness, punchline strength, and performability first.
Use recoverable script opposition, setup clarity, logical resolution, topic specificity,
concision, and originality only as secondary criteria.

Then return selected_variant_id for the best overall eligible variant and an overall rationale.
Select by ID only. Never rewrite a joke.
""".strip(),
        payload,
    )


def _validate_variants(variants: list[ValidatedJokeVariantOutput]) -> list[str]:
    """Apply deterministic surface-form requirements."""
    identifiers = _unique_ids(variants, "variant_id", stage="variants")
    expected_ids = {"V1", "V2", "V3"}
    if set(identifiers) != expected_ids or len(identifiers) != len(expected_ids):
        raise ValueError(f"Variants must use exactly V1, V2, and V3; received {identifiers}.")
    for variant in variants:
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
    """Require the complete immutable B1-B8 candidate set."""
    identifiers = _unique_ids(candidates, "candidate_id", stage=stage)
    expected_ids = {f"B{index}" for index in range(1, 9)}
    if set(identifiers) != expected_ids or len(identifiers) != len(expected_ids):
        raise ValueError(
            f"{stage} must use exactly B1 through B8; received {identifiers}."
        )
    return identifiers


def _gate_failure_summary(assessments: list[TheoryGateAssessmentOutput]) -> str:
    """Summarize which mandatory criteria rejected the candidate set."""
    criteria = (
        "dual_compatibility",
        "genuine_opposition",
        "single_axis",
        "anchor_supports_both",
        "coherent_logical_mechanism",
        "recognizable_second_reading",
    )
    failures = {
        criterion: sum(not bool(getattr(assessment, criterion)) for assessment in assessments)
        for criterion in criteria
    }
    return ", ".join(f"{criterion}={count}" for criterion, count in failures.items() if count)


def _validate_pairwise_selection(
    selection: PairwiseSelectionOutput,
    eligible_ids: list[str],
) -> None:
    """Require a complete and internally valid pairwise comparison set."""
    if selection.selected_variant_id not in eligible_ids:
        raise ValueError("Pairwise selector chose a variant that was not eligible.")

    expected_pairs = {frozenset(pair) for pair in itertools.combinations(eligible_ids, 2)}
    actual_pairs: set[frozenset[str]] = set()
    for comparison in selection.comparisons:
        pair = frozenset((comparison.left_variant_id, comparison.right_variant_id))
        if comparison.winner_variant_id not in pair:
            raise ValueError("A pairwise winner was not a member of its comparison.")
        actual_pairs.add(pair)
    if actual_pairs != expected_pairs or len(selection.comparisons) != len(expected_pairs):
        raise ValueError("Pairwise selector did not return exactly every required comparison.")


def _dry_run_fixtures() -> tuple[
    AudienceExpectationOutput,
    list[GTVHCandidateOutput],
    list[TheoryGateAssessmentOutput],
    GTVHCandidateOutput,
    GTVHPlanOutput,
    list[ValidatedJokeVariantOutput],
    list[BlindReconstructionAssessmentOutput],
]:
    """Create coherent placeholders used only to expose every dry-run prompt."""
    audience = AudienceExpectationOutput(
        script_a="Een publieke voorziening levert bezoekers een dienst.",
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
            logical_mechanism="omkering van gever en ontvanger",
        )
        for index in range(1, 9)
    ]
    gates = [
        TheoryGateAssessmentOutput(
            candidate_id=candidate.candidate_id,
            dual_compatibility=True,
            genuine_opposition=True,
            single_axis=True,
            anchor_supports_both=True,
            coherent_logical_mechanism=True,
            recognizable_second_reading=True,
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
    reconstructions = [
        BlindReconstructionAssessmentOutput(
            variant_id=variant.variant_id,
            recovered_script_a="De instelling helpt de bezoeker.",
            recovered_script_b="De bezoeker wordt door de instelling gebruikt.",
            recovered_anchor="voorziening",
            opposition_axis="geven/nemen",
            dual_reading_valid=True,
            resolution_valid=True,
            topic_specific=True,
            rationale="Dry-run reconstructie is geldig.",
        )
        for variant in variants
    ]
    return audience, candidates, gates, candidates[0], plan, variants, reconstructions


def dry_run_validated_gtvh_pipeline(spec: PipelineSpec, request: JokeRequest) -> PipelineResult:
    """Build every validated-GTVH prompt without model calls."""
    audience, candidates, gates, selected, plan, variants, reconstructions = _dry_run_fixtures()
    prompts = [
        ("audience_expectation", build_audience_expectation_prompt(spec, request)),
        ("opposition_candidates", build_opposition_candidates_prompt(spec, request, audience)),
        ("theory_gate", build_theory_gate_prompt(spec, request, audience, candidates)),
        ("candidate_selection", build_candidate_selection_prompt(spec, request, audience, candidates)),
        ("gtvh_plan", build_gtvh_plan_prompt(spec, request, audience, selected)),
        ("variants", build_validated_variants_prompt(spec, request, audience, selected, plan)),
        ("blind_reconstruction", build_blind_reconstruction_prompt(spec, request, variants)),
        ("pairwise_selection", build_pairwise_selection_prompt(spec, request, variants, reconstructions)),
    ]
    combined_prompt = "\n\n---\n\n".join(f"## {stage}\n{prompt}" for stage, prompt in prompts)
    semantic_plan = SemanticPlan(
        setup_script=audience.script_a,
        opposing_script=selected.script_b,
        opposition_type=plan.opposition_type,
        trigger=plan.lexical_anchor,
        setup_goal=plan.setup_goal,
        punch_goal=plan.punch_goal,
        style_mode=spec.style_mode,
    )
    joke = "[dry run] Validated GTVH prompts built successfully."
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=spec.name,
        request=request,
        prompt=combined_prompt,
        joke=joke,
        semantic_plan=semantic_plan,
        raw_response=combined_prompt,
        script_b_candidates=[ScriptBCandidate(script_b=candidate.script_b) for candidate in candidates],
        script_b_rationale="Dry run selected candidate B1 after the theory gate.",
        variants=[JokeVariant(text=variant.full_text, angle=variant.angle) for variant in variants],
        metadata={
            "family": spec.family,
            "style_mode": spec.style_mode,
            "stages": [stage for stage, _ in prompts],
            "gtvh_trace": {
                "audience_expectation": audience.model_dump(),
                "candidates": [candidate.model_dump() for candidate in candidates],
                "candidate_attempts": [
                    [candidate.model_dump() for candidate in candidates]
                ],
                "theory_gate": [gate.model_dump() for gate in gates],
                "theory_gate_attempts": [
                    [gate.model_dump() for gate in gates]
                ],
                "approved_candidate_ids": [candidate.candidate_id for candidate in candidates],
                "selected_candidate_id": selected.candidate_id,
                "gtvh_plan": plan.model_dump(),
                "detailed_variants": [variant.model_dump() for variant in variants],
                "blind_reconstruction": [item.model_dump() for item in reconstructions],
                "eligible_variant_ids": [variant.variant_id for variant in variants],
                "selected_variant_id": "V1",
            },
        },
    )


def run_validated_gtvh_pipeline(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    model: str,
) -> PipelineResult:
    """Run the additive eight-stage, theory-validated GTVH pipeline."""
    raw_responses: dict[str, str] = {}
    prompts: list[tuple[str, str]] = []
    usage: UsageSummary | None = None

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

    audience = call(
        "audience_expectation",
        build_audience_expectation_prompt(spec, request),
        AudienceExpectationOutput,
    )
    assert isinstance(audience, AudienceExpectationOutput)

    candidates_payload = call(
        "opposition_candidates",
        build_opposition_candidates_prompt(spec, request, audience),
        GTVHCandidatesOutput,
    )
    assert isinstance(candidates_payload, GTVHCandidatesOutput)
    candidates = candidates_payload.candidates
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
    gate_attempts = [
        [assessment.model_dump() for assessment in gate_payload.assessments]
    ]
    gates_by_id = {assessment.candidate_id: assessment for assessment in gate_payload.assessments}
    approved = [
        candidate
        for candidate in candidates
        if _passes_theory_gate(gates_by_id[candidate.candidate_id])
    ]
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
        gate_attempts.append(
            [assessment.model_dump() for assessment in gate_payload.assessments]
        )
        gates_by_id = {
            assessment.candidate_id: assessment
            for assessment in gate_payload.assessments
        }
        approved = [
            candidate
            for candidate in candidates
            if _passes_theory_gate(gates_by_id[candidate.candidate_id])
        ]
        if not approved:
            summary = _gate_failure_summary(gate_payload.assessments)
            raise ValueError(
                "No Script B candidate passed every mandatory SSTH/GTVH gate criterion "
                f"after one targeted repair attempt. Failed checks: {summary}."
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
            "Candidate selector chose an ID that did not pass the theory gate: "
            f"{selection.selected_candidate_id!r}."
        )
    selected = approved_by_id[selection.selected_candidate_id]

    plan = call(
        "gtvh_plan",
        build_gtvh_plan_prompt(spec, request, audience, selected),
        GTVHPlanOutput,
    )
    assert isinstance(plan, GTVHPlanOutput)

    variants_payload = call(
        "variants",
        build_validated_variants_prompt(spec, request, audience, selected, plan),
        ValidatedJokeVariantsOutput,
    )
    assert isinstance(variants_payload, ValidatedJokeVariantsOutput)
    variants = variants_payload.variants
    variant_ids = _validate_variants(variants)

    reconstruction = call(
        "blind_reconstruction",
        build_blind_reconstruction_prompt(spec, request, variants),
        BlindReconstructionOutput,
    )
    assert isinstance(reconstruction, BlindReconstructionOutput)
    reconstruction_ids = _unique_ids(
        reconstruction.assessments,
        "variant_id",
        stage="blind_reconstruction",
    )
    _require_same_ids(variant_ids, reconstruction_ids, stage="blind_reconstruction")
    reconstruction_by_id = {
        assessment.variant_id: assessment for assessment in reconstruction.assessments
    }
    eligible = [
        variant
        for variant in variants
        if all(
            (
                reconstruction_by_id[variant.variant_id].dual_reading_valid,
                reconstruction_by_id[variant.variant_id].resolution_valid,
                reconstruction_by_id[variant.variant_id].topic_specific,
            )
        )
    ]
    if len(eligible) < 2:
        raise ValueError(
            "Fewer than two variants passed blind dual-reading, resolution, and topic-specificity checks."
        )

    eligible_reconstructions = [
        reconstruction_by_id[variant.variant_id] for variant in eligible
    ]
    final_selection = call(
        "pairwise_selection",
        build_pairwise_selection_prompt(
            spec,
            request,
            eligible,
            eligible_reconstructions,
        ),
        PairwiseSelectionOutput,
    )
    assert isinstance(final_selection, PairwiseSelectionOutput)
    eligible_ids = [variant.variant_id for variant in eligible]
    _validate_pairwise_selection(final_selection, eligible_ids)
    variants_by_id = {variant.variant_id: variant for variant in variants}
    best = variants_by_id[final_selection.selected_variant_id]

    semantic_plan = SemanticPlan(
        setup_script=audience.script_a,
        opposing_script=selected.script_b,
        opposition_type=plan.opposition_type,
        trigger=plan.lexical_anchor,
        setup_goal=plan.setup_goal,
        punch_goal=plan.punch_goal,
        style_mode=spec.style_mode,
    )
    combined_prompt = "\n\n---\n\n".join(
        f"## {stage}\n{prompt}" for stage, prompt in prompts
    )
    rejected_variant_ids = [
        variant.variant_id for variant in variants if variant.variant_id not in eligible_ids
    ]
    warnings = (
        [f"Blind reconstruction rejected variants: {', '.join(rejected_variant_ids)}."]
        if rejected_variant_ids
        else []
    )
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=spec.name,
        request=request,
        prompt=combined_prompt,
        joke=best.full_text,
        semantic_plan=semantic_plan,
        raw_response=json.dumps(raw_responses, ensure_ascii=False, indent=2),
        warnings=warnings,
        script_b_candidates=[
            ScriptBCandidate(script_b=candidate.script_b) for candidate in candidates
        ],
        script_b_rationale=selection.rationale,
        variants=[
            JokeVariant(text=variant.full_text, angle=variant.angle) for variant in variants
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
                    assessment.model_dump() for assessment in gate_payload.assessments
                ],
                "theory_gate_attempts": gate_attempts,
                "approved_candidate_ids": [
                    candidate.candidate_id for candidate in approved
                ],
                "selected_candidate_id": selected.candidate_id,
                "gtvh_plan": plan.model_dump(),
                "detailed_variants": [variant.model_dump() for variant in variants],
                "blind_reconstruction": [
                    assessment.model_dump()
                    for assessment in reconstruction.assessments
                ],
                "eligible_variant_ids": eligible_ids,
                "pairwise_comparisons": [
                    comparison.model_dump()
                    for comparison in final_selection.comparisons
                ],
                "selected_variant_id": final_selection.selected_variant_id,
                "selection_rationale": final_selection.rationale,
            },
        },
    )
