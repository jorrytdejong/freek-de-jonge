from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, TypeVar

from pydantic import BaseModel

from core.categories import category_defaults, normalize_category
from core.category_script_opposition_examples import load_category_script_opposition_examples
from core.freek_category_script_opposition_examples import load_freek_category_script_opposition_examples
from core.llm import add_usage, generate_structured
from core.joke_length import joke_length_instruction, joke_sentence_count, joke_word_count, validate_joke_length
from core.prompting import build_generation_prompt
from core.schemas import (
    CriticOutput,
    JokeRequest,
    JokeVariant,
    JokeVariantOutput,
    JokeVariantsOutput,
    JokeRepairVariantsOutput,
    JokeRepairVariantOutput,
    PipelineResult,
    PipelineSpec,
    ScriptAOutput,
    ScriptBCandidatesOutput,
    ScriptBCandidate,
    ScriptBSelectionOutput,
    SemanticPlan,
    SemanticPlanOutput,
    UsageSummary,
)
from core.styles import c_pipeline_style_guidance, style_guidance
from pipelines import plan_fidelity
from pipelines import shared_script_opposition as shared_so

StageOutput = TypeVar("StageOutput", bound=BaseModel)


def _structured_prompt(task: str, payload: dict[str, Any]) -> str:
    """Combine stage instructions and input into one prompt.

    Args:
        task: Instructions for the current pipeline stage.
        payload: Structured input supplied to the stage.

    Returns:
        Prompt containing the instructions and serialized payload.
    """
    return f"{task}\n\nInput:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\nReturn the requested structured fields."


def _base_payload(spec: PipelineSpec, request: JokeRequest) -> dict[str, Any]:
    """Build shared input with condition-specific examples.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.

    Returns:
        Base stage payload for the selected condition.
    """
    payload: dict[str, Any] = {
        "topic": request.topic,
    }
    if spec.style_mode == "freek":
        payload["style_guidance"] = (
            c_pipeline_style_guidance(spec.style_mode)
            if spec.code == "C2"
            else style_guidance(spec.style_mode)
        )
    if spec.code == "D1":
        category = normalize_category(request.category)
        examples = load_category_script_opposition_examples(category)
        if examples:
            payload["category_script_opposition_examples"] = examples
            payload["category_script_opposition_example_instruction"] = (
                "Use these examples as context for how the selected humor category can map to script opposition. "
                "Do not copy wording, names, or specific situations."
            )
    if spec.code == "D2":
        category = normalize_category(request.category)
        examples = load_freek_category_script_opposition_examples(category)
        if examples:
            payload["freek_category_script_opposition_examples"] = examples
            payload["freek_category_script_opposition_example_instruction"] = (
                "Use these Freek de Jonge examples as context for how the selected humor category can map to "
                "script opposition in Freek-style cabaret. Do not copy wording, names, or specific situations."
            )
    return payload


def _serialized_plan(spec: PipelineSpec, plan: SemanticPlan) -> dict[str, Any]:
    """Serialize a plan without leaking category fields into C1/C2 prompts."""
    payload = asdict(plan)
    if spec.family != "category_script":
        payload.pop("category", None)
    return payload


def _stage_call(
    prompt: str,
    *,
    stage: str,
    model: str,
    response_model: type[StageOutput],
) -> tuple[StageOutput, str, UsageSummary]:
    """Run one structured stage with contextualized errors.

    Args:
        prompt: Complete stage prompt.
        stage: Stage name used in error messages.
        model: OpenAI model identifier.
        response_model: Pydantic output type for the stage.

    Returns:
        Parsed stage output, raw response text, and token usage.

    Raises:
        ValueError: If structured generation fails.
    """
    try:
        parsed, raw, usage = generate_structured(prompt, response_model, model=model)
    except ValueError as exc:
        raise ValueError(f"{stage} structured output failed: {exc}") from exc
    return parsed, raw, usage


def _validate_script_a_structure(script_a: ScriptAOutput) -> None:
    """Require the structured situation requested by the C/D Script A stage."""
    missing = []
    for field_name in ("apparent_goal", "expected_outcome"):
        if not getattr(script_a, field_name):
            missing.append(field_name)
    for field_name in (
        "participants_and_roles",
        "preconditions",
        "expected_actions",
        "expected_propositions",
    ):
        if not getattr(script_a, field_name):
            missing.append(field_name)
    if missing:
        raise ValueError(
            "script_a omitted required structured-script fields: "
            + ", ".join(missing)
        )


