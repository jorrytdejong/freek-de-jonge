from __future__ import annotations

from dataclasses import dataclass
import itertools
import json
from typing import Any

from core.llm import add_usage, generate_structured
from core.joke_length import joke_length_instruction
from core.schemas import (
    JokeRequest,
    PairwiseComparisonOutput,
    PairwiseSelectionOutput,
    PipelineSpec,
    PlanFidelityAssessmentOutput,
    PlanFidelityOutput,
    JokeRepairVariantsOutput,
    ResourceFidelityOutput,
    UsageSummary,
)


RESOURCE_FIELDS = {
    "SO": "script_opposition",
    "LM": "logical_mechanism",
    "SI": "situation",
    "TA": "target",
    "NS": "narrative_strategy",
    "LA": "language",
}


@dataclass(frozen=True)
class FidelityVariant:
    variant_id: str
    text: str
    angle: str


@dataclass
class PlanFidelitySelectionResult:
    assessments: list[PlanFidelityAssessmentOutput]
    passing_variant_ids: list[str]
    selection: PairwiseSelectionOutput
    selected_variant_id: str
    prompts: list[tuple[str, str]]
    raw_responses: dict[str, str]
    usage: UsageSummary | None
    warnings: list[str]
    variants: list[FidelityVariant]
    repaired: bool = False


def _structured_prompt(task: str, payload: dict[str, Any]) -> str:
    return (
        f"{task}\n\nInput:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        "\n\nReturn the requested structured fields."
    )


def build_plan_fidelity_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    required_resources: list[str],
    intended_plan: dict[str, Any],
    variants: list[FidelityVariant],
) -> str:
    """Build the plan-aware fidelity audit used after variant generation."""
    return _structured_prompt(
        """
You evaluate whether completed Dutch jokes realize their supplied intended plan.
This is a plan-fidelity audit, not blind reconstruction and not a creativity review.

Evaluation stage 1: Plan fidelity.
Assess exactly one record for every variant_id. Compare the text with the intended
plan; do not reward a different opposition or mechanism merely because it also works.

For every variant:
- recover realized_script_a, realized_script_b, and realized_opposition_axis
- assess Script Opposition fidelity: the intended A and B, axis, overlap, and switch
- assess setup_dominance, latent_script_b, shared_cues_realized,
  switch_trigger_realized, and retrospective_reinterpretation
- assess joke validity independently of theory fidelity:
  is_spoken_naturally, has_recognizable_setup, has_clear_turn, has_punchline,
  and sounds_like_a_joke
- set unplanned_opposition true when the joke works mainly through a different SO
- assess LM, SI, TA, NS, and LA only when they occur in required_resources
- for a non-required resource, set applicable=false and preserved=null
- Target is applicable only when TA is required and the intended target is non-null

Resource meanings:
- SO: intended scripts, opposition axis, overlap/shared cues, and switch
- LM: intended way the incongruity becomes retrospectively understandable
- SI: intended participants, activities, objects, and setting
- TA: intended butt of the joke
- NS: intended textual organization and punch placement
- LA: intended lexical hinge, register, wording constraints, and ending

Set preserved=true only for functional preservation, not topical resemblance.
Joke validity is non-compensatory: a variant is not a passing joke when any of
the five joke-validity fields is false, even if every theory resource is preserved.
Return all resource objects and one concise overall rationale per variant.
""".strip(),
        {
            "topic": request.topic,
            "required_resources": required_resources,
            "intended_plan": intended_plan,
            "variants": [
                {
                    "variant_id": variant.variant_id,
                    "text": variant.text,
                    "angle": variant.angle,
                }
                for variant in variants
            ],
        },
    )


def build_pairwise_selection_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    required_resources: list[str],
    variants: list[FidelityVariant],
    assessments: list[PlanFidelityAssessmentOutput],
    passing_variant_ids: list[str],
) -> str:
    pairs = [
        {"left_variant_id": left.variant_id, "right_variant_id": right.variant_id}
        for left, right in itertools.combinations(variants, 2)
    ]
    return _structured_prompt(
        f"""
You perform the final pairwise selection among generated joke variants.
Write rationales in Dutch and never rewrite a joke.

Evaluation stage 2: Pairwise selection.
Return exactly one comparison for every required pair. Judge fidelity to the
supplied required plan, setup clarity, switch strength, retrospective
reinterpretation, concision, funniness, and originality.
The mandatory surface-length policy is: {joke_length_instruction()}

Selection rules:
- every compared variant must comply with the mandatory surface-length policy
- if passing_variant_ids is non-empty, every passing variant outranks every failing variant
- among variants with equal pass status, prefer stronger required-resource fidelity,
  then the stronger joke
- if no variant passed, select the best available variant and explain the structural failure
- prefer a variant that is clearly performable as a spoken joke; do not select an
  explanation, slogan, observation, or summary merely because it has good theory fidelity
- selected_variant_id and every winner_variant_id must reference supplied IDs

Select by ID only.
""".strip(),
        {
            "topic": request.topic,
            "required_resources": required_resources,
            "variants": [
                {
                    "variant_id": variant.variant_id,
                    "text": variant.text,
                    "angle": variant.angle,
                }
                for variant in variants
            ],
            "fidelity_assessments": [assessment.model_dump() for assessment in assessments],
            "passing_variant_ids": passing_variant_ids,
            "required_pairs": pairs,
        },
    )


