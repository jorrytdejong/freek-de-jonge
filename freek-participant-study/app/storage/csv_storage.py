"""Atomic local CSV storage for resumable participant progress."""

from __future__ import annotations

import csv
import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

from app.storage.base import SavedProgress

DEFAULT_PROGRESS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "runtime" / "progress.csv"
)
LEGACY_FIELDNAMES = (
    "session_id",
    "study_version",
    "is_test",
    "current_page",
    "profile_json",
    "responses_json",
    "drafts_json",
    "created_at",
    "updated_at",
)
FIELDNAMES = (
    "session_id",
    "study_version",
    "is_test",
    "current_page",
    "profile_json",
    "responses_json",
    "drafts_json",
    "status",
    "final_comment",
    "submissions_json",
    "created_at",
    "updated_at",
)

_LOCKS_GUARD = threading.Lock()
_FILE_LOCKS: dict[Path, threading.RLock] = {}


class ProgressStorageError(RuntimeError):
    """Raised when progress cannot be read or replaced safely."""


class AlreadySubmittedError(ProgressStorageError):
    """Raised when a real participant session is submitted again."""


def _file_lock(path: Path) -> threading.RLock:
    resolved = path.resolve()
    with _LOCKS_GUARD:
        return _FILE_LOCKS.setdefault(resolved, threading.RLock())


def _parse_json_object(
    value: str,
    *,
    field: str,
    session_id: str,
) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ProgressStorageError(
            f"Session {session_id} has invalid JSON in {field}."
        ) from error
    if not isinstance(parsed, dict):
        raise ProgressStorageError(
            f"Session {session_id} must contain a JSON object in {field}."
        )
    return parsed


def _parse_nested_objects(
    value: str,
    *,
    field: str,
    session_id: str,
) -> dict[str, dict[str, object]]:
    parsed = _parse_json_object(
        value,
        field=field,
        session_id=session_id,
    )
    if not all(
        isinstance(key, str) and isinstance(item, dict)
        for key, item in parsed.items()
    ):
        raise ProgressStorageError(
            f"Session {session_id} has invalid records in {field}."
        )
    return parsed


def _parse_submission_events(
    value: str,
    *,
    session_id: str,
    study_version: str,
    is_test: bool,
) -> tuple[dict[str, object], ...]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ProgressStorageError(
            f"Session {session_id} has invalid JSON in submissions_json."
        ) from error
    if not isinstance(parsed, list) or not all(
        isinstance(event, dict) for event in parsed
    ):
        raise ProgressStorageError(
            f"Session {session_id} has invalid submission events."
        )
    for submission_number, event in enumerate(parsed, start=1):
        expected_id = (
            f"{session_id}-submission-{submission_number:03d}"
        )
        if (
            event.get("submission_id") != expected_id
            or event.get("submission_number") != submission_number
            or event.get("study_version") != study_version
            or event.get("is_test") is not is_test
            or not isinstance(event.get("profile"), dict)
            or not isinstance(event.get("responses"), dict)
            or not isinstance(event.get("final_comment"), str)
            or not isinstance(event.get("submitted_at"), str)
        ):
            raise ProgressStorageError(
                f"Session {session_id} has an invalid submission event."
            )
        _parse_timestamp(
            event["submitted_at"],
            field="submission submitted_at",
            session_id=session_id,
        )
    return tuple(parsed)


def _parse_timestamp(
    value: str,
    *,
    field: str,
    session_id: str,
) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ProgressStorageError(
            f"Session {session_id} has invalid {field}."
        ) from error
    if parsed.tzinfo is None:
        raise ProgressStorageError(
            f"Session {session_id} has a timezone-free {field}."
        )
    return parsed


def _parse_row(row: dict[str, str], *, row_number: int) -> SavedProgress:
    session_id = (row.get("session_id") or "").strip()
    if not session_id:
        raise ProgressStorageError(
            f"Progress row {row_number} has no session_id."
        )
    is_test_text = (row.get("is_test") or "").strip().lower()
    if is_test_text not in {"true", "false"}:
        raise ProgressStorageError(
            f"Session {session_id} has invalid is_test."
        )
    study_version = (row.get("study_version") or "").strip()
    current_page = (row.get("current_page") or "").strip()
    if not study_version or not current_page:
        raise ProgressStorageError(
            f"Session {session_id} has empty progress metadata."
        )

    profile_text = (row.get("profile_json") or "").strip()
    profile = (
        None
        if profile_text == "null"
        else _parse_json_object(
            profile_text,
            field="profile_json",
            session_id=session_id,
        )
    )
    submissions_text = (row.get("submissions_json") or "").strip()
    submissions = (
        ()
        if not submissions_text
        else _parse_submission_events(
            submissions_text,
            session_id=session_id,
            study_version=study_version,
            is_test=is_test_text == "true",
        )
    )
    status = (row.get("status") or "in_progress").strip()
    if status not in {"in_progress", "submitted"}:
        raise ProgressStorageError(
            f"Session {session_id} has invalid submission status."
        )
    if (status == "submitted") != bool(submissions):
        raise ProgressStorageError(
            f"Session {session_id} has inconsistent submission status."
        )
    return SavedProgress(
        session_id=session_id,
        study_version=study_version,
        is_test=is_test_text == "true",
        current_page=current_page,
        profile=profile,
        responses=_parse_nested_objects(
            row.get("responses_json") or "",
            field="responses_json",
            session_id=session_id,
        ),
        drafts=_parse_nested_objects(
            row.get("drafts_json") or "",
            field="drafts_json",
            session_id=session_id,
        ),
        status=status,
        final_comment=row.get("final_comment") or "",
        submissions=submissions,
        created_at=_parse_timestamp(
            row.get("created_at") or "",
            field="created_at",
            session_id=session_id,
        ),
        updated_at=_parse_timestamp(
            row.get("updated_at") or "",
            field="updated_at",
            session_id=session_id,
        ),
    )


