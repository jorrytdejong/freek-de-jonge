from __future__ import annotations

import json
from tempfile import TemporaryDirectory
from pathlib import Path

from core.storage import get_joke, list_jokes, save_joke_result
from schemas import JokeRequest, JokeResult, JokeVariant, SemanticPlan, UsageSummary


def make_fake_result() -> JokeResult:
    request = JokeRequest(
        topic="treinvertraging",
        audience="volwassen Nederlands publiek",
        voice="droog",
        format="one_liner",
        constraints=["kort houden"],
    )
    best_joke = JokeVariant(text="De trein had vertraging, maar noemde het contemplatie.", angle="dry")
    return JokeResult(
        request=request,
        plan=SemanticPlan(
            script_a="reizen volgens dienstregeling",
            script_b="filosofisch wachten",
            opposition_type="normal_abnormal",
            trigger="vertraging als contemplatie",
            setup_goal="herkenbare treinvertraging",
            punch_goal="vertraging herinterpreteren",
        ),
        variants=[best_joke],
        best_joke=best_joke,
        usage=UsageSummary(
            model="gpt-5.4-mini",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.0003,
            duration_seconds=1.25,
        ),
    )


def main() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "jokes.sqlite3"
        result = make_fake_result()
        joke_id = save_joke_result("test_pipeline", "Test Pipeline", result, database_path)

        stored_rows = list_jokes("trein", database_path)
        assert len(stored_rows) == 1
        stored = stored_rows[0]
        assert stored.id == joke_id
        assert stored.pipeline_id == "test_pipeline"
        assert stored.pipeline_name == "Test Pipeline"
        assert stored.best_joke == result.best_joke.text
        assert stored.model == "gpt-5.4-mini"
        assert json.loads(stored.constraints_json) == ["kort houden"]

        fetched = get_joke(joke_id, database_path)
        assert fetched is not None
        payload = json.loads(fetched.result_json)
        assert payload["request"]["topic"] == "treinvertraging"
        assert payload["best_joke"]["text"] == result.best_joke.text

    print("Storage test passed.")


if __name__ == "__main__":
    main()
