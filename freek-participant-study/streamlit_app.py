"""Blinded, resumable participant application for the ACL humor experiment."""

from __future__ import annotations

import json
import os
from decimal import Decimal
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from app.acl_admin import (
    ADMIN_SCOPES,
    ADMIN_STATUSES,
    SCOPE_ALL,
    SCOPE_REAL,
    SCOPE_TEST,
    STATUS_SUBMITTED,
    build_condition_summary,
    build_dimension_summary,
    build_item_summary,
    build_overview,
    build_pipeline_style_summary,
    build_topic_summary,
    filter_export_tables,
    filter_submission_status,
    verify_admin_password,
)
from app.acl_assignment import (
    AssignedItem,
    ParticipantAssignment,
    assignment_fingerprint,
    build_assignment,
)
from app.acl_config import (
    ITEMS_PER_PARTICIPANT,
    RATING_DIMENSIONS,
    RATING_ENDPOINTS,
    RATING_QUESTIONS,
    STUDY_VERSION,
)
from app.acl_exports import (
    PARTICIPANT_COLUMNS,
    RATING_COLUMNS,
    ExportValidationError,
    build_export_tables,
    rows_to_csv,
)
from app.acl_ratings import ItemRatingValidationError, validate_item_response
from app.acl_sessions import (
    DEFAULT_SESSIONS_PATH,
    ParticipantSession,
    SessionAccessStatus,
    SessionValidationError,
    load_sessions,
    load_sessions_csv_text,
    resolve_session,
)
from app.acl_stimuli import JokeItem, StimulusValidationError, load_stimuli
from app.participant import ProfileValidationError, validate_profile
from app.rewards import (
    CSVRewardLedger,
    FakeRewardProvider,
    RewardBudgetExceededError,
    RewardClaim,
    RewardConfigurationError,
    RewardIssuancePausedError,
    RewardLedgerError,
    RewardService,
    RewardSettings,
    TremendousAPIError,
    TremendousSandboxRewardProvider,
    build_reward_operations_overview,
    filter_reward_records,
    reward_audit_csv,
    reward_audit_rows,
)
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


def configured_secrets() -> dict[str, object]:
    try:
        return dict(st.secrets)
    except StreamlitSecretNotFoundError:
        return {}


storage_environment = dict(os.environ)
if (
    "FREEK_STUDY_PROGRESS_PATH" not in storage_environment
    and storage_environment.get("FREEK_STUDY_STORAGE", "csv") == "csv"
):
    storage_environment["FREEK_STUDY_PROGRESS_PATH"] = str(
        Path(__file__).resolve().parent / "data" / "runtime" / "acl_progress.csv"
    )
try:
    progress_storage = create_progress_storage(
        environ=storage_environment,
        secrets=configured_secrets(),
    )
except (ProgressStorageError, StorageConfigurationError) as error:
    st.error(f"Opslagconfiguratie mislukt: {error}")
    st.stop()

try:
    reward_settings = RewardSettings.from_sources(
        environ=dict(os.environ),
        secrets=configured_secrets(),
    )
except RewardConfigurationError as error:
    st.error(f"Beloningsconfiguratie mislukt: {error}")
    st.stop()
reward_provider = (
    FakeRewardProvider()
    if reward_settings.mode == "fake"
    else TremendousSandboxRewardProvider(
        api_key=reward_settings.tremendous_api_key,
        campaign_id=reward_settings.tremendous_campaign_id,
        funding_source_id=reward_settings.tremendous_funding_source_id,
    )
)
reward_service = None
if reward_settings.enabled:
    reward_ledger = CSVRewardLedger(reward_settings.ledger_path)
    try:
        reward_ledger.scrub_legacy_links()
    except RewardLedgerError as error:
        st.error(f"Beloningsopslag kon niet veilig worden gemigreerd: {error}")
        st.stop()
    reward_service = RewardService(
        reward_ledger,
        reward_provider,
        max_issued_count=reward_settings.max_issued_count,
        budget_limit=reward_settings.budget_eur,
    )


def configured_admin_password() -> str | None:
    if password := os.environ.get("FREEK_STUDY_ADMIN_PASSWORD"):
        return password
    try:
        password = st.secrets.get("admin_password")
    except StreamlitSecretNotFoundError:
        return None
    return str(password) if password else None


def navigate_to_page(session: ParticipantSession, page: str) -> None:
    if os.environ.get("FREEK_STUDY_IN_PROCESS_NAVIGATION") == "true":
        st.query_params["page"] = page
        st.rerun()
    destination = "?" + urlencode({"session": session.session_id, "page": page})
    st.html(
        f"<script>window.location.replace({json.dumps(destination)});</script>",
        unsafe_allow_javascript=True,
    )
    st.stop()


def render_header() -> None:
    st.markdown(
        '<header class="study-header"><strong>Onderzoek naar humor en stijl</strong></header>',
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        f'<footer class="study-footer">Onderzoeksversie {STUDY_VERSION}</footer>',
        unsafe_allow_html=True,
    )


def render_save_status(session: ParticipantSession) -> None:
    if st.session_state.get(f"saved_at:{session.session_id}"):
        st.caption("✓ Opgeslagen")


def profile_key(session_id: str) -> str:
    return f"profile:{session_id}"


def response_key(session_id: str, item_id: str) -> str:
    return f"item_response:{session_id}:{item_id}"


def draft_key(session_id: str, item_id: str) -> str:
    return f"item_draft:{session_id}:{item_id}"


