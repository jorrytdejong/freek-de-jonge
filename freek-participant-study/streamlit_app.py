from html import escape
from urllib.parse import urlencode

import streamlit as st

from app.assignment import assignment_fingerprint, build_assignment
from app.health import health_snapshot
from app.participant import ProfileValidationError, validate_profile
from app.sessions import (
    ParticipantSession,
    SessionAccessStatus,
    SessionValidationError,
    load_sessions,
    resolve_session,
)
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


def render_footer() -> None:
    st.markdown(
        f"""
        <footer class="study-footer">
            <span class="study-footer-mark" aria-hidden="true"></span>
            <span>Onderzoeksversie {health["study_version"]}</span>
        </footer>
        """,
        unsafe_allow_html=True,
    )


def render_access_state(status: SessionAccessStatus) -> None:
    content = {
        SessionAccessStatus.MISSING: (
            "Onderzoekslink vereist",
            "Open de persoonlijke link die je voor dit onderzoek hebt ontvangen.",
        ),
        SessionAccessStatus.UNKNOWN: (
            "Deze onderzoekslink is niet geldig",
            "Controleer of je de volledige link hebt geopend.",
        ),
        SessionAccessStatus.INACTIVE: (
            "Deze onderzoekslink is niet actief",
            "Deze sessie kan momenteel niet worden gebruikt.",
        ),
    }
    title, message = content[status]
    render_header()
    st.markdown(
        f"""
        <main class="study-content access-content">
            <h1>{escape(title)}</h1>
            <div class="study-accent" aria-hidden="true"></div>
            <p class="study-intro">{escape(message)}</p>
        </main>
        """,
        unsafe_allow_html=True,
    )
    render_footer()


