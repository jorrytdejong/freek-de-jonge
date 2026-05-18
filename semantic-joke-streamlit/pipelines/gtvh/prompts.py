from __future__ import annotations

from pipelines.gtvh.models import (
    GTVHRequest,
    LanguageStage,
    LogicalMechanismStage,
    NarrativeStrategyStage,
    ScriptOppositionStage,
    SituationStage,
)


def shared_context(request: GTVHRequest) -> str:
    return (
        f"User topic: {request.topic}\n"
        f"Audience: {request.audience}\n"
        f"Style notes: {request.style_notes}\n"
        "Important language rule: all generated content must be in Dutch. "
        "That includes the joke drafts and all text values inside the JSON outputs. "
        "Keep the JSON keys exactly as requested, but write every value in natural Dutch.\n"
        "You are helping build a joke through a staged pipeline. "
        "Return valid structured output only."
    )


def situation_prompt(request: GTVHRequest) -> str:
    return (
        f"{shared_context(request)}\n\n"
        "Task: Pick one ordinary, recognizable situation directly related to the user's topic. "
        "Keep it concrete and specific: where is it happening, who is there, and what are they trying to do? "
        "Choose a situation that naturally brings the topic into action rather than just mentioning it abstractly. "
        "Important: the 'characters' field must be an array of strings, even if there is only one character or one group.\n\n"
        "Return keys: setting, characters, goal, summary."
    )


def script_opposition_prompt(request: GTVHRequest, situation: SituationStage) -> str:
    return (
        f"{shared_context(request)}\n\n"
        f"Situation summary: {situation.summary}\n"
        f"Setting: {situation.setting}\n"
        f"Characters: {', '.join(situation.characters)}\n"
        f"Goal: {situation.goal}\n\n"
        "Task: Identify two competing scripts for this situation. "
        "Script A must be the most obvious, ordinary interpretation of the situation. "
        "Script B must be a second plausible interpretation that can later replace or disrupt Script A. "
        "The two scripts must be opposed in a humor-relevant way, such as normal/absurd, non-sex/seks, "
        "competent/incompetent, expected/unexpected, sincere/deceptive, or possible/impossible.\n\n"
        "Important:\n"
        "- Describe both scripts as short situation-models, not just single words.\n"
        "- Script A and Script B must both fit the same setup.\n"
        "- All values must be in Dutch.\n\n"
        "Return keys: script_a, script_b, opposition_type, why_they_conflict."
    )


def logical_mechanism_prompt(
    request: GTVHRequest,
    situation: SituationStage,
    opposition: ScriptOppositionStage,
) -> str:
    return (
        f"{shared_context(request)}\n\n"
        f"Situation summary: {situation.summary}\n"
        f"Script A: {opposition.script_a}\n"
        f"Script B: {opposition.script_b}\n"
        f"Opposition type: {opposition.opposition_type}\n"
        f"Why they conflict: {opposition.why_they_conflict}\n\n"
        "Task: Choose one logical mechanism that allows the joke to move from Script A to Script B. "
        "Prefer one of these: reversal, faulty logic, over-literal interpretation, false analogy, "
        "exaggeration, role inversion, or juxtaposition. Explain how the mechanism creates the comic turn.\n\n"
        "Return keys: mechanism, twist_explanation."
    )


def narrative_strategy_prompt(
    request: GTVHRequest,
    situation: SituationStage,
    opposition: ScriptOppositionStage,
    mechanism: LogicalMechanismStage,
) -> str:
    return (
        f"{shared_context(request)}\n\n"
        f"Situation summary: {situation.summary}\n"
        f"Script A: {opposition.script_a}\n"
        f"Script B: {opposition.script_b}\n"
        f"Opposition type: {opposition.opposition_type}\n"
        f"Logical mechanism: {mechanism.mechanism}\n"
        f"Twist explanation: {mechanism.twist_explanation}\n\n"
        "Task: Choose the best delivery format for this joke: one-liner, question-answer, short dialogue, "
        "brief anecdote, mock advice, or list item. Pick the format that gives the cleanest setup and strongest timing.\n\n"
        "Return keys: format, why_it_works."
    )


def language_prompt(
    request: GTVHRequest,
    situation: SituationStage,
    opposition: ScriptOppositionStage,
    mechanism: LogicalMechanismStage,
    strategy: NarrativeStrategyStage,
) -> str:
    return (
        f"{shared_context(request)}\n\n"
        f"Situation summary: {situation.summary}\n"
        f"Script A: {opposition.script_a}\n"
        f"Script B: {opposition.script_b}\n"
        f"Opposition type: {opposition.opposition_type}\n"
        f"Logical mechanism: {mechanism.mechanism}\n"
        f"Narrative strategy: {strategy.format}\n\n"
        "Task: Write 3 versions of the joke in the chosen format. Keep the setup short, make the wording natural, "
        "and place the punchline as late as possible. Vary rhythm, diction, and phrasing.\n\n"
        "Return keys: version_a, version_b, version_c."
    )


def target_prompt(request: GTVHRequest, language: LanguageStage) -> str:
    return (
        f"{shared_context(request)}\n\n"
        f"Draft A: {language.version_a}\n"
        f"Draft B: {language.version_b}\n"
        f"Draft C: {language.version_c}\n\n"
        "Task: Decide whether this joke needs a target. Add a target only if it genuinely strengthens clarity "
        "or comic effect without becoming lazy. If it does not need one, keep it target-free.\n\n"
        "Return keys: needs_target, target, neutral_version, target_version, rationale."
    )


def refinement_prompt(request: GTVHRequest, language: LanguageStage, target) -> str:
    return (
        f"{shared_context(request)}\n\n"
        f"Draft A: {language.version_a}\n"
        f"Draft B: {language.version_b}\n"
        f"Draft C: {language.version_c}\n"
        f"Neutral version: {target.neutral_version}\n"
        f"Target version: {target.target_version or 'None'}\n\n"
        "Task: Evaluate the drafts for clarity, surprise, brevity, and punchline strength. "
        "Cut extra words and keep only the strongest final version plus one backup.\n\n"
        "Return keys: best_version, backup_version, why_best_works."
    )

