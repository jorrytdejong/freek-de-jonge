from __future__ import annotations

from core.runner import run_pipeline
from core.schemas import (
    AudienceExpectationOutput,
    BlindReconstructionAssessmentOutput,
    BlindReconstructionOutput,
    GTVHCandidateOutput,
    GTVHCandidatesOutput,
    GTVHPlanOutput,
    JokeRequest,
    PairwiseComparisonOutput,
    PairwiseSelectionOutput,
    TheoryGateAssessmentOutput,
    TheoryGateOutput,
    UsageSummary,
    ValidatedCandidateSelectionOutput,
    ValidatedJokeVariantOutput,
    ValidatedJokeVariantsOutput,
)
from pipelines import validated_gtvh


def candidate(candidate_id: str) -> GTVHCandidateOutput:
    """Build one deterministic valid opposition candidate."""
    return GTVHCandidateOutput(
        candidate_id=candidate_id,
        script_b=f"De bezoeker voorziet de instelling ({candidate_id}).",
        opposition_axis="geven/nemen",
        opposed_proposition="De instelling geeft iets aan de bezoeker.",
        shared_anchor="voorziening",
        reading_a="De instelling voorziet de bezoeker.",
        reading_b="De bezoeker voorziet de instelling.",
        logical_mechanism="omkering van gever en ontvanger",
    )


CANDIDATES = [candidate(f"B{index}") for index in range(1, 9)]
VARIANTS = [
    ValidatedJokeVariantOutput(
        variant_id=f"V{index}",
        setup=f"De voorziening staat voor u klaar, versie {index}.",
        punchline="U hoeft alleen uzelf in te leveren.",
        full_text=(
            f"De voorziening staat voor u klaar, versie {index}. "
            "U hoeft alleen uzelf in te leveren."
        ),
        angle="geven/nemen",
        anchor_surface_form="voorziening",
    )
    for index in range(1, 4)
]


def fake_generate_structured(prompt, response_model, *, model):
    """Return a complete deterministic E-pipeline fixture."""
    outputs = {
        AudienceExpectationOutput: AudienceExpectationOutput(
            script_a="Een voorziening geeft iets aan de bezoeker.",
            expected_propositions=[
                "De instelling geeft iets.",
                "De bezoeker ontvangt iets.",
            ],
            audience_expectation="De instelling helpt de bezoeker.",
        ),
        GTVHCandidatesOutput: GTVHCandidatesOutput(candidates=CANDIDATES),
        TheoryGateOutput: TheoryGateOutput(
            assessments=[
                TheoryGateAssessmentOutput(
                    candidate_id=item.candidate_id,
                    dual_compatibility=True,
                    genuine_opposition=True,
                    single_axis=True,
                    anchor_supports_both=True,
                    coherent_logical_mechanism=True,
                    recognizable_second_reading=True,
                    rationale="Alle harde criteria zijn expliciet gerealiseerd.",
                )
                for item in CANDIDATES
            ]
        ),
        ValidatedCandidateSelectionOutput: ValidatedCandidateSelectionOutput(
            selected_candidate_id="B3",
            rationale="B3 heeft de bondigste omkering.",
        ),
        GTVHPlanOutput: GTVHPlanOutput(
            opposition_type="geven/nemen",
            logical_mechanism="omkering van gever en ontvanger",
            situation="een bezoeker bij een publieke instelling",
            target="institutionele taal",
            narrative_strategy="setup gevolgd door late rolomkering",
            lexical_anchor="voorziening",
            setup_goal="Laat de instelling behulpzaam lijken.",
            punch_goal="Onthul dat de bezoeker wordt ingeleverd.",
            punch_final_word="inleveren",
        ),
        ValidatedJokeVariantsOutput: ValidatedJokeVariantsOutput(variants=VARIANTS),
        BlindReconstructionOutput: BlindReconstructionOutput(
            assessments=[
                BlindReconstructionAssessmentOutput(
                    variant_id=item.variant_id,
                    recovered_script_a="De instelling helpt.",
                    recovered_script_b="De instelling neemt.",
                    recovered_anchor="voorziening",
                    opposition_axis="geven/nemen",
                    dual_reading_valid=True,
                    resolution_valid=True,
                    topic_specific=True,
                    rationale="Beide lezingen zijn uit de tekst te reconstrueren.",
                )
                for item in VARIANTS
            ]
        ),
        PairwiseSelectionOutput: PairwiseSelectionOutput(
            comparisons=[
                PairwiseComparisonOutput(
                    left_variant_id="V1",
                    right_variant_id="V2",
                    winner_variant_id="V2",
                    rationale="V2 is bondiger.",
                ),
                PairwiseComparisonOutput(
                    left_variant_id="V1",
                    right_variant_id="V3",
                    winner_variant_id="V1",
                    rationale="V1 heeft een duidelijkere setup.",
                ),
                PairwiseComparisonOutput(
                    left_variant_id="V2",
                    right_variant_id="V3",
                    winner_variant_id="V2",
                    rationale="V2 heeft de sterkste switch.",
                ),
            ],
            selected_variant_id="V2",
            rationale="V2 wint de pairwise vergelijking.",
        ),
    }
    parsed = outputs[response_model]
    return parsed, parsed.model_dump_json(), UsageSummary(model=model, total_tokens=10)


