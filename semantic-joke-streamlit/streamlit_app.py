from __future__ import annotations

import json
import os
import sys
from json import JSONDecodeError
from html import escape
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.pricing import DEFAULT_MODEL, MODEL_PRICING
from core.registry import PIPELINES, run_pipelines
from core.storage import StoredJoke, get_joke, init_database, list_jokes, save_joke_results
from schemas import JokeRequest, JokeResult, UsageSummary


def get_secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except Exception:
        return None
    return str(value) if value else None


def resolve_api_key() -> str | None:
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key
    secret_key = get_secret("OPENAI_API_KEY")
    if secret_key:
        os.environ["OPENAI_API_KEY"] = secret_key
        return secret_key
    return None


def parse_constraints(raw_constraints: str) -> list[str]:
    return [line.strip() for line in raw_constraints.splitlines() if line.strip()]


def format_cost(usage: UsageSummary) -> str:
    if usage.estimated_cost_usd is None:
        return "unknown"
    return f"${usage.estimated_cost_usd:.6f}"


def format_duration(usage: UsageSummary) -> str:
    if usage.duration_seconds is None:
        return "unknown"
    return f"{usage.duration_seconds:.2f}s"


def format_optional_cost(cost: float | None) -> str:
    if cost is None:
        return "unknown"
    return f"${cost:.6f}"


def format_optional_duration(duration: float | None) -> str:
    if duration is None:
        return "unknown"
    return f"{duration:.2f}s"


def render_usage(usage: UsageSummary | None) -> None:
    st.subheader("Generation Stats")
    if usage is None:
        st.info("No usage metadata was returned for this run.")
        return

    model, input_tokens, output_tokens, total_tokens, cost, duration = st.columns(6)
    model.metric("Model", usage.model)
    input_tokens.metric("Input", f"{usage.input_tokens:,}")
    output_tokens.metric("Output", f"{usage.output_tokens:,}")
    total_tokens.metric("Total", f"{usage.total_tokens:,}")
    cost.metric("Cost", format_cost(usage))
    duration.metric("Duration", format_duration(usage))