def rating_key(session_id: str, item_id: str, dimension: str) -> str:
    return f"rating:{session_id}:{item_id}:{dimension}"


def final_comment_key(session_id: str) -> str:
    return f"final_comment:{session_id}"


def submissions_key(session_id: str) -> str:
    return f"submissions:{session_id}"


def format_euro_amount(amount: object) -> str:
    return f"€{amount:.2f}".replace(".", ",")


def reward_error_message(error: TremendousAPIError) -> str:
    if error.status_code == 402:
        return (
            "De testrekening heeft onvoldoende saldo. De onderzoeker moet het "
            "sandboxsaldo aanvullen voordat je de testvergoeding kunt openen."
        )
    if error.status_code in {401, 403, 422}:
        return (
            "De testvergoeding is momenteel verkeerd geconfigureerd. "
            "Neem contact op met de onderzoeker."
        )
    if error.uncertain:
        return (
            "Tremendous heeft nog niet bevestigd wat er is gebeurd. Je vaste "
            "orderreferentie voorkomt een dubbele testvergoeding; probeer zo opnieuw."
        )
    return (
        "Tremendous is tijdelijk niet bereikbaar. Er wordt bij een nieuwe poging "
        "eerst gecontroleerd of de testvergoeding al bestaat."
    )


def stored_reward_claim(session: ParticipantSession) -> RewardClaim | None:
    assert reward_service is not None
    try:
        return reward_service.load_claim(
            session_id=session.session_id,
            study_version=STUDY_VERSION,
            is_test=session.is_test,
        )
    except TremendousAPIError as error:
        st.error(reward_error_message(error))
        return None
    except RewardLedgerError:
        st.error("De status van je testbeloning kon niet veilig worden gelezen.")
        st.stop()


def stored_reward_status(session: ParticipantSession) -> str | None:
    assert reward_service is not None
    try:
        return reward_service.load_status(
            session_id=session.session_id,
            study_version=STUDY_VERSION,
            is_test=session.is_test,
        )
    except RewardLedgerError:
        st.error("De status van je testbeloning kon niet veilig worden gelezen.")
        st.stop()


def reward_issuance_is_paused() -> bool:
    assert reward_service is not None
    try:
        return reward_service.load_control().paused
    except RewardLedgerError:
        st.error("De uitgiftestatus van de testbeloning kon niet worden gelezen.")
        st.stop()


def issue_reward(session: ParticipantSession, *, eligible: bool) -> None:
    assert reward_service is not None
    try:
        reward_service.claim_reward(
            session_id=session.session_id,
            study_version=STUDY_VERSION,
            is_test=session.is_test,
            eligible=eligible,
            amount=reward_settings.amount_eur,
        )
    except TremendousAPIError as error:
        st.error(reward_error_message(error))
        return
    except RewardBudgetExceededError:
        st.error(
            "Het maximale aantal testvergoedingen of het ingestelde testbudget "
            "is bereikt. Neem contact op met de onderzoeker."
        )
        return
    except RewardIssuancePausedError:
        st.info(
            "Nieuwe testvergoedingen zijn tijdelijk gepauzeerd. Je kunt deze pagina "
            "later opnieuw openen."
        )
        return
    except RewardLedgerError:
        st.error("Je testbeloning kon niet veilig worden opgeslagen. Probeer opnieuw.")
        st.stop()
    st.rerun()


def decline_reward(session: ParticipantSession, *, eligible: bool) -> None:
    assert reward_service is not None
    try:
        reward_service.decline_reward(
            session_id=session.session_id,
            study_version=STUDY_VERSION,
            is_test=session.is_test,
            eligible=eligible,
            amount=reward_settings.amount_eur,
        )
    except RewardLedgerError:
        st.error("Je keuze kon niet veilig worden opgeslagen. Probeer opnieuw.")
        st.stop()
    st.rerun()