class CSVProgressStorage:
    """Store one atomic progress snapshot per anonymous session."""

    def __init__(self, path: Path = DEFAULT_PROGRESS_PATH) -> None:
        self.path = path
        self._lock = _file_lock(path)

    def _read_all(self) -> dict[str, SavedProgress]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = tuple(reader.fieldnames or ())
                if fieldnames not in {FIELDNAMES, LEGACY_FIELDNAMES}:
                    raise ProgressStorageError(
                        "Progress file has an unexpected column contract."
                    )
                rows = list(reader)
        except OSError as error:
            raise ProgressStorageError(
                f"Progress file could not be read: {self.path}"
            ) from error

        records: dict[str, SavedProgress] = {}
        for row_number, row in enumerate(rows, start=2):
            record = _parse_row(row, row_number=row_number)
            if record.session_id in records:
                raise ProgressStorageError(
                    f"Duplicate progress session: {record.session_id}."
                )
            records[record.session_id] = record
        return records

    def load_progress(self, session_id: str) -> SavedProgress | None:
        with self._lock:
            return self._read_all().get(session_id)

    def save_progress(
        self,
        *,
        session_id: str,
        study_version: str,
        is_test: bool,
        current_page: str,
        profile: dict[str, object] | None,
        responses: dict[str, dict[str, object]],
        drafts: dict[str, dict[str, object]],
        final_comment: str = "",
        submissions: tuple[dict[str, object], ...] = (),
        now: datetime | None = None,
    ) -> SavedProgress:
        saved_at = now or datetime.now(UTC)
        if saved_at.tzinfo is None:
            raise ProgressStorageError("Save timestamp must include a timezone.")

        with self._lock:
            records = self._read_all()
            existing = records.get(session_id)
            if (
                existing is not None
                and existing.status == "submitted"
                and not existing.is_test
            ):
                raise AlreadySubmittedError(
                    f"Real session {session_id} is already submitted."
                )
            record = SavedProgress(
                session_id=session_id,
                study_version=study_version,
                is_test=is_test,
                current_page=current_page,
                profile=profile,
                responses=responses,
                drafts=drafts,
                status="submitted" if submissions else "in_progress",
                final_comment=final_comment,
                submissions=submissions,
                created_at=(
                    existing.created_at if existing is not None else saved_at
                ),
                updated_at=saved_at,
            )
            records[session_id] = record
            self._write_all(records)
            return record

    def submit_response(
        self,
        *,
        session_id: str,
        study_version: str,
        is_test: bool,
        profile: dict[str, object],
        responses: dict[str, dict[str, object]],
        final_comment: str,
        now: datetime | None = None,
    ) -> SavedProgress:
        submitted_at = now or datetime.now(UTC)
        if submitted_at.tzinfo is None:
            raise ProgressStorageError(
                "Submission timestamp must include a timezone."
            )

        with self._lock:
            records = self._read_all()
            existing = records.get(session_id)
            if existing is not None and existing.submissions and not is_test:
                raise AlreadySubmittedError(
                    f"Real session {session_id} is already submitted."
                )
            if existing is not None and existing.is_test != is_test:
                raise ProgressStorageError(
                    f"Session type changed for {session_id}."
                )

            previous_submissions = (
                existing.submissions if existing is not None else ()
            )
            submission_number = len(previous_submissions) + 1
            event: dict[str, object] = {
                "submission_id": (
                    f"{session_id}-submission-{submission_number:03d}"
                ),
                "submission_number": submission_number,
                "submitted_at": submitted_at.isoformat(),
                "study_version": study_version,
                "is_test": is_test,
                "profile": profile,
                "responses": responses,
                "final_comment": final_comment,
            }
            submissions = (*previous_submissions, event)
            record = SavedProgress(
                session_id=session_id,
                study_version=study_version,
                is_test=is_test,
                current_page="debrief",
                profile=profile,
                responses=responses,
                drafts={},
                status="submitted",
                final_comment=final_comment,
                submissions=submissions,
                created_at=(
                    existing.created_at
                    if existing is not None
                    else submitted_at
                ),
                updated_at=submitted_at,
            )
            records[session_id] = record
            self._write_all(records)
            return record

    def _write_all(self, records: dict[str, SavedProgress]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
                writer.writeheader()
                for session_id in sorted(records):
                    record = records[session_id]
                    writer.writerow(
                        {
                            "session_id": record.session_id,
                            "study_version": record.study_version,
                            "is_test": str(record.is_test).lower(),
                            "current_page": record.current_page,
                            "profile_json": json.dumps(
                                record.profile,
                                ensure_ascii=True,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            "responses_json": json.dumps(
                                record.responses,
                                ensure_ascii=True,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            "drafts_json": json.dumps(
                                record.drafts,
                                ensure_ascii=True,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            "status": record.status,
                            "final_comment": record.final_comment,
                            "submissions_json": json.dumps(
                                record.submissions,
                                ensure_ascii=True,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            "created_at": record.created_at.isoformat(),
                            "updated_at": record.updated_at.isoformat(),
                        }
                    )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        except (OSError, TypeError, ValueError) as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise ProgressStorageError(
                f"Progress file could not be replaced: {self.path}"
            ) from error
