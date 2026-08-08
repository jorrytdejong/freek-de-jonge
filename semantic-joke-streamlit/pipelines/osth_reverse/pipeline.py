from __future__ import annotations

from time import perf_counter
from typing import TypeVar

from openai import OpenAI

from core.llm import require_client
from core.pipeline import PipelineDefinition
from core.pricing import active_model
from core.usage import summarize_usage, usage_from_response
from pipelines.osth_reverse.models import (
    ConstraintPlanInput,
    DiscoursePlanInput,
    DiscourseTMR,
    DraftJokeInput,
    FinalOSTHAnalysis,
    GenerationRequest,
    IncongruityAnalysis,
    IncongruityTargetInput,
    JokeGenerationResult,
    JokeLength,
    JokeMechanismVerification,
    LexiconOntologyPlan,
    LexiconOntologyPlanInput,
    OppositionTargetInput,
    OppositionType,
    ScriptAnalysis,
    ScriptOppositionAnalysis,
    ScriptTargetInput,
    SemanticConstraintBatch,
    StrictModel,
    SurfacePlanInput,
    SurfaceRealizationPlan,
    TMRHypothesesBatch,
    TMRPlanInput,
    TabooLevel,
    TargetFinalInput,
    VerificationInput,
    GeneratedJoke,
)
from pipelines.osth_reverse.prompts import (
    CONSTRAINT_PROMPT,
    DISCOURSE_PROMPT,
    DRAFT_PROMPT,
    INCONGRUITY_PROMPT,
    LEXICON_ONTOLOGY_PROMPT,
    OPPOSITION_PROMPT,
    SCRIPT_PROMPT,
    SURFACE_PLAN_PROMPT,
    TARGET_FINAL_PROMPT,
    TMR_PROMPT,
    VERIFY_PROMPT,
)
from schemas import JokeRequest, JokeResult, JokeVariant, ScriptBCandidate, SemanticPlan, UsageSummary


PIPELINE_ID = "osth_reverse"
PIPELINE_NAME = "OStH Reverse Pipeline"
PIPELINE_DESCRIPTION = "Notebook-inspired reverse-OStH generation: target analysis, opposition, TMR plans, constraints, surface realization, draft, and verification."

T = TypeVar("T", bound=StrictModel)