def _validate_script_b_candidate_ids(candidates: list[ScriptBCandidate]) -> None:
    """Require one immutable candidate for every ID from B1 through B4."""
    identifiers = [candidate.candidate_id for candidate in candidates]
    expected = {f"B{index}" for index in range(1, 5)}
    if len(identifiers) != 4 or set(identifiers) != expected:
        raise ValueError(
            "script_b_candidates must use exactly B1 through B4; "
            f"received {identifiers}."
        )


def build_script_a_prompt(spec: PipelineSpec, request: JokeRequest) -> str:
    """Build the prompt that identifies the normal setup script.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.

    Returns:
        Script A stage prompt.
    """
    payload = _base_payload(spec, request)
    return _structured_prompt(
        """
You design jokes using script opposition.
Always write creative fields in Dutch.

Stage 1: Script A.
Given a topic and any supplied style guidance:
1. identify the participants and their default roles
2. identify the apparent goal, its normal preconditions, and expected actions
3. identify the expected outcome and 2-5 concrete audience assumptions
4. compress this structured situation into one concise script_a

Script A must be the most normal, common-sense reading of the topic. A script is a
structured situation, not merely an attitude or opinion.
Return script_a, participants_and_roles, apparent_goal, preconditions,
expected_actions, expected_outcome, and expected_propositions.
""".strip(),
        payload,
    )


def build_script_b_candidates_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    script_a: str,
    script_a_structure: dict[str, Any] | None = None,
) -> str:
    """Build the prompt that proposes opposing second scripts.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        script_a: Normal setup interpretation from the previous stage.

    Returns:
        Script B candidate-generation prompt.
    """
    payload = {
        **_base_payload(spec, request),
        "script_a": script_a,
    }
    if script_a_structure:
        payload["script_a_structure"] = script_a_structure
    category_instruction = ""
    if spec.family == "category_script":
        category = normalize_category(request.category)
        payload["category"] = category
        payload["category_context"] = category_defaults(category)
        category_instruction = "\nIf a humor category is provided, use it to shape the kind of opposition.\n"
    return _structured_prompt(
        f"""
You construct candidate Script B interpretations under SSTH/GTVH.
Always write creative fields in Dutch.

Stage 2: Script B candidates.
Generate exactly 4 candidates with candidate_id B1 through B4.
A script is a structured situation with participants, roles, a goal, preconditions,
actions, and an outcome. Script B must be a coherent alternative situation, not merely
a surprising opinion, metaphor, exaggeration, or darker description of Script A.

For every candidate:
- state a complete and recognizable script_b, including roles_b and goal_b
- identify one dominant opposition_axis; the scripts must be locally incompatible on
  that axis but need not be literal logical negations
- identify the Script A expectation that is opposed or functionally reversed
- specify how roles change in role_remapping
- give shared_cues that can already occur under both readings
- distinguish the late switch_trigger from those earlier shared cues
- propose a hinge_event that is anomalous, useless, or inappropriate under Script A
- explain why the same hinge event is purposeful or appropriate under Script B in
  anomaly_under_a and resolution_under_b
- state the precise logical_mechanism that makes the switch quickly resolvable
- prefer a functional reversal in which one condition blocks Script A's goal but
  enables Script B's goal
- keep Script A dominant until the switch trigger and keep Script B plausible

Clean axes may include actual/non-actual, normal/abnormal, possible/impossible,
good/bad, life/death, non-sex/sex, money/non-money, high-status/low-status,
public/private, or literal/social meaning. Do not write the completed joke yet.
{category_instruction}
Return candidate_id, script_b, opposition_axis, opposed_expectation, roles_b, goal_b,
role_remapping, shared_cues, switch_trigger, hinge_event, anomaly_under_a,
resolution_under_b, and logical_mechanism for each candidate.
""".strip(),
        payload,
    )


def build_script_b_ranker_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    script_a: str,
    candidates: list[ScriptBCandidate],
) -> str:
    """Build the prompt that selects the strongest opposing script.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        script_a: Normal setup interpretation.
        candidates: Candidate opposing interpretations to rank.

    Returns:
        Script B ranking prompt.
    """
    payload = {
        **_base_payload(spec, request),
        "script_a": script_a,
        "candidates": [asdict(candidate) for candidate in candidates],
    }
    payoff_criterion = "- best payoff potential"
    if spec.family == "category_script":
        payload["category"] = normalize_category(request.category)
        payoff_criterion = "- best payoff potential for the requested style and category"
    return _structured_prompt(
        f"""
You rank candidate second readings for a joke.
Always write creative fields in Dutch.

Stage 3: Script B ranking.
Select the single best script_b candidate based on:
- clearest and most economical opposition to script_a
- strongest single opposition axis
- strongest setup test: without the trigger, a normal reader chooses Script A
- strongest switch test: the hinge event creates a specific anomaly under Script A
- strongest retrospective test: Script B resolves that anomaly and reinterprets an
  earlier cue rather than appending unrelated surprise
- strongest functional reversal when available
- clearest separation between shared cues and the late switch trigger
- most recognizable Script B in its own right
{payoff_criterion}

Return selected_candidate_id, the exact unchanged script_b, and rationale.
""".strip(),
        payload,
    )