def invalid_selection_generate_structured(prompt, response_model, *, model):
    """Return an out-of-set candidate ID only at the selection stage."""
    if response_model is ValidatedCandidateSelectionOutput:
        parsed = ValidatedCandidateSelectionOutput(
            selected_candidate_id="B99",
            rationale="Deze kandidaat bestaat niet.",
        )
        return parsed, parsed.model_dump_json(), UsageSummary(model=model, total_tokens=10)
    return fake_generate_structured(prompt, response_model, model=model)


def main() -> None:
    """Verify normal execution, zero-pass repair, and membership guards."""
    original = validated_gtvh.generate_structured
    validated_gtvh.generate_structured = fake_generate_structured
    try:
        result = run_pipeline(
            "E1",
            JokeRequest(topic="de gemeente"),
            model="test-model",
        )
    finally:
        validated_gtvh.generate_structured = original

    trace = result.metadata["gtvh_trace"]
    assert result.semantic_plan.opposing_script == CANDIDATES[2].script_b
    assert trace["selected_candidate_id"] == "B3"
    assert trace["selected_variant_id"] == "V2"
    assert result.joke == VARIANTS[1].full_text
    assert result.metadata["stages"] == [
        "audience_expectation",
        "opposition_candidates",
        "theory_gate",
        "candidate_selection",
        "gtvh_plan",
        "variants",
        "blind_reconstruction",
        "pairwise_selection",
    ]

    repair_state = {"gate_calls": 0}

    def zero_pass_then_recover(prompt, response_model, *, model):
        if response_model is TheoryGateOutput:
            repair_state["gate_calls"] += 1
            if repair_state["gate_calls"] == 1:
                parsed = TheoryGateOutput(
                    assessments=[
                        TheoryGateAssessmentOutput(
                            candidate_id=item.candidate_id,
                            dual_compatibility=False,
                            genuine_opposition=False,
                            single_axis=True,
                            anchor_supports_both=False,
                            coherent_logical_mechanism=False,
                            recognizable_second_reading=True,
                            rationale="De eerste kandidaatset is slechts een herformulering.",
                        )
                        for item in CANDIDATES
                    ]
                )
                return parsed, parsed.model_dump_json(), UsageSummary(
                    model=model,
                    total_tokens=10,
                )
        return fake_generate_structured(prompt, response_model, model=model)

    validated_gtvh.generate_structured = zero_pass_then_recover
    try:
        repaired = run_pipeline(
            "E1",
            JokeRequest(topic="de gemeente"),
            model="test-model",
        )
    finally:
        validated_gtvh.generate_structured = original

    assert repair_state["gate_calls"] == 2
    assert "opposition_repair" in repaired.metadata["stages"]
    assert "theory_gate_repaired" in repaired.metadata["stages"]
    assert len(repaired.metadata["gtvh_trace"]["candidate_attempts"]) == 2
    assert len(repaired.metadata["gtvh_trace"]["theory_gate_attempts"]) == 2
    assert repaired.joke == VARIANTS[1].full_text

    validated_gtvh.generate_structured = invalid_selection_generate_structured
    try:
        try:
            run_pipeline("E1", JokeRequest(topic="de gemeente"), model="test-model")
        except ValueError as exc:
            assert "did not pass the theory gate" in str(exc)
        else:
            raise AssertionError("Out-of-set candidate selection was not rejected.")
    finally:
        validated_gtvh.generate_structured = original

    print("ACL validated GTVH pipeline test passed.")


if __name__ == "__main__":
    main()
