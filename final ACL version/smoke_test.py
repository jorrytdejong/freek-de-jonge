from __future__ import annotations

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
    results = run_matrix(request, dry_run=True)
    assert [result.pipeline_code for result in results] == PIPELINE_ORDER
    for result in results:
        assert result.prompt
        assert result.pipeline_name
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
    print("ACL final pipeline smoke test passed.")


if __name__ == "__main__":
    main()
