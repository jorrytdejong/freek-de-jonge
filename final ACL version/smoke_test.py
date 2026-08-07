from __future__ import annotations

from core.categories import CATEGORY_INVENTORY
from core.freek_examples import EXAMPLE_SEGMENTS
from core.llm import DEFAULT_MODEL, available_model_ids
from core.runner import run_matrix
from core.schemas import JokeRequest
from pipelines.conditions import PIPELINE_ORDER


def main() -> None:
    """Verify that every condition builds a valid dry-run result.

    Returns:
        None.
    """
    request = JokeRequest(
        topic="de wachtrij bij de gemeente",
        category="Ironie",
    )
    assert DEFAULT_MODEL == "gpt-5.6-terra"
    assert available_model_ids()[0] == DEFAULT_MODEL
    assert len(EXAMPLE_SEGMENTS) == 10
    assert len({filename for filename, _ in EXAMPLE_SEGMENTS}) == 5
    results = run_matrix(request, dry_run=True)
    by_code = {result.pipeline_code: result for result in results}
    assert [result.pipeline_code for result in results] == PIPELINE_ORDER
    assert all(set(details) == {"description"} for details in CATEGORY_INVENTORY.values())
    for result in results:
        assert result.prompt
        assert result.pipeline_name
        assert "Comic validity requirements:" in result.prompt
        assert (
            "Use a concrete situation, action, object, phrase, or human reaction rather than abstract commentary."
            not in result.prompt
        )
        assert result.semantic_plan.style_mode in {"none", "freek"}
        if result.pipeline_code in {"C1", "C2", "D1", "D2", "E1", "E2"}:
            assert result.script_b_candidates
            assert result.script_b_rationale
        if result.pipeline_code in {"C1", "C2", "D1", "D2"}:
            assert "script_b_candidates" in result.prompt
        if result.pipeline_code in {"E1", "E2"}:
            assert "opposition_candidates" in result.prompt
            assert "theory_gate" in result.prompt
            assert "blind_reconstruction" in result.prompt
            assert result.metadata["gtvh_trace"]

    assert "category_context" not in by_code["C1"].prompt
    assert "category_context" not in by_code["C2"].prompt
    assert "Freek" not in by_code["A1"].prompt
    assert "semantic turn" not in by_code["A1"].prompt.lower()
    assert "Comic eligibility is non-compensatory." in by_code["C1"].prompt
    assert "Comic eligibility is non-compensatory." in by_code["E1"].prompt
    assert "moral seriousness" not in by_code["A2"].prompt.lower()
    assert "culminate in laughter rather than moral agreement" in by_code["A2"].prompt
    assert "freek_jokes_tagged_with_category" not in by_code["B1"].prompt
    assert "freek_jokes_tagged_with_category" in by_code["B2"].prompt
    assert "freek_jokes_tagged_with_category" not in by_code["D1"].prompt
    assert "freek_jokes_tagged_with_category" in by_code["D2"].prompt
    assert "category_script_opposition_examples" not in by_code["D1"].prompt
    assert "freek_category_script_opposition_examples" not in by_code["D2"].prompt
    assert by_code["B1"].semantic_plan.trigger is None
    assert by_code["B2"].semantic_plan.trigger is None
    assert by_code["D1"].semantic_plan.trigger == "[generated during semantic planning]"
    assert by_code["D2"].semantic_plan.trigger == "[generated during semantic planning]"

    try:
        run_matrix(
            JokeRequest(topic="de gemeente", category="Leedvermaak"),
            pipeline_codes=["B2"],
            dry_run=True,
        )
    except ValueError as exc:
        assert "No Freek de Jonge jokes tagged" in str(exc)
    else:
        raise AssertionError("B2 must not substitute generic context when category-matched Freek jokes are absent.")
    print("ACL final pipeline smoke test passed.")


if __name__ == "__main__":
    main()
