import os
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st

from app.assignment import (
    ParticipantAssignment,
    assignment_fingerprint,
    build_assignment,
)
from app.config import STUDY_VERSION
from app.health import health_snapshot
from app.participant import ProfileValidationError, validate_profile
from app.ratings import (
    DisplayedVariant,
    GroupRatingValidationError,
    build_displayed_variants,
    validate_group_response,
)
from app.sessions import (
    ParticipantSession,
    SessionAccessStatus,
    SessionValidationError,
    load_sessions,
    resolve_session,
)
from app.stimuli import JokeGroup, StimulusValidationError, load_stimuli
from app.storage import CSVProgressStorage, ProgressStorageError
from app.storage.csv_storage import DEFAULT_PROGRESS_PATH


st.set_page_config(
    page_title="Onderzoek naar humor en stijl",
    page_icon=":material/rate_review:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

health = health_snapshot()
progress_storage = CSVProgressStorage(
    Path(
        os.environ.get(
            "FREEK_STUDY_PROGRESS_PATH",
            str(DEFAULT_PROGRESS_PATH),
        )
    )
)
SCROLL_TO_TOP_KEY = "navigation:scroll_to_top"
SCROLL_REQUEST_COUNTER_KEY = "navigation:scroll_request_counter"


def request_scroll_to_top() -> None:
    request_number = (
        st.session_state.get(SCROLL_REQUEST_COUNTER_KEY, 0) + 1
    )
    st.session_state[SCROLL_REQUEST_COUNTER_KEY] = request_number
    st.session_state[SCROLL_TO_TOP_KEY] = request_number


def apply_requested_scroll() -> None:
    request_number = st.session_state.pop(SCROLL_TO_TOP_KEY, None)
    if request_number is None:
        return

    st.html(
        f"""
        <script>
            const requestNumber = {request_number};
            let attempts = 0;
            const scrollToTop = () => {{
                const parentDocument = window.parent.document;
                const scrollTargets = [
                    parentDocument.querySelector('[data-testid="stMain"]'),
                    parentDocument.querySelector(
                        '[data-testid="stAppViewContainer"]'
                    ),
                    parentDocument.scrollingElement,
                    parentDocument.documentElement,
                    parentDocument.body
                ].filter(Boolean);

                scrollTargets.forEach((target) => {{
                    target.scrollTop = 0;
                    target.scrollLeft = 0;
                }});
                window.parent.scrollTo(0, 0);

                attempts += 1;
                if (attempts < 30) {{
                    window.parent.setTimeout(scrollToTop, 50);
                }}
            }};
            window.parent.requestAnimationFrame(() => {{
                window.parent.requestAnimationFrame(scrollToTop);
            }});
        </script>
        """,
        unsafe_allow_javascript=True,
    )


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


def render_save_status(session: ParticipantSession) -> None:
    if st.session_state.get(f"saved_at:{session.session_id}") is None:
        return
    st.markdown(
        """
        <div class="save-status">
            <span class="save-status-mark" aria-hidden="true"></span>
            <span>Opgeslagen</span>
        </div>
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


def render_participant_intro(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
) -> None:
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
                persist_progress(
                    session,
                    assignment,
                    current_page="profile-complete",
                )
                st.query_params["page"] = "profile-complete"
                st.rerun()

    render_footer()


def render_profile_complete(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
) -> None:
    profile = st.session_state.get(f"profile:{session.session_id}")
    if profile is None:
        render_participant_intro(session, assignment)
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
        if st.button(
            "Verder",
            type="primary",
            icon=":material/arrow_forward:",
        ):
            persist_progress(
                session,
                assignment,
                current_page="group-1",
            )
            request_scroll_to_top()
            st.query_params["page"] = "group-1"
            st.rerun()
    render_footer()


def group_response_key(session_id: str, group_id: str) -> str:
    return f"group_response:{session_id}:{group_id}"


def group_draft_key(session_id: str, group_id: str) -> str:
    return f"group_draft:{session_id}:{group_id}"


def rating_widget_key(
    session_id: str,
    variant_id: str,
    dimension: str,
) -> str:
    return f"rating:{session_id}:{variant_id}:{dimension}"


def collect_progress_state(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
) -> tuple[
    dict[str, object] | None,
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
]:
    profile = st.session_state.get(f"profile:{session.session_id}")
    responses: dict[str, dict[str, object]] = {}
    drafts: dict[str, dict[str, object]] = {}
    for assigned_group in assignment.groups:
        group_id = assigned_group.group_id
        response = st.session_state.get(
            group_response_key(session.session_id, group_id)
        )
        draft = st.session_state.get(
            group_draft_key(session.session_id, group_id)
        )
        if response is not None:
            responses[group_id] = response
        if draft is not None:
            drafts[group_id] = draft
    return profile, responses, drafts


def persist_progress(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    *,
    current_page: str,
) -> None:
    profile, responses, drafts = collect_progress_state(
        session,
        assignment,
    )
    try:
        saved = progress_storage.save_progress(
            session_id=session.session_id,
            study_version=STUDY_VERSION,
            is_test=session.is_test,
            current_page=current_page,
            profile=profile,
            responses=responses,
            drafts=drafts,
        )
    except ProgressStorageError:
        st.error(
            "Je voortgang kon niet veilig worden opgeslagen. "
            "Probeer het opnieuw voordat je verdergaat."
        )
        st.stop()
    st.session_state[f"saved_at:{session.session_id}"] = (
        saved.updated_at.isoformat()
    )


def hydrate_progress(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
) -> str | None:
    hydrated_key = f"progress_hydrated:{session.session_id}"
    if st.session_state.get(hydrated_key):
        return None

    try:
        saved = progress_storage.load_progress(session.session_id)
    except ProgressStorageError:
        st.error(
            "De opgeslagen voortgang is beschadigd en kan niet veilig "
            "worden geopend."
        )
        st.stop()

    st.session_state[hydrated_key] = True
    if saved is None:
        return None
    if saved.study_version != STUDY_VERSION or saved.is_test != session.is_test:
        st.error(
            "De opgeslagen voortgang hoort bij een andere onderzoeksversie."
        )
        st.stop()

    assigned_group_ids = {
        assigned_group.group_id for assigned_group in assignment.groups
    }
    if (
        set(saved.responses) - assigned_group_ids
        or set(saved.drafts) - assigned_group_ids
    ):
        st.error(
            "De opgeslagen voortgang past niet bij deze onderzoekslink."
        )
        st.stop()

    allowed_pages = {
        "intro",
        "profile-complete",
        "groups-complete",
        *(
            f"group-{group_index + 1}"
            for group_index in range(len(assignment.groups))
        ),
    }
    if saved.current_page not in allowed_pages:
        st.error("De opgeslagen positie in het onderzoek is niet geldig.")
        st.stop()

    if saved.profile is not None:
        try:
            validate_profile(
                age=saved.profile.get("age"),
                freek_familiarity=saved.profile.get("freek_familiarity"),
                consent=saved.profile.get("consent", False),
            )
        except ProfileValidationError:
            st.error("De opgeslagen deelnemersgegevens zijn niet geldig.")
            st.stop()
        st.session_state[f"profile:{session.session_id}"] = saved.profile

    for group_id, response in saved.responses.items():
        st.session_state[
            group_response_key(session.session_id, group_id)
        ] = response
    for group_id, draft in saved.drafts.items():
        st.session_state[
            group_draft_key(session.session_id, group_id)
        ] = draft
    st.session_state[f"saved_at:{session.session_id}"] = (
        saved.updated_at.isoformat()
    )
    return saved.current_page


def restore_group_widgets(
    session: ParticipantSession,
    joke_group: JokeGroup,
    displayed_variants: tuple[DisplayedVariant, ...],
) -> None:
    draft = st.session_state.get(
        group_draft_key(session.session_id, joke_group.group_id)
    )
    response = st.session_state.get(
        group_response_key(session.session_id, joke_group.group_id)
    )

    if draft is not None:
        saved_ratings = draft["ratings"]
        saved_comment = draft["comment"]
    elif response is not None:
        saved_ratings = {
            rating["variant_id"]: rating for rating in response["ratings"]
        }
        saved_comment = response["comment"]
    else:
        return

    for variant in displayed_variants:
        saved_rating = saved_ratings[variant.variant_id]
        for dimension in ("funniness", "freek_similarity"):
            st.session_state.setdefault(
                rating_widget_key(
                    session.session_id,
                    variant.variant_id,
                    dimension,
                ),
                saved_rating[dimension] or 0,
            )
    st.session_state.setdefault(
        f"group_comment:{session.session_id}:{joke_group.group_id}",
        saved_comment,
    )


def store_group_draft(
    session: ParticipantSession,
    joke_group: JokeGroup,
    raw_ratings: dict[str, dict[str, int | None]],
    comment: str,
) -> None:
    st.session_state[
        group_draft_key(session.session_id, joke_group.group_id)
    ] = {
        "group_id": joke_group.group_id,
        "ratings": raw_ratings,
        "comment": comment,
    }


def render_rating_group(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    groups: tuple[JokeGroup, ...],
    group_index: int,
) -> None:
    profile = st.session_state.get(f"profile:{session.session_id}")
    if profile is None:
        render_participant_intro(session, assignment)
        return

    assigned_group = assignment.groups[group_index]
    joke_group = next(
        group for group in groups if group.group_id == assigned_group.group_id
    )
    displayed_variants = build_displayed_variants(
        assigned_group,
        joke_group,
    )
    restore_group_widgets(session, joke_group, displayed_variants)
    group_number = group_index + 1
    group_count = len(assignment.groups)

    render_header()
    with st.container(key="rating_group"):
        st.progress(
            group_number / group_count,
            text=f"Jokegroep {group_number} van {group_count}",
        )
        render_save_status(session)
        st.markdown(
            f"""
            <div class="rating-heading">
                <h1>{escape(joke_group.title)}</h1>
                <p>
                    Beoordeel iedere versie op grappigheid en op de mate
                    waarin de tekst op Freek de Jonge lijkt.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        raw_ratings: dict[str, dict[str, int | None]] = {}
        with st.container(
            key=f"group_rating_{session.session_id}_{joke_group.group_id}",
            border=False,
        ):
            for variant in displayed_variants:
                with st.container(
                    key=(
                        f"rating_variant_{joke_group.group_id}_"
                        f"{variant.display_label}"
                    )
                ):
                    st.markdown(
                        f"""
                        <div class="rating-variant-copy">
                            <h2>Versie {escape(variant.display_label)}</h2>
                            <p>{escape(variant.text)}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    funniness_column, freek_column = st.columns(
                        2,
                        gap="large",
                    )
                    with funniness_column:
                        funniness_value = st.select_slider(
                            "Grappigheid",
                            options=[0, 1, 2, 3, 4, 5],
                            format_func=lambda value: (
                                "Kies" if value == 0 else str(value)
                            ),
                            key=rating_widget_key(
                                session.session_id,
                                variant.variant_id,
                                "funniness",
                            ),
                        )
                        st.markdown(
                            """
                            <div class="rating-endpoints">
                                <span>Helemaal niet grappig</span>
                                <span>Heel grappig</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with freek_column:
                        freek_value = st.select_slider(
                            "Lijkt op Freek de Jonge",
                            options=[0, 1, 2, 3, 4, 5],
                            format_func=lambda value: (
                                "Kies" if value == 0 else str(value)
                            ),
                            key=rating_widget_key(
                                session.session_id,
                                variant.variant_id,
                                "freek_similarity",
                            ),
                        )
                        st.markdown(
                            """
                            <div class="rating-endpoints">
                                <span>Helemaal niet</span>
                                <span>Heel erg</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    raw_ratings[variant.variant_id] = {
                        "funniness": (
                            None if funniness_value == 0 else funniness_value
                        ),
                        "freek_similarity": (
                            None if freek_value == 0 else freek_value
                        ),
                    }

            comment = st.text_area(
                "Opmerking over deze groep (optioneel)",
                max_chars=1000,
                height=120,
                key=(
                    f"group_comment:{session.session_id}:"
                    f"{joke_group.group_id}"
                ),
            )
            previous_column, next_column = st.columns(2, gap="medium")
            with previous_column:
                previous_clicked = False
                if group_index > 0:
                    previous_clicked = st.button(
                        "Vorige groep",
                        icon=":material/arrow_back:",
                        use_container_width=True,
                        key=f"previous_group_{joke_group.group_id}",
                    )
            with next_column:
                next_clicked = st.button(
                    (
                        "Groepen afronden"
                        if group_number == group_count
                        else "Volgende groep"
                    ),
                    type="primary",
                    icon=":material/arrow_forward:",
                    use_container_width=True,
                    key=f"next_group_{joke_group.group_id}",
                )

        draft_payload = {
            "group_id": joke_group.group_id,
            "ratings": raw_ratings,
            "comment": comment,
        }
        existing_draft = st.session_state.get(
            group_draft_key(session.session_id, joke_group.group_id)
        )
        response = st.session_state.get(
            group_response_key(session.session_id, joke_group.group_id)
        )
        response_ratings = (
            {
                rating["variant_id"]: {
                    "funniness": rating["funniness"],
                    "freek_similarity": rating["freek_similarity"],
                }
                for rating in response["ratings"]
            }
            if response is not None
            else None
        )
        matches_response = (
            response is not None
            and response_ratings == raw_ratings
            and response["comment"] == comment.strip()
        )
        has_draft_content = any(
            value is not None
            for rating in raw_ratings.values()
            for value in rating.values()
        ) or bool(comment.strip())

        progress_changed = False
        if matches_response or not has_draft_content:
            if existing_draft is not None:
                st.session_state.pop(
                    group_draft_key(
                        session.session_id,
                        joke_group.group_id,
                    ),
                    None,
                )
                progress_changed = True
        elif existing_draft != draft_payload:
            store_group_draft(
                session,
                joke_group,
                raw_ratings,
                comment,
            )
            progress_changed = True

        if progress_changed:
            persist_progress(
                session,
                assignment,
                current_page=f"group-{group_number}",
            )

        if previous_clicked:
            persist_progress(
                session,
                assignment,
                current_page=f"group-{group_index}",
            )
            request_scroll_to_top()
            st.query_params["page"] = f"group-{group_index}"
            st.rerun()

        if next_clicked:
            try:
                response = validate_group_response(
                    group_id=joke_group.group_id,
                    displayed_variants=displayed_variants,
                    raw_ratings=raw_ratings,
                    comment=comment,
                )
            except GroupRatingValidationError as error:
                messages = "\n".join(
                    f"- {message}" for message in error.messages
                )
                st.error(
                    "Beantwoord beide schalen voor iedere versie:"
                    f"\n\n{messages}"
                )
            else:
                st.session_state[
                    group_response_key(
                        session.session_id,
                        joke_group.group_id,
                    )
                ] = {
                    "group_id": response.group_id,
                    "ratings": [
                        {
                            "display_label": rating.display_label,
                            "display_position": rating.display_position,
                            "variant_id": rating.variant_id,
                            "funniness": rating.funniness,
                            "freek_similarity": rating.freek_similarity,
                        }
                        for rating in response.ratings
                    ],
                    "comment": response.comment,
                }
                st.session_state.pop(
                    group_draft_key(
                        session.session_id,
                        joke_group.group_id,
                    ),
                    None,
                )
                next_page = (
                    "groups-complete"
                    if group_number == group_count
                    else f"group-{group_number + 1}"
                )
                persist_progress(
                    session,
                    assignment,
                    current_page=next_page,
                )
                request_scroll_to_top()
                st.query_params["page"] = next_page
                st.rerun()
    render_footer()
    apply_requested_scroll()


def render_groups_complete(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    groups: tuple[JokeGroup, ...],
) -> None:
    for group_index, assigned_group in enumerate(assignment.groups):
        response = st.session_state.get(
            group_response_key(session.session_id, assigned_group.group_id)
        )
        if response is None:
            render_rating_group(
                session,
                assignment,
                groups,
                group_index,
            )
            return

    render_header()
    with st.container(key="rating_complete"):
        st.progress(1.0, text="5 van 5 jokegroepen beoordeeld")
        render_save_status(session)
        st.markdown(
            """
            <div class="completion-mark" aria-hidden="true"></div>
            <h1>Alle jokegroepen zijn beoordeeld</h1>
            <p>Bedankt. Je antwoorden zijn klaar voor de laatste controle.</p>
            """,
            unsafe_allow_html=True,
        )
        back_column, continue_column = st.columns(2, gap="medium")
        with back_column:
            if st.button(
                "Terug naar laatste groep",
                icon=":material/arrow_back:",
                use_container_width=True,
            ):
                persist_progress(
                    session,
                    assignment,
                    current_page=f"group-{len(assignment.groups)}",
                )
                request_scroll_to_top()
                st.query_params["page"] = f"group-{len(assignment.groups)}"
                st.rerun()
        with continue_column:
            st.button(
                "Antwoorden controleren",
                type="primary",
                disabled=True,
                icon=":material/fact_check:",
                use_container_width=True,
            )
    render_footer()
    apply_requested_scroll()


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
            margin-right: 0.75rem;
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
        .st-key-profile_complete,
        .st-key-rating_group,
        .st-key-rating_complete {
            margin: 0 auto;
            max-width: 48rem;
            padding: 4.5rem 2rem 5rem;
        }

        .st-key-rating_group {
            max-width: 68rem;
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

        .rating-heading {
            margin-bottom: 2.75rem;
            max-width: 48rem;
        }

        .st-key-rating_group [data-testid="stProgress"],
        .st-key-rating_complete [data-testid="stProgress"] {
            margin-bottom: 2.25rem;
        }

        .st-key-rating_group [data-testid="stProgress"] p,
        .st-key-rating_complete [data-testid="stProgress"] p {
            color: var(--study-muted);
            font-size: 0.88rem;
            font-weight: 650;
        }

        .save-status {
            align-items: center;
            color: var(--study-muted);
            display: flex;
            font-size: 0.82rem;
            gap: 0.5rem;
            margin: -1.5rem 0 2rem;
        }

        .save-status-mark {
            background: var(--study-green);
            border-radius: 50%;
            display: inline-block;
            height: 0.45rem;
            width: 0.45rem;
        }

        .rating-context {
            color: var(--study-green);
            font-size: 0.9rem;
            font-weight: 700;
            margin: 0 0 0.7rem;
        }

        .rating-heading h1,
        .st-key-rating_complete h1 {
            color: var(--study-text);
            font-size: 2.4rem;
            line-height: 1.2;
            margin: 0 0 1rem;
        }

        .rating-heading > p:last-child,
        .st-key-rating_complete > div p {
            color: var(--study-muted);
            font-size: 1.02rem;
            line-height: 1.65;
            margin: 0;
        }

        .st-key-rating_group [class*="st-key-group_rating_"] {
            border-top: 2px solid var(--study-green);
        }

        .st-key-rating_group [class*="st-key-rating_variant_"] {
            border-bottom: 1px solid var(--study-border);
            padding: 2rem 0 2.25rem;
        }

        .st-key-rating_group
        [class*="st-key-rating_variant_"]
        [data-testid="stHorizontalBlock"] {
            gap: 4rem;
        }

        .rating-variant-copy {
            margin-bottom: 1.35rem;
        }

        .rating-variant-copy h2 {
            color: var(--study-green);
            font-size: 1rem;
            font-weight: 750;
            line-height: 1.4;
            margin: 0 0 0.55rem;
        }

        .rating-variant-copy p {
            color: var(--study-text);
            font-size: 1.08rem;
            line-height: 1.65;
            margin: 0;
            max-width: 58rem;
        }

        .st-key-rating_group [data-testid="stSelectSlider"] label p {
            font-size: 0.92rem;
            font-weight: 700;
        }

        .rating-endpoints {
            color: var(--study-muted);
            display: flex;
            font-size: 0.76rem;
            justify-content: space-between;
            line-height: 1.35;
            margin-top: -0.55rem;
        }

        .rating-endpoints span {
            max-width: 48%;
        }

        .rating-endpoints span:last-child {
            text-align: right;
        }

        .st-key-rating_group [data-testid="stTextArea"] {
            border-top: 1px solid var(--study-border);
            margin-top: 1.5rem;
            padding-top: 2rem;
        }

        .st-key-rating_group [data-testid="stButton"] button,
        .st-key-rating_complete [data-testid="stButton"] button {
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 650;
            min-height: 3.25rem;
        }

        .st-key-rating_group [data-testid="stButton"] {
            margin-top: 1rem;
        }

        .st-key-rating_complete [data-testid="stHorizontalBlock"] {
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
            .st-key-profile_complete,
            .st-key-rating_group,
            .st-key-rating_complete {
                padding: 3rem 1.25rem 4rem;
            }

            .preview-heading h1 {
                font-size: 2rem;
            }

            .intro-heading h1,
            .st-key-profile_complete h1,
            .rating-heading h1,
            .st-key-rating_complete h1 {
                font-size: 2rem;
            }

            .st-key-rating_group [data-testid="stHorizontalBlock"] {
                flex-direction: column;
                gap: 1.5rem;
            }

            .st-key-rating_group
            [class*="st-key-rating_variant_"]
            [data-testid="stHorizontalBlock"] {
                gap: 1.5rem;
            }

            .st-key-rating_group [data-testid="stColumn"] {
                width: 100%;
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
resume_page = hydrate_progress(
    participant_session,
    participant_assignment,
)
page = st.query_params.get("page")
if page is None and resume_page is not None:
    st.query_params["page"] = resume_page
    st.rerun()
group_pages = {
    f"group-{group_index + 1}": group_index
    for group_index in range(len(participant_assignment.groups))
}
if page == "intro":
    render_participant_intro(
        participant_session,
        participant_assignment,
    )
elif page == "profile-complete":
    render_profile_complete(participant_session, participant_assignment)
elif page in group_pages:
    render_rating_group(
        participant_session,
        participant_assignment,
        stimulus_groups,
        group_pages[page],
    )
elif page in {"group-complete", "groups-complete"}:
    render_groups_complete(
        participant_session,
        participant_assignment,
        stimulus_groups,
    )
else:
    render_participant_start(
        participant_session,
        assignment_fingerprint(participant_assignment),
    )