def build_plan_context_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    script_a: str,
    script_b: str,
    script_b_context: ScriptBCandidate | None = None,
) -> str:
    """Build the prompt that completes the semantic joke plan.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        script_a: Normal setup interpretation.
        script_b: Selected opposing interpretation.

    Returns:
        Semantic plan stage prompt.
    """
    payload = {
        **_base_payload(spec, request),
        "script_a": script_a,
        "script_b": script_b,
    }
    if script_b_context is not None:
        payload["script_b_context"] = asdict(script_b_context)
    request_inputs = "request, script_a, and selected script_b"
    if spec.family == "category_script":
        category = normalize_category(request.category)
        payload["category"] = category
        payload["category_context"] = category_defaults(category)
        request_inputs = "request, script_a, selected script_b, and category"
    return _structured_prompt(
        f"""
You finalize a semantic joke plan from a chosen script opposition.
Always write creative fields in Dutch.

Stage 4: Semantic plan.
Given the {request_inputs}:
1. name the opposition type
2. list the earlier shared cues that remain interpretable under both scripts
3. identify the late trigger that makes Script B preferred
4. state the hinge event, its anomaly under Script A, and its resolution under Script B
5. state any role remapping between the scripts
6. define the setup goal and punch goal

Do not collapse shared cues and switch trigger into one vague anchor. The trigger may be
a word, phrase, action, role, object, condition, or situation. Keep every field concise.
Return opposition_type, shared_cues, trigger, hinge_event, anomaly_under_a,
resolution_under_b, role_remapping, setup_goal, and punch_goal.
""".strip(),
        payload,
    )


def build_generator_prompt(spec: PipelineSpec, request: JokeRequest, plan: SemanticPlan) -> str:
    """Build the prompt that generates variants from a plan.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        plan: Completed semantic joke plan.

    Returns:
        Joke-variant generation prompt.
    """
    payload = {
        **_base_payload(spec, request),
        "plan": _serialized_plan(spec, plan),
    }
    return _structured_prompt(
        f"""
You write jokes from a semantic plan.
Always write all joke variants in Dutch.

Treat the topic as broad inspiration rather than a literal assignment. The joke
may use an adjacent situation and need not mention the topic explicitly.

Stage 5: Joke generation.
Write three distinct joke variants that preserve the same script opposition.
Write each as a joke intended to be spoken aloud by one comedian to a Dutch audience.
Each variant must have a recognizable setup, a clear turn or misdirection, and a
final punchline that creates the laugh.
Let the setup feel socially normal and recognizable so Script A is dominant but not exclusive.
Plant one or two shared cues that appear ordinary under Script A and gain a second
function under Script B. Introduce the smallest possible switch trigger late.
The punch must make a preceding action or condition anomalous under Script A but
immediately purposeful under Script B. After the punch, at least one earlier detail
must acquire a new role or meaning.
Prefer a clear semantic reversal over shock value.
The second reading should feel surprisingly true, not merely fictional.
Do not explain Script B or name the opposition. {joke_length_instruction()}
Do not write an observation, explanation, summary, moral, slogan, or policy statement.
Do not end with an abstract conclusion; the final sentence must be the punchline.
Mentally read each variant aloud and rewrite it if it does not sound performable.
End on the strongest word or phrase.
Return structured variants with text and angle fields.
""".strip(),
        payload,
    )


def build_critic_prompt(
    spec: PipelineSpec,
    request: JokeRequest,
    plan: SemanticPlan,
    variants: list[JokeVariant],
) -> str:
    """Build the prompt that selects the strongest variant.

    Args:
        spec: Experiment condition specification.
        request: User-supplied joke request.
        plan: Completed semantic joke plan.
        variants: Generated joke variants to evaluate.

    Returns:
        Critic selection prompt.
    """
    payload = {
        **_base_payload(spec, request),
        "plan": _serialized_plan(spec, plan),
        "variants": [asdict(variant) for variant in variants],
    }
    return _structured_prompt(
        """
You select the best joke.
The winning joke must remain in Dutch.

Stage 6: Critic selection.
Pick the variant with:
- the clearest setup
- the strongest late switch trigger
- the clearest anomaly under Script A and resolution under Script B
- the strongest retrospective reinterpretation of an earlier cue
- no unrelated surprise appended only in the punchline
- the best fit to the requested style mode
- the strongest realization of the semantic plan

Return the text and angle fields.
The text must exactly match one generated variant.
""".strip(),
        payload,
    )


