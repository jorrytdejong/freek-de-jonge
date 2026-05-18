from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiscourseRole(str, Enum):
    setup = "setup"
    development = "development"
    punchline = "punchline"
    unknown = "unknown"


class ConceptKind(str, Enum):
    event = "event"
    object = "object"
    property = "property"
    role = "role"
    state = "state"
    script = "script"


class FacetKind(str, Enum):
    default = "default"
    sem = "sem"
    relaxable_to = "relaxable_to"
    necessary = "necessary"
    possible = "possible"
    marginal = "marginal"


class OppositionType(str, Enum):
    actual_nonactual = "actual_nonactual"
    normal_abnormal = "normal_abnormal"
    possible_impossible = "possible_impossible"
    good_bad = "good_bad"
    life_death = "life_death"
    nonsexual_sexual = "nonsexual_sexual"
    money_nonmoney = "money_nonmoney"
    high_status_low_status = "high_status_low_status"
    other = "other"


class JokeLength(str, Enum):
    one_liner = "one_liner"
    short_dialogue = "short_dialogue"
    short_anecdote = "short_anecdote"


class TabooLevel(str, Enum):
    clean = "clean"
    mild = "mild"
    edgy = "edgy"


class Confidence(StrictModel):
    value: float = Field(ge=0, le=1)
    rationale: str


class Evidence(StrictModel):
    sentence_id: str
    quote: str
    explanation: str


class PlannedCue(StrictModel):
    cue_id: str
    intended_surface_text: str
    semantic_function: str
    should_appear_before_punchline: bool


class FinalOSTHAnalysis(StrictModel):
    first_script_summary: str
    incongruity_summary: str
    second_script_summary: str
    opposition_summary: str
    required_world_knowledge: list[str]
    final_explanation: str


class ScriptParticipant(StrictModel):
    script_role: str
    entity_id: str
    concept_id: str
    evidence: list[Evidence]


class ScriptCandidate(StrictModel):
    script_id: str
    name: str
    participants: list[ScriptParticipant]
    preconditions: list[str]
    expected_events: list[str]
    goals: list[str]
    supporting_evidence: list[Evidence]
    confidence: Confidence


class ScriptAnalysis(StrictModel):
    primary_script: ScriptCandidate
    alternative_scripts: list[ScriptCandidate]


class IncongruityAnalysis(StrictModel):
    active_script: ScriptCandidate
    incongruous_event_id: str
    incongruous_text: str
    violated_expectation: str
    why_it_fails: str
    severity: Confidence


class ScriptOppositionAnalysis(StrictModel):
    script_1: ScriptCandidate
    script_2: ScriptCandidate
    opposition_type: OppositionType
    explanation: str
    confidence: Confidence


class TMRParticipant(StrictModel):
    role: str
    entity_id: str
    concept_id: str


class TMRProperty(StrictModel):
    name: str
    value_text: str
    value_concept_id: str | None


class TMREvent(StrictModel):
    event_id: str
    concept_id: str
    participants: list[TMRParticipant]
    properties: list[TMRProperty]


class SenseSelection(StrictModel):
    sentence_id: str
    surface: str
    selected_sense_id: str
    reason: str


class TMRHypothesis(StrictModel):
    tmr_id: str
    sentence_id: str
    events: list[TMREvent]
    selected_senses: list[SenseSelection]
    assumptions: list[str]
    constraint_violations: list[str]
    plausibility: Confidence


class TMRHypotheses(StrictModel):
    sentence_id: str
    hypotheses: list[TMRHypothesis]


class TMRHypothesesBatch(StrictModel):
    sentence_hypotheses: list[TMRHypotheses]


class EntityState(StrictModel):
    entity_id: str
    label: str
    concept_id: str
    state_description: str
    evidence: list[Evidence]


class DiscourseRelation(StrictModel):
    source_id: str
    relation_type: str
    target_id: str
    explanation: str


class DiscourseTMR(StrictModel):
    entities: list[EntityState]
    selected_sentence_tmrs: list[TMRHypothesis]
    discourse_relations: list[DiscourseRelation]
    unresolved_ambiguities: list[str]


class SemanticConstraint(StrictModel):
    constraint_id: str
    applies_to_concept_id: str
    role: str
    allowed_type_concept_id: str
    default_concept_id: str | None
    preconditions: list[str]
    expected_effects: list[str]
    confidence: Confidence
    evidence: list[Evidence]


class SemanticConstraintSet(StrictModel):
    sentence_id: str
    constraints: list[SemanticConstraint]


class SemanticConstraintBatch(StrictModel):
    constraint_sets: list[SemanticConstraintSet]


class CandidateSense(StrictModel):
    sense_id: str
    gloss: str
    ontology_concept_id: str
    semantic_type: str
    constraints: list[str]
    confidence: Confidence


class Lexeme(StrictModel):
    sentence_id: str
    surface: str
    lemma: str
    part_of_speech: str
    candidate_senses: list[CandidateSense]
    evidence: list[Evidence]


class LexiconExtraction(StrictModel):
    lexemes: list[Lexeme]


class OntologyConcept(StrictModel):
    concept_id: str
    label: str
    kind: ConceptKind
    is_a: str | None
    definition: str
    evidence: list[Evidence]


class OntologyRelation(StrictModel):
    source_concept_id: str
    relation_type: str
    target_concept_id: str
    confidence: Confidence
    evidence: list[Evidence]