def build_joke_repair_prompt(
    request: JokeRequest,
    *,
    intended_plan: dict[str, Any],
    variants: list[FidelityVariant],
    assessments: list[PlanFidelityAssessmentOutput],
) -> str:
    """Build a focused repair prompt for variants that are not jokes yet."""
    return _structured_prompt(
        f"""
The supplied variants preserve some of a semantic plan but failed the joke-validity gate.
Rewrite all three as actual Dutch jokes intended to be spoken aloud by one comedian.

Each repaired variant must contain:
- a recognizable spoken setup
- a clear turn or misdirection
- a final punchline that creates the laugh

Do not write an explanation, summary, moral, slogan, policy statement, or description
of a joke. Do not end with an abstract conclusion. Preserve the intended Script
Opposition and required resources. Keep each variant within {joke_length_instruction()}.
Return exactly three repaired variants with variant_id V1, V2, and V3, text, and angle.
""".strip(),
        {
            "topic": request.topic,
            "intended_plan": intended_plan,
            "variants": [
                {"variant_id": item.variant_id, "text": item.text, "angle": item.angle}
                for item in variants
            ],
            "failed_assessments": [assessment.model_dump() for assessment in assessments],
        },
    )


def build_length_repair_prompt(
    request: JokeRequest,
    *,
    intended_plan: dict[str, Any],
    variants: list[FidelityVariant],
) -> str:
    """Build a focused one-pass repair prompt for length violations."""
    return _structured_prompt(
        f"""
Some generated variants violate the mandatory surface-length policy.
Rewrite only as much as necessary to make every variant comply with
{joke_length_instruction()}

Preserve the intended Script Opposition, setup, switch, punchline, and required
GTVH resources. Do not add explanation, a new premise, or a different joke.
Keep valid variants substantively unchanged. Return exactly three variants with
variant_id V1, V2, and V3, text, and angle.
""".strip(),
        {
            "topic": request.topic,
            "intended_plan": intended_plan,
            "variants": [
                {
                    "variant_id": item.variant_id,
                    "text": item.text,
                    "angle": item.angle,
                }
                for item in variants
            ],
        },
    )


def build_single_length_repair_prompt(
    request: JokeRequest,
    *,
    intended_plan: dict[str, Any],
    text: str,
    angle: str,
) -> str:
    """Build a focused repair prompt for one direct-generation joke."""
    return _structured_prompt(
        f"""
Rewrite this Dutch joke only as much as necessary to satisfy
{joke_length_instruction()}

Preserve its premise, comic turn, and punchline. Do not explain the joke or add
a new premise. Return the repaired text and angle only.
""".strip(),
        {
            "topic": request.topic,
            "intended_plan": intended_plan,
            "text": text,
            "angle": angle,
        },
    )


def validate_variants(variants: list[FidelityVariant]) -> list[str]:
    """Require the same fixed V1-V3 candidate set in C and E evaluation."""
    identifiers = [variant.variant_id for variant in variants]
    if identifiers != ["V1", "V2", "V3"]:
        raise ValueError(f"Evaluation variants must be ordered V1, V2, V3; received {identifiers}.")
    if len({variant.text for variant in variants}) != 3:
        raise ValueError("Evaluation variants must contain three distinct joke texts.")
    return identifiers


