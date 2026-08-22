"""Durable Google Sheets storage for participant progress."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Protocol, TypeVar

from app.storage.base import SavedProgress
from app.storage.csv_storage import (
    FIELDNAMES,
    AlreadySubmittedError,
    ProgressStorageError,
    parse_progress_row,
    serialize_progress_row,
)

T = TypeVar("T")
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
INITIALIZATION_ATTEMPTS = 4


class Worksheet(Protocol):
    def get_all_values(self) -> list[list[str]]: ...

    def append_row(
        self,
        values: Sequence[str],
        *,
        value_input_option: str,
        table_range: str,
    ) -> object: ...

    def update(
        self,
        values: Sequence[Sequence[str]],
        range_name: str,
        *,
        value_input_option: str,
    ) -> object: ...


def _is_transient(error: Exception) -> bool:
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    return status_code in TRANSIENT_STATUS_CODES


class GoogleSheetsProgressStorage:
    """Keep one current snapshot per session in a private worksheet."""

    def __init__(
        self,
        worksheet: Worksheet,
        *,
        max_attempts: int = 4,
        retry_delay_seconds: float = 0.25,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one.")
        self.worksheet = worksheet
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.sleep = sleep
        self._lock = threading.RLock()

    @classmethod
    def from_service_account(
        cls,
        *,
        spreadsheet_url: str,
        worksheet_name: str,
        credentials: Mapping[str, object],
    ) -> GoogleSheetsProgressStorage:
        import gspread

        for attempt in range(1, INITIALIZATION_ATTEMPTS + 1):
            try:
                client = gspread.service_account_from_dict(dict(credentials))
                spreadsheet = client.open_by_url(spreadsheet_url)
                worksheet = spreadsheet.worksheet(worksheet_name)
                break
            except Exception as error:
                if not _is_transient(error) or attempt == INITIALIZATION_ATTEMPTS:
                    raise ProgressStorageError(
                        "Google Sheets storage could not be initialized."
                    ) from error
                time.sleep(0.25 * (2 ** (attempt - 1)))
        else:
            raise AssertionError("Initialization loop exhausted without returning.")
        return cls(worksheet)

    def _retry(self, operation: Callable[[], T]) -> T:
        for attempt in range(1, self.max_attempts + 1):
            try:
                return operation()
            except Exception as error:
                if not _is_transient(error) or attempt == self.max_attempts:
                    raise ProgressStorageError(
                        "Google Sheets storage operation failed."
                    ) from error
                self.sleep(self.retry_delay_seconds * (2 ** (attempt - 1)))
        raise AssertionError("Retry loop exhausted without returning.")

    def _read_rows(self) -> list[list[str]]:
        values = self._retry(self.worksheet.get_all_values)
        if not values or not any(values[0]):
            self._retry(
                lambda: self.worksheet.update(
                    [list(FIELDNAMES)],
                    "A1:L1",
                    value_input_option="RAW",
                )
            )
            return []
        # Older spreadsheet exports could leave a pandas-style index column
        # before the shared contract. Keep reading those rows so a harmless
        # legacy layout cannot take the whole app offline.
        if (
            len(values[0]) == len(FIELDNAMES) + 1
            and not values[0][0]
            and tuple(values[0][1:]) == FIELDNAMES
        ):
            values = [row[1:] for row in values]
        if tuple(values[0]) != FIELDNAMES:
            raise ProgressStorageError(
                "Google Sheets progress worksheet has an unexpected column contract."
            )
        return values[1:]

    def _read_all(self) -> tuple[dict[str, SavedProgress], dict[str, int]]:
        records: dict[str, SavedProgress] = {}
        row_numbers: dict[str, int] = {}
        for row_number, values in enumerate(self._read_rows(), start=2):
            if len(values) > len(FIELDNAMES):
                raise ProgressStorageError(
                    f"Progress row {row_number} has unexpected extra columns."
                )
            padded = [*values, *([""] * (len(FIELDNAMES) - len(values)))]
            row = dict(zip(FIELDNAMES, padded, strict=False))
            record = parse_progress_row(row, row_number=row_number)
            if record.session_id in records:
                raise ProgressStorageError(
                    f"Duplicate progress session: {record.session_id}."
                )
            records[record.session_id] = record
            row_numbers[record.session_id] = row_number
        return records, row_numbers

    def list_progress(self) -> tuple[SavedProgress, ...]:
        with self._lock:
            records, _ = self._read_all()
            return tuple(records[session_id] for session_id in sorted(records))

    def load_progress(self, session_id: str) -> SavedProgress | None:
        with self._lock:
            records, _ = self._read_all()
            return records.get(session_id)

    def _persist(self, record: SavedProgress) -> None:
        row = serialize_progress_row(record)
        values = [row[field] for field in FIELDNAMES]

        def write() -> None:
            _, row_numbers = self._read_all()
            row_number = row_numbers.get(record.session_id)
            if row_number is None:
                self.worksheet.append_row(
                    values,
                    value_input_option="RAW",
                    table_range="A:L",
                )
            else:
                self.worksheet.update(
                    [values],
                    f"A{row_number}:L{row_number}",
                    value_input_option="RAW",
                )

        self._retry(write)

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
            records, _ = self._read_all()
            existing = records.get(session_id)
            if (
                existing is not None
                and existing.status == "submitted"
                and not existing.is_test
            ):
                raise AlreadySubmittedError(
                    f"Real session {session_id} is already submitted."
                )
            if existing is not None and existing.is_test != is_test:
                raise ProgressStorageError(f"Session type changed for {session_id}.")
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
                created_at=existing.created_at if existing is not None else saved_at,
                updated_at=saved_at,
            )
            self._persist(record)
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
            raise ProgressStorageError("Submission timestamp must include a timezone.")
        with self._lock:
            records, _ = self._read_all()
            existing = records.get(session_id)
            if existing is not None and existing.submissions and not is_test:
                raise AlreadySubmittedError(
                    f"Real session {session_id} is already submitted."
                )
            if existing is not None and existing.is_test != is_test:
                raise ProgressStorageError(f"Session type changed for {session_id}.")
            previous = existing.submissions if existing is not None else ()
            number = len(previous) + 1
            event: dict[str, object] = {
                "submission_id": f"{session_id}-submission-{number:03d}",
                "submission_number": number,
                "submitted_at": submitted_at.isoformat(),
                "study_version": study_version,
                "is_test": is_test,
                "profile": profile,
                "responses": responses,
                "final_comment": final_comment,
            }
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
                submissions=(*previous, event),
                created_at=existing.created_at
                if existing is not None
                else submitted_at,
                updated_at=submitted_at,
            )
            self._persist(record)
            return record