def _shared_candidate(candidate) -> ScriptBCandidate:
    """Convert the shared C/E candidate without adding an E-only Logical Mechanism."""
    return ScriptBCandidate(
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


def _shared_c_plan(spec: PipelineSpec, shared) -> SemanticPlan:
    """Map the selected common SO directly into C's SO-only realization plan."""
    selected = shared.selected
    return SemanticPlan(
        setup_script=shared.audience.script_a,
        opposing_script=selected.script_b,
        opposition_type=selected.opposition_axis,
        trigger=selected.switch_trigger,
        setup_goal="Maak Script A dominant met de gedeelde cues en normale rollen.",
        punch_goal="Activeer het geselecteerde Script B laat en herinterpreteer eerder materiaal.",
        shared_cues=selected.shared_cues,
        hinge_event=selected.hinge_event,
        anomaly_under_a=selected.anomaly_under_a,
        resolution_under_b=selected.resolution_under_b,
        role_remapping=selected.role_remapping,
        style_mode=spec.style_mode,
    )


def _shared_so_metadata(shared) -> dict[str, Any]:
    return {
        "audience_expectation": shared.audience.model_dump(),
        "candidates": [candidate.model_dump() for candidate in shared.candidates],
        "candidate_attempts": shared.candidate_attempts,
        "theory_gate": [assessment.model_dump() for assessment in shared.assessments],
        "theory_gate_attempts": shared.theory_gate_attempts,
        "approved_candidate_ids": [candidate.candidate_id for candidate in shared.approved],
        "selected_candidate_id": shared.selected.candidate_id,
    }


def _shared_c_intended_plan(shared, plan: SemanticPlan) -> dict[str, Any]:
    return {
        "script_a": shared.audience.model_dump(),
        "selected_script_opposition": shared.selected.model_dump(),
        "so_realization_plan": asdict(plan),
    }


def _dry_run_shared_c_pipeline(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    shared_result: shared_so.SharedScriptOppositionResult | None = None,
) -> PipelineResult:
    shared = shared_result or shared_so.dry_run_shared_script_opposition(spec, request)
    plan = _shared_c_plan(spec, shared)
    fidelity_variants = [
        plan_fidelity.FidelityVariant(
            variant_id=f"V{index}",
            text=f"[dry run C variant {index}]",
            angle="dry run",
        )
        for index in range(1, 4)
    ]
    evaluation = plan_fidelity.dry_run_plan_fidelity_selection(
        spec,
        request,
        required_resources=["SO"],
        intended_plan=_shared_c_intended_plan(shared, plan),
        variants=fidelity_variants,
    )
    prompts = [
        *shared.prompts,
        ("variants", build_generator_prompt(spec, request, plan)),
        *evaluation.prompts,
    ]
    combined_prompt = "\n\n---\n\n".join(
        f"## {stage}\n{prompt}" for stage, prompt in prompts
    )
    joke = fidelity_variants[0].text
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=spec.name,
        request=request,
        prompt=combined_prompt,
        joke=joke,
        semantic_plan=plan,
        raw_response=combined_prompt,
        script_b_candidates=[_shared_candidate(candidate) for candidate in shared.candidates],
        script_b_rationale=shared.selection_rationale,
        variants=[
            JokeVariant(text=variant.text, angle=variant.angle)
            for variant in fidelity_variants
        ],
        metadata={
            "family": spec.family,
            "style_mode": spec.style_mode,
            "stages": [stage for stage, _ in prompts],
            "shared_so_trace": _shared_so_metadata(shared),
            "plan_fidelity": [
                assessment.model_dump() for assessment in evaluation.assessments
            ],
            "passing_variant_ids": evaluation.passing_variant_ids,
            "joke_repaired": evaluation.repaired,
            "selected_variant_id": evaluation.selected_variant_id,
        },
    )


