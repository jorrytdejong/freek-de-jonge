import json
import os
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from app.admin import (
    ADMIN_SCOPES,
    ADMIN_STATUSES,
    SCOPE_REAL,
    STATUS_SUBMITTED,
    build_dimension_summary,
    build_group_summary,
    build_overview,
    build_variant_summary,
    filter_export_tables,
    filter_submission_status,
    verify_admin_password,
)
from app.assignment import (
    AssignedGroup,
    ParticipantAssignment,
    assignment_fingerprint,
    build_assignment,
)
from app.config import STUDY_VERSION
from app.exports import (
    PARTICIPANT_COLUMNS,
    RATING_COLUMNS,
    ExportValidationError,
    build_export_tables,
    rows_to_csv,
)
from app.health import health_snapshot
from app.participant import ProfileValidationError, validate_profile
from app.ratings import (
    DisplayedVariant,
    GroupRatingValidationError,
    build_displayed_variants,
    validate_group_response,
)
from app.sessions import (
    DEFAULT_SESSIONS_PATH,
    ParticipantSession,
    SessionAccessStatus,
    SessionValidationError,
    load_sessions,
    load_sessions_csv_text,
    resolve_session,
)
from app.stimuli import JokeGroup, StimulusValidationError, load_stimuli
from app.storage import (
    AlreadySubmittedError,
    ProgressStorageError,
    StorageConfigurationError,
    create_progress_storage,
)