def passes_required_plan(
    assessment: PlanFidelityAssessmentOutput,
    required_resources: list[str],
) -> bool:
    """Compute rather than delegate the non-compensatory fidelity decision."""
    common_checks = (
        assessment.setup_dominance,
        assessment.latent_script_b,
        assessment.shared_cues_realized,
        assessment.switch_trigger_realized,
        assessment.retrospective_reinterpretation,
        not assessment.unplanned_opposition,
        assessment.is_spoken_naturally,
        assessment.has_recognizable_setup,
        assessment.has_clear_turn,
        assessment.has_punchline,
        assessment.sounds_like_a_joke,
    )
    if not all(common_checks):
        return False
    for resource in required_resources:
        field_name = RESOURCE_FIELDS[resource]
        resource_result = getattr(assessment, field_name)
        if not resource_result.applicable or resource_result.preserved is not True:
            return False
    return True


def _validate_assessments(
    assessments: list[PlanFidelityAssessmentOutput],
    variant_ids: list[str],
) -> None:
    assessment_ids = [assessment.variant_id for assessment in assessments]
    if len(assessment_ids) != len(set(assessment_ids)) or set(assessment_ids) != set(variant_ids):
        raise ValueError(
            "Plan-fidelity assessments must contain exactly one record for every variant ID."
        )


def _validate_pairwise_selection(
    selection: PairwiseSelectionOutput,
    variant_ids: list[str],
    passing_variant_ids: list[str],
) -> None:
    if selection.selected_variant_id not in variant_ids:
        raise ValueError("Pairwise selector chose an unknown variant ID.")
    if passing_variant_ids and selection.selected_variant_id not in passing_variant_ids:
        raise ValueError("Pairwise selector chose a failing variant while a passing variant existed.")

    expected_pairs = {frozenset(pair) for pair in itertools.combinations(variant_ids, 2)}
    actual_pairs: set[frozenset[str]] = set()
    passing = set(passing_variant_ids)
    for comparison in selection.comparisons:
        pair = frozenset((comparison.left_variant_id, comparison.right_variant_id))
        if comparison.winner_variant_id not in pair:
            raise ValueError("A pairwise winner was not a member of its comparison.")
        pair_passers = pair & passing
        if len(pair_passers) == 1 and comparison.winner_variant_id not in pair_passers:
            raise ValueError("A failing variant defeated a passing variant in pairwise selection.")
        actual_pairs.add(pair)
    if actual_pairs != expected_pairs or len(selection.comparisons) != len(expected_pairs):
        raise ValueError("Pairwise selector did not return exactly every required comparison.")


def run_plan_fidelity_selection(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    model: str,
    required_resources: list[str],
    intended_plan: dict[str, Any],
    variants: list[FidelityVariant],
    repair_on_failure: bool = True,
) -> PlanFidelitySelectionResult:
    """Run the common two-call evaluation and selection procedure for C and E."""
    variant_ids = validate_variants(variants)
    prompts: list[tuple[str, str]] = []
    raw_responses: dict[str, str] = {}
    usage: UsageSummary | None = None

    fidelity_prompt = build_plan_fidelity_prompt(
        spec,
        request,
        required_resources=required_resources,
        intended_plan=intended_plan,
        variants=variants,
    )
    fidelity, raw, stage_usage = generate_structured(
        fidelity_prompt,
        PlanFidelityOutput,
        model=model,
    )
    prompts.append(("plan_fidelity", fidelity_prompt))
    raw_responses["plan_fidelity"] = raw
    usage = add_usage(usage, stage_usage)
    _validate_assessments(fidelity.assessments, variant_ids)
    assessments_by_id = {
        assessment.variant_id: assessment for assessment in fidelity.assessments
    }
    passing_variant_ids = [
        variant_id
        for variant_id in variant_ids
        if passes_required_plan(assessments_by_id[variant_id], required_resources)
    ]

    if not passing_variant_ids and repair_on_failure:
        repair_prompt = build_joke_repair_prompt(
            request,
            intended_plan=intended_plan,
            variants=variants,
            assessments=fidelity.assessments,
        )
        try:
            repaired_payload, repair_raw, repair_usage = generate_structured(
                repair_prompt,
                JokeRepairVariantsOutput,
                model=model,
            )
        except KeyError:
            # Keep compatibility with older deterministic test doubles that do
            # not register the optional repair response model.
            repaired_payload = None
        if repaired_payload is None:
            repair_on_failure = False
        else:
            repaired_by_id = {
                item.variant_id: FidelityVariant(
                    variant_id=item.variant_id,
                    text=item.text,
                    angle=item.angle,
                )
                for item in repaired_payload.variants
            }
            if set(repaired_by_id) != set(variant_ids) or len(repaired_by_id) != len(variant_ids):
                raise ValueError(
                    "Joke repair must return exactly the original variant IDs."
                )
            repaired_variants = [repaired_by_id[variant_id] for variant_id in variant_ids]
            repaired_result = run_plan_fidelity_selection(
                spec,
                request,
                model=model,
                required_resources=required_resources,
                intended_plan=intended_plan,
                variants=repaired_variants,
                repair_on_failure=False,
            )
            repaired_result.prompts.insert(0, ("joke_repair", repair_prompt))
            repaired_result.raw_responses = {
                "joke_repair": repair_raw,
                **repaired_result.raw_responses,
            }
            repaired_result.usage = add_usage(repair_usage, repaired_result.usage)
            repaired_result.warnings.insert(
                0,
                "Initial variants failed the joke-validity gate and were rewritten by a repair pass.",
            )
            repaired_result.variants = repaired_variants
            repaired_result.repaired = True
            return repaired_result

    selection_prompt = build_pairwise_selection_prompt(
        spec,
        request,
        required_resources=required_resources,
        variants=variants,
        assessments=fidelity.assessments,
        passing_variant_ids=passing_variant_ids,
    )
    selection, raw, stage_usage = generate_structured(
        selection_prompt,
        PairwiseSelectionOutput,
        model=model,
    )
    prompts.append(("pairwise_selection", selection_prompt))
    raw_responses["pairwise_selection"] = raw
    usage = add_usage(usage, stage_usage)
    _validate_pairwise_selection(selection, variant_ids, passing_variant_ids)

    warnings = []
    if not passing_variant_ids:
        warnings.append(
            "No generated variant preserved every required plan resource; "
            "the selector returned the best structurally unsuccessful variant."
        )
    return PlanFidelitySelectionResult(
        assessments=fidelity.assessments,
        passing_variant_ids=passing_variant_ids,
        selection=selection,
        selected_variant_id=selection.selected_variant_id,
        prompts=prompts,
        raw_responses=raw_responses,
        usage=usage,
        warnings=warnings,
        variants=variants,
    )