def parse_as(client: OpenAI, model_cls: type[T], system_prompt: str, payload: StrictModel | str) -> tuple[T, UsageSummary | None]:
    user_payload = payload if isinstance(payload, str) else payload.model_dump_json(indent=2)
    response = client.responses.parse(
        model=active_model(),
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
        text_format=model_cls,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("The model did not return a parsed structured output.")
    return parsed, usage_from_response(response)


def target_length_from_request(request: JokeRequest) -> JokeLength:
    if request.format == "one_liner":
        return JokeLength.one_liner
    if request.format == "short":
        return JokeLength.short_dialogue
    return JokeLength.short_anecdote


def generation_request_from_joke_request(request: JokeRequest) -> GenerationRequest:
    requirements = ["Schrijf de uiteindelijke grap in het Nederlands.", *request.constraints]
    return GenerationRequest(
        topic=request.topic,
        audience_context=request.audience,
        desired_tone=request.voice,
        taboo_level=TabooLevel.clean,
        target_length=target_length_from_request(request),
        first_script_hint=None,
        second_script_hint=None,
        desired_opposition=None,
        forbidden_content=[],
        additional_requirements=requirements,
    )


def design_intended_final_analysis(
    client: OpenAI,
    request: GenerationRequest,
    usages: list[UsageSummary],
    prior_revision_feedback: list[str] | None = None,
) -> FinalOSTHAnalysis:
    payload = TargetFinalInput(request=request, prior_revision_feedback=prior_revision_feedback or [])
    result, usage = parse_as(client, FinalOSTHAnalysis, TARGET_FINAL_PROMPT, payload)
    if usage is not None:
        usages.append(usage)
    return result


def design_target_opposition(
    client: OpenAI,
    request: GenerationRequest,
    intended_final_analysis: FinalOSTHAnalysis,
    usages: list[UsageSummary],
) -> ScriptOppositionAnalysis:
    payload = OppositionTargetInput(request=request, intended_final_analysis=intended_final_analysis)
    result, usage = parse_as(client, ScriptOppositionAnalysis, OPPOSITION_PROMPT, payload)
    if usage is not None:
        usages.append(usage)
    return result


def design_target_incongruity(
    client: OpenAI,
    request: GenerationRequest,
    intended_final_analysis: FinalOSTHAnalysis,
    target_opposition: ScriptOppositionAnalysis,
    usages: list[UsageSummary],
) -> IncongruityAnalysis:
    payload = IncongruityTargetInput(
        request=request,
        intended_final_analysis=intended_final_analysis,
        target_opposition=target_opposition,
    )
    result, usage = parse_as(client, IncongruityAnalysis, INCONGRUITY_PROMPT, payload)
    if usage is not None:
        usages.append(usage)
    return result


def design_scripts(
    client: OpenAI,
    request: GenerationRequest,
    intended_final_analysis: FinalOSTHAnalysis,
    target_opposition: ScriptOppositionAnalysis,
    target_incongruity: IncongruityAnalysis,
    usages: list[UsageSummary],
) -> ScriptAnalysis:
    payload = ScriptTargetInput(
        request=request,
        intended_final_analysis=intended_final_analysis,
        target_opposition=target_opposition,
        target_incongruity=target_incongruity,
    )
    result, usage = parse_as(client, ScriptAnalysis, SCRIPT_PROMPT, payload)
    if usage is not None:
        usages.append(usage)
    return result


def build_discourse_plan(
    client: OpenAI,
    request: GenerationRequest,
    intended_final_analysis: FinalOSTHAnalysis,
    target_opposition: ScriptOppositionAnalysis,
    target_incongruity: IncongruityAnalysis,
    scripts: ScriptAnalysis,
    usages: list[UsageSummary],
) -> DiscourseTMR:
    payload = DiscoursePlanInput(
        request=request,
        intended_final_analysis=intended_final_analysis,
        target_opposition=target_opposition,
        target_incongruity=target_incongruity,
        scripts=scripts,
    )
    result, usage = parse_as(client, DiscourseTMR, DISCOURSE_PROMPT, payload)
    if usage is not None:
        usages.append(usage)
    return result


def build_tmr_plan(
    client: OpenAI,
    request: GenerationRequest,
    discourse_plan: DiscourseTMR,
    scripts: ScriptAnalysis,
    target_incongruity: IncongruityAnalysis,
    usages: list[UsageSummary],
) -> TMRHypothesesBatch:
    payload = TMRPlanInput(
        request=request,
        discourse_plan=discourse_plan,
        scripts=scripts,
        target_incongruity=target_incongruity,
    )
    result, usage = parse_as(client, TMRHypothesesBatch, TMR_PROMPT, payload)
    if usage is not None:
        usages.append(usage)
    return result


def build_semantic_constraints(
    client: OpenAI,
    request: GenerationRequest,
    tmr_plan: TMRHypothesesBatch,
    scripts: ScriptAnalysis,
    target_opposition: ScriptOppositionAnalysis,
    usages: list[UsageSummary],
) -> SemanticConstraintBatch:
    payload = ConstraintPlanInput(
        request=request,
        tmr_plan=tmr_plan,
        scripts=scripts,
        target_opposition=target_opposition,
    )
    result, usage = parse_as(client, SemanticConstraintBatch, CONSTRAINT_PROMPT, payload)
    if usage is not None:
        usages.append(usage)
    return result


def build_lexicon_ontology_plan(
    client: OpenAI,
    request: GenerationRequest,
    intended_final_analysis: FinalOSTHAnalysis,
    scripts: ScriptAnalysis,
    discourse_plan: DiscourseTMR,
    tmr_plan: TMRHypothesesBatch,
    semantic_constraints: SemanticConstraintBatch,
    usages: list[UsageSummary],
) -> LexiconOntologyPlan:
    payload = LexiconOntologyPlanInput(
        request=request,
        intended_final_analysis=intended_final_analysis,
        scripts=scripts,
        discourse_plan=discourse_plan,
        tmr_plan=tmr_plan,
        semantic_constraints=semantic_constraints,
    )
    result, usage = parse_as(client, LexiconOntologyPlan, LEXICON_ONTOLOGY_PROMPT, payload)
    if usage is not None:
        usages.append(usage)
    return result


def build_surface_plan(
    client: OpenAI,
    request: GenerationRequest,
    intended_final_analysis: FinalOSTHAnalysis,
    target_opposition: ScriptOppositionAnalysis,
    target_incongruity: IncongruityAnalysis,
    scripts: ScriptAnalysis,
    discourse_plan: DiscourseTMR,
    tmr_plan: TMRHypothesesBatch,
    lexicon_ontology_plan: LexiconOntologyPlan,
    usages: list[UsageSummary],
) -> SurfaceRealizationPlan:
    payload = SurfacePlanInput(
        request=request,
        intended_final_analysis=intended_final_analysis,
        target_opposition=target_opposition,
        target_incongruity=target_incongruity,
        scripts=scripts,
        discourse_plan=discourse_plan,
        tmr_plan=tmr_plan,
        lexicon_ontology_plan=lexicon_ontology_plan,
    )
    result, usage = parse_as(client, SurfaceRealizationPlan, SURFACE_PLAN_PROMPT, payload)
    if usage is not None:
        usages.append(usage)
    return result


def draft_joke(
    client: OpenAI,
    request: GenerationRequest,
    intended_final_analysis: FinalOSTHAnalysis,
    target_opposition: ScriptOppositionAnalysis,
    target_incongruity: IncongruityAnalysis,
    scripts: ScriptAnalysis,
    surface_plan: SurfaceRealizationPlan,
    lexicon_ontology_plan: LexiconOntologyPlan,
    usages: list[UsageSummary],
) -> GeneratedJoke:
    payload = DraftJokeInput(
        request=request,
        intended_final_analysis=intended_final_analysis,
        target_opposition=target_opposition,
        target_incongruity=target_incongruity,
        scripts=scripts,
        surface_plan=surface_plan,
        lexicon_ontology_plan=lexicon_ontology_plan,
    )
    result, usage = parse_as(client, GeneratedJoke, DRAFT_PROMPT, payload)
    if usage is not None:
        usages.append(usage)
    return result


def verify_joke_mechanism(
    client: OpenAI,
    request: GenerationRequest,
    intended_final_analysis: FinalOSTHAnalysis,
    target_opposition: ScriptOppositionAnalysis,
    target_incongruity: IncongruityAnalysis,
    scripts: ScriptAnalysis,
    generated_joke: GeneratedJoke,
    usages: list[UsageSummary],
) -> JokeMechanismVerification:
    payload = VerificationInput(
        request=request,
        intended_final_analysis=intended_final_analysis,
        target_opposition=target_opposition,
        target_incongruity=target_incongruity,
        scripts=scripts,
        generated_joke=generated_joke,
    )
    result, usage = parse_as(client, JokeMechanismVerification, VERIFY_PROMPT, payload)
    if usage is not None:
        usages.append(usage)
    return result


def semantic_plan_from_osth(
    intended_final_analysis: FinalOSTHAnalysis,
    target_opposition: ScriptOppositionAnalysis,
    target_incongruity: IncongruityAnalysis,
    surface_plan: SurfaceRealizationPlan,
) -> SemanticPlan:
    return SemanticPlan(
        script_a=intended_final_analysis.first_script_summary,
        script_b=intended_final_analysis.second_script_summary,
        opposition_type=target_opposition.opposition_type.value,
        trigger=target_incongruity.incongruous_text,
        setup_goal=surface_plan.setup_strategy,
        punch_goal=surface_plan.punchline_strategy,
    )


def script_b_candidates_from_osth(target_opposition: ScriptOppositionAnalysis, scripts: ScriptAnalysis) -> list[ScriptBCandidate]:
    candidates = [ScriptBCandidate(script_b=target_opposition.script_2.name)]
    for script in scripts.alternative_scripts:
        if script.name != target_opposition.script_2.name:
            candidates.append(ScriptBCandidate(script_b=script.name))
    return candidates


def rationale_from_osth(
    intended_final_analysis: FinalOSTHAnalysis,
    target_opposition: ScriptOppositionAnalysis,
    verification: JokeMechanismVerification,
) -> str:
    issue_text = "; ".join(issue.description for issue in verification.issues) or "Geen belangrijke verificatieproblemen."
    return (
        f"{target_opposition.explanation}\n\n"
        f"Intended mechanism: {intended_final_analysis.final_explanation}\n\n"
        f"Mechanism match: {verification.mechanism_match.value:.2f}. "
        f"Surface naturalness: {verification.surface_naturalness.value:.2f}. "
        f"{issue_text}"
    )


def run(request: JokeRequest, client: OpenAI | None = None) -> JokeResult:
    client = require_client(client)
    started_at = perf_counter()
    usages: list[UsageSummary] = []
    generation_request = generation_request_from_joke_request(request)

    intended_final_analysis = design_intended_final_analysis(client, generation_request, usages)
    target_opposition = design_target_opposition(client, generation_request, intended_final_analysis, usages)
    target_incongruity = design_target_incongruity(
        client,
        generation_request,
        intended_final_analysis,
        target_opposition,
        usages,
    )
    scripts = design_scripts(
        client,
        generation_request,
        intended_final_analysis,
        target_opposition,
        target_incongruity,
        usages,
    )
    discourse_plan = build_discourse_plan(
        client,
        generation_request,
        intended_final_analysis,
        target_opposition,
        target_incongruity,
        scripts,
        usages,
    )
    tmr_plan = build_tmr_plan(client, generation_request, discourse_plan, scripts, target_incongruity, usages)
    semantic_constraints = build_semantic_constraints(client, generation_request, tmr_plan, scripts, target_opposition, usages)
    lexicon_ontology_plan = build_lexicon_ontology_plan(
        client,
        generation_request,
        intended_final_analysis,
        scripts,
        discourse_plan,
        tmr_plan,
        semantic_constraints,
        usages,
    )
    surface_plan = build_surface_plan(
        client,
        generation_request,
        intended_final_analysis,
        target_opposition,
        target_incongruity,
        scripts,
        discourse_plan,
        tmr_plan,
        lexicon_ontology_plan,
        usages,
    )
    generated_joke = draft_joke(
        client,
        generation_request,
        intended_final_analysis,
        target_opposition,
        target_incongruity,
        scripts,
        surface_plan,
        lexicon_ontology_plan,
        usages,
    )
    verification = verify_joke_mechanism(
        client,
        generation_request,
        intended_final_analysis,
        target_opposition,
        target_incongruity,
        scripts,
        generated_joke,
        usages,
    )
    result = JokeGenerationResult(
        request=generation_request,
        intended_final_analysis=intended_final_analysis,
        target_opposition=target_opposition,
        target_incongruity=target_incongruity,
        scripts=scripts,
        discourse_plan=discourse_plan,
        tmr_plan=tmr_plan,
        semantic_constraints=semantic_constraints,
        lexicon_ontology_plan=lexicon_ontology_plan,
        surface_plan=surface_plan,
        generated_joke=generated_joke,
        verification=verification,
    )
    variant = JokeVariant(
        text=generated_joke.text,
        angle=f"OStH verified {verification.mechanism_match.value:.2f}",
    )
    return JokeResult(
        request=request,
        plan=semantic_plan_from_osth(intended_final_analysis, target_opposition, target_incongruity, surface_plan),
        script_b_candidates=script_b_candidates_from_osth(target_opposition, scripts),
        script_b_rationale=rationale_from_osth(intended_final_analysis, target_opposition, verification),
        variants=[variant],
        best_joke=variant,
        usage=summarize_usage(usages, started_at),
        artifacts={"osth_reverse": result.model_dump()},
    )


PIPELINE = PipelineDefinition(
    id=PIPELINE_ID,
    name=PIPELINE_NAME,
    description=PIPELINE_DESCRIPTION,
    runner=run,
)