def render_reward(session: ParticipantSession, *, eligible: bool) -> None:
    st.divider()
    st.subheader(f"Een koffie van {format_euro_amount(reward_settings.amount_eur)}")
    st.write(
        "Als dank voor je deelname kun je een testvergoeding ter waarde van een "
        "koffie ontvangen. Deze vergoeding is volledig vrijwillig: je keuze heeft "
        "geen invloed op je deelname of je ingediende antwoorden."
    )
    if reward_settings.mode == "tremendous_sandbox":
        st.warning("TREMENDOUS-SANDBOX — deze beloning gebruikt alleen testgeld.")
    else:
        st.warning("TESTBELONING — deze claim heeft geen geldwaarde.")
    claim = stored_reward_claim(session)
    if claim:
        st.success(
            f"Je testvergoeding van {format_euro_amount(claim.amount)} is aangemaakt."
        )
        if claim.redemption_url:
            st.link_button(
                "Open Tremendous om te kiezen of je status te bekijken",
                claim.redemption_url,
                type="primary",
            )
        else:
            st.code(claim.reference, language=None)
        st.caption(
            "Tremendous verwerkt de gegevens die nodig zijn voor de gekozen "
            "uitbetalingsvorm. Deze gegevens worden niet aan je onderzoeksantwoorden "
            "toegevoegd. Een al gebruikte link toont de actuele uitbetalingsstatus."
        )
        return
    reward_status = stored_reward_status(session)
    if reward_status == "issued":
        st.info(
            "Je testvergoeding is al veilig aangemaakt, maar de Tremendous-link "
            "kon nu niet worden vernieuwd."
        )
        if st.button(
            "Probeer de Tremendous-link opnieuw",
            type="primary",
            key=f"reward_link_retry:{session.session_id}",
        ):
            st.rerun()
        return
    issuance_paused = reward_issuance_is_paused()
    if reward_status == "declined":
        st.info("Je hebt ervoor gekozen geen testvergoeding te ontvangen.")
        st.caption(
            "Deze keuze is apart van je onderzoeksantwoorden opgeslagen. "
            "Je kunt hieronder alsnog voor de testvergoeding kiezen."
        )
        if issuance_paused:
            st.info(
                "Nieuwe testvergoedingen zijn tijdelijk gepauzeerd. Je eerdere "
                "keuze blijft opgeslagen."
            )
        elif st.button(
            "Toch een testvergoeding ontvangen",
            type="primary",
            key=f"reward_reconsider:{session.session_id}",
        ):
            issue_reward(session, eligible=eligible)
        return
    if issuance_paused:
        st.info(
            "Nieuwe testvergoedingen zijn tijdelijk gepauzeerd. Je onderzoeksantwoorden "
            "zijn wel veilig ingediend; open deze pagina later opnieuw."
        )
        if st.button(
            "Geen testvergoeding, bedankt",
            key=f"reward_decline_paused:{session.session_id}",
        ):
            decline_reward(session, eligible=eligible)
        return
    st.write("Wil je de optionele testvergoeding ontvangen?")
    accept_column, decline_column = st.columns(2)
    with accept_column:
        if st.button(
            "Ontvang mijn testvergoeding",
            type="primary",
            use_container_width=True,
            key=f"reward_accept:{session.session_id}",
        ):
            issue_reward(session, eligible=eligible)
    with decline_column:
        if st.button(
            "Geen testvergoeding, bedankt",
            use_container_width=True,
            key=f"reward_decline:{session.session_id}",
        ):
            decline_reward(session, eligible=eligible)
    st.caption(
        "Bij accepteren opent Tremendous in een afzonderlijke pagina. Je kiest daar "
        "zelf een beschikbare uitbetalingsvorm."
    )


def collect_progress_state(
    session: ParticipantSession, assignment: ParticipantAssignment
) -> tuple[
    dict[str, object] | None,
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
]:
    responses = {}
    drafts = {}
    for assigned in assignment.items:
        if response := st.session_state.get(
            response_key(session.session_id, assigned.item_id)
        ):
            responses[assigned.item_id] = response
        if draft := st.session_state.get(
            draft_key(session.session_id, assigned.item_id)
        ):
            drafts[assigned.item_id] = draft
    return st.session_state.get(profile_key(session.session_id)), responses, drafts


def persist_progress(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    *,
    current_page: str,
) -> None:
    profile, responses, drafts = collect_progress_state(session, assignment)
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
                final_comment_key(session.session_id), ""
            ),
            submissions=tuple(
                st.session_state.get(submissions_key(session.session_id), ())
            ),
        )
    except AlreadySubmittedError:
        st.error("Deze onderzoekslink is al definitief ingediend.")
        st.stop()
    except ProgressStorageError:
        st.error("Je voortgang kon niet veilig worden opgeslagen. Probeer opnieuw.")
        st.stop()
    st.session_state[f"saved_at:{session.session_id}"] = saved.updated_at.isoformat()


def validate_response_record(assigned: AssignedItem, response: object) -> None:
    if not isinstance(response, dict):
        raise ValueError("Invalid response object.")
    validate_item_response(
        item_id=assigned.item_id,
        display_position=assigned.display_position,
        raw_ratings={
            dimension: response.get(dimension) for dimension in RATING_DIMENSIONS
        },
    )
    if (
        response.get("item_id") != assigned.item_id
        or response.get("display_position") != assigned.display_position
    ):
        raise ValueError("Invalid response mapping.")


def validate_draft_record(assigned: AssignedItem, draft: object) -> None:
    if (
        not isinstance(draft, dict)
        or draft.get("item_id") != assigned.item_id
        or draft.get("display_position") != assigned.display_position
        or not isinstance(draft.get("ratings"), dict)
    ):
        raise ValueError("Invalid draft mapping.")
    ratings = draft["ratings"]
    if set(ratings) != set(RATING_DIMENSIONS):
        raise ValueError("Invalid draft dimensions.")
    for value in ratings.values():
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5
        ):
            raise ValueError("Invalid draft value.")