def dry_run_plan_fidelity_selection(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    required_resources: list[str],
    intended_plan: dict[str, Any],
    variants: list[FidelityVariant],
) -> PlanFidelitySelectionResult:
    """Build the shared evaluation prompts with coherent deterministic fixtures."""
    variant_ids = validate_variants(variants)

    def resource(code: str) -> ResourceFidelityOutput:
        applicable = code in required_resources
        return ResourceFidelityOutput(
            applicable=applicable,
            preserved=True if applicable else None,
            rationale=(
                "De vereiste bron is functioneel behouden."
                if applicable
                else "Deze bron valt buiten de conditie."
            ),
        )

    assessments = [
        PlanFidelityAssessmentOutput(
            variant_id=variant_id,
            realized_script_a="De instelling helpt de bezoeker.",
            realized_script_b="De instelling gebruikt de bezoeker.",
            realized_opposition_axis="geven/nemen",
            script_opposition=resource("SO"),
            logical_mechanism=resource("LM"),
            situation=resource("SI"),
            target=resource("TA"),
            narrative_strategy=resource("NS"),
            language=resource("LA"),
            setup_dominance=True,
            latent_script_b=True,
            shared_cues_realized=True,
            switch_trigger_realized=True,
            retrospective_reinterpretation=True,
            unplanned_opposition=False,
            rationale="De variant bewaart het vereiste plan.",
        )
        for variant_id in variant_ids
    ]
    passing_variant_ids = list(variant_ids)
    fidelity_prompt = build_plan_fidelity_prompt(
        spec,
        request,
        required_resources=required_resources,
        intended_plan=intended_plan,
        variants=variants,
    )
    selection_prompt = build_pairwise_selection_prompt(
        spec,
        request,
        required_resources=required_resources,
        variants=variants,
        assessments=assessments,
        passing_variant_ids=passing_variant_ids,
    )
    comparisons = [
        PairwiseComparisonOutput(
            left_variant_id=left,
            right_variant_id=right,
            winner_variant_id=left,
            rationale="De linkervariant bewaart het plan iets scherper.",
        )
        for left, right in itertools.combinations(variant_ids, 2)
    ]
    selection = PairwiseSelectionOutput(
        comparisons=comparisons,
        selected_variant_id="V1",
        rationale="V1 realiseert het vereiste plan het sterkst.",
    )
    return PlanFidelitySelectionResult(
        assessments=assessments,
        passing_variant_ids=passing_variant_ids,
        selection=selection,
        selected_variant_id="V1",
        prompts=[
            ("plan_fidelity", fidelity_prompt),
            ("pairwise_selection", selection_prompt),
        ],
        raw_responses={},
        usage=None,
        warnings=[],
        variants=variants,
    )
