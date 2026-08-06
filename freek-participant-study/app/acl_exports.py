"""Create analysis-ready ACL participant and item-rating exports."""

from __future__ import annotations

import csv
import io
import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.acl_assignment import assignment_fingerprint, build_assignment
from app.acl_config import RATING_DIMENSIONS, STUDY_VERSION
from app.acl_ratings import MAXIMUM_RATING, MINIMUM_RATING
from app.acl_sessions import ParticipantSession
from app.acl_stimuli import JokeItem
from app.storage.base import SavedProgress

EXPORT_SCHEMA_VERSION = "2"
DEFAULT_EXPORT_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "data" / "runtime" / "acl_exports"
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
    "assigned_item_ids",
    "assignment_seed",
    "assignment_fingerprint",
    "item_count",
    "completed_item_count",
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
    "item_id",
    "item_position",
    "topic_id",
    "topic",
    "condition_code",
    "pipeline_family",
    "freek_style",
    "model",
    "result_sha256",
    "joke_text",
    "funniness",
    "freek_similarity",
    "coherence",
    "originality",
    "final_comment",
    "submitted_at",
)


class ExportValidationError(ValueError):
    """Raised when saved ACL data violates the versioned export schema."""


@dataclass(frozen=True)
class ExportTables:
    participants: tuple[dict[str, object], ...]
    ratings: tuple[dict[str, object], ...]


def _integer(
    value: object, *, field: str, session_id: str, minimum: int, maximum: int
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise ExportValidationError(f"Session {session_id} has invalid {field}.")
    return value


def _snapshot(record: SavedProgress) -> tuple[object, ...]:
    if not record.submissions:
        return record.profile, record.responses, record.final_comment, "", "", ""
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
    stimuli: tuple[JokeItem, ...],
) -> ExportTables:
    items_by_id = {item.item_id: item for item in stimuli}
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
                f"Session {session_id} is absent from registry."
            )
        if (
            record.study_version != STUDY_VERSION
            or record.is_test != session.is_test
            or record.status not in {"in_progress", "submitted"}
            or ((record.status == "submitted") != bool(record.submissions))
        ):
            raise ExportValidationError(
                f"Session {session_id} has inconsistent metadata."
            )

        assignment = build_assignment(session, stimuli)
        fingerprint = assignment_fingerprint(assignment)
        (
            profile,
            responses,
            final_comment,
            submission_id,
            submission_number,
            submitted_at,
        ) = _snapshot(record)
        if not isinstance(responses, dict) or not isinstance(final_comment, str):
            raise ExportValidationError(f"Session {session_id} has invalid payloads.")
        assigned_ids = {item.item_id for item in assignment.items}
        if set(responses) - assigned_ids:
            raise ExportValidationError(
                f"Session {session_id} has unassigned responses."
            )
        if record.status == "submitted" and set(responses) != assigned_ids:
            raise ExportValidationError(
                f"Submitted session {session_id} is incomplete."
            )

        age: int | str = ""
        familiarity: int | str = ""
        consent: bool | str = ""
        if profile is not None:
            if not isinstance(profile, dict):
                raise ExportValidationError(
                    f"Session {session_id} has invalid profile."
                )
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
                raise ExportValidationError(f"Session {session_id} lacks consent.")
            consent = True

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
                "assigned_item_ids": "|".join(
                    item.item_id for item in assignment.items
                ),
                "assignment_seed": session_id,
                "assignment_fingerprint": fingerprint,
                "item_count": len(assignment.items),
                "completed_item_count": len(responses),
                "final_comment": final_comment,
                "created_at": record.created_at.isoformat(),
                "updated_at": record.updated_at.isoformat(),
                "submitted_at": submitted_at,
            }
        )

        for assigned in assignment.items:
            response = responses.get(assigned.item_id)
            if response is None:
                continue
            if not isinstance(response, dict):
                raise ExportValidationError(
                    f"Session {session_id} has invalid response."
                )
            if (
                response.get("item_id") != assigned.item_id
                or response.get("display_position") != assigned.display_position
            ):
                raise ExportValidationError(
                    f"Session {session_id} has a mismatched item response."
                )
            scores = {
                dimension: _integer(
                    response.get(dimension),
                    field=dimension,
                    session_id=session_id,
                    minimum=MINIMUM_RATING,
                    maximum=MAXIMUM_RATING,
                )
                for dimension in RATING_DIMENSIONS
            }
            stimulus = items_by_id[assigned.item_id]
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
                    "item_id": stimulus.item_id,
                    "item_position": assigned.display_position,
                    "topic_id": stimulus.topic_id,
                    "topic": stimulus.topic,
                    "condition_code": stimulus.condition_code,
                    "pipeline_family": stimulus.pipeline_family,
                    "freek_style": stimulus.freek_style,
                    "model": stimulus.model,
                    "result_sha256": stimulus.result_sha256,
                    "joke_text": stimulus.text,
                    **scores,
                    "final_comment": final_comment,
                    "submitted_at": submitted_at,
                }
            )

    tables = ExportTables(tuple(participant_rows), tuple(rating_rows))
    validate_export_tables(tables)
    return tables


def validate_export_tables(tables: ExportTables) -> None:
    participant_ids: set[str] = set()
    expected_counts: dict[str, int] = {}
    for row in tables.participants:
        if tuple(row) != PARTICIPANT_COLUMNS:
            raise ExportValidationError("Participant export columns changed.")
        session_id = row["session_id"]
        if not isinstance(session_id, str) or session_id in participant_ids:
            raise ExportValidationError("Participant export row grain is invalid.")
        participant_ids.add(session_id)
        expected_counts[session_id] = int(row["completed_item_count"])
    rating_keys: set[tuple[object, object]] = set()
    actual_counts: Counter[str] = Counter()
    for row in tables.ratings:
        if tuple(row) != RATING_COLUMNS:
            raise ExportValidationError("Rating export columns changed.")
        key = (row["session_id"], row["item_id"])
        if row["session_id"] not in participant_ids or key in rating_keys:
            raise ExportValidationError("Rating export row grain is invalid.")
        rating_keys.add(key)
        actual_counts[str(row["session_id"])] += 1
    if any(
        actual_counts[session] != expected
        for session, expected in expected_counts.items()
    ):
        raise ExportValidationError(
            "Participant and rating completion counts disagree."
        )


def rows_to_csv(columns: tuple[str, ...], rows: Iterable[dict[str, object]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {column: _spreadsheet_safe(value) for column, value in row.items()}
        )
    return output.getvalue()


def _spreadsheet_safe(value: object) -> object:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def write_export_files(
    tables: ExportTables, output_directory: Path = DEFAULT_EXPORT_DIRECTORY
) -> tuple[Path, Path]:
    validate_export_tables(tables)
    output_directory.mkdir(parents=True, exist_ok=True)
    destinations = (
        (
            output_directory / "participants.csv",
            rows_to_csv(PARTICIPANT_COLUMNS, tables.participants),
        ),
        (
            output_directory / "ratings.csv",
            rows_to_csv(RATING_COLUMNS, tables.ratings),
        ),
    )
    written = []
    for destination, content in destinations:
        temporary_path = None
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