def hydrate_progress(
    session: ParticipantSession, assignment: ParticipantAssignment
) -> str | None:
    hydrated_key = f"progress_hydrated:{session.session_id}"
    if st.session_state.get(hydrated_key):
        return None
    try:
        saved = progress_storage.load_progress(session.session_id)
    except ProgressStorageError:
        st.error("De opgeslagen voortgang is beschadigd en kan niet worden geopend.")
        st.stop()
    st.session_state[hydrated_key] = True
    if saved is None:
        return None
    if saved.study_version != STUDY_VERSION or saved.is_test != session.is_test:
        st.error("De opgeslagen voortgang hoort bij een andere onderzoeksversie.")
        st.stop()
    assigned_by_id = {item.item_id: item for item in assignment.items}
    if set(saved.responses) - set(assigned_by_id) or set(saved.drafts) - set(
        assigned_by_id
    ):
        st.error("De opgeslagen voortgang past niet bij deze onderzoekslink.")
        st.stop()
    try:
        for item_id, response in saved.responses.items():
            validate_response_record(assigned_by_id[item_id], response)
        for item_id, draft in saved.drafts.items():
            validate_draft_record(assigned_by_id[item_id], draft)
        if saved.profile is not None:
            validate_profile(
                age=saved.profile.get("age"),
                freek_familiarity=saved.profile.get("freek_familiarity"),
                consent=saved.profile.get("consent", False),
            )
    except (ItemRatingValidationError, ProfileValidationError, ValueError):
        st.error("De opgeslagen antwoorden zijn niet geldig.")
        st.stop()
    allowed_pages = {
        "intro",
        "profile-complete",
        "review",
        "debrief",
        *(f"item-{position}" for position in range(1, ITEMS_PER_PARTICIPANT + 1)),
    }
    if saved.current_page not in allowed_pages:
        st.error("De opgeslagen positie in het onderzoek is niet geldig.")
        st.stop()
    if saved.profile is not None:
        st.session_state[profile_key(session.session_id)] = saved.profile
    for item_id, response in saved.responses.items():
        st.session_state[response_key(session.session_id, item_id)] = response
    for item_id, draft in saved.drafts.items():
        st.session_state[draft_key(session.session_id, item_id)] = draft
    st.session_state[final_comment_key(session.session_id)] = saved.final_comment
    st.session_state[submissions_key(session.session_id)] = list(saved.submissions)
    st.session_state[f"saved_at:{session.session_id}"] = saved.updated_at.isoformat()
    if saved.status == "submitted" and not session.is_test:
        st.session_state[f"force_debrief:{session.session_id}"] = True
        return "debrief"
    return saved.current_page