def render_participant_start(
    session: ParticipantSession,
    fingerprint: str,
) -> None:
    session_status = "Testsessie is geldig." if session.is_test else (
        "Onderzoekslink is geldig."
    )
    test_notice = ""
    if session.is_test:
        test_notice = (
            '<p class="study-session-note">'
            "Dit is een testsessie. Antwoorden worden later als "
            "testgegevens gemarkeerd."
            "</p>"
        )
    render_header()
    with st.container(key="participant_start"):
        st.markdown(
            f"""
            <span class="assignment-fingerprint" data-assignment-fingerprint="{escape(fingerprint)}"></span>
            <h1>Onderzoek naar humor en stijl</h1>
            <div class="study-accent" aria-hidden="true"></div>
            <p class="study-intro">Welkom bij de onderzoeksomgeving.</p>
            <div class="study-status">
                <span class="study-status-mark" aria-hidden="true"></span>
                <span>{escape(session_status)}</span>
            </div>
            {test_notice}
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Start onderzoek",
            type="primary",
            icon=":material/play_arrow:",
        ):
            st.query_params["page"] = "intro"
            st.rerun()
    render_footer()


def render_participant_intro(session: ParticipantSession) -> None:
    render_header()
    with st.container(key="participant_intro"):
        back_href = f"?{urlencode({'session': session.session_id})}"
        st.markdown(
            f"""
            <div class="intro-heading">
                <a class="preview-back" href="{escape(back_href)}">Terug</a>
                <h1>Over het onderzoek</h1>
                <p>
                    In dit onderzoek beoordeel je verschillende versies van
                    korte grappen. Je krijgt 5 groepen met elk 8 versies.
                    Deelname duurt ongeveer 15 minuten.
                </p>
            </div>
            <section class="intro-section">
                <h2>Freek de Jonge</h2>
                <p>
                    Bij iedere versie vragen we ook in hoeverre de tekst op
                    Freek de Jonge lijkt. Daarmee bedoelen we zowel stijl als
                    onderwerp. De teksten zijn experimenteel en niet door
                    Freek de Jonge geschreven.
                </p>
            </section>
            <section class="intro-section intro-privacy">
                <h2>Privacy en je onderzoekslink</h2>
                <p>
                    We vragen geen naam of contactgegevens. Je antwoorden
                    worden gekoppeld aan de unieke code in je onderzoekslink.
                    Deel deze persoonlijke link daarom niet met anderen.
                </p>
            </section>
            """,
            unsafe_allow_html=True,
        )

        with st.form(
            key=f"participant_profile_{session.session_id}",
            clear_on_submit=False,
            border=False,
        ):
            st.markdown("## Over jou")
            age = st.number_input(
                "Wat is je leeftijd in hele jaren?",
                min_value=1,
                max_value=120,
                value=None,
                step=1,
                placeholder="Bijvoorbeeld 34",
            )
            familiarity = st.radio(
                "Hoe goed ken je het werk van Freek de Jonge?",
                options=[1, 2, 3, 4, 5],
                index=None,
                horizontal=True,
            )
            st.markdown(
                """
                <div class="scale-endpoints">
                    <span>1 = Helemaal niet bekend</span>
                    <span>5 = Zeer bekend</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            consent = st.checkbox(
                "Ik heb bovenstaande informatie gelezen en neem vrijwillig "
                "deel aan dit onderzoek."
            )
            submitted = st.form_submit_button(
                "Verder",
                type="primary",
                icon=":material/arrow_forward:",
            )

        if submitted:
            try:
                profile = validate_profile(
                    age=age,
                    freek_familiarity=familiarity,
                    consent=consent,
                )
            except ProfileValidationError as error:
                messages = "\n".join(
                    f"- {message}" for message in error.messages
                )
                st.error(f"Controleer de verplichte velden:\n\n{messages}")
            else:
                st.session_state[f"profile:{session.session_id}"] = {
                    "age": profile.age,
                    "freek_familiarity": profile.freek_familiarity,
                    "consent": profile.consent,
                }
                st.query_params["page"] = "profile-complete"
                st.rerun()

    render_footer()


def render_profile_complete(session: ParticipantSession) -> None:
    profile = st.session_state.get(f"profile:{session.session_id}")
    if profile is None:
        render_participant_intro(session)
        return

    render_header()
    with st.container(key="profile_complete"):
        st.markdown(
            """
            <div class="completion-mark" aria-hidden="true"></div>
            <h1>Je gegevens zijn gecontroleerd</h1>
            <p>Bedankt voor het invullen van de eerste vragen.</p>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "Verder",
            type="primary",
            disabled=True,
            icon=":material/arrow_forward:",
        )
    render_footer()


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
    session_registry = load_sessions(
        {group.group_id for group in stimulus_groups}
    )
except (StimulusValidationError, SessionValidationError) as error:
    st.error(f"Configuratiecontrole mislukt: {error}")
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

        .study-session-note {
            border-left: 3px solid var(--study-coral);
            color: var(--study-muted);
            font-size: 0.94rem;
            line-height: 1.55;
            margin: -0.5rem 0 2rem;
            max-width: 34rem;
            padding-left: 1rem;
        }

        .access-content {
            min-height: 620px;
        }

        .st-key-participant_start {
            margin-left: clamp(1.5rem, 14vw, 14rem);
            max-width: 50rem;
            min-height: 620px;
            padding: 9rem 3rem 5rem;
        }

        .st-key-participant_start h1 {
            color: var(--study-text);
            font-size: 2.75rem;
            font-weight: 700;
            line-height: 1.16;
            margin: 0;
            max-width: 48rem;
        }

        .st-key-participant_start [data-testid="stButton"] {
            width: 22rem;
        }

        .st-key-participant_start [data-testid="stButton"] button {
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 650;
            min-height: 3.5rem;
            width: 100%;
        }

        .assignment-fingerprint {
            display: none;
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

        .st-key-participant_intro,
        .st-key-profile_complete {
            margin: 0 auto;
            max-width: 48rem;
            padding: 4.5rem 2rem 5rem;
        }

        .intro-heading {
            margin-bottom: 2.75rem;
        }

        .intro-heading h1,
        .st-key-profile_complete h1 {
            color: var(--study-text);
            font-size: 2.4rem;
            line-height: 1.2;
            margin: 1rem 0 1rem;
        }

        .intro-heading p,
        .st-key-profile_complete p {
            color: var(--study-muted);
            font-size: 1.05rem;
            line-height: 1.7;
            margin: 0;
        }

        .intro-section {
            border-top: 1px solid var(--study-border);
            padding: 2rem 0;
        }

        .intro-section h2,
        .st-key-participant_intro [data-testid="stForm"] h2 {
            color: var(--study-text);
            font-size: 1.25rem;
            line-height: 1.4;
            margin: 0 0 0.7rem;
        }

        .intro-section p {
            color: var(--study-muted);
            font-size: 1rem;
            line-height: 1.7;
            margin: 0;
        }

        .intro-privacy {
            border-left: 3px solid var(--study-coral);
            padding-left: 1.25rem;
        }

        .st-key-participant_intro [data-testid="stForm"] {
            border-top: 1px solid var(--study-border);
            margin-top: 0.5rem;
            padding-top: 2rem;
        }

        .st-key-participant_intro [data-testid="stNumberInput"] {
            max-width: 18rem;
        }

        .st-key-participant_intro [data-testid="stRadio"] {
            margin-top: 1rem;
        }

        .scale-endpoints {
            color: var(--study-muted);
            display: flex;
            font-size: 0.82rem;
            justify-content: space-between;
            margin: -0.5rem 0 1.5rem;
            max-width: 28rem;
        }

        .st-key-participant_intro [data-testid="stFormSubmitButton"] button,
        .st-key-profile_complete [data-testid="stButton"] button {
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 650;
            min-height: 3.25rem;
            min-width: 10rem;
        }

        .completion-mark {
            border: 3px solid var(--study-green);
            border-radius: 50%;
            height: 3rem;
            margin-bottom: 2rem;
            position: relative;
            width: 3rem;
        }

        .completion-mark::after {
            border-bottom: 3px solid var(--study-green);
            border-right: 3px solid var(--study-green);
            content: "";
            height: 0.9rem;
            left: 1.05rem;
            position: absolute;
            top: 0.55rem;
            transform: rotate(45deg);
            width: 0.48rem;
        }

        .st-key-profile_complete [data-testid="stButton"] {
            margin-top: 2rem;
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

            .st-key-participant_start {
                margin-left: 0;
                min-height: 560px;
                padding: 5rem 1.25rem 3rem;
            }

            .st-key-participant_start h1 {
                font-size: 2.1rem;
            }

            .st-key-participant_start [data-testid="stButton"] {
                width: 100%;
            }

            .study-footer {
                min-height: 92px;
                padding: 0 1.25rem;
            }

            .st-key-stimulus_preview {
                padding: 3rem 1.25rem 4rem;
            }

            .st-key-participant_intro,
            .st-key-profile_complete {
                padding: 3rem 1.25rem 4rem;
            }

            .preview-heading h1 {
                font-size: 2rem;
            }

            .intro-heading h1,
            .st-key-profile_complete h1 {
                font-size: 2rem;
            }

            .scale-endpoints {
                gap: 1rem;
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

session_access = resolve_session(st.query_params.get("session"), session_registry)
if session_access.status is not SessionAccessStatus.VALID:
    render_access_state(session_access.status)
    st.stop()

participant_session = session_access.session
assert participant_session is not None
participant_assignment = build_assignment(participant_session, stimulus_groups)
page = st.query_params.get("page")
if page == "intro":
    render_participant_intro(participant_session)
elif page == "profile-complete":
    render_profile_complete(participant_session)
else:
    render_participant_start(
        participant_session,
        assignment_fingerprint(participant_assignment),
    )
