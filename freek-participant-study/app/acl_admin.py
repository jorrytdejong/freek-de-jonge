"""Read-only filtering and descriptive summaries for the ACL study."""

from __future__ import annotations

import hmac
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from app.acl_config import RATING_DIMENSIONS
from app.acl_exports import ExportTables, validate_export_tables

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
    completed_item_count: int
    rating_count: int
    means: dict[str, float | None]


def verify_admin_password(candidate: str, expected: str | None) -> bool:
    if not candidate or not expected:
        return False
    return hmac.compare_digest(candidate.encode(), expected.encode())


def filter_export_tables(tables: ExportTables, scope: str) -> ExportTables:
    if scope not in ADMIN_SCOPES:
        raise ValueError(f"Unknown scope: {scope}")
    if scope == SCOPE_ALL:
        validate_export_tables(tables)
        return tables
    include_test = scope == SCOPE_TEST
    participants = tuple(
        row for row in tables.participants if row["is_test"] is include_test
    )
    session_ids = {row["session_id"] for row in participants}
    ratings = tuple(row for row in tables.ratings if row["session_id"] in session_ids)
    result = ExportTables(participants, ratings)
    validate_export_tables(result)
    return result


def filter_submission_status(tables: ExportTables, status: str) -> ExportTables:
    if status not in ADMIN_STATUSES:
        raise ValueError(f"Unknown status: {status}")
    if status == STATUS_ALL:
        validate_export_tables(tables)
        return tables
    participants = tuple(
        row for row in tables.participants if row["submission_status"] == "submitted"
    )
    session_ids = {row["session_id"] for row in participants}
    ratings = tuple(row for row in tables.ratings if row["session_id"] in session_ids)
    result = ExportTables(participants, ratings)
    validate_export_tables(result)
    return result


def _mean(values: Iterable[int]) -> float | None:
    numbers = tuple(values)
    return None if not numbers else round(sum(numbers) / len(numbers), 2)


def build_overview(tables: ExportTables) -> AdminOverview:
    validate_export_tables(tables)
    return AdminOverview(
        session_count=len(tables.participants),
        submitted_count=sum(
            row["submission_status"] == "submitted" for row in tables.participants
        ),
        in_progress_count=sum(
            row["submission_status"] == "in_progress" for row in tables.participants
        ),
        completed_item_count=sum(
            int(row["completed_item_count"]) for row in tables.participants
        ),
        rating_count=len(tables.ratings),
        means={
            dimension: _mean(int(row[dimension]) for row in tables.ratings)
            for dimension in RATING_DIMENSIONS
        },
    )


def build_dimension_summary(tables: ExportTables) -> tuple[dict[str, object], ...]:
    overview = build_overview(tables)
    labels = {
        "funniness": "Grappigheid",
        "freek_similarity": "Freek-gelijkenis",
        "coherence": "Coherentie",
    }
    return tuple(
        {"Schaal": labels[dimension], "Gemiddelde": mean}
        for dimension, mean in overview.means.items()
        if mean is not None
    )


def build_recruitment_source_summary(
    tables: ExportTables,
) -> tuple[dict[str, object], ...]:
    validate_export_tables(tables)
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in tables.participants:
        grouped[str(row["recruitment_source"])].append(row)
    return tuple(
        {
            "Wervingsbron": source,
            "Sessies": len(rows),
            "Ingediend": sum(row["submission_status"] == "submitted" for row in rows),
            "Bezig": sum(row["submission_status"] == "in_progress" for row in rows),
            "Voltooide items": sum(int(row["completed_item_count"]) for row in rows),
        }
        for source, rows in sorted(grouped.items())
    )


def _group_summary(
    tables: ExportTables, keys: tuple[str, ...]
) -> tuple[dict[str, object], ...]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in tables.ratings:
        grouped[tuple(row[key] for key in keys)].append(row)
    output = []
    for values, rows in sorted(grouped.items(), key=lambda pair: pair[0]):
        result = {key: value for key, value in zip(keys, values, strict=True)}
        result.update(
            {
                "N": len(rows),
                **{
                    f"mean_{dimension}": _mean(int(row[dimension]) for row in rows)
                    for dimension in RATING_DIMENSIONS
                },
            }
        )
        output.append(result)
    return tuple(output)


def build_condition_summary(tables: ExportTables) -> tuple[dict[str, object], ...]:
    validate_export_tables(tables)
    return _group_summary(tables, ("condition_code",))


def build_pipeline_style_summary(
    tables: ExportTables,
) -> tuple[dict[str, object], ...]:
    validate_export_tables(tables)
    return _group_summary(tables, ("pipeline_family", "freek_style"))


def build_topic_summary(tables: ExportTables) -> tuple[dict[str, object], ...]:
    validate_export_tables(tables)
    return _group_summary(tables, ("topic_id", "topic"))


def build_item_summary(tables: ExportTables) -> tuple[dict[str, object], ...]:
    validate_export_tables(tables)
    return _group_summary(tables, ("item_id", "topic", "condition_code"))
