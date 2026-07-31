from __future__ import annotations

import os
import json
import sys
from dataclasses import asdict
from pathlib import Path

import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parents[1]
PROJECT_PATH = str(PROJECT_DIR)
if PROJECT_PATH in sys.path:
    sys.path.remove(PROJECT_PATH)
sys.path.insert(0, PROJECT_PATH)

for module_name in list(sys.modules):
    if module_name == "core" or module_name.startswith("core."):
        del sys.modules[module_name]

from core.categories import CATEGORY_INVENTORY
from core.llm import DEFAULT_MODEL, MissingAPIKeyError, available_model_ids, model_description, model_label
from core.runner import run_matrix
from core.schemas import JokeRequest
from pipelines.conditions import PIPELINE_ORDER, PIPELINE_SPECS


TOPIC_PROPOSALS = (
    "Familie en opvoeding",
    "Jeugd, school en de Zeeuwse jaren",
    "Religie, kerk en geloof",
    "Nederlandse politiek en bestuur",
    "Oorlog, vrede en geweld",
    "Ouder worden en sterfelijkheid",
    "Gezondheid, ziekte en zorg",
    "Liefde, huwelijk en seksualiteit",
    "Nederlandse identiteit en volksaard",
    "Werk, geld en economie",
    "Media, technologie en mobiele telefoons",
    "Kunst, theater en cabaret",
    "Migratie en de multiculturele samenleving",
    "Klimaat, milieu en natuur",
    "Corona, afstand en sociaal contact",
)


def apply_topic_proposal() -> None:
    """Copy the selected proposal into the editable topic field.

    Returns:
        None.
    """
    proposal = st.session_state.get("topic_proposal")
    if proposal:
        st.session_state["topic_input"] = proposal


def render_styles() -> None:
    """Inject the custom CSS used by the Streamlit results page.

    Returns:
        None.
    """
    st.markdown(
        """
        <style>
        .main .block-container {
            max-width: 1180px;
            padding-top: 2rem;
        }
        .acl-result {
            border: 1px solid #d8dee8;
            border-radius: 8px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.75rem;
            background: #fbfcfe;
        }
        .acl-code {
            color: #2f5f6f;
            font-weight: 700;
            letter-spacing: 0;
        }
        .acl-joke {
            font-size: 1.05rem;
            line-height: 1.5;
            margin-top: 0.4rem;
        }
        .acl-meta {
            color: #5d6878;
            font-size: 0.86rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def build_request() -> JokeRequest:
    """Render request controls and collect their current values.

    Returns:
        A joke request populated from the Streamlit controls.
    """
    if "topic_input" not in st.session_state:
        st.session_state["topic_input"] = "de wachtrij bij de gemeente"

    st.selectbox(
        "Topic proposal from the transcripts",
        options=(None, *TOPIC_PROPOSALS),
        format_func=lambda proposal: "Select a recurring topic..." if proposal is None else proposal,
        key="topic_proposal",
        on_change=apply_topic_proposal,
        help="These 15 proposals are recurring themes in the five transcripts from 2005-2025.",
    )
    topic = st.text_input(
        "Topic",
        key="topic_input",
        help="Choose a proposal above or edit this field to use your own topic.",
    )
    category = st.selectbox("Humor category", options=list(CATEGORY_INVENTORY.keys()), index=0)

    return JokeRequest(
        topic=topic,
        category=category,
        audience="Dutch general audience",
        joke_format="short joke",
        constraints=[],
    )


def render_results(results) -> None:
    """Render generated pipeline results and their optional traces.

    Args:
        results: Pipeline results to display in matrix order.

    Returns:
        None.
    """
    st.subheader("Generated Matrix")
    for result in results:
        usage_text = ""
        if result.usage:
            usage_text = f" | {result.usage.total_tokens:,} tokens | {result.usage.model}"
        st.markdown(
            f"""
            <div class="acl-result">
                <div><span class="acl-code">{result.pipeline_code}</span> {result.pipeline_name}</div>
                <div class="acl-joke">{result.joke}</div>
                <div class="acl-meta">{result.metadata["family"]} | style={result.metadata["style_mode"]}{usage_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if result.warnings:
            st.warning(" ".join(result.warnings))
        if result.script_b_candidates:
            with st.expander(f"{result.pipeline_code} script-opposition trace"):
                plan = result.semantic_plan
                st.markdown(
                    f"""
                    **Script A:** {plan.setup_script or ""}

                    **Script B:** {plan.opposing_script or ""}

                    **Opposition:** {plan.opposition_type or ""}

                    **Trigger:** {plan.trigger or ""}

                    **Rationale:** {result.script_b_rationale}
                    """
                )
                st.write([asdict(candidate) for candidate in result.script_b_candidates])
                if result.variants:
                    st.write([asdict(variant) for variant in result.variants])
                gtvh_trace = result.metadata.get("gtvh_trace")
                if gtvh_trace:
                    st.markdown("**Validated GTVH audit**")
                    st.json(gtvh_trace)


def main() -> None:
    """Render and run the ACL final pipeline matrix application.

    Returns:
        None.
    """
    st.set_page_config(page_title="ACL Final Pipeline Matrix", page_icon=":material/experiment:", layout="wide")
    render_styles()
    st.title("ACL Final Pipeline Matrix")
    st.caption("A1-E2 generation conditions for the Freek de Jonge humor-generation experiment.")

    with st.sidebar:
        st.subheader("Pipelines")
        selected = st.multiselect(
            "Select conditions",
            options=PIPELINE_ORDER,
            default=PIPELINE_ORDER,
            format_func=lambda code: f"{code} - {PIPELINE_SPECS[code].name}",
        )
        model_ids = available_model_ids()
        env_model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        default_model_index = model_ids.index(env_model) if env_model in model_ids else model_ids.index(DEFAULT_MODEL)
        model = st.selectbox(
            "Model",
            options=model_ids,
            index=default_model_index,
            format_func=model_label,
        )
        st.caption(model_description(model))
        dry_run = st.toggle("Dry run", value=not bool(os.getenv("OPENAI_API_KEY")))
        show_prompts = st.toggle("Show prompts", value=False)

    request = build_request()
    generate = st.button("Run selected pipelines", type="primary")

    if generate:
        if not selected:
            st.error("Select at least one pipeline.")
            return
        try:
            with st.spinner("Running ACL final matrix..."):
                results = run_matrix(request, pipeline_codes=selected, model=model, dry_run=dry_run)
        except MissingAPIKeyError as exc:
            st.error(str(exc))
            return
        except ValueError as exc:
            st.error(f"Pipeline validation stopped the run: {exc}")
            return

        render_results(results)
        if show_prompts:
            st.subheader("Prompts")
            for result in results:
                with st.expander(f"{result.pipeline_code} prompt"):
                    st.code(result.prompt)

        st.download_button(
            "Download JSON",
            data=json.dumps([asdict(result) for result in results], indent=2, ensure_ascii=False),
            file_name="acl_final_pipeline_results.json",
            mime="application/json",
        )
    else:
        st.info("Choose inputs and run the selected conditions. Dry run builds prompts without using the API.")


if __name__ == "__main__":
    main()
