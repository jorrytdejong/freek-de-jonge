from html import escape

import streamlit as st

from app.health import health_snapshot
from app.stimuli import JokeGroup, StimulusValidationError, load_stimuli


st.set_page_config(
    page_title="Onderzoek naar humor en stijl",
    page_icon=":material/rate_review:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

health = health_snapshot()


def render_header() -> None:
    st.markdown(
        """
        <header class="study-header">
            <p class="study-brand">Freek participant study</p>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_stimulus_preview(groups: tuple[JokeGroup, ...]) -> None:
    render_header()
    with st.container(key="stimulus_preview"):
        st.markdown(
            """
            <div class="preview-heading">
                <a class="preview-back" href="./">Terug naar start</a>
                <h1>Stimuluspreview</h1>
                <p>Controleer de fictieve teksten en interne labels voor pilot-1.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        selected_group_id = st.selectbox(
            "Jokegroep",
            options=[group.group_id for group in groups],
            format_func=lambda group_id: next(
                f"{group.group_id} - {group.title}"
                for group in groups
                if group.group_id == group_id
            ),
        )
        selected_group = next(
            group for group in groups if group.group_id == selected_group_id
        )

        st.markdown(
            f"""
            <div class="preview-summary">
                <strong>{escape(selected_group.group_id)}</strong>
                <span>{escape(selected_group.title)}</span>
                <span>{len(selected_group.variants)} varianten</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for variant in selected_group.variants:
            st.markdown(
                f"""
                <article class="preview-variant">
                    <div class="preview-meta">
                        <code>{escape(variant.variant_id)}</code>
                        <span>{escape(variant.variant_role)}</span>
                    </div>
                    <p>{escape(variant.text)}</p>
                </article>
                """,
                unsafe_allow_html=True,
            )

        st.caption(
            "Deze teksten zijn fictief en experimenteel. "
            "Ze zijn niet geschreven door Freek de Jonge."
        )


try:
    stimulus_groups = load_stimuli()
except StimulusValidationError as error:
    st.error(f"Stimuluscontrole mislukt: {error}")
    st.stop()

st.markdown(
    """
    <style>
        :root {
            --study-background: #ffffff;
            --study-text: #18221f;
            --study-muted: #56615d;
            --study-border: #dce2df;
            --study-green: #126443;
            --study-coral: #ed6b5f;
        }

        html,
        body,
        [data-testid="stAppViewContainer"] {
            background: var(--study-background);
            color: var(--study-text);
        }

        html,
        body,
        button,
        input,
        textarea {
            letter-spacing: 0;
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"] {
            display: none;
        }

        [data-testid="stMainBlockContainer"] {
            max-width: none;
            padding: 0;
        }

        .study-header {
            align-items: center;
            border-bottom: 1px solid var(--study-border);
            display: flex;
            min-height: 86px;
            padding: 0 3rem;
        }

        .study-brand {
            color: var(--study-text);
            font-size: 1.1rem;
            font-weight: 700;
            line-height: 1.4;
            margin: 0;
        }

        .study-content {
            margin-left: clamp(1.5rem, 14vw, 14rem);
            max-width: 50rem;
            min-height: 620px;
            padding: 9rem 3rem 5rem;
        }

        .study-content h1 {
            color: var(--study-text);
            font-size: 2.75rem;
            font-weight: 700;
            line-height: 1.16;
            margin: 0;
            max-width: 48rem;
        }

        .study-accent {
            background: var(--study-green);
            border-radius: 2px;
            height: 4px;
            margin: 1.7rem 0 2.25rem;
            width: 4.75rem;
        }

        .study-intro {
            color: var(--study-text);
            font-size: 1.25rem;
            line-height: 1.6;
            margin: 0 0 1.7rem;
        }

        .study-status {
            align-items: center;
            color: var(--study-text);
            display: flex;
            font-size: 1rem;
            gap: 0.85rem;
            line-height: 1.5;
            margin-bottom: 2.25rem;
        }

        .study-start {
            align-items: center;
            background: #f7f8f7;
            border: 1px solid #d1d7d4;
            border-radius: 6px;
            color: #9ba29f;
            cursor: not-allowed;
            display: inline-flex;
            font-family: inherit;
            font-size: 1rem;
            font-weight: 650;
            gap: 0.8rem;
            justify-content: flex-start;
            min-height: 3.5rem;
            padding: 0 1.25rem;
            width: 22rem;
        }

        .study-start-icon {
            border-bottom: 0.38rem solid transparent;
            border-left: 0.58rem solid #aeb4b1;
            border-top: 0.38rem solid transparent;
            display: inline-block;
            height: 0;
            width: 0;
        }

        .study-status-mark {
            border: 2px solid var(--study-green);
            border-radius: 50%;
            display: inline-block;
            flex: 0 0 1.5rem;
            height: 1.5rem;
            position: relative;
            width: 1.5rem;
        }

        .study-status-mark::after {
            border-bottom: 2px solid var(--study-green);
            border-right: 2px solid var(--study-green);
            content: "";
            height: 0.45rem;
            left: 0.48rem;
            position: absolute;
            top: 0.27rem;
            transform: rotate(45deg);
            width: 0.24rem;
        }

        .study-footer {
            align-items: center;
            border-top: 1px solid var(--study-border);
            color: var(--study-muted);
            display: flex;
            font-size: 0.9rem;
            gap: 0.8rem;
            min-height: 110px;
            padding: 0 4rem;
        }

        .study-footer-mark {
            background: var(--study-coral);
            display: inline-block;
            height: 1.1rem;
            width: 0.25rem;
            box-shadow:
                0.45rem 0 0 var(--study-coral),
                0.9rem 0 0 var(--study-coral);
        }

        .st-key-stimulus_preview {
            margin: 0 auto;
            max-width: 58rem;
            padding: 4.5rem 2rem 5rem;
        }

        .preview-heading {
            margin-bottom: 2.5rem;
        }

        .preview-heading h1 {
            color: var(--study-text);
            font-size: 2.4rem;
            line-height: 1.2;
            margin: 1rem 0 0.75rem;
        }

        .preview-heading p {
            color: var(--study-muted);
            font-size: 1rem;
            line-height: 1.6;
            margin: 0;
        }

        .preview-back {
            color: var(--study-green);
            font-size: 0.92rem;
            font-weight: 650;
            text-decoration: none;
        }

        .preview-back:hover {
            text-decoration: underline;
        }

        .st-key-stimulus_preview div[data-testid="stSelectbox"] {
            max-width: 32rem;
        }

        .preview-summary {
            align-items: baseline;
            border-bottom: 2px solid var(--study-green);
            display: flex;
            gap: 1rem;
            margin: 2.5rem 0 0;
            padding-bottom: 1rem;
        }

        .preview-summary strong {
            color: var(--study-green);
        }

        .preview-summary span:last-child {
            color: var(--study-muted);
            font-size: 0.88rem;
            margin-left: auto;
        }

        .preview-variant {
            border-bottom: 1px solid var(--study-border);
            padding: 1.5rem 0;
        }

        .preview-meta {
            align-items: center;
            color: var(--study-muted);
            display: flex;
            font-size: 0.82rem;
            gap: 1rem;
            margin-bottom: 0.65rem;
        }

        .preview-meta code {
            color: var(--study-green);
            font-size: 0.82rem;
            font-weight: 700;
        }

        .preview-variant p {
            color: var(--study-text);
            font-size: 1.05rem;
            line-height: 1.65;
            margin: 0;
        }

        @media (max-width: 700px) {
            .study-header {
                min-height: 72px;
                padding: 0 1.25rem;
            }

            .study-content {
                margin-left: 0;
                min-height: 560px;
                padding: 5rem 1.25rem 3rem;
            }

            .study-content h1 {
                font-size: 2.1rem;
            }

            .study-intro {
                font-size: 1.1rem;
            }

            .study-start {
                width: 100%;
            }

            .study-footer {
                min-height: 92px;
                padding: 0 1.25rem;
            }

            .st-key-stimulus_preview {
                padding: 3rem 1.25rem 4rem;
            }

            .preview-heading h1 {
                font-size: 2rem;
            }

            .preview-summary {
                align-items: flex-start;
                flex-direction: column;
                gap: 0.35rem;
            }

            .preview-summary span:last-child {
                margin-left: 0;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

if st.query_params.get("preview") == "1":
    render_stimulus_preview(stimulus_groups)
    st.stop()

render_header()
st.markdown(
    """
    <main class="study-content">
        <h1>Onderzoek naar humor en stijl</h1>
        <div class="study-accent" aria-hidden="true"></div>
        <p class="study-intro">Welkom bij de onderzoeksomgeving.</p>
        <div class="study-status">
            <span class="study-status-mark" aria-hidden="true"></span>
            <span>De applicatie is gereed.</span>
        </div>
        <button class="study-start" type="button" disabled aria-disabled="true">
            <span class="study-start-icon" aria-hidden="true"></span>
            <span>Start onderzoek</span>
        </button>
    </main>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <footer class="study-footer">
        <span class="study-footer-mark" aria-hidden="true"></span>
        <span>Onderzoeksversie {health["study_version"]}</span>
    </footer>
    """,
    unsafe_allow_html=True,
)