def render_access_state(status: SessionAccessStatus) -> None:
    messages = {
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
    title, message = messages[status]
    render_header()
    st.markdown(f"# {escape(title)}\n\n{escape(message)}")
    render_footer()


def render_start(session: ParticipantSession, fingerprint: str) -> None:
    render_header()
    st.markdown(
        f'<span data-assignment-fingerprint="{escape(fingerprint)}"></span>',
        unsafe_allow_html=True,
    )
    st.title("Onderzoek naar humor en stijl")
    st.write("Welkom. Je persoonlijke onderzoekslink is geldig.")
    if session.is_test:
        st.info("Dit is een testsessie; antwoorden blijven herkenbaar als testdata.")
    if st.button("Start onderzoek", type="primary", icon=":material/play_arrow:"):
        navigate_to_page(session, "intro")
    render_footer()


def render_intro(
    session: ParticipantSession, assignment: ParticipantAssignment
) -> None:
    render_header()
    st.title("Over het onderzoek")
    st.write(
        "Je beoordeelt 12 korte, experimentele grappen. Per grap geef je vier "
        "scores. Deelname duurt ongeveer 10 minuten."
    )
    st.markdown("## Freek de Jonge")
    st.write(
        "Een van de vragen gaat over gelijkenis met de stijl van Freek de Jonge. "
        "De teksten zijn experimenteel en niet door Freek de Jonge geschreven."
    )
    st.markdown("## Privacy")
    st.write(
        "We vragen geen naam of contactgegevens. Antwoorden worden gekoppeld aan "
        "de unieke code in je persoonlijke onderzoekslink."
    )
    with st.form(f"participant_profile_{session.session_id}", border=False):
        st.markdown("## Over jou")
        age = st.number_input(
            "Wat is je leeftijd in hele jaren?",
            min_value=1,
            max_value=120,
            value=None,
            step=1,
        )
        familiarity = st.radio(
            "Hoe goed ken je het werk van Freek de Jonge?",
            options=[1, 2, 3, 4, 5],
            index=None,
            horizontal=True,
        )
        st.caption("1 = Helemaal niet bekend · 5 = Zeer bekend")
        consent = st.checkbox(
            "Ik heb bovenstaande informatie gelezen en neem vrijwillig deel aan "
            "dit onderzoek."
        )
        submitted = st.form_submit_button("Verder", type="primary")
    if submitted:
        try:
            profile = validate_profile(
                age=age, freek_familiarity=familiarity, consent=consent
            )
        except ProfileValidationError as error:
            st.error("\n".join(f"- {message}" for message in error.messages))
        else:
            st.session_state[profile_key(session.session_id)] = {
                "age": profile.age,
                "freek_familiarity": profile.freek_familiarity,
                "consent": profile.consent,
            }
            persist_progress(session, assignment, current_page="profile-complete")
            navigate_to_page(session, "profile-complete")
    render_footer()


def render_profile_complete(
    session: ParticipantSession, assignment: ParticipantAssignment
) -> None:
    if st.session_state.get(profile_key(session.session_id)) is None:
        render_intro(session, assignment)
        return
    render_header()
    st.title("Klaar om te beginnen")
    st.write("Je krijgt nu 12 grappen, één per pagina.")
    if st.button("Naar de eerste grap", type="primary"):
        persist_progress(session, assignment, current_page="item-1")
        navigate_to_page(session, "item-1")
    render_footer()


def restore_rating_widgets(session: ParticipantSession, assigned: AssignedItem) -> None:
    draft = st.session_state.get(draft_key(session.session_id, assigned.item_id))
    response = st.session_state.get(response_key(session.session_id, assigned.item_id))
    ratings = draft["ratings"] if draft is not None else response
    if ratings is None:
        return
    for dimension in RATING_DIMENSIONS:
        st.session_state.setdefault(
            rating_key(session.session_id, assigned.item_id, dimension),
            ratings.get(dimension) or 0,
        )


def render_rating_slider(
    session: ParticipantSession, assigned: AssignedItem, dimension: str
) -> int | None:
    value = st.select_slider(
        RATING_QUESTIONS[dimension],
        options=[0, 1, 2, 3, 4, 5],
        format_func=lambda selected: "Kies" if selected == 0 else str(selected),
        key=rating_key(session.session_id, assigned.item_id, dimension),
    )
    low, high = RATING_ENDPOINTS[dimension]
    st.caption(f"1 = {low} · 5 = {high}")
    return None if value == 0 else value


def render_rating_item(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    stimuli: tuple[JokeItem, ...],
    item_index: int,
) -> None:
    if st.session_state.get(profile_key(session.session_id)) is None:
        render_intro(session, assignment)
        return
    assigned = assignment.items[item_index]
    stimulus = next(item for item in stimuli if item.item_id == assigned.item_id)
    restore_rating_widgets(session, assigned)
    position = item_index + 1
    returning_to_review = (
        st.session_state.get(f"review_edit:{session.session_id}") == assigned.item_id
    )
    render_header()
    st.progress(position / len(assignment.items), text=f"Grap {position} van 12")
    render_save_status(session)
    st.markdown(
        f'<article class="joke-card"><p>{escape(stimulus.text)}</p></article>',
        unsafe_allow_html=True,
    )
    first_column, second_column = st.columns(2, gap="large")
    raw_ratings: dict[str, int | None] = {}
    with first_column:
        raw_ratings["funniness"] = render_rating_slider(session, assigned, "funniness")
        raw_ratings["coherence"] = render_rating_slider(session, assigned, "coherence")
    with second_column:
        raw_ratings["freek_similarity"] = render_rating_slider(
            session, assigned, "freek_similarity"
        )
        raw_ratings["originality"] = render_rating_slider(
            session, assigned, "originality"
        )

    draft = {
        "item_id": assigned.item_id,
        "display_position": assigned.display_position,
        "ratings": raw_ratings,
    }
    existing_draft = st.session_state.get(
        draft_key(session.session_id, assigned.item_id)
    )
    response = st.session_state.get(response_key(session.session_id, assigned.item_id))
    matches_response = response is not None and all(
        response.get(dimension) == value for dimension, value in raw_ratings.items()
    )
    has_content = any(value is not None for value in raw_ratings.values())
    changed = False
    if matches_response or not has_content:
        if existing_draft is not None:
            st.session_state.pop(draft_key(session.session_id, assigned.item_id), None)
            changed = True
    elif existing_draft != draft:
        st.session_state[draft_key(session.session_id, assigned.item_id)] = draft
        changed = True
    if changed:
        persist_progress(session, assignment, current_page=f"item-{position}")

    previous_column, next_column = st.columns(2)
    with previous_column:
        previous_clicked = (
            item_index > 0
            and not returning_to_review
            and st.button("Vorige grap", use_container_width=True)
        )
    with next_column:
        next_label = (
            "Terug naar controle"
            if returning_to_review
            else (
                "Naar controle"
                if position == len(assignment.items)
                else "Volgende grap"
            )
        )
        next_clicked = st.button(next_label, type="primary", use_container_width=True)
    if previous_clicked:
        persist_progress(session, assignment, current_page=f"item-{item_index}")
        navigate_to_page(session, f"item-{item_index}")
    if next_clicked:
        try:
            validated = validate_item_response(
                item_id=assigned.item_id,
                display_position=assigned.display_position,
                raw_ratings=raw_ratings,
            )
        except ItemRatingValidationError as error:
            st.error(
                "Beantwoord alle vier schalen:\n\n"
                + "\n".join(f"- {message}" for message in error.messages)
            )
        else:
            st.session_state[response_key(session.session_id, assigned.item_id)] = {
                "item_id": validated.item_id,
                "display_position": validated.display_position,
                **{
                    dimension: getattr(validated, dimension)
                    for dimension in RATING_DIMENSIONS
                },
            }
            st.session_state.pop(draft_key(session.session_id, assigned.item_id), None)
            destination = (
                "review"
                if returning_to_review or position == len(assignment.items)
                else f"item-{position + 1}"
            )
            st.session_state.pop(f"review_edit:{session.session_id}", None)
            persist_progress(session, assignment, current_page=destination)
            navigate_to_page(session, destination)
    render_footer()


def first_incomplete_item(
    session: ParticipantSession, assignment: ParticipantAssignment
) -> int | None:
    for index, assigned in enumerate(assignment.items):
        if (
            st.session_state.get(response_key(session.session_id, assigned.item_id))
            is None
        ):
            return index
    return None


def render_item_summary(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    stimuli: tuple[JokeItem, ...],
    index: int,
    *,
    editable: bool,
) -> None:
    assigned = assignment.items[index]
    stimulus = next(item for item in stimuli if item.item_id == assigned.item_id)
    response = st.session_state[response_key(session.session_id, assigned.item_id)]
    with st.expander(f"Grap {index + 1}", expanded=False):
        st.write(stimulus.text)
        st.markdown(
            "  \n".join(
                f"**{RATING_QUESTIONS[dimension]}** — {response[dimension]}"
                for dimension in RATING_DIMENSIONS
            )
        )
        if editable and st.button(f"Bewerk grap {index + 1}", key=f"edit-{index + 1}"):
            st.session_state[f"review_edit:{session.session_id}"] = assigned.item_id
            destination = f"item-{index + 1}"
            persist_progress(session, assignment, current_page=destination)
            navigate_to_page(session, destination)


def submit_progress(
    session: ParticipantSession, assignment: ParticipantAssignment
) -> None:
    profile, responses, _ = collect_progress_state(session, assignment)
    if profile is None or len(responses) != len(assignment.items):
        st.error("Niet alle verplichte antwoorden zijn compleet.")
        st.stop()
    for assigned in assignment.items:
        validate_response_record(assigned, responses[assigned.item_id])
    try:
        saved = progress_storage.submit_response(
            session_id=session.session_id,
            study_version=STUDY_VERSION,
            is_test=session.is_test,
            profile=profile,
            responses=responses,
            final_comment=st.session_state.get(
                final_comment_key(session.session_id), ""
            ).strip(),
        )
    except AlreadySubmittedError:
        st.error("Deze onderzoekslink is al definitief ingediend.")
        st.stop()
    except ProgressStorageError:
        st.error("Je antwoorden konden niet veilig worden ingediend. Probeer opnieuw.")
        st.stop()
    st.session_state[submissions_key(session.session_id)] = list(saved.submissions)
    st.session_state[f"saved_at:{session.session_id}"] = saved.updated_at.isoformat()


def render_review(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    stimuli: tuple[JokeItem, ...],
) -> None:
    if (incomplete := first_incomplete_item(session, assignment)) is not None:
        render_rating_item(session, assignment, stimuli, incomplete)
        return
    render_header()
    st.progress(1.0, text="12 van 12 grappen beoordeeld")
    render_save_status(session)
    st.title("Controleer je antwoorden")
    st.write("Je kunt iedere grap nog openen en aanpassen vóór het indienen.")
    for index in range(len(assignment.items)):
        render_item_summary(session, assignment, stimuli, index, editable=True)
    final_comment = st.text_area(
        "Algemene opmerking over de grappen of het onderzoek (optioneel)",
        max_chars=2000,
        height=120,
        key=final_comment_key(session.session_id),
    )
    saved_comment_key = f"saved_final_comment:{session.session_id}"
    if st.session_state.get(saved_comment_key) != final_comment:
        persist_progress(session, assignment, current_page="review")
        st.session_state[saved_comment_key] = final_comment
    back_column, submit_column = st.columns(2)
    with back_column:
        if st.button("Terug naar laatste grap", use_container_width=True):
            persist_progress(session, assignment, current_page="item-12")
            navigate_to_page(session, "item-12")
    with submit_column:
        if st.button("Definitief indienen", type="primary", use_container_width=True):
            submit_progress(session, assignment)
            navigate_to_page(session, "debrief")
    render_footer()


def render_debrief(
    session: ParticipantSession,
    assignment: ParticipantAssignment,
    stimuli: tuple[JokeItem, ...],
) -> None:
    submissions = st.session_state.get(submissions_key(session.session_id), [])
    if not submissions:
        render_review(session, assignment, stimuli)
        return
    render_header()
    st.title("Bedankt voor je deelname")
    st.success("Je antwoorden zijn veilig ingediend.")
    st.write(
        "De grappen waren experimenteel en niet door Freek de Jonge geschreven. "
        "We vergelijken verschillende generatieprocedures zonder die labels aan "
        "deelnemers te tonen."
    )
    if reward_settings.enabled:
        render_reward(session, eligible=bool(submissions))
    if session.is_test:
        st.info(f"Testinzending {len(submissions)} is opgeslagen.")
        if st.button("Nieuwe testinzending"):
            persist_progress(session, assignment, current_page="review")
            navigate_to_page(session, "review")
    st.markdown("## Ingediende antwoorden")
    for index in range(len(assignment.items)):
        render_item_summary(session, assignment, stimuli, index, editable=False)
    render_footer()


def render_preview(stimuli: tuple[JokeItem, ...]) -> None:
    render_header()
    st.title("Interne stimuluspreview")
    selected = st.selectbox(
        "Item",
        options=[item.item_id for item in stimuli],
        format_func=lambda item_id: next(
            f"{item.item_id} — {item.topic}"
            for item in stimuli
            if item.item_id == item_id
        ),
    )
    item = next(item for item in stimuli if item.item_id == selected)
    st.write(item.text)
    st.json(
        {
            "item_id": item.item_id,
            "topic": item.topic,
            "condition": item.condition_code,
            "pipeline": item.pipeline_family,
            "freek_style": item.freek_style,
            "model": item.model,
            "result_sha256": item.result_sha256,
        }
    )
    st.warning("Deze interne labels mogen niet aan deelnemers worden getoond.")
    render_footer()


def render_admin_login() -> None:
    render_header()
    st.title("Beheeromgeving")
    with st.form("admin_login_form"):
        candidate = st.text_input("Wachtwoord", type="password")
        submitted = st.form_submit_button("Inloggen", type="primary")
    if submitted:
        if verify_admin_password(candidate, configured_admin_password()):
            st.session_state["admin_authenticated"] = True
            st.rerun()
        else:
            st.error("Het wachtwoord is niet correct.")
    render_footer()


def render_admin_dashboard(
    stimuli: tuple[JokeItem, ...], sessions: dict[str, ParticipantSession]
) -> None:
    render_header()
    try:
        tables = build_export_tables(
            progress_storage.list_progress(), sessions, stimuli
        )
    except (ProgressStorageError, ExportValidationError):
        st.error("De onderzoeksdata kon niet veilig worden gevalideerd.")
        return
    st.title("Onderzoeksdashboard")
    scope = st.segmented_control(
        "Gegevensselectie", ADMIN_SCOPES, default=SCOPE_REAL, selection_mode="single"
    )
    status = st.segmented_control(
        "Inzendingsstatus",
        ADMIN_STATUSES,
        default=STATUS_SUBMITTED,
        selection_mode="single",
    )
    selected = filter_submission_status(
        filter_export_tables(tables, scope or SCOPE_REAL), status or STATUS_SUBMITTED
    )
    overview = build_overview(selected)
    metrics = st.columns(5)
    metrics[0].metric("Sessies", overview.session_count)
    metrics[1].metric("Ingediend", overview.submitted_count)
    metrics[2].metric("Bezig", overview.in_progress_count)
    metrics[3].metric("Voltooide items", overview.completed_item_count)
    metrics[4].metric("Beoordelingen", overview.rating_count)
    st.markdown("## Gemiddelden per schaal")
    st.dataframe(build_dimension_summary(selected), hide_index=True, width="stretch")
    st.markdown("## Resultaten per conditie")
    st.dataframe(build_condition_summary(selected), hide_index=True, width="stretch")
    st.markdown("## Pipeline × Freek-stijl")
    st.dataframe(
        build_pipeline_style_summary(selected), hide_index=True, width="stretch"
    )
    st.markdown("## Resultaten per topic")
    st.dataframe(build_topic_summary(selected), hide_index=True, width="stretch")
    st.markdown("## Resultaten per item")
    st.dataframe(build_item_summary(selected), hide_index=True, width="stretch")
    first, second = st.columns(2)
    with first:
        st.download_button(
            "Deelnemers downloaden",
            rows_to_csv(PARTICIPANT_COLUMNS, selected.participants).encode("utf-8-sig"),
            file_name="participants.csv",
        )
    with second:
        st.download_button(
            "Beoordelingen downloaden",
            rows_to_csv(RATING_COLUMNS, selected.ratings).encode("utf-8-sig"),
            file_name="ratings.csv",
        )
    render_reward_operations()
    render_footer()


def render_reward_operations() -> None:
    """Show reward delivery health only inside the authenticated admin route."""
    if reward_service is None:
        return
    st.markdown("## Beloningsoperaties")
    try:
        control = reward_service.load_control()
    except RewardLedgerError:
        st.error("De uitgiftebediening kon niet veilig worden gelezen.")
        return
    if control.paused:
        st.warning(
            "NIEUWE UITGIFTE GEPAUZEERD — bestaande beloningen blijven toegankelijk."
        )
        if st.button("Nieuwe uitgifte hervatten", type="primary"):
            try:
                reward_service.set_paused(False)
            except RewardLedgerError:
                st.error("De uitgifte kon niet veilig worden hervat.")
            else:
                st.rerun()
    else:
        st.success("Nieuwe uitgifte is actief.")
        pause_confirmed = st.checkbox(
            "Ik bevestig dat ik nieuwe testvergoedingen tijdelijk wil pauzeren."
        )
        if st.button("Nieuwe uitgifte pauzeren", disabled=not pause_confirmed):
            try:
                reward_service.set_paused(True)
            except RewardLedgerError:
                st.error("De uitgifte kon niet veilig worden gepauzeerd.")
            else:
                st.rerun()
    if reward_settings.mode == "tremendous_sandbox":
        if st.button("Tremendous-bezorgstatussen vernieuwen"):
            try:
                reconciliation = reward_service.reconcile_issued_rewards()
            except RewardLedgerError:
                st.error("De vernieuwde Tremendous-status kon niet worden opgeslagen.")
            else:
                st.session_state["reward_reconciliation_notice"] = {
                    "checked": reconciliation.checked_count,
                    "updated": reconciliation.updated_count,
                    "failed": reconciliation.failed_count,
                }
                st.rerun()
        if notice := st.session_state.pop("reward_reconciliation_notice", None):
            if notice["failed"]:
                st.warning(
                    f"{notice['checked']} status(sen) gecontroleerd; "
                    f"{notice['failed']} konden niet worden opgehaald."
                )
            else:
                st.success(
                    f"{notice['checked']} status(sen) gecontroleerd; "
                    f"{notice['updated']} gewijzigd."
                )
    reward_scope = st.segmented_control(
        "Beloningsselectie",
        ADMIN_SCOPES,
        default=SCOPE_ALL,
        selection_mode="single",
        key="reward_operations_scope",
    )
    include_test = None if reward_scope == SCOPE_ALL else reward_scope == SCOPE_TEST
    try:
        all_records = reward_service.ledger.list_records()
        records = filter_reward_records(all_records, include_test=include_test)
    except RewardLedgerError:
        st.error("De beloningsadministratie kon niet veilig worden gelezen.")
        return
    overview = build_reward_operations_overview(records)
    capacity_overview = build_reward_operations_overview(all_records)
    st.caption(
        "Los van onderzoeksantwoorden; bevat alleen pseudonieme operationele gegevens."
    )
    metrics = st.columns(6)
    metrics[0].metric("Keuzes", overview.total_count)
    metrics[1].metric("Aangemaakt", overview.issued_count)
    metrics[2].metric("Geweigerd", overview.declined_count)
    metrics[3].metric("Mislukt", overview.failed_count)
    metrics[4].metric("Bezig", overview.issuing_count)
    amount_label = (
        format_euro_amount(overview.issued_amount)
        if overview.currency in {None, "EUR"}
        else f"{overview.issued_amount} {overview.currency}"
    )
    metrics[5].metric("Aangemaakte waarde", amount_label)
    capacity_metrics = st.columns(5)
    remaining_count = max(
        0, reward_settings.max_issued_count - capacity_overview.reserved_count
    )
    remaining_budget = max(
        reward_settings.budget_eur - capacity_overview.reserved_amount,
        Decimal("0"),
    )
    capacity_metrics[0].metric(
        "Resterende beloningen",
        remaining_count,
        help=f"Harde limiet: {reward_settings.max_issued_count}",
    )
    capacity_metrics[1].metric(
        "Resterend budget",
        format_euro_amount(remaining_budget),
        help=f"Hard budget: {format_euro_amount(reward_settings.budget_eur)}",
    )
    capacity_metrics[2].metric(
        "Link actief",
        overview.provider_succeeded_count,
        help="Tremendous-bezorgstatus SUCCEEDED; dit bewijst geen verzilvering.",
    )
    capacity_metrics[3].metric(
        "Providerfout",
        overview.provider_failed_count,
    )
    capacity_metrics[4].metric("Niet gecontroleerd", overview.unchecked_count)
    if overview.failed_count:
        st.warning(
            f"{overview.failed_count} beloning(en) zijn mislukt en kunnen veilig "
            "opnieuw worden geprobeerd via de deelnemerslink."
        )
    if overview.stuck_count:
        st.warning(
            f"{overview.stuck_count} beloning(en) staan langer dan tien minuten op "
            "'issuing'. Een nieuwe poging gebruikt dezelfde orderreferentie."
        )
    audit_rows = reward_audit_rows(records)
    st.dataframe(audit_rows, hide_index=True, width="stretch")
    st.download_button(
        "Beloningslog downloaden",
        reward_audit_csv(records).encode("utf-8-sig"),
        file_name="reward_operations.csv",
        mime="text/csv",
    )


def render_admin(
    stimuli: tuple[JokeItem, ...], sessions: dict[str, ParticipantSession]
) -> None:
    if not st.session_state.get("admin_authenticated"):
        render_admin_login()
    else:
        render_admin_dashboard(stimuli, sessions)


try:
    stimulus_items = load_stimuli()
    private_sessions_csv = configured_secrets().get("sessions_csv")
    if private_sessions_csv and "FREEK_STUDY_SESSIONS_PATH" not in os.environ:
        session_registry = load_sessions_csv_text(
            stimulus_items, str(private_sessions_csv)
        )
    else:
        session_registry = load_sessions(
            stimulus_items,
            Path(os.environ.get("FREEK_STUDY_SESSIONS_PATH", DEFAULT_SESSIONS_PATH)),
        )
except (StimulusValidationError, SessionValidationError) as error:
    st.error(f"Configuratiecontrole mislukt: {error}")
    st.stop()

st.markdown(
    """
    <style>
    :root { --ink:#18221f; --muted:#5e6965; --green:#126443; --line:#dce2df; }
    [data-testid="stHeader"], [data-testid="stToolbar"] { display:none; }
    [data-testid="stMainBlockContainer"] { max-width: 920px; padding-top: 2rem; }
    .study-header { border-bottom:1px solid var(--line); color:var(--ink);
        margin-bottom:2.5rem; padding:1.25rem 0; }
    .study-footer { border-top:1px solid var(--line); color:var(--muted);
        margin-top:4rem; padding:1.5rem 0; }
    .joke-card { background:#f5f7f6; border-left:5px solid var(--green);
        border-radius:6px; font-size:1.3rem; line-height:1.65;
        margin:1.75rem 0 2.25rem; padding:1.75rem 2rem; }
    @media (max-width: 700px) {
        [data-testid="stHorizontalBlock"] { flex-direction:column; }
        [data-testid="stColumn"] { width:100%; }
        .joke-card { font-size:1.12rem; padding:1.25rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if st.query_params.get("admin") == "1":
    render_admin(stimulus_items, session_registry)
    st.stop()
if st.query_params.get("preview") == "1":
    render_preview(stimulus_items)
    st.stop()

access = resolve_session(st.query_params.get("session"), session_registry)
if access.status is not SessionAccessStatus.VALID:
    render_access_state(access.status)
    st.stop()
participant_session = access.session
assert participant_session is not None
participant_assignment = build_assignment(participant_session, stimulus_items)
resume_page = hydrate_progress(participant_session, participant_assignment)
page = st.query_params.get("page")
if st.session_state.get(f"force_debrief:{participant_session.session_id}"):
    if page != "debrief":
        st.query_params["page"] = "debrief"
        st.rerun()
if page is None and resume_page is not None:
    st.query_params["page"] = resume_page
    st.rerun()
item_pages = {
    f"item-{position}": position - 1
    for position in range(1, len(participant_assignment.items) + 1)
}
if page == "intro":
    render_intro(participant_session, participant_assignment)
elif page == "profile-complete":
    render_profile_complete(participant_session, participant_assignment)
elif page in item_pages:
    render_rating_item(
        participant_session,
        participant_assignment,
        stimulus_items,
        item_pages[page],
    )
elif page == "review":
    render_review(participant_session, participant_assignment, stimulus_items)
elif page == "debrief":
    render_debrief(participant_session, participant_assignment, stimulus_items)
else:
    render_start(participant_session, assignment_fingerprint(participant_assignment))