def render_plan(result: JokeResult) -> None:
    st.subheader("Semantic Plan")
    st.markdown(
        f"""
        <div class="report-grid">
            <div><strong>Script A</strong><span>{escape(result.plan.script_a)}</span></div>
            <div><strong>Script B</strong><span>{escape(result.plan.script_b)}</span></div>
            <div><strong>Opposition</strong><span>{escape(result.plan.opposition_type)}</span></div>
            <div><strong>Trigger</strong><span>{escape(result.plan.trigger)}</span></div>
            <div><strong>Setup</strong><span>{escape(result.plan.setup_goal)}</span></div>
            <div><strong>Punch</strong><span>{escape(result.plan.punch_goal)}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if result.script_b_candidates:
        st.subheader("Script B Loop")
        for index, candidate in enumerate(result.script_b_candidates, start=1):
            st.markdown(
                f'<div class="candidate"><span>{index}</span>{escape(candidate.script_b)}</div>',
                unsafe_allow_html=True,
            )

    if result.script_b_rationale:
        st.subheader("Why This Script B")
        st.markdown(f'<div class="text-panel">{escape(result.script_b_rationale)}</div>', unsafe_allow_html=True)


def render_variants(result: JokeResult) -> None:
    st.subheader("Variants")
    for index, variant in enumerate(result.variants, start=1):
        st.markdown(
            f"""
            <div class="variant-card">
                <div class="variant-heading">Variant {index} - {escape(variant.angle)}</div>
                <div class="variant-text">{escape(variant.text)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_result(result: JokeResult, *, show_plan: bool, show_variants: bool, show_json: bool) -> None:
    st.markdown(
        f"""
        <section class="best-joke">
            <div class="best-label">Best joke</div>
            <p>{escape(result.best_joke.text)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    render_usage(result.usage)

    if show_plan:
        render_plan(result)

    if show_variants:
        render_variants(result)

    if show_json:
        st.subheader("Raw JSON")
        st.code(result.model_dump_json(indent=2), language="json")


def render_comparison(results: dict[str, JokeResult]) -> None:
    st.subheader("Pipeline Comparison")
    rows = []
    for pipeline_id, result in results.items():
        usage = result.usage
        rows.append(
            {
                "Pipeline": PIPELINES[pipeline_id].name,
                "Best joke": result.best_joke.text,
                "Model": usage.model if usage is not None else "unknown",
                "Input tokens": usage.input_tokens if usage is not None else 0,
                "Output tokens": usage.output_tokens if usage is not None else 0,
                "Total tokens": usage.total_tokens if usage is not None else 0,
                "Cost": format_cost(usage) if usage is not None else "unknown",
                "Duration": format_duration(usage) if usage is not None else "unknown",
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)


def render_pipeline_details(
    results: dict[str, JokeResult],
    *,
    show_plan: bool,
    show_variants: bool,
    show_json: bool,
) -> None:
    st.subheader("Detailed Reports")
    tabs = st.tabs([PIPELINES[pipeline_id].name for pipeline_id in results])
    for tab, (pipeline_id, result) in zip(tabs, results.items(), strict=True):
        with tab:
            st.caption(PIPELINES[pipeline_id].description)
            render_result(result, show_plan=show_plan, show_variants=show_variants, show_json=show_json)


def render_pipeline_menu() -> list[str]:
    st.subheader("Pipeline")
    pipeline_ids = list(PIPELINES.keys())
    selected_pipeline_id = st.selectbox(
        "Choose one pipeline",
        options=pipeline_ids,
        format_func=lambda pipeline_id: PIPELINES[pipeline_id].name,
        key="selected_pipeline_id",
    )
    st.caption(PIPELINES[selected_pipeline_id].description)
    return [selected_pipeline_id]


def history_rows(stored_jokes: list[StoredJoke]) -> list[dict[str, object]]:
    return [
        {
            "ID": joke.id,
            "Created": joke.created_at,
            "Pipeline": joke.pipeline_name,
            "Topic": joke.topic,
            "Best joke": joke.best_joke,
            "Model": joke.model or "unknown",
            "Cost": format_optional_cost(joke.estimated_cost_usd),
            "Duration": format_optional_duration(joke.duration_seconds),
        }
        for joke in stored_jokes
    ]


def render_saved_joke_detail(joke: StoredJoke) -> None:
    st.markdown(
        f"""
        <section class="best-joke">
            <div class="best-label">Saved joke</div>
            <p>{escape(joke.best_joke)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    model, input_tokens, output_tokens, total_tokens, cost, duration = st.columns(6)
    model.metric("Model", joke.model or "unknown")
    input_tokens.metric("Input", f"{joke.input_tokens:,}")
    output_tokens.metric("Output", f"{joke.output_tokens:,}")
    total_tokens.metric("Total", f"{joke.total_tokens:,}")
    cost.metric("Cost", format_optional_cost(joke.estimated_cost_usd))
    duration.metric("Duration", format_optional_duration(joke.duration_seconds))

    st.subheader("Request")
    try:
        constraints = ", ".join(json.loads(joke.constraints_json)) or "none"
    except (JSONDecodeError, TypeError):
        constraints = joke.constraints_json or "none"
    st.markdown(
        f"""
        <div class="report-grid">
            <div><strong>Pipeline</strong><span>{escape(joke.pipeline_name)}</span></div>
            <div><strong>Created</strong><span>{escape(joke.created_at)}</span></div>
            <div><strong>Topic</strong><span>{escape(joke.topic)}</span></div>
            <div><strong>Audience</strong><span>{escape(joke.audience)}</span></div>
            <div><strong>Voice</strong><span>{escape(joke.voice)}</span></div>
            <div><strong>Format</strong><span>{escape(joke.format)}</span></div>
            <div><strong>Constraints</strong><span>{escape(constraints)}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.toggle("Show saved raw JSON", value=False, key=f"saved_json_{joke.id}"):
        st.code(joke.result_json, language="json")


def render_history() -> None:
    st.subheader("Saved Joke History")
    search = st.text_input("Search saved jokes", placeholder="Search topic, pipeline, model, or joke text")
    stored_jokes = list_jokes(search)

    if not stored_jokes:
        st.info("No saved jokes found yet.")
        return

    st.dataframe(history_rows(stored_jokes), hide_index=True, use_container_width=True)
    selected_joke_id = st.selectbox(
        "Inspect saved joke",
        options=[joke.id for joke in stored_jokes],
        format_func=lambda joke_id: next(
            f"#{joke.id} - {joke.pipeline_name} - {joke.topic}" for joke in stored_jokes if joke.id == joke_id
        ),
    )
    selected_joke = get_joke(selected_joke_id)
    if selected_joke is not None:
        render_saved_joke_detail(selected_joke)


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --sj-ink: #1f2933;
            --sj-muted: #64748b;
            --sj-line: #d7dee8;
            --sj-soft: #f5f7fb;
            --sj-accent: #2a9d8f;
            --sj-warm: #e76f51;
        }

        .block-container {
            max-width: 1120px;
            padding-top: 2.5rem;
            padding-bottom: 4rem;
        }

        h1, h2, h3 {
            letter-spacing: 0;
            color: var(--sj-ink);
        }

        .best-joke {
            border: 1px solid var(--sj-line);
            border-left: 6px solid var(--sj-accent);
            background: linear-gradient(135deg, #ffffff 0%, #f2fbf8 100%);
            padding: 1.35rem 1.5rem;
            margin: 1.25rem 0 1.5rem;
        }

        .best-label {
            color: var(--sj-accent);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0;
            text-transform: uppercase;
            margin-bottom: 0.45rem;
        }

        .best-joke p {
            color: var(--sj-ink);
            font-size: 1.35rem;
            line-height: 1.45;
            margin: 0;
            font-weight: 700;
        }

        .report-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            margin-bottom: 1.25rem;
        }

        .report-grid > div,
        .text-panel,
        .candidate,
        .variant-card {
            border: 1px solid var(--sj-line);
            background: #ffffff;
            padding: 0.85rem 0.95rem;
        }

        .report-grid strong {
            display: block;
            color: var(--sj-warm);
            font-size: 0.78rem;
            margin-bottom: 0.35rem;
        }

        .report-grid span,
        .text-panel,
        .variant-text {
            color: var(--sj-ink);
            line-height: 1.55;
        }

        .candidate {
            align-items: flex-start;
            display: flex;
            gap: 0.75rem;
            margin-bottom: 0.55rem;
        }

        .candidate span {
            background: var(--sj-soft);
            color: var(--sj-accent);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 1.7rem;
            height: 1.7rem;
            font-weight: 700;
        }

        .variant-card {
            margin-bottom: 0.75rem;
        }

        .variant-heading {
            color: var(--sj-warm);
            font-size: 0.82rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }

        @media (max-width: 760px) {
            .report-grid {
                grid-template-columns: 1fr;
            }

            .best-joke p {
                font-size: 1.12rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Semantic Joke Pipelines", page_icon=":material/theater_comedy:", layout="wide")
    init_database()
    apply_styles()

    st.title("Semantic Joke Pipelines")
    st.caption("Run multiple Dutch semantic joke pipelines and compare their reports.")

    api_key = resolve_api_key()

    with st.sidebar:
        st.header("Settings")
        audience = st.text_input("Audience", value="volwassen Nederlands publiek")
        voice = st.text_input("Voice", value="droog, intelligent, licht absurd")
        joke_format = st.selectbox("Format", options=["one_liner", "short", "monologue"], index=0)
        constraints_text = st.text_area("Constraints", placeholder="One constraint per line")

        models = list(MODEL_PRICING.keys())
        active_model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        model_index = models.index(active_model) if active_model in models else models.index(DEFAULT_MODEL)
        selected_model = st.selectbox("Model", options=models, index=model_index)
        selected_pipeline_ids = render_pipeline_menu()

        st.divider()
        show_plan = st.toggle("Show semantic plan", value=True)
        show_variants = st.toggle("Show variants", value=True)
        show_json = st.toggle("Show raw JSON", value=False)

        if api_key is None:
            st.divider()
            entered_api_key = st.text_input("OpenAI API key", type="password")
            if entered_api_key:
                os.environ["OPENAI_API_KEY"] = entered_api_key
                api_key = entered_api_key

    with st.form("semantic_joke_form"):
        topic = st.text_input("Topic", placeholder="Bijvoorbeeld: bureaucratie, klimaatbeleid, treinvertraging")
        submitted = st.form_submit_button("Generate comparison", use_container_width=True)

    if submitted:
        if not topic.strip():
            st.error("Please enter a topic before generating a report.")
            return
        if api_key is None:
            st.error("OPENAI_API_KEY is required. Add it to the environment, Streamlit secrets, or the sidebar field.")
            return
        if not selected_pipeline_ids:
            st.error("Select at least one pipeline before generating a comparison.")
            return

        os.environ["OPENAI_MODEL"] = selected_model
        request = JokeRequest(
            topic=topic.strip(),
            audience=audience.strip() or "volwassen Nederlands publiek",
            voice=voice.strip() or "droog, intelligent, licht absurd",
            format=joke_format,
            constraints=parse_constraints(constraints_text),
        )

        try:
            with st.spinner("Generating semantic joke pipeline comparison..."):
                results = run_pipelines(selected_pipeline_ids, request)
                st.session_state["latest_results"] = results
                saved_ids = save_joke_results(
                    results,
                    {pipeline_id: PIPELINES[pipeline_id].name for pipeline_id in results},
                )
                st.success(f"Saved {len(saved_ids)} joke{'s' if len(saved_ids) != 1 else ''} to history.")
        except Exception as exc:
            st.error(f"Generation failed: {exc}")
            return

    generator_tab, history_tab = st.tabs(["Generator", "History"])
    with generator_tab:
        results = st.session_state.get("latest_results")
        if not results:
            st.info("Enter a topic and generate a comparison to see the selected joke pipelines.")
        else:
            render_comparison(results)
            render_pipeline_details(results, show_plan=show_plan, show_variants=show_variants, show_json=show_json)

    with history_tab:
        render_history()


if __name__ == "__main__":
    main()