st.set_page_config(
    page_title="Onderzoek naar humor en stijl",
    page_icon=":material/rate_review:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

health = health_snapshot()


def configured_secrets() -> dict[str, object]:
    try:
        return dict(st.secrets)
    except StreamlitSecretNotFoundError:
        return {}


try:
    progress_storage = create_progress_storage(secrets=configured_secrets())
except (ProgressStorageError, StorageConfigurationError) as error:
    st.error(f"Opslagconfiguratie mislukt: {error}")
    st.stop()


def configured_admin_password() -> str | None:
    environment_password = os.environ.get("FREEK_STUDY_ADMIN_PASSWORD")
    if environment_password:
        return environment_password
    try:
        secret_password = st.secrets.get("admin_password")
    except StreamlitSecretNotFoundError:
        return None
    return str(secret_password) if secret_password else None


def final_comment_key(session_id: str) -> str:
    return f"final_comment:{session_id}"


def submissions_key(session_id: str) -> str:
    return f"submissions:{session_id}"


def navigate_to_page(session: ParticipantSession, page: str) -> None:
    if os.environ.get("FREEK_STUDY_IN_PROCESS_NAVIGATION") == "true":
        st.query_params["page"] = page
        st.rerun()

    query = urlencode(
        {
            "session": session.session_id,
            "page": page,
        }
    )
    destination = f"?{query}#study-page-top"
    st.html(
        f"""
        <script>
            if ('scrollRestoration' in window.history) {{
                window.history.scrollRestoration = 'manual';
            }}
            window.location.replace({json.dumps(destination)});
        </script>
        """,
        unsafe_allow_javascript=True,
    )
    st.stop()


def render_header() -> None:
    st.markdown(
        """
        <header class="study-header" id="study-page-top">
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
    session_status = (
        "Testsessie is geldig." if session.is_test else ("Onderzoekslink is geldig.")
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
            navigate_to_page(session, "intro")
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
                messages = "\n".join(f"- {message}" for message in error.messages)
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
                navigate_to_page(session, "profile-complete")

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
            navigate_to_page(session, "group-1")
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


def validate_response_record(
    assigned_group: AssignedGroup,
    joke_group: JokeGroup,
    response: dict[str, object],
) -> None:
    displayed_variants = build_displayed_variants(
        assigned_group,
        joke_group,
    )
    ratings = response.get("ratings")
    if (
        response.get("group_id") != assigned_group.group_id
        or not isinstance(ratings, list)
        or len(ratings) != len(displayed_variants)
        or not isinstance(response.get("comment"), str)
    ):
        raise ValueError("Invalid response structure.")

    raw_ratings: dict[str, dict[str, int | None]] = {}
    for displayed, rating in zip(displayed_variants, ratings, strict=True):
        if (
            not isinstance(rating, dict)
            or rating.get("variant_id") != displayed.variant_id
            or rating.get("display_label") != displayed.display_label
            or rating.get("display_position") != displayed.display_position
        ):
            raise ValueError("Invalid response mapping.")
        raw_ratings[displayed.variant_id] = {
            "funniness": rating.get("funniness"),
            "freek_similarity": rating.get("freek_similarity"),
        }

    validate_group_response(
        group_id=assigned_group.group_id,
        displayed_variants=displayed_variants,
        raw_ratings=raw_ratings,
        comment=response["comment"],
    )


def validate_draft_record(
    assigned_group: AssignedGroup,
    draft: dict[str, object],
) -> None:
    ratings = draft.get("ratings")
    if (
        draft.get("group_id") != assigned_group.group_id
        or not isinstance(ratings, dict)
        or set(ratings) != set(assigned_group.variant_ids)
        or not isinstance(draft.get("comment"), str)
    ):
        raise ValueError("Invalid draft structure.")
    for values in ratings.values():
        if not isinstance(values, dict):
            raise ValueError("Invalid draft rating.")
        for dimension in ("funniness", "freek_similarity"):
            value = values.get(dimension)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= 5
            ):
                raise ValueError("Invalid draft value.")


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
        draft = st.session_state.get(group_draft_key(session.session_id, group_id))
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
            final_comment=st.session_state.get(
                final_comment_key(session.session_id),
                "",
            ),
            submissions=tuple(
                st.session_state.get(
                    submissions_key(session.session_id),
                    (),
                )
            ),
        )
    except AlreadySubmittedError:
        st.error("Deze onderzoekslink is al definitief ingediend.")
        st.stop()
    except ProgressStorageError:
        st.error(
            "Je voortgang kon niet veilig worden opgeslagen. "
            "Probeer het opnieuw voordat je verdergaat."
        )
        st.stop()
    st.session_state[f"saved_at:{session.session_id}"] = saved.updated_at.isoformat()


def submit_progress(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    groups: tuple[JokeGroup, ...],
) -> None:
    profile, responses, _ = collect_progress_state(session, assignment)
    if profile is None or len(responses) != len(assignment.groups):
        st.error("Niet alle verplichte antwoorden zijn compleet.")
        st.stop()
    try:
        for assigned_group in assignment.groups:
            joke_group = next(
                group for group in groups if group.group_id == assigned_group.group_id
            )
            validate_response_record(
                assigned_group,
                joke_group,
                responses[assigned_group.group_id],
            )
    except (
        GroupRatingValidationError,
        KeyError,
        StopIteration,
        ValueError,
    ):
        st.error("Een opgeslagen jokegroep is niet volledig of niet geldig.")
        st.stop()

    final_comment = st.session_state.get(
        final_comment_key(session.session_id),
        "",
    ).strip()
    try:
        saved = progress_storage.submit_response(
            session_id=session.session_id,
            study_version=STUDY_VERSION,
            is_test=session.is_test,
            profile=profile,
            responses=responses,
            final_comment=final_comment,
        )
    except AlreadySubmittedError:
        st.error("Deze onderzoekslink is al definitief ingediend.")
        st.stop()
    except ProgressStorageError:
        st.error(
            "Je antwoorden konden niet veilig worden ingediend. Probeer het opnieuw."
        )
        st.stop()

    st.session_state[submissions_key(session.session_id)] = list(saved.submissions)
    st.session_state[f"submission_status:{session.session_id}"] = saved.status
    st.session_state[f"saved_at:{session.session_id}"] = saved.updated_at.isoformat()
    for assigned_group in assignment.groups:
        st.session_state.pop(
            group_draft_key(
                session.session_id,
                assigned_group.group_id,
            ),
            None,
        )


def hydrate_progress(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    groups: tuple[JokeGroup, ...],
) -> str | None:
    hydrated_key = f"progress_hydrated:{session.session_id}"
    if st.session_state.get(hydrated_key):
        return None

    try:
        saved = progress_storage.load_progress(session.session_id)
    except ProgressStorageError:
        st.error(
            "De opgeslagen voortgang is beschadigd en kan niet veilig worden geopend."
        )
        st.stop()

    st.session_state[hydrated_key] = True
    if saved is None:
        return None
    if saved.study_version != STUDY_VERSION or saved.is_test != session.is_test:
        st.error("De opgeslagen voortgang hoort bij een andere onderzoeksversie.")
        st.stop()

    assigned_group_ids = {
        assigned_group.group_id for assigned_group in assignment.groups
    }
    if (
        set(saved.responses) - assigned_group_ids
        or set(saved.drafts) - assigned_group_ids
    ):
        st.error("De opgeslagen voortgang past niet bij deze onderzoekslink.")
        st.stop()

    try:
        for assigned_group in assignment.groups:
            joke_group = next(
                group for group in groups if group.group_id == assigned_group.group_id
            )
            response = saved.responses.get(assigned_group.group_id)
            if response is not None:
                validate_response_record(
                    assigned_group,
                    joke_group,
                    response,
                )
            draft = saved.drafts.get(assigned_group.group_id)
            if draft is not None:
                validate_draft_record(assigned_group, draft)
    except (
        GroupRatingValidationError,
        StopIteration,
        ValueError,
    ):
        st.error("De opgeslagen beoordelingen zijn niet geldig.")
        st.stop()

    allowed_pages = {
        "intro",
        "profile-complete",
        "groups-complete",
        "review",
        "debrief",
        *(f"group-{group_index + 1}" for group_index in range(len(assignment.groups))),
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
        st.session_state[group_response_key(session.session_id, group_id)] = response
    for group_id, draft in saved.drafts.items():
        st.session_state[group_draft_key(session.session_id, group_id)] = draft
    st.session_state[final_comment_key(session.session_id)] = saved.final_comment
    st.session_state[submissions_key(session.session_id)] = list(saved.submissions)
    st.session_state[f"submission_status:{session.session_id}"] = saved.status
    if saved.status == "submitted" and not session.is_test:
        st.session_state[f"force_debrief:{session.session_id}"] = True
    st.session_state[f"saved_at:{session.session_id}"] = saved.updated_at.isoformat()
    return (
        "debrief"
        if saved.status == "submitted" and not session.is_test
        else saved.current_page
    )


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
        saved_ratings = {rating["variant_id"]: rating for rating in response["ratings"]}
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
    st.session_state[group_draft_key(session.session_id, joke_group.group_id)] = {
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
    review_edit_key = f"review_edit_group:{session.session_id}"
    returning_to_review = st.session_state.get(review_edit_key) == joke_group.group_id

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
                        f"rating_variant_{joke_group.group_id}_{variant.display_label}"
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
                        "freek_similarity": (None if freek_value == 0 else freek_value),
                    }

            comment = st.text_area(
                "Opmerking over deze groep (optioneel)",
                max_chars=1000,
                height=120,
                key=(f"group_comment:{session.session_id}:{joke_group.group_id}"),
            )
            previous_column, next_column = st.columns(2, gap="medium")
            with previous_column:
                previous_clicked = False
                if group_index > 0 and not returning_to_review:
                    previous_clicked = st.button(
                        "Vorige groep",
                        icon=":material/arrow_back:",
                        use_container_width=True,
                        key=f"previous_group_{joke_group.group_id}",
                    )
            with next_column:
                next_clicked = st.button(
                    (
                        "Terug naar controle"
                        if returning_to_review
                        else (
                            "Groepen afronden"
                            if group_number == group_count
                            else "Volgende groep"
                        )
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
            navigate_to_page(session, f"group-{group_index}")

        if next_clicked:
            try:
                response = validate_group_response(
                    group_id=joke_group.group_id,
                    displayed_variants=displayed_variants,
                    raw_ratings=raw_ratings,
                    comment=comment,
                )
            except GroupRatingValidationError as error:
                messages = "\n".join(f"- {message}" for message in error.messages)
                st.error(f"Beantwoord beide schalen voor iedere versie:\n\n{messages}")
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
                    "review"
                    if returning_to_review or group_number == group_count
                    else f"group-{group_number + 1}"
                )
                if returning_to_review:
                    st.session_state.pop(review_edit_key, None)
                persist_progress(
                    session,
                    assignment,
                    current_page=next_page,
                )
                navigate_to_page(session, next_page)
    render_footer()


def render_group_summary(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    groups: tuple[JokeGroup, ...],
    group_index: int,
    *,
    editable: bool,
) -> None:
    assigned_group = assignment.groups[group_index]
    joke_group = next(
        group for group in groups if group.group_id == assigned_group.group_id
    )
    response = st.session_state[
        group_response_key(session.session_id, assigned_group.group_id)
    ]
    ratings_by_variant = {
        rating["variant_id"]: rating for rating in response["ratings"]
    }
    displayed_variants = build_displayed_variants(
        assigned_group,
        joke_group,
    )

    with st.expander(
        f"Jokegroep {group_index + 1}: {joke_group.title}",
        expanded=False,
    ):
        for variant in displayed_variants:
            rating = ratings_by_variant[variant.variant_id]
            st.markdown(
                f"""
                <div class="review-rating">
                    <div class="review-rating-copy">
                        <strong>Versie {escape(variant.display_label)}</strong>
                        <span>{escape(variant.text)}</span>
                    </div>
                    <div class="review-rating-scores">
                        <span>
                            Grappigheid
                            <strong>{rating["funniness"]}</strong>
                        </span>
                        <span>
                            Lijkt op Freek de Jonge
                            <strong>{rating["freek_similarity"]}</strong>
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        if response["comment"]:
            st.markdown(
                f"""
                <div class="review-comment">
                    <strong>Opmerking bij deze groep</strong>
                    <p>{escape(response["comment"])}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        if editable and st.button(
            f"Bewerk jokegroep {group_index + 1}",
            icon=":material/edit:",
            key=f"edit_review_group_{group_index + 1}",
        ):
            destination = f"group-{group_index + 1}"
            st.session_state[f"review_edit_group:{session.session_id}"] = (
                joke_group.group_id
            )
            persist_progress(
                session,
                assignment,
                current_page=destination,
            )
            navigate_to_page(session, destination)


def first_incomplete_group(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
) -> int | None:
    for group_index, assigned_group in enumerate(assignment.groups):
        if (
            st.session_state.get(
                group_response_key(
                    session.session_id,
                    assigned_group.group_id,
                )
            )
            is None
        ):
            return group_index
    return None


def render_review(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    groups: tuple[JokeGroup, ...],
) -> None:
    incomplete_group = first_incomplete_group(session, assignment)
    if incomplete_group is not None:
        render_rating_group(
            session,
            assignment,
            groups,
            incomplete_group,
        )
        return

    render_header()
    with st.container(key="study_review"):
        st.progress(1.0, text="5 van 5 jokegroepen beoordeeld")
        render_save_status(session)
        st.markdown(
            """
            <div class="review-heading">
                <h1>Controleer je antwoorden</h1>
                <p>
                    Bekijk de vijf jokegroepen voordat je de antwoorden
                    definitief indient.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for group_index in range(len(assignment.groups)):
            render_group_summary(
                session,
                assignment,
                groups,
                group_index,
                editable=True,
            )

        final_comment = st.text_area(
            "Algemene opmerking over het onderzoek (optioneel)",
            max_chars=2000,
            height=140,
            key=final_comment_key(session.session_id),
        )
        saved_comment_key = f"saved_final_comment:{session.session_id}"
        if saved_comment_key not in st.session_state:
            st.session_state[saved_comment_key] = final_comment
        elif st.session_state[saved_comment_key] != final_comment:
            persist_progress(
                session,
                assignment,
                current_page="review",
            )
            st.session_state[saved_comment_key] = final_comment

        back_column, submit_column = st.columns(2, gap="medium")
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
                navigate_to_page(
                    session,
                    f"group-{len(assignment.groups)}",
                )
        with submit_column:
            if st.button(
                "Definitief indienen",
                type="primary",
                icon=":material/send:",
                use_container_width=True,
            ):
                submit_progress(session, assignment, groups)
                navigate_to_page(session, "debrief")
    render_footer()


def render_debrief(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    groups: tuple[JokeGroup, ...],
) -> None:
    submissions = st.session_state.get(
        submissions_key(session.session_id),
        [],
    )
    if not submissions:
        render_review(session, assignment, groups)
        return

    render_header()
    with st.container(key="study_debrief"):
        st.markdown(
            """
            <div class="completion-mark" aria-hidden="true"></div>
            <div class="debrief-heading">
                <h1>Bedankt voor je deelname</h1>
                <p>Je antwoorden zijn veilig ingediend.</p>
            </div>
            <section class="debrief-copy">
                <h2>Over dit onderzoek</h2>
                <p>
                    Met deze studie onderzoeken we hoe verschillende versies
                    van dezelfde grap worden beoordeeld op grappigheid en op
                    gelijkenis met de stijl en onderwerpen van Freek de Jonge.
                    De teksten zijn experimenteel en niet door Freek de Jonge
                    geschreven.
                </p>
            </section>
            """,
            unsafe_allow_html=True,
        )

        if session.is_test:
            st.info(
                f"Testinzending {len(submissions)} is opgeslagen en blijft "
                "herkenbaar als testdata."
            )
            if st.button(
                "Nieuwe testinzending",
                icon=":material/replay:",
            ):
                persist_progress(
                    session,
                    assignment,
                    current_page="review",
                )
                navigate_to_page(session, "review")

        st.markdown("## Ingediende antwoorden")
        for group_index in range(len(assignment.groups)):
            render_group_summary(
                session,
                assignment,
                groups,
                group_index,
                editable=False,
            )
        final_comment = st.session_state.get(
            final_comment_key(session.session_id),
            "",
        )
        if final_comment:
            st.markdown(
                f"""
                <div class="review-comment final-review-comment">
                    <strong>Algemene opmerking</strong>
                    <p>{escape(final_comment)}</p>
                </div>
                """,
                unsafe_allow_html=True,
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


def render_admin_login() -> None:
    render_header()
    with st.container(key="admin_login"):
        st.markdown(
            """
            <div class="admin-heading">
                <p class="admin-context">Beheeromgeving</p>
                <h1>Inloggen</h1>
                <p>Voer het beheerderswachtwoord in om onderzoeksdata te bekijken.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("admin_login_form", border=False):
            candidate = st.text_input(
                "Wachtwoord",
                type="password",
                autocomplete="current-password",
            )
            submitted = st.form_submit_button(
                "Inloggen",
                type="primary",
                icon=":material/login:",
            )
        if submitted:
            expected = configured_admin_password()
            if expected is None:
                st.error("De beheeromgeving is nog niet geconfigureerd.")
            elif verify_admin_password(candidate, expected):
                st.session_state["admin_authenticated"] = True
                st.rerun()
            else:
                st.error("Het wachtwoord is niet correct.")
    render_footer()


def render_admin_session_inspection(
    participants: tuple[dict[str, object], ...],
    ratings: tuple[dict[str, object], ...],
) -> None:
    st.markdown("## Antwoorden bekijken")
    if not participants:
        st.info("Binnen deze selectie zijn geen sessies beschikbaar.")
        return

    participants_by_id = {str(row["session_id"]): row for row in participants}
    selected_session_id = st.selectbox(
        "Sessie",
        options=tuple(participants_by_id),
        format_func=lambda session_id: (
            f"{session_id} | {participants_by_id[session_id]['submission_status']}"
        ),
    )
    participant = participants_by_id[selected_session_id]
    session_ratings = tuple(
        row for row in ratings if row["session_id"] == selected_session_id
    )
    metadata_columns = st.columns(4)
    metadata_columns[0].metric("Status", participant["submission_status"])
    metadata_columns[1].metric(
        "Voltooide groepen",
        f"{participant['completed_group_count']} / {participant['group_count']}",
    )
    metadata_columns[2].metric("Leeftijd", participant["age"] or "-")
    metadata_columns[3].metric(
        "Bekendheid Freek",
        participant["freek_familiarity"] or "-",
    )
    st.caption(
        f"Study version: {participant['study_version']} | "
        f"Assignment: {participant['assignment_fingerprint']} | "
        f"Testdata: {'ja' if participant['is_test'] else 'nee'}"
    )

    group_ids = tuple(dict.fromkeys(str(row["group_id"]) for row in session_ratings))
    for group_id in group_ids:
        group_rows = tuple(
            row for row in session_ratings if row["group_id"] == group_id
        )
        with st.expander(
            f"{group_id} · {group_rows[0]['group_title']}",
            expanded=False,
        ):
            st.dataframe(
                [
                    {
                        "Versie": f"Versie {row['display_label']}",
                        "Variant": row["variant_id"],
                        "Tekst": row["joke_text"],
                        "Grappigheid": row["funniness"],
                        "Freek-gelijkenis": row["freek_similarity"],
                    }
                    for row in group_rows
                ],
                hide_index=True,
                width="stretch",
            )
            group_comment = str(group_rows[0]["group_comment"])
            if group_comment:
                st.markdown("**Opmerking bij deze groep**")
                st.write(group_comment)

    if participant["final_comment"]:
        st.markdown("**Algemene opmerking**")
        st.write(participant["final_comment"])


def render_admin_dashboard(
    groups: tuple[JokeGroup, ...],
    sessions: dict[str, ParticipantSession],
) -> None:
    render_header()
    try:
        records = progress_storage.list_progress()
        all_tables = build_export_tables(records, sessions, groups)
    except (ProgressStorageError, ExportValidationError):
        with st.container(key="admin_dashboard"):
            st.error(
                "De onderzoeksdata kon niet veilig worden gevalideerd. "
                "Er zijn geen statistieken of downloads beschikbaar."
            )
        render_footer()
        return

    with st.container(key="admin_dashboard"):
        heading_column, logout_column = st.columns([5, 1])
        with heading_column:
            st.markdown(
                """
                <div class="admin-heading">
                    <p class="admin-context">Beheeromgeving</p>
                    <h1>Onderzoeksdashboard</h1>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with logout_column:
            if st.button(
                "Uitloggen",
                icon=":material/logout:",
                width="stretch",
            ):
                st.session_state.pop("admin_authenticated", None)
                st.rerun()

        scope = st.segmented_control(
            "Gegevensselectie",
            options=ADMIN_SCOPES,
            default=SCOPE_REAL,
            selection_mode="single",
        )
        status = st.segmented_control(
            "Inzendingsstatus",
            options=ADMIN_STATUSES,
            default=STATUS_SUBMITTED,
            selection_mode="single",
        )
        scoped_tables = filter_export_tables(
            all_tables,
            scope or SCOPE_REAL,
        )
        selected_tables = filter_submission_status(
            scoped_tables,
            status or STATUS_SUBMITTED,
        )
        overview = build_overview(selected_tables)

        metric_columns = st.columns(5)
        metric_columns[0].metric("Sessies", overview.session_count)
        metric_columns[1].metric("Ingediend", overview.submitted_count)
        metric_columns[2].metric("Bezig", overview.in_progress_count)
        metric_columns[3].metric(
            "Voltooide groepen",
            overview.completed_group_count,
        )
        metric_columns[4].metric("Beoordelingen", overview.rating_count)

        st.markdown("## Vergelijking beoordelingsschalen")
        dimension_rows = build_dimension_summary(selected_tables)
        if dimension_rows:
            dimension_columns = st.columns(2)
            dimension_columns[0].metric(
                "Gemiddelde grappigheid",
                f"{overview.mean_funniness:.2f}",
            )
            dimension_columns[1].metric(
                "Gemiddelde Freek-gelijkenis",
                f"{overview.mean_freek_similarity:.2f}",
            )
            st.bar_chart(
                dimension_rows,
                x="Schaal",
                y="Gemiddelde",
                horizontal=True,
            )
        else:
            st.info("Binnen deze selectie zijn nog geen beoordelingen.")

        st.markdown("## Blootstelling per jokegroep")
        group_summary = build_group_summary(
            selected_tables,
            {group.group_id: group.title for group in groups},
        )
        if group_summary:
            st.dataframe(
                group_summary,
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("Binnen deze selectie zijn nog geen voltooide groepen.")

        st.markdown("## Resultaten per interne variant")
        variant_summary = build_variant_summary(selected_tables)
        if variant_summary:
            st.dataframe(
                variant_summary,
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("Binnen deze selectie zijn nog geen variantresultaten.")

        st.markdown("## Downloads")
        st.caption(
            "Downloads volgen de huidige gegevensselectie en gebruiken "
            "exportschema versie 1."
        )
        participant_download, rating_download = st.columns(2)
        with participant_download:
            st.download_button(
                "Deelnemers downloaden",
                data=rows_to_csv(
                    PARTICIPANT_COLUMNS,
                    selected_tables.participants,
                ).encode("utf-8-sig"),
                file_name="participants.csv",
                mime="text/csv",
                icon=":material/download:",
                width="stretch",
            )
        with rating_download:
            st.download_button(
                "Beoordelingen downloaden",
                data=rows_to_csv(
                    RATING_COLUMNS,
                    selected_tables.ratings,
                ).encode("utf-8-sig"),
                file_name="ratings.csv",
                mime="text/csv",
                icon=":material/download:",
                width="stretch",
            )

        render_admin_session_inspection(
            selected_tables.participants,
            selected_tables.ratings,
        )
    render_footer()


def render_admin(
    groups: tuple[JokeGroup, ...],
    sessions: dict[str, ParticipantSession],
) -> None:
    if not st.session_state.get("admin_authenticated", False):
        render_admin_login()
        return
    render_admin_dashboard(groups, sessions)


try:
    stimulus_groups = load_stimuli()
    valid_group_ids = {group.group_id for group in stimulus_groups}
    private_sessions_csv = configured_secrets().get("sessions_csv")
    if private_sessions_csv and "FREEK_STUDY_SESSIONS_PATH" not in os.environ:
        session_registry = load_sessions_csv_text(
            valid_group_ids,
            str(private_sessions_csv),
        )
    else:
        session_registry = load_sessions(
            valid_group_ids,
            Path(
                os.environ.get(
                    "FREEK_STUDY_SESSIONS_PATH",
                    str(DEFAULT_SESSIONS_PATH),
                )
            ),
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
        .st-key-rating_complete,
        .st-key-study_review,
        .st-key-study_debrief,
        .st-key-admin_login,
        .st-key-admin_dashboard {
            margin: 0 auto;
            max-width: 48rem;
            padding: 4.5rem 2rem 5rem;
        }

        .st-key-rating_group,
        .st-key-study_review,
        .st-key-admin_dashboard {
            max-width: 68rem;
        }

        .admin-heading {
            margin-bottom: 2rem;
        }

        .admin-context {
            color: var(--study-green);
            font-size: 0.84rem;
            font-weight: 750;
            margin: 0 0 0.5rem;
            text-transform: uppercase;
        }

        .admin-heading h1 {
            color: var(--study-text);
            font-size: 2.25rem;
            line-height: 1.2;
            margin: 0 0 0.75rem;
        }

        .admin-heading p:last-child {
            color: var(--study-muted);
            line-height: 1.6;
            margin: 0;
        }

        .st-key-admin_login [data-testid="stForm"] {
            max-width: 28rem;
        }

        .st-key-admin_dashboard h2 {
            border-top: 1px solid var(--study-border);
            color: var(--study-text);
            font-size: 1.2rem;
            margin: 2.5rem 0 1rem;
            padding-top: 2rem;
        }

        .st-key-admin_dashboard [data-testid="stMetric"] {
            border-left: 3px solid var(--study-green);
            padding-left: 0.8rem;
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
        .st-key-rating_complete [data-testid="stProgress"],
        .st-key-study_review [data-testid="stProgress"] {
            margin-bottom: 2.25rem;
        }

        .st-key-rating_group [data-testid="stProgress"] p,
        .st-key-rating_complete [data-testid="stProgress"] p,
        .st-key-study_review [data-testid="stProgress"] p {
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

        .review-heading,
        .debrief-heading {
            margin-bottom: 2.5rem;
            max-width: 48rem;
        }

        .review-heading h1,
        .debrief-heading h1 {
            color: var(--study-text);
            font-size: 2.4rem;
            line-height: 1.2;
            margin: 0 0 1rem;
        }

        .review-heading p,
        .debrief-heading p,
        .debrief-copy p {
            color: var(--study-muted);
            font-size: 1.02rem;
            line-height: 1.65;
            margin: 0;
        }

        .st-key-study_review [data-testid="stExpander"],
        .st-key-study_debrief [data-testid="stExpander"] {
            border-color: var(--study-border);
            border-radius: 6px;
            margin-bottom: 0.8rem;
        }

        .st-key-study_review [data-testid="stExpander"] summary,
        .st-key-study_debrief [data-testid="stExpander"] summary {
            font-weight: 700;
            min-height: 3.5rem;
        }

        .review-rating {
            align-items: start;
            border-top: 1px solid var(--study-border);
            display: grid;
            gap: 2rem;
            grid-template-columns: minmax(0, 1fr) auto;
            padding: 1rem 0;
        }

        .review-rating-copy {
            display: grid;
            gap: 0.35rem;
        }

        .review-rating-copy strong {
            color: var(--study-green);
            font-size: 0.88rem;
        }

        .review-rating-copy span {
            color: var(--study-text);
            line-height: 1.55;
        }

        .review-rating-scores {
            display: grid;
            gap: 0.65rem;
            min-width: 16rem;
        }

        .review-rating-scores span {
            align-items: center;
            color: var(--study-muted);
            display: flex;
            font-size: 0.82rem;
            justify-content: space-between;
        }

        .review-rating-scores strong {
            color: var(--study-text);
            font-size: 1rem;
            margin-left: 1rem;
        }

        .review-comment {
            border-left: 3px solid var(--study-coral);
            margin: 1rem 0;
            padding: 0.3rem 0 0.3rem 1rem;
        }

        .review-comment strong {
            color: var(--study-text);
            font-size: 0.88rem;
        }

        .review-comment p {
            color: var(--study-muted);
            line-height: 1.55;
            margin: 0.35rem 0 0;
        }

        .st-key-study_review [data-testid="stTextArea"] {
            border-top: 2px solid var(--study-green);
            margin-top: 2.5rem;
            padding-top: 2rem;
        }

        .st-key-study_review [data-testid="stButton"] button,
        .st-key-study_debrief [data-testid="stButton"] button {
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 650;
            min-height: 3.25rem;
        }

        .debrief-copy {
            border-top: 1px solid var(--study-border);
            margin: 2rem 0;
            padding-top: 2rem;
        }

        .debrief-copy h2 {
            color: var(--study-text);
            font-size: 1.2rem;
            margin: 0 0 0.75rem;
        }

        .st-key-study_debrief > div > h2 {
            border-top: 2px solid var(--study-green);
            margin-top: 3rem;
            padding-top: 2rem;
        }

        .final-review-comment {
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
            .st-key-rating_complete,
            .st-key-study_review,
            .st-key-study_debrief,
            .st-key-admin_login,
            .st-key-admin_dashboard {
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

            .review-heading h1,
            .debrief-heading h1,
            .admin-heading h1 {
                font-size: 2rem;
            }

            .review-rating {
                gap: 1rem;
                grid-template-columns: 1fr;
            }

            .review-rating-scores {
                min-width: 0;
            }

            .st-key-rating_group [data-testid="stHorizontalBlock"] {
                flex-direction: column;
                gap: 1.5rem;
            }

            .st-key-study_review [data-testid="stHorizontalBlock"] {
                flex-direction: column;
                gap: 1rem;
            }

            .st-key-admin_dashboard [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
            }

            .st-key-rating_group
            [class*="st-key-rating_variant_"]
            [data-testid="stHorizontalBlock"] {
                gap: 1.5rem;
            }

            .st-key-rating_group [data-testid="stColumn"] {
                width: 100%;
            }

            .st-key-study_review [data-testid="stColumn"] {
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

if st.query_params.get("admin") == "1":
    render_admin(stimulus_groups, session_registry)
    st.stop()

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
    stimulus_groups,
)
page = st.query_params.get("page")
if (
    st.session_state.get(f"force_debrief:{participant_session.session_id}")
    and page != "debrief"
):
    st.query_params["page"] = "debrief"
    st.rerun()
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
elif page in {"group-complete", "groups-complete", "review"}:
    render_review(
        participant_session,
        participant_assignment,
        stimulus_groups,
    )
elif page == "debrief":
    render_debrief(
        participant_session,
        participant_assignment,
        stimulus_groups,
    )
else:
    render_participant_start(
        participant_session,
        assignment_fingerprint(participant_assignment),
    )
