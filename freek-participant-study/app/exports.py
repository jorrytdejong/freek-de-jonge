"""Build and validate analysis-ready participant and rating tables."""

from __future__ import annotations

import csv
import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.assignment import assignment_fingerprint, build_assignment
from app.ratings import MAXIMUM_RATING, MINIMUM_RATING, build_displayed_variants
from app.sessions import ParticipantSession
from app.stimuli import JokeGroup
from app.storage.base import SavedProgress

EXPORT_SCHEMA_VERSION = "1"
DEFAULT_EXPORT_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "data" / "runtime" / "exports"
)

PARTICIPANT_COLUMNS = (
    "export_schema_version",
    "session_id",
    "study_version",
    "is_test",
    "submission_status",
    "submission_count",
    "latest_submission_id",
    "latest_submission_number",
    "age",
    "freek_familiarity",
    "consent",
    "assigned_group_ids",
    "assignment_seed",
    "assignment_fingerprint",
    "group_count",
    "completed_group_count",
    "final_comment",
    "created_at",
    "updated_at",
    "submitted_at",
)

RATING_COLUMNS = (
    "export_schema_version",
    "session_id",
    "submission_id",
    "submission_number",
    "study_version",
    "is_test",
    "submission_status",
    "age",
    "freek_familiarity",
    "assignment_seed",
    "assignment_fingerprint",
    "group_id",
    "group_position",
    "group_title",
    "variant_id",
    "variant_role",
    "joke_text",
    "display_label",
    "display_position",
    "funniness",
    "freek_similarity",
    "group_comment",
    "final_comment",
    "submitted_at",
)


class ExportValidationError(ValueError):
    """Raised when stored research data violates the export schema."""


@dataclass(frozen=True)
class ExportTables:
    participants: tuple[dict[str, object], ...]
    ratings: tuple[dict[str, object], ...]


