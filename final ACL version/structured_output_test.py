from __future__ import annotations

from core.runner import run_pipeline
from core.schemas import (
    CriticOutput,
    JokeRequest,
    JokeVariantOutput,
    JokeVariantsOutput,
    ScriptAOutput,
    ScriptBCandidateOutput,
    ScriptBCandidatesOutput,
    ScriptBSelectionOutput,
    SemanticPlanOutput,
    UsageSummary,
)
from pipelines import script_opposition


def fake_generate_structured(prompt, response_model, *, model):
    """Return deterministic structured fixtures for pipeline testing.

    Args:
        prompt: Prompt accepted for compatibility with the real helper.
        response_model: Pydantic output type requested by the pipeline.
        model: Model label recorded in the fake usage summary.

    Returns:
        Parsed fixture, serialized fixture, and fake usage metadata.
    """
    outputs = {
        ScriptAOutput: ScriptAOutput(script_a="normale verwachting"),
        ScriptBCandidatesOutput: ScriptBCandidatesOutput(
            candidates=[
                ScriptBCandidateOutput(script_b="tegengestelde werkelijkheid"),
                ScriptBCandidateOutput(script_b="verborgen eigenbelang"),
            ]
        ),
        ScriptBSelectionOutput: ScriptBSelectionOutput(
            script_b="verborgen eigenbelang",
            rationale="Dit levert de duidelijkste tegenstelling op.",
        ),
        SemanticPlanOutput: SemanticPlanOutput(
            opposition_type="publiek/prive",
            trigger="dienstverlening",
            setup_goal="Activeer de normale verwachting.",
            punch_goal="Onthul het verborgen eigenbelang.",
        ),
        JokeVariantsOutput: JokeVariantsOutput(
            variants=[
                JokeVariantOutput(text="Variant een.", angle="droog"),
                JokeVariantOutput(text="Variant twee.", angle="ironisch"),
            ]
        ),
        CriticOutput: CriticOutput(text="Variant twee.", angle="ironisch"),
        JokeVariantOutput: JokeVariantOutput(text="Directe grap.", angle="direct"),
    }
    parsed = outputs[response_model]
    return parsed, parsed.model_dump_json(), UsageSummary(model=model, total_tokens=10)


def main() -> None:
    """Verify direct and staged pipelines against structured fixtures.

    Returns:
        None.
    """
    original = script_opposition.generate_structured
    script_opposition.generate_structured = fake_generate_structured
    try:
        request = JokeRequest(topic="de gemeente", category="Ironie")
        direct = run_pipeline("A1", request, model="test-model")
        staged = run_pipeline("D2", request, model="test-model")
    finally:
        script_opposition.generate_structured = original

    assert direct.joke == "Directe grap."
    assert direct.variants[0].angle == "direct"
    assert staged.semantic_plan.setup_script == "normale verwachting"
    assert staged.semantic_plan.opposing_script == "verborgen eigenbelang"
    assert len(staged.script_b_candidates) == 2
    assert staged.joke == "Variant twee."
    assert staged.metadata["stages"] == [
        "script_a",
        "script_b_candidates",
        "script_b_ranker",
        "plan_context",
        "variants",
        "critic",
    ]
    print("ACL final Pydantic structured-output test passed.")


if __name__ == "__main__":
    main()