class PropertyAssertion(StrictModel):
    concept_id: str
    property_name: str
    filler_concept_id: str | None
    literal_value: str | None
    facet: FacetKind | None
    confidence: Confidence
    evidence: list[Evidence]


class OntologyPatch(StrictModel):
    concepts: list[OntologyConcept]
    relations: list[OntologyRelation]
    properties: list[PropertyAssertion]
    coverage_notes: list[str]


class GenerationRequest(StrictModel):
    topic: str
    audience_context: str
    desired_tone: str
    taboo_level: TabooLevel
    target_length: JokeLength
    first_script_hint: str | None
    second_script_hint: str | None
    desired_opposition: OppositionType | None
    forbidden_content: list[str]
    additional_requirements: list[str]


class TargetFinalInput(StrictModel):
    request: GenerationRequest
    prior_revision_feedback: list[str]


class OppositionTargetInput(StrictModel):
    request: GenerationRequest
    intended_final_analysis: FinalOSTHAnalysis


class IncongruityTargetInput(StrictModel):
    request: GenerationRequest
    intended_final_analysis: FinalOSTHAnalysis
    target_opposition: ScriptOppositionAnalysis


class ScriptTargetInput(StrictModel):
    request: GenerationRequest
    intended_final_analysis: FinalOSTHAnalysis
    target_opposition: ScriptOppositionAnalysis
    target_incongruity: IncongruityAnalysis


class DiscoursePlanInput(StrictModel):
    request: GenerationRequest
    intended_final_analysis: FinalOSTHAnalysis
    target_opposition: ScriptOppositionAnalysis
    target_incongruity: IncongruityAnalysis
    scripts: ScriptAnalysis


class TMRPlanInput(StrictModel):
    request: GenerationRequest
    discourse_plan: DiscourseTMR
    scripts: ScriptAnalysis
    target_incongruity: IncongruityAnalysis


class ConstraintPlanInput(StrictModel):
    request: GenerationRequest
    tmr_plan: TMRHypothesesBatch
    scripts: ScriptAnalysis
    target_opposition: ScriptOppositionAnalysis


class LexiconOntologyPlanInput(StrictModel):
    request: GenerationRequest
    intended_final_analysis: FinalOSTHAnalysis
    scripts: ScriptAnalysis
    discourse_plan: DiscourseTMR
    tmr_plan: TMRHypothesesBatch
    semantic_constraints: SemanticConstraintBatch


class LexiconOntologyPlan(StrictModel):
    lexicon: LexiconExtraction
    ontology: OntologyPatch
    planned_cues: list[PlannedCue]


class PlannedSentence(StrictModel):
    sentence_id: str
    discourse_role: DiscourseRole
    semantic_function: str
    speaker: str | None
    must_include_cues: list[PlannedCue]
    must_avoid: list[str]
    syntactic_shape: str


class SurfaceRealizationPlan(StrictModel):
    sentences: list[PlannedSentence]
    setup_strategy: str
    misdirection_strategy: str
    punchline_strategy: str
    revision_risks: list[str]


class SurfacePlanInput(StrictModel):
    request: GenerationRequest
    intended_final_analysis: FinalOSTHAnalysis
    target_opposition: ScriptOppositionAnalysis
    target_incongruity: IncongruityAnalysis
    scripts: ScriptAnalysis
    discourse_plan: DiscourseTMR
    tmr_plan: TMRHypothesesBatch
    lexicon_ontology_plan: LexiconOntologyPlan


class DraftJokeInput(StrictModel):
    request: GenerationRequest
    intended_final_analysis: FinalOSTHAnalysis
    target_opposition: ScriptOppositionAnalysis
    target_incongruity: IncongruityAnalysis
    scripts: ScriptAnalysis
    surface_plan: SurfaceRealizationPlan
    lexicon_ontology_plan: LexiconOntologyPlan


class GeneratedJoke(StrictModel):
    title: str | None
    text: str
    punchline: str
    intended_cues_used: list[PlannedCue]
    why_surface_should_work: str
    confidence: Confidence


class VerificationIssue(StrictModel):
    issue_id: str
    severity: Confidence
    description: str
    suggested_fix: str


class JokeMechanismVerification(StrictModel):
    first_script_recoverable: bool
    second_script_recoverable: bool
    incongruity_recoverable: bool
    opposition_recoverable: bool
    surface_naturalness: Confidence
    mechanism_match: Confidence
    issues: list[VerificationIssue]
    revision_advice: list[str]


class VerificationInput(StrictModel):
    request: GenerationRequest
    intended_final_analysis: FinalOSTHAnalysis
    target_opposition: ScriptOppositionAnalysis
    target_incongruity: IncongruityAnalysis
    scripts: ScriptAnalysis
    generated_joke: GeneratedJoke


class JokeGenerationResult(StrictModel):
    request: GenerationRequest
    intended_final_analysis: FinalOSTHAnalysis
    target_opposition: ScriptOppositionAnalysis
    target_incongruity: IncongruityAnalysis
    scripts: ScriptAnalysis
    discourse_plan: DiscourseTMR
    tmr_plan: TMRHypothesesBatch
    semantic_constraints: SemanticConstraintBatch
    lexicon_ontology_plan: LexiconOntologyPlan
    surface_plan: SurfaceRealizationPlan
    generated_joke: GeneratedJoke
    verification: JokeMechanismVerification