def _integer(
    value: object,
    *,
    field: str,
    session_id: str,
    minimum: int,
    maximum: int,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise ExportValidationError(
            f"Session {session_id} has invalid {field}."
        )
    return value


def _snapshot(
    record: SavedProgress,
) -> tuple[
    dict[str, object] | None,
    dict[str, dict[str, object]],
    str,
    str,
    int | str,
    str,
]:
    if not record.submissions:
        return (
            record.profile,
            record.responses,
            record.final_comment,
            "",
            "",
            "",
        )

    event = record.submissions[-1]
    profile = event.get("profile")
    responses = event.get("responses")
    final_comment = event.get("final_comment")
    submission_id = event.get("submission_id")
    submission_number = event.get("submission_number")
    submitted_at = event.get("submitted_at")
    if (
        not isinstance(profile, dict)
        or not isinstance(responses, dict)
        or not all(
            isinstance(group_id, str) and isinstance(response, dict)
            for group_id, response in responses.items()
        )
        or not isinstance(final_comment, str)
        or not isinstance(submission_id, str)
        or isinstance(submission_number, bool)
        or not isinstance(submission_number, int)
        or not isinstance(submitted_at, str)
        or event.get("study_version") != record.study_version
        or event.get("is_test") is not record.is_test
    ):
        raise ExportValidationError(
            f"Session {record.session_id} has an invalid latest submission."
        )
    return (
        profile,
        responses,
        final_comment,
        submission_id,
        submission_number,
        submitted_at,
    )


def build_export_tables(
    records: Iterable[SavedProgress],
    sessions: dict[str, ParticipantSession],
    groups: tuple[JokeGroup, ...],
) -> ExportTables:
    """Create one participant row per session and one row per saved rating."""
    groups_by_id = {group.group_id: group for group in groups}
    stimulus_versions = {
        variant.study_version
        for group in groups
        for variant in group.variants
    }
    if len(stimulus_versions) != 1:
        raise ExportValidationError("Stimuli contain inconsistent study versions.")
    stimulus_version = next(iter(stimulus_versions))
    participant_rows: list[dict[str, object]] = []
    rating_rows: list[dict[str, object]] = []
    seen_sessions: set[str] = set()

    for record in sorted(records, key=lambda item: item.session_id):
        session_id = record.session_id
        if session_id in seen_sessions:
            raise ExportValidationError(f"Duplicate session {session_id}.")
        seen_sessions.add(session_id)

        session = sessions.get(session_id)
        if session is None:
            raise ExportValidationError(
                f"Saved session {session_id} is absent from the registry."
            )
        if session.is_test != record.is_test:
            raise ExportValidationError(
                f"Session {session_id} has inconsistent test status."
            )
        if record.study_version != stimulus_version:
            raise ExportValidationError(
                f"Session {session_id} does not match the stimulus study version."
            )
        if record.status not in {"in_progress", "submitted"} or (
            (record.status == "submitted") != bool(record.submissions)
        ):
            raise ExportValidationError(
                f"Session {session_id} has inconsistent submission status."
            )

        assignment = build_assignment(session, groups)
        fingerprint = assignment_fingerprint(assignment)
        (
            profile,
            responses,
            final_comment,
            submission_id,
            submission_number,
            submitted_at,
        ) = _snapshot(record)
        if not isinstance(final_comment, str):
            raise ExportValidationError(
                f"Session {session_id} has invalid final_comment."
            )

        age: int | str = ""
        familiarity: int | str = ""
        consent: bool | str = ""
        if profile is not None:
            age = _integer(
                profile.get("age"),
                field="age",
                session_id=session_id,
                minimum=1,
                maximum=120,
            )
            familiarity = _integer(
                profile.get("freek_familiarity"),
                field="freek_familiarity",
                session_id=session_id,
                minimum=1,
                maximum=5,
            )
            if profile.get("consent") is not True:
                raise ExportValidationError(
                    f"Session {session_id} has invalid consent."
                )
            consent = True

        unknown_responses = set(responses) - {
            group.group_id for group in assignment.groups
        }
        if unknown_responses:
            raise ExportValidationError(
                f"Session {session_id} has responses outside its assignment."
            )
        if record.status == "submitted" and len(responses) != len(assignment.groups):
            raise ExportValidationError(
                f"Submitted session {session_id} is missing completed groups."
            )

        participant_rows.append(
            {
                "export_schema_version": EXPORT_SCHEMA_VERSION,
                "session_id": session_id,
                "study_version": record.study_version,
                "is_test": record.is_test,
                "submission_status": record.status,
                "submission_count": len(record.submissions),
                "latest_submission_id": submission_id,
                "latest_submission_number": submission_number,
                "age": age,
                "freek_familiarity": familiarity,
                "consent": consent,
                "assigned_group_ids": "|".join(
                    group.group_id for group in assignment.groups
                ),
                "assignment_seed": session_id,
                "assignment_fingerprint": fingerprint,
                "group_count": len(assignment.groups),
                "completed_group_count": len(responses),
                "final_comment": final_comment,
                "created_at": record.created_at.isoformat(),
                "updated_at": record.updated_at.isoformat(),
                "submitted_at": submitted_at,
            }
        )

        for group_position, assigned_group in enumerate(
            assignment.groups,
            start=1,
        ):
            response = responses.get(assigned_group.group_id)
            if response is None:
                continue
            joke_group = groups_by_id[assigned_group.group_id]
            displayed = build_displayed_variants(assigned_group, joke_group)
            displayed_by_id = {item.variant_id: item for item in displayed}
            variants_by_id = {
                variant.variant_id: variant for variant in joke_group.variants
            }

            if response.get("group_id") != assigned_group.group_id:
                raise ExportValidationError(
                    f"Session {session_id} has a mismatched group response."
                )
            raw_ratings = response.get("ratings")
            group_comment = response.get("comment")
            if not isinstance(raw_ratings, list) or not isinstance(
                group_comment, str
            ):
                raise ExportValidationError(
                    f"Session {session_id} has invalid response data for "
                    f"{assigned_group.group_id}."
                )
            if len(raw_ratings) != len(displayed):
                raise ExportValidationError(
                    f"Session {session_id} has an incomplete response for "
                    f"{assigned_group.group_id}."
                )

            seen_variants: set[str] = set()
            for raw_rating in raw_ratings:
                if not isinstance(raw_rating, dict):
                    raise ExportValidationError(
                        f"Session {session_id} has an invalid rating record."
                    )
                variant_id = raw_rating.get("variant_id")
                if not isinstance(variant_id, str) or variant_id in seen_variants:
                    raise ExportValidationError(
                        f"Session {session_id} has invalid variant IDs in "
                        f"{assigned_group.group_id}."
                    )
                seen_variants.add(variant_id)
                expected = displayed_by_id.get(variant_id)
                if expected is None or (
                    raw_rating.get("display_label") != expected.display_label
                    or raw_rating.get("display_position")
                    != expected.display_position
                ):
                    raise ExportValidationError(
                        f"Session {session_id} has an invalid displayed-version "
                        f"mapping for {variant_id}."
                    )
                funniness = _integer(
                    raw_rating.get("funniness"),
                    field="funniness",
                    session_id=session_id,
                    minimum=MINIMUM_RATING,
                    maximum=MAXIMUM_RATING,
                )
                similarity = _integer(
                    raw_rating.get("freek_similarity"),
                    field="freek_similarity",
                    session_id=session_id,
                    minimum=MINIMUM_RATING,
                    maximum=MAXIMUM_RATING,
                )
                stimulus = variants_by_id[variant_id]
                rating_rows.append(
                    {
                        "export_schema_version": EXPORT_SCHEMA_VERSION,
                        "session_id": session_id,
                        "submission_id": submission_id,
                        "submission_number": submission_number,
                        "study_version": record.study_version,
                        "is_test": record.is_test,
                        "submission_status": record.status,
                        "age": age,
                        "freek_familiarity": familiarity,
                        "assignment_seed": session_id,
                        "assignment_fingerprint": fingerprint,
                        "group_id": assigned_group.group_id,
                        "group_position": group_position,
                        "group_title": joke_group.title,
                        "variant_id": variant_id,
                        "variant_role": stimulus.variant_role,
                        "joke_text": stimulus.text,
                        "display_label": expected.display_label,
                        "display_position": expected.display_position,
                        "funniness": funniness,
                        "freek_similarity": similarity,
                        "group_comment": group_comment,
                        "final_comment": final_comment,
                        "submitted_at": submitted_at,
                    }
                )
            if seen_variants != set(displayed_by_id):
                raise ExportValidationError(
                    f"Session {session_id} has missing variants in "
                    f"{assigned_group.group_id}."
                )

    tables = ExportTables(
        participants=tuple(participant_rows),
        ratings=tuple(rating_rows),
    )
    validate_export_tables(tables)
    return tables


def validate_export_tables(tables: ExportTables) -> None:
    """Validate row keys, row grain, and participant-rating relationships."""
    participant_ids: set[str] = set()
    for row in tables.participants:
        if tuple(row) != PARTICIPANT_COLUMNS:
            raise ExportValidationError("Participant export columns changed.")
        session_id = row["session_id"]
        if not isinstance(session_id, str) or session_id in participant_ids:
            raise ExportValidationError(
                "Participant export must contain one row per session."
            )
        participant_ids.add(session_id)

    rating_keys: set[tuple[object, object, object]] = set()
    rating_counts: dict[str, int] = {}
    for row in tables.ratings:
        if tuple(row) != RATING_COLUMNS:
            raise ExportValidationError("Rating export columns changed.")
        session_id = row["session_id"]
        key = (session_id, row["group_id"], row["variant_id"])
        if session_id not in participant_ids or key in rating_keys:
            raise ExportValidationError("Rating export has an invalid row grain.")
        rating_keys.add(key)
        rating_counts[str(session_id)] = rating_counts.get(str(session_id), 0) + 1

    for row in tables.participants:
        expected = int(row["completed_group_count"]) * 8
        actual = rating_counts.get(str(row["session_id"]), 0)
        if actual != expected:
            raise ExportValidationError(
                f"Session {row['session_id']} has {actual} rating rows; "
                f"expected {expected}."
            )


def rows_to_csv(
    columns: tuple[str, ...],
    rows: Iterable[dict[str, object]],
) -> str:
    """Serialize validated rows with stable columns and spreadsheet-safe UTF-8."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                column: _spreadsheet_safe_value(value)
                for column, value in row.items()
            }
        )
    return output.getvalue()


def _spreadsheet_safe_value(value: object) -> object:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def write_export_files(
    tables: ExportTables,
    output_directory: Path = DEFAULT_EXPORT_DIRECTORY,
) -> tuple[Path, Path]:
    """Atomically replace both local analysis CSV files."""
    validate_export_tables(tables)
    output_directory.mkdir(parents=True, exist_ok=True)
    outputs = (
        (
            output_directory / "participants.csv",
            rows_to_csv(PARTICIPANT_COLUMNS, tables.participants),
        ),
        (
            output_directory / "ratings.csv",
            rows_to_csv(RATING_COLUMNS, tables.ratings),
        ),
    )
    written: list[Path] = []
    for destination, content in outputs:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8-sig",
                newline="",
                dir=output_directory,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, destination)
        except OSError as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise ExportValidationError(
                f"Could not write export file {destination}."
            ) from error
        written.append(destination)
    return written[0], written[1]
