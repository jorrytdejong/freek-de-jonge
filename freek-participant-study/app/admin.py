"""Authentication and descriptive summaries for the read-only admin view."""

from __future__ import annotations

import hmac
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from app.exports import ExportTables, validate_export_tables

SCOPE_REAL = "Echte deelnemers"
SCOPE_TEST = "Testsessies"
SCOPE_ALL = "Alles"
ADMIN_SCOPES = (SCOPE_REAL, SCOPE_TEST, SCOPE_ALL)
STATUS_SUBMITTED = "Ingediend"
STATUS_ALL = "Alle statussen"
ADMIN_STATUSES = (STATUS_SUBMITTED, STATUS_ALL)


@dataclass(frozen=True)
class AdminOverview:
    session_count: int
    submitted_count: int
    in_progress_count: int
    completed_group_count: int
    rating_count: int
    mean_funniness: float | None
    mean_freek_similarity: float | None


def verify_admin_password(candidate: str, expected: str | None) -> bool:
    """Compare a supplied password without timing-sensitive equality."""
    if not expected or not candidate:
        return False
    return hmac.compare_digest(
        candidate.encode("utf-8"),
        expected.encode("utf-8"),
    )


def filter_export_tables(tables: ExportTables, scope: str) -> ExportTables:
    """Return validated tables for real, test, or all saved sessions."""
    if scope not in ADMIN_SCOPES:
        raise ValueError(f"Unknown admin data scope: {scope}")
    if scope == SCOPE_ALL:
        validate_export_tables(tables)
        return tables

    include_test = scope == SCOPE_TEST
    participants = tuple(
        row for row in tables.participants if row["is_test"] is include_test
    )
    session_ids = {str(row["session_id"]) for row in participants}
    ratings = tuple(
        row
        for row in tables.ratings
        if str(row["session_id"]) in session_ids
    )
    filtered = ExportTables(participants=participants, ratings=ratings)
    validate_export_tables(filtered)
    return filtered


def filter_submission_status(
    tables: ExportTables,
    status: str,
) -> ExportTables:
    """Keep definitive submissions by default or include all saved states."""
    if status not in ADMIN_STATUSES:
        raise ValueError(f"Unknown admin submission status: {status}")
    if status == STATUS_ALL:
        validate_export_tables(tables)
        return tables

    participants = tuple(
        row
        for row in tables.participants
        if row["submission_status"] == "submitted"
    )
    session_ids = {str(row["session_id"]) for row in participants}
    ratings = tuple(
        row
        for row in tables.ratings
        if str(row["session_id"]) in session_ids
    )
    filtered = ExportTables(participants=participants, ratings=ratings)
    validate_export_tables(filtered)
    return filtered


def _mean(values: Iterable[int]) -> float | None:
    items = tuple(values)
    if not items:
        return None
    return round(sum(items) / len(items), 2)


def build_overview(tables: ExportTables) -> AdminOverview:
    """Summarize progress, completion, and both rating dimensions."""
    validate_export_tables(tables)
    return AdminOverview(
        session_count=len(tables.participants),
        submitted_count=sum(
            row["submission_status"] == "submitted"
            for row in tables.participants
        ),
        in_progress_count=sum(
            row["submission_status"] == "in_progress"
            for row in tables.participants
        ),
        completed_group_count=sum(
            int(row["completed_group_count"])
            for row in tables.participants
        ),
        rating_count=len(tables.ratings),
        mean_funniness=_mean(
            int(row["funniness"]) for row in tables.ratings
        ),
        mean_freek_similarity=_mean(
            int(row["freek_similarity"]) for row in tables.ratings
        ),
    )


def build_group_summary(
    tables: ExportTables,
    group_titles: dict[str, str] | None = None,
) -> tuple[dict[str, object], ...]:
    """Aggregate exposure and ratings by internal joke group."""
    validate_export_tables(tables)
    assigned_counts: dict[str, int] = defaultdict(int)
    for participant in tables.participants:
        assigned_group_ids = str(participant["assigned_group_ids"]).split("|")
        for group_id in filter(None, assigned_group_ids):
            assigned_counts[group_id] += 1

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in tables.ratings:
        grouped[str(row["group_id"])].append(row)

    rows = []
    for group_id in sorted(set(assigned_counts) | set(grouped)):
        ratings = grouped[group_id]
        rows.append(
            {
                "Groep": group_id,
                "Titel": (
                    ratings[0]["group_title"]
                    if ratings
                    else (group_titles or {}).get(group_id, "")
                ),
                "Toegewezen": assigned_counts[group_id],
                "Beoordeeld door": len(
                    {str(row["session_id"]) for row in ratings}
                ),
                "Beoordelingen": len(ratings),
                "Gem. grappigheid": _mean(
                    int(row["funniness"]) for row in ratings
                ),
                "Gem. Freek-gelijkenis": _mean(
                    int(row["freek_similarity"]) for row in ratings
                ),
            }
        )
    return tuple(rows)


def build_variant_summary(
    tables: ExportTables,
) -> tuple[dict[str, object], ...]:
    """Aggregate both dimensions for every internal joke version."""
    validate_export_tables(tables)
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in tables.ratings:
        grouped[(str(row["group_id"]), str(row["variant_id"]))].append(row)

    rows = []
    for group_id, variant_id in sorted(grouped):
        ratings = grouped[(group_id, variant_id)]
        rows.append(
            {
                "Groep": group_id,
                "Variant": variant_id,
                "Rol": ratings[0]["variant_role"],
                "N": len(ratings),
                "Gem. grappigheid": _mean(
                    int(row["funniness"]) for row in ratings
                ),
                "Gem. Freek-gelijkenis": _mean(
                    int(row["freek_similarity"]) for row in ratings
                ),
            }
        )
    return tuple(rows)


def build_dimension_summary(
    tables: ExportTables,
) -> tuple[dict[str, object], ...]:
    """Return chart-ready overall means for the two rating dimensions."""
    overview = build_overview(tables)
    if overview.rating_count == 0:
        return ()
    return (
        {
            "Schaal": "Grappigheid",
            "Gemiddelde": overview.mean_funniness,
        },
        {
            "Schaal": "Lijkt op Freek de Jonge",
            "Gemiddelde": overview.mean_freek_similarity,
        },
    )