def _run_shared_c_pipeline(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    model: str,
    shared_result: shared_so.SharedScriptOppositionResult | None = None,
) -> PipelineResult:
    shared = shared_result or shared_so.run_shared_script_opposition(spec, request, model=model)
    plan = _shared_c_plan(spec, shared)
    raw_responses = dict(shared.raw_responses)
    usage = shared.usage

    variants_payload, raw, stage_usage = _stage_call(
        build_generator_prompt(spec, request, plan),
        stage="variants",
        model=model,
        response_model=JokeVariantsOutput,
    )
    raw_responses["variants"] = raw
    usage = add_usage(usage, stage_usage)
    variants = [
        JokeVariant(text=variant.text, angle=variant.angle)
        for variant in variants_payload.variants
    ]
    length_repair_prompt: str | None = None
    if len(variants) != 3:
        raise ValueError(f"C generation must return exactly three variants; received {len(variants)}.")
    if any(
        not 20 <= joke_word_count(variant.text) <= 45
        or joke_sentence_count(variant.text) > 3
        for variant in variants
    ):
        repair_variants = [
            plan_fidelity.FidelityVariant(
                variant_id=f"V{index}", text=variant.text, angle=variant.angle
            )
            for index, variant in enumerate(variants, start=1)
        ]
        repair_prompt = plan_fidelity.build_length_repair_prompt(
            request,
            intended_plan=_shared_c_intended_plan(shared, plan),
            variants=repair_variants,
        )
        repaired_payload, repair_raw, repair_usage = _stage_call(
            repair_prompt,
            stage="length_repair",
            model=model,
            response_model=JokeRepairVariantsOutput,
        )
        length_repair_prompt = repair_prompt
        raw_responses["length_repair"] = repair_raw
        usage = add_usage(usage, repair_usage)
        repaired_by_id = {item.variant_id: item for item in repaired_payload.variants}
        if set(repaired_by_id) != {"V1", "V2", "V3"}:
            raise ValueError("Length repair must return exactly V1, V2, and V3.")
        variants = [
            JokeVariant(
                text=repaired_by_id[f"V{index}"].text,
                angle=repaired_by_id[f"V{index}"].angle,
            )
            for index in range(1, 4)
        ]
        for index, variant in enumerate(variants, start=1):
            validate_joke_length(variant.text, label=f"Repaired variant V{index}")
    fidelity_variants = [
        plan_fidelity.FidelityVariant(
            variant_id=f"V{index}",
            text=variant.text,
            angle=variant.angle,
        )
        for index, variant in enumerate(variants, start=1)
    ]
    evaluation = plan_fidelity.run_plan_fidelity_selection(
        spec,
        request,
        model=model,
        required_resources=["SO"],
        intended_plan=_shared_c_intended_plan(shared, plan),
        variants=fidelity_variants,
    )
    raw_responses.update(evaluation.raw_responses)
    usage = add_usage(usage, evaluation.usage)
    evaluated_variants = evaluation.variants
    variants_by_id = {
        variant.variant_id: JokeVariant(text=variant.text, angle=variant.angle)
        for variant in evaluated_variants
    }
    best = variants_by_id[evaluation.selected_variant_id]

    prompts = [
        *shared.prompts,
        ("variants", build_generator_prompt(spec, request, plan)),
        *(([("length_repair", length_repair_prompt)] if length_repair_prompt else [])),
        *evaluation.prompts,
    ]
    combined_prompt = "\n\n---\n\n".join(
        f"## {stage}\n{prompt}" for stage, prompt in prompts
    )
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=spec.name,
        request=request,
        prompt=combined_prompt,
        joke=best.text,
        semantic_plan=plan,
        raw_response=json.dumps(raw_responses, ensure_ascii=False, indent=2),
        warnings=evaluation.warnings,
        script_b_candidates=[_shared_candidate(candidate) for candidate in shared.candidates],
        script_b_rationale=shared.selection_rationale,
        variants=[JokeVariant(text=item.text, angle=item.angle) for item in evaluated_variants],
        usage=usage,
        metadata={
            "family": spec.family,
            "style_mode": spec.style_mode,
            "stages": list(raw_responses),
            "shared_so_trace": _shared_so_metadata(shared),
            "plan_fidelity": [
                {
                    **assessment.model_dump(),
                    "passes_required_plan": plan_fidelity.passes_required_plan(
                        assessment,
                        ["SO"],
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
    )


def dry_run_script_opposition_pipeline(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    shared_result: shared_so.SharedScriptOppositionResult | None = None,
) -> PipelineResult:
    """Build all staged prompts without making model calls.

    Args:
        spec: Script-opposition condition specification.
        request: User-supplied joke request.

    Returns:
        Dry-run result containing every constructed stage prompt.
    """
    if spec.family == "script_opposition":
        return _dry_run_shared_c_pipeline(spec, request, shared_result=shared_result)

    category = normalize_category(request.category) if spec.family == "category_script" else None
    defaults = category_defaults(category)
    script_a = defaults["setup_script"]
    script_a_structure = {
        "script_a": script_a,
        "participants_and_roles": [
            "een instelling als dienstverlener",
            "een bezoeker als ontvanger",
        ],
        "apparent_goal": "De bezoeker ontvangt een normale dienst.",
        "preconditions": ["De instelling is beschikbaar en behulpzaam."],
        "expected_actions": ["De instelling helpt de bezoeker."],
        "expected_outcome": "De bezoeker vertrekt geholpen.",
        "expected_propositions": [
            "De instelling geeft iets aan de bezoeker.",
            "De bezoeker houdt de controle.",
        ],
    }
    candidates = [
        ScriptBCandidate(
            candidate_id=f"B{index}",
            script_b=f"{defaults['opposing_script']} ({index}).",
            opposition_axis="geven/nemen",
            opposed_expectation="De instelling geeft iets aan de bezoeker.",
            roles_b=[
                "de instelling als ontvanger",
                "de bezoeker als middel",
            ],
            goal_b="De instelling ontvangt iets van de bezoeker.",
            role_remapping=[
                "de instelling: gever -> ontvanger",
                "de bezoeker: ontvanger -> middel",
            ],
            shared_cues=[defaults["trigger"]],
            switch_trigger="de bezoeker moet zichzelf inleveren",
            hinge_event="De bezoeker moet iets afstaan om geholpen te worden.",
            anomaly_under_a="De dienstverlening kost de bezoeker juist iets wezenlijks.",
            resolution_under_b="De instelling blijkt de werkelijke ontvanger.",
            logical_mechanism="omkering van gever en ontvanger",
        )
        for index in range(1, 5)
    ]
    selected_candidate = candidates[0]
    script_b = selected_candidate.script_b
    plan = SemanticPlan(
        category=category,
        setup_script=script_a,
        opposing_script=script_b,
        opposition_type=selected_candidate.opposition_axis,
        trigger=selected_candidate.switch_trigger,
        setup_goal="Activeer de normale verwachting dat de instelling helpt.",
        punch_goal="Onthul laat dat de instelling de werkelijke ontvanger is.",
        shared_cues=selected_candidate.shared_cues,
        hinge_event=selected_candidate.hinge_event,
        anomaly_under_a=selected_candidate.anomaly_under_a,
        resolution_under_b=selected_candidate.resolution_under_b,
        role_remapping=selected_candidate.role_remapping,
        style_mode=spec.style_mode,
    )
    prompts = [
        ("script_a", build_script_a_prompt(spec, request)),
        (
            "script_b_candidates",
            build_script_b_candidates_prompt(
                spec,
                request,
                script_a,
                script_a_structure,
            ),
        ),
        (
            "script_b_ranker",
            build_script_b_ranker_prompt(spec, request, script_a, candidates),
        ),
        (
            "plan_context",
            build_plan_context_prompt(
                spec,
                request,
                script_a,
                script_b,
                selected_candidate,
            ),
        ),
        ("variants", build_generator_prompt(spec, request, plan)),
        ("critic", build_critic_prompt(spec, request, plan, [JokeVariant(text="[dry run variant]", angle="dry run")])),
    ]
    prompt = "\n\n---\n\n".join(f"## {stage}\n{stage_prompt}" for stage, stage_prompt in prompts)
    variant = JokeVariant(text="[dry run] Staged script-opposition prompts built successfully.", angle="dry run")
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=spec.name,
        request=request,
        prompt=prompt,
        joke=variant.text,
        semantic_plan=plan,
        raw_response=prompt,
        script_b_candidates=candidates,
        script_b_rationale="Dry run used category/default script-opposition placeholders.",
        variants=[variant],
        metadata={"family": spec.family, "style_mode": spec.style_mode, "stages": [stage for stage, _ in prompts]},
    )


def run_script_opposition_pipeline(
    spec: PipelineSpec,
    request: JokeRequest,
    *,
    model: str,
    shared_result: shared_so.SharedScriptOppositionResult | None = None,
) -> PipelineResult:
    """Run the six-stage script-opposition pipeline.

    Args:
        spec: Script-opposition condition specification.
        request: User-supplied joke request.
        model: OpenAI model identifier.

    Returns:
        Generated joke, semantic trace, variants, and usage metadata.
    """
    if spec.family == "script_opposition":
        return _run_shared_c_pipeline(
            spec,
            request,
            model=model,
            shared_result=shared_result,
        )

    raw_responses: dict[str, str] = {}
    usage: UsageSummary | None = None

    script_a_payload, raw, stage_usage = _stage_call(
        build_script_a_prompt(spec, request),
        stage="script_a",
        model=model,
        response_model=ScriptAOutput,
    )
    raw_responses["script_a"] = raw
    usage = add_usage(usage, stage_usage)
    _validate_script_a_structure(script_a_payload)
    script_a = script_a_payload.script_a

    candidates_payload, raw, stage_usage = _stage_call(
        build_script_b_candidates_prompt(
            spec,
            request,
            script_a,
            script_a_payload.model_dump(exclude_none=True),
        ),
        stage="script_b_candidates",
        model=model,
        response_model=ScriptBCandidatesOutput,
    )
    raw_responses["script_b_candidates"] = raw
    usage = add_usage(usage, stage_usage)
    candidates = [
        ScriptBCandidate(**candidate.model_dump())
        for candidate in candidates_payload.candidates
    ]
    _validate_script_b_candidate_ids(candidates)

    selection_payload, raw, stage_usage = _stage_call(
        build_script_b_ranker_prompt(spec, request, script_a, candidates),
        stage="script_b_ranker",
        model=model,
        response_model=ScriptBSelectionOutput,
    )
    raw_responses["script_b_ranker"] = raw
    usage = add_usage(usage, stage_usage)
    candidates_by_id = {
        candidate.candidate_id: candidate for candidate in candidates
    }
    if selection_payload.selected_candidate_id not in candidates_by_id:
        raise ValueError(
            "script_b_ranker selected an unknown candidate ID: "
            f"{selection_payload.selected_candidate_id!r}."
        )
    selected_candidate = candidates_by_id[selection_payload.selected_candidate_id]
    if selection_payload.script_b != selected_candidate.script_b:
        raise ValueError(
            "script_b_ranker must return the selected candidate's exact unchanged script_b."
        )
    script_b = selected_candidate.script_b
    rationale = selection_payload.rationale

    plan_payload, raw, stage_usage = _stage_call(
        build_plan_context_prompt(
            spec,
            request,
            script_a,
            script_b,
            selected_candidate,
        ),
        stage="plan_context",
        model=model,
        response_model=SemanticPlanOutput,
    )
    raw_responses["plan_context"] = raw
    usage = add_usage(usage, stage_usage)
    plan = SemanticPlan(
        category=normalize_category(request.category) if spec.family == "category_script" else None,
        setup_script=script_a,
        opposing_script=script_b,
        opposition_type=plan_payload.opposition_type,
        trigger=plan_payload.trigger,
        setup_goal=plan_payload.setup_goal,
        punch_goal=plan_payload.punch_goal,
        shared_cues=plan_payload.shared_cues,
        hinge_event=plan_payload.hinge_event,
        anomaly_under_a=plan_payload.anomaly_under_a,
        resolution_under_b=plan_payload.resolution_under_b,
        role_remapping=plan_payload.role_remapping,
        style_mode=spec.style_mode,
    )

    variants_payload, raw, stage_usage = _stage_call(
        build_generator_prompt(spec, request, plan),
        stage="variants",
        model=model,
        response_model=JokeVariantsOutput,
    )
    raw_responses["variants"] = raw
    usage = add_usage(usage, stage_usage)
    variants = [
        JokeVariant(text=variant.text, angle=variant.angle)
        for variant in variants_payload.variants
    ]
    length_repair_prompt: str | None = None
    if any(
        not 20 <= joke_word_count(variant.text) <= 45
        or joke_sentence_count(variant.text) > 3
        for variant in variants
    ):
        repair_variants = [
            plan_fidelity.FidelityVariant(
                variant_id=f"V{index}", text=variant.text, angle=variant.angle
            )
            for index, variant in enumerate(variants, start=1)
        ]
        length_repair_prompt = plan_fidelity.build_length_repair_prompt(
            request,
            intended_plan={"semantic_plan": asdict(plan)},
            variants=repair_variants,
        )
        repaired_payload, repair_raw, repair_usage = _stage_call(
            length_repair_prompt,
            stage="length_repair",
            model=model,
            response_model=JokeRepairVariantsOutput,
        )
        repaired_by_id = {item.variant_id: item for item in repaired_payload.variants}
        if set(repaired_by_id) != {"V1", "V2", "V3"}:
            raise ValueError("Length repair must return exactly V1, V2, and V3.")
        variants = [
            JokeVariant(
                text=repaired_by_id[f"V{index}"].text,
                angle=repaired_by_id[f"V{index}"].angle,
            )
            for index in range(1, 4)
        ]
        raw_responses["length_repair"] = repair_raw
        usage = add_usage(usage, repair_usage)
    for index, variant in enumerate(variants, start=1):
        validate_joke_length(variant.text, label=f"Variant V{index}")

    critic_payload, raw, stage_usage = _stage_call(
        build_critic_prompt(spec, request, plan, variants),
        stage="critic",
        model=model,
        response_model=CriticOutput,
    )
    raw_responses["critic"] = raw
    usage = add_usage(usage, stage_usage)
    best = next(
        (variant for variant in variants if variant.text == critic_payload.text),
        JokeVariant(text=critic_payload.text, angle=critic_payload.angle),
    )
    validate_joke_length(best.text, label=f"{spec.code} selected joke")

    prompt = "\n\n---\n\n".join(
        [
            f"## script_a\n{build_script_a_prompt(spec, request)}",
            "## script_b_candidates\n"
            + build_script_b_candidates_prompt(
                spec,
                request,
                script_a,
                script_a_payload.model_dump(exclude_none=True),
            ),
            f"## script_b_ranker\n{build_script_b_ranker_prompt(spec, request, script_a, candidates)}",
            f"## plan_context\n{build_plan_context_prompt(spec, request, script_a, script_b, selected_candidate)}",
            f"## variants\n{build_generator_prompt(spec, request, plan)}",
            *([f"## length_repair\n{length_repair_prompt}"] if length_repair_prompt else []),
            f"## critic\n{build_critic_prompt(spec, request, plan, variants)}",
        ]
    )
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=spec.name,
        request=request,
        prompt=prompt,
        joke=best.text,
        semantic_plan=plan,
        raw_response=json.dumps(raw_responses, ensure_ascii=False, indent=2),
        script_b_candidates=candidates,
        script_b_rationale=rationale,
        variants=variants,
        usage=usage,
        metadata={"family": spec.family, "style_mode": spec.style_mode, "stages": list(raw_responses)},
    )


def run_direct_condition(spec: PipelineSpec, request: JokeRequest, *, model: str, dry_run: bool) -> PipelineResult:
    """Run or dry-run a direct generation condition.

    Args:
        spec: Direct-generation condition specification.
        request: User-supplied joke request.
        model: OpenAI model identifier.
        dry_run: Whether to build the prompt without a model call.

    Returns:
        Direct-generation or dry-run pipeline result.
    """
    plan = SemanticPlan(
        category=normalize_category(request.category) if spec.family == "category" else None,
        trigger=category_defaults(request.category)["trigger"] if spec.family == "category" else None,
        style_mode=spec.style_mode,
    )
    prompt = build_generation_prompt(spec, request, plan)
    if dry_run:
        joke = "[dry run] Prompt built successfully; no joke was generated."
        angle = "direct generation"
        raw_response = joke
        usage = None
    else:
        parsed, raw_response, usage = generate_structured(prompt, JokeVariantOutput, model=model)
        joke = parsed.text
        angle = parsed.angle
        if not 20 <= joke_word_count(joke) <= 45 or joke_sentence_count(joke) > 3:
            repair_prompt = plan_fidelity.build_single_length_repair_prompt(
                request,
                intended_plan={"pipeline": spec.code, "style_mode": spec.style_mode},
                text=joke,
                angle=angle,
            )
            repaired, repair_raw, repair_usage = generate_structured(
                repair_prompt,
                JokeRepairVariantOutput,
                model=model,
            )
            joke = repaired.text
            angle = repaired.angle
            raw_response = json.dumps(
                {"generation": raw_response, "length_repair": repair_raw},
                ensure_ascii=False,
                indent=2,
            )
            usage = add_usage(usage, repair_usage)
            prompt = f"{prompt}\n\n---\n\n## length_repair\n{repair_prompt}"
        validate_joke_length(joke, label=f"{spec.code} joke")
    variant = JokeVariant(text=joke, angle=angle)
    return PipelineResult(
        pipeline_code=spec.code,
        pipeline_name=spec.name,
        request=request,
        prompt=prompt,
        joke=joke,
        semantic_plan=plan,
        raw_response=raw_response,
        variants=[variant],
        usage=usage,
        metadata={"family": spec.family, "style_mode": spec.style_mode, "stages": ["direct_generation"]},
    )
