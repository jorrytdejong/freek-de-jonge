from __future__ import annotations

from itertools import combinations

from core.schemas import JokeRequest
from pipelines.conditions import PIPELINE_SPECS
from pipelines.simplified_ce import (
    CANDIDATE_IDS,
    VARIANT_IDS,
    SimpleComparison,
    SimpleFinalEvaluation,
    SimpleGTVHPlan,
    SimpleOpposition,
    SimpleOppositionAssessment,
    SimpleOppositionAudit,
    SimpleOppositionSet,
    SimpleVariant,
    SimpleVariantAssessment,
    SimpleVariants,
    build_evaluation_prompt,
    build_generation_prompt,
    build_gtvh_prompt,
    build_opposition_audit_prompt,
    build_opposition_prompt,
    _validate_audit,
    _validate_evaluation,
)


REQUEST = JokeRequest(topic="de wachtrij bij de gemeente")
PROPOSALS = SimpleOppositionSet(
    script_a="De gemeente helpt een inwoner.",
    audience_expectation="De inwoner krijgt hulp.",
    candidates=[
        SimpleOpposition(
            candidate_id=candidate_id,
            script_b=f"De gemeente gebruikt de inwoner ({candidate_id}).",
            opposition_axis="helpen/gebruiken",
            shared_cues=["loket", "bijdrage"],
            switch_trigger="lever uzelf in",
            role_reversal="helper wordt ontvanger",
            retrospective_reinterpretation="De bijdrage blijkt de inwoner zelf.",
        )
        for candidate_id in CANDIDATE_IDS
    ],
)
AUDIT = SimpleOppositionAudit(
    assessments=[
        SimpleOppositionAssessment(
            candidate_id=candidate_id,
            supports_both_meanings=True,
            meanings_really_conflict=True,
            normal_meaning_comes_first=True,
            hidden_meaning_is_clear_after_switch=True,
            earlier_words_gain_new_meaning=True,
            rationale="De omslag werkt.",
        )
        for candidate_id in CANDIDATE_IDS
    ],
    selected_candidate_id="B2",
    selection_rationale="B2 heeft de duidelijkste omslag.",
)
GTVH = SimpleGTVHPlan(
    logical_mechanism="rolomkering",
    situation="een inwoner aan het gemeenteloket",
    target="bureaucratie",
    narrative_strategy="kort verhaal",
    language="bijdrage en inleveren dragen de dubbele betekenis",
)
VARIANTS = SimpleVariants(
    variants=[
        SimpleVariant(
            variant_id=variant_id,
            text=(
                "Bij het gemeenteloket vroeg ik om hulp met mijn bijdrage. "
                "De ambtenaar glimlachte: natuurlijk, lever uzelf maar in; "
                "de gemeente komt dit jaar nog één inwoner tekort."
            ),
            angle="De inwoner is de gemeentelijke bijdrage.",
        )
        for variant_id in VARIANT_IDS
    ]
)


def evaluation(*, is_e: bool) -> SimpleFinalEvaluation:
    return SimpleFinalEvaluation(
        assessments=[
            SimpleVariantAssessment(
                variant_id=variant_id,
                preserves_script_opposition=True,
                preserves_logical_mechanism=True if is_e else None,
                preserves_situation=True if is_e else None,
                preserves_target=True if is_e else None,
                preserves_narrative_strategy=True if is_e else None,
                preserves_language_plan=True if is_e else None,
                clear_switch=True,
                punchline_lands=True,
                humor_score=4,
                rationale="Plan en punchline blijven zichtbaar.",
            )
            for variant_id in VARIANT_IDS
        ],
        comparisons=[
            SimpleComparison(
                left_variant_id=left,
                right_variant_id=right,
                winner_variant_id=left,
                rationale="De linkervariant is compacter.",
            )
            for left, right in combinations(VARIANT_IDS, 2)
        ],
        selected_variant_id="V1",
        selection_rationale="V1 is het duidelijkst.",
    )


def test_plain_language_prompts_and_shared_so() -> None:
    proposal_prompt = build_opposition_prompt(REQUEST)
    audit_prompt = build_opposition_audit_prompt(REQUEST, PROPOSALS)
    assert "normal situation" in proposal_prompt
    assert "hidden meanings" in proposal_prompt
    assert "simple questions" in audit_prompt
    assert "Logical Mechanism" not in proposal_prompt
    assert _validate_audit(PROPOSALS, AUDIT).candidate_id == "B2"


def test_c_and_e_keep_the_same_selected_opposition() -> None:
    selected = _validate_audit(PROPOSALS, AUDIT)
    c_prompt = build_generation_prompt(
        PIPELINE_SPECS["C1"], REQUEST, PROPOSALS.script_a, selected, None
    )
    e_prompt = build_generation_prompt(
        PIPELINE_SPECS["E1"], REQUEST, PROPOSALS.script_a, selected, GTVH
    )
    assert selected.script_b in c_prompt
    assert selected.script_b in e_prompt
    assert "Use only the normal and hidden meanings" in c_prompt
    assert GTVH.logical_mechanism in e_prompt
    assert "Do not change either meaning" in build_gtvh_prompt(
        REQUEST, PROPOSALS.script_a, selected
    )


def test_combined_evaluation_preserves_condition_difference() -> None:
    selected = _validate_audit(PROPOSALS, AUDIT)
    c_prompt = build_evaluation_prompt(
        PIPELINE_SPECS["C1"], REQUEST, PROPOSALS.script_a, selected, VARIANTS, None
    )
    e_prompt = build_evaluation_prompt(
        PIPELINE_SPECS["E1"], REQUEST, PROPOSALS.script_a, selected, VARIANTS, GTVH
    )
    assert "must be null" in c_prompt
    assert "extra E choice" in e_prompt
    assert _validate_evaluation(evaluation(is_e=False), is_e=False)[0] == list(VARIANT_IDS)
    assert _validate_evaluation(evaluation(is_e=True), is_e=True)[0] == list(VARIANT_IDS)
