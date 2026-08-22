import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from app.storage import (
    AlreadySubmittedError,
    GoogleSheetsProgressStorage,
    ProgressStorageError,
)
from app.storage.csv_storage import FIELDNAMES


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeAPIError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"API status {status_code}")
        self.response = FakeResponse(status_code)


class FakeWorksheet:
    def __init__(self) -> None:
        self.values: list[list[str]] = []
        self.get_failures: list[Exception] = []
        self.timeout_after_next_append = False
        self.append_count = 0
        self._lock = threading.Lock()

    def get_all_values(self) -> list[list[str]]:
        with self._lock:
            if self.get_failures:
                raise self.get_failures.pop(0)
            return [row.copy() for row in self.values]

    def append_row(
        self,
        values: list[str],
        *,
        value_input_option: str,
        table_range: str,
    ) -> None:
        self.assert_raw(value_input_option)
        assert table_range == "A:L"
        with self._lock:
            self.values.append(list(values))
            self.append_count += 1
            if self.timeout_after_next_append:
                self.timeout_after_next_append = False
                raise TimeoutError("Response lost after append.")

    def update(
        self,
        values: list[list[str]],
        range_name: str,
        *,
        value_input_option: str,
    ) -> None:
        self.assert_raw(value_input_option)
        start_row = int(range_name.split(":", 1)[0][1:])
        with self._lock:
            while len(self.values) < start_row:
                self.values.append([])
            self.values[start_row - 1] = list(values[0])

    @staticmethod
    def assert_raw(value_input_option: str) -> None:
        assert value_input_option == "RAW"


class GoogleSheetsProgressStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.worksheet = FakeWorksheet()
        self.sleeps: list[float] = []
        self.storage = GoogleSheetsProgressStorage(
            self.worksheet,
            retry_delay_seconds=0.1,
            sleep=self.sleeps.append,
        )
        self.now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)

    def save(self, session_id: str = "test-session-01"):
        return self.storage.save_progress(
            session_id=session_id,
            study_version="pilot-1",
            is_test=session_id.startswith("test-"),
            current_page="group-2",
            profile={"age": 37},
            responses={"G01": {"comment": "Klaar."}},
            drafts={"G02": {"comment": "Bezig."}},
            now=self.now,
        )

    def test_round_trip_uses_the_shared_tabular_contract(self) -> None:
        saved = self.save()

        self.assertEqual(self.storage.load_progress(saved.session_id), saved)
        self.assertEqual(tuple(self.worksheet.values[0]), FIELDNAMES)
        self.assertEqual(len(self.worksheet.values), 2)

    def test_transient_reads_use_exponential_retry(self) -> None:
        self.worksheet.get_failures = [FakeAPIError(429), FakeAPIError(503)]

        self.assertIsNone(self.storage.load_progress("missing-session"))

        self.assertEqual(self.sleeps, [0.1, 0.2])

    def test_blank_first_row_is_initialized_as_an_empty_sheet(self) -> None:
        self.worksheet.values = [[]]

        self.assertIsNone(self.storage.load_progress("missing-session"))
        self.assertEqual(tuple(self.worksheet.values[0]), FIELDNAMES)

    def test_legacy_index_column_is_ignored(self) -> None:
        self.worksheet.values = [["", *FIELDNAMES], ["0", *[""] * len(FIELDNAMES)]]

        self.assertEqual(
            self.storage._read_rows(),
            [[""] * len(FIELDNAMES)],
        )

    def test_permanent_api_error_is_not_retried(self) -> None:
        self.worksheet.get_failures = [FakeAPIError(403)]

        with self.assertRaisesRegex(ProgressStorageError, "operation failed"):
            self.storage.list_progress()

        self.assertEqual(self.sleeps, [])

    def test_timeout_after_append_is_retried_without_duplicate_row(self) -> None:
        self.worksheet.timeout_after_next_append = True

        saved = self.save()

        self.assertEqual(self.storage.load_progress(saved.session_id), saved)
        self.assertEqual(self.worksheet.append_count, 1)
        self.assertEqual(len(self.worksheet.values), 2)
        self.assertEqual(self.sleeps, [0.1])

    def test_concurrent_real_submission_accepts_exactly_one(self) -> None:
        barrier = threading.Barrier(2)

        def submit() -> str:
            barrier.wait()
            try:
                self.storage.submit_response(
                    session_id="real-session-01",
                    study_version="pilot-1",
                    is_test=False,
                    profile={"age": 40},
                    responses={"G01": {"comment": "Klaar."}},
                    final_comment="Afgerond.",
                    now=self.now,
                )
            except AlreadySubmittedError:
                return "rejected"
            return "submitted"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: submit(), range(2)))

        self.assertCountEqual(outcomes, ["submitted", "rejected"])
        saved = self.storage.load_progress("real-session-01")
        assert saved is not None
        self.assertEqual(len(saved.submissions), 1)


if __name__ == "__main__":
    unittest.main()
