import csv
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.storage import (
    AlreadySubmittedError,
    CSVProgressStorage,
    ProgressStorageError,
)
from app.storage.csv_storage import FIELDNAMES, LEGACY_FIELDNAMES


class CSVProgressStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "progress.csv"
        self.storage = CSVProgressStorage(self.path)
        self.first_time = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)

    def save_example(
        self,
        *,
        session_id: str = "test-session-01",
        now: datetime | None = None,
        current_page: str = "group-2",
    ):
        return self.storage.save_progress(
            session_id=session_id,
            study_version="pilot-1",
            is_test=True,
            current_page=current_page,
            profile={
                "age": 37,
                "freek_familiarity": 4,
                "consent": True,
            },
            responses={
                "G01": {
                    "group_id": "G01",
                    "ratings": [],
                    "comment": "",
                }
            },
            drafts={
                "G02": {
                    "group_id": "G02",
                    "ratings": {
                        "G02-V01": {
                            "funniness": 3,
                            "freek_similarity": None,
                        }
                    },
                    "comment": "Halverwege.",
                }
            },
            now=now or self.first_time,
        )

    def test_round_trip_preserves_structured_progress(self) -> None:
        saved = self.save_example()

        loaded = self.storage.load_progress("test-session-01")

        self.assertEqual(loaded, saved)
        assert loaded is not None
        self.assertEqual(loaded.current_page, "group-2")
        self.assertEqual(loaded.profile["age"], 37)
        self.assertEqual(
            loaded.drafts["G02"]["comment"],
            "Halverwege.",
        )

    def test_replacing_one_session_preserves_others_and_created_at(self) -> None:
        first = self.save_example()
        self.save_example(
            session_id="test-session-02",
            now=self.first_time + timedelta(minutes=1),
        )
        updated = self.save_example(
            now=self.first_time + timedelta(minutes=2),
            current_page="group-3",
        )

        self.assertEqual(updated.created_at, first.created_at)
        self.assertEqual(
            updated.updated_at,
            self.first_time + timedelta(minutes=2),
        )
        self.assertEqual(
            self.storage.load_progress("test-session-02").session_id,
            "test-session-02",
        )
        with self.path.open(encoding="utf-8", newline="") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 2)

    def test_list_progress_returns_sessions_in_stable_order(self) -> None:
        self.save_example(session_id="test-session-02")
        self.save_example(session_id="test-session-01")

        self.assertEqual(
            [record.session_id for record in self.storage.list_progress()],
            ["test-session-01", "test-session-02"],
        )

    def test_malformed_existing_file_is_not_overwritten(self) -> None:
        self.path.write_text(
            "session_id,unexpected\nbroken,value\n",
            encoding="utf-8",
        )
        original = self.path.read_bytes()

        with self.assertRaisesRegex(
            ProgressStorageError,
            "unexpected column contract",
        ):
            self.save_example()

        self.assertEqual(self.path.read_bytes(), original)

    def test_invalid_json_is_rejected(self) -> None:
        self.save_example()
        content = self.path.read_text(encoding="utf-8")
        self.path.write_text(
            content.replace('"{""G01""', '"{invalid'),
            encoding="utf-8",
        )

        with self.assertRaises(ProgressStorageError):
            self.storage.load_progress("test-session-01")

    def test_failed_serialization_leaves_previous_file_intact(self) -> None:
        self.save_example()
        original = self.path.read_bytes()

        with self.assertRaisesRegex(
            ProgressStorageError,
            "could not be replaced",
        ):
            self.storage.save_progress(
                session_id="test-session-01",
                study_version="pilot-1",
                is_test=True,
                current_page="group-2",
                profile=None,
                responses={"G01": {"not_json": {1, 2, 3}}},
                drafts={},
                now=self.first_time + timedelta(minutes=1),
            )

        self.assertEqual(self.path.read_bytes(), original)

    def test_timezone_free_save_timestamp_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ProgressStorageError,
            "timestamp must include a timezone",
        ):
            self.save_example(now=datetime(2026, 7, 30, 12, 0))

    def test_legacy_progress_is_loaded_and_upgraded_on_save(self) -> None:
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=LEGACY_FIELDNAMES)
            writer.writeheader()
            writer.writerow(
                {
                    "session_id": "test-session-01",
                    "study_version": "pilot-1",
                    "is_test": "true",
                    "current_page": "group-2",
                    "profile_json": "null",
                    "responses_json": "{}",
                    "drafts_json": "{}",
                    "created_at": self.first_time.isoformat(),
                    "updated_at": self.first_time.isoformat(),
                }
            )

        loaded = self.storage.load_progress("test-session-01")

        assert loaded is not None
        self.assertEqual(loaded.status, "in_progress")
        self.assertFalse(loaded.submissions)
        self.save_example(now=self.first_time + timedelta(minutes=1))
        with self.path.open(encoding="utf-8", newline="") as handle:
            self.assertIn("submissions_json", next(csv.reader(handle)))

    def test_real_session_can_only_be_submitted_once(self) -> None:
        first = self.storage.submit_response(
            session_id="real-session-01",
            study_version="pilot-1",
            is_test=False,
            profile={"age": 40},
            responses={"G01": {"ratings": []}},
            final_comment="Klaar.",
            now=self.first_time,
        )

        self.assertEqual(first.status, "submitted")
        self.assertEqual(len(first.submissions), 1)
        with self.assertRaises(AlreadySubmittedError):
            self.storage.submit_response(
                session_id="real-session-01",
                study_version="pilot-1",
                is_test=False,
                profile={"age": 40},
                responses={"G01": {"ratings": []}},
                final_comment="Nogmaals.",
                now=self.first_time + timedelta(minutes=1),
            )
        with self.assertRaises(AlreadySubmittedError):
            self.storage.save_progress(
                session_id="real-session-01",
                study_version="pilot-1",
                is_test=False,
                current_page="group-1",
                profile={"age": 40},
                responses={},
                drafts={},
            )

    def test_test_submissions_are_numbered_and_immutable(self) -> None:
        first = self.storage.submit_response(
            session_id="test-session-01",
            study_version="pilot-1",
            is_test=True,
            profile={"age": 37},
            responses={"G01": {"comment": "Eerste versie."}},
            final_comment="Eerste inzending.",
            now=self.first_time,
        )
        second = self.storage.submit_response(
            session_id="test-session-01",
            study_version="pilot-1",
            is_test=True,
            profile={"age": 38},
            responses={"G01": {"comment": "Tweede versie."}},
            final_comment="Tweede inzending.",
            now=self.first_time + timedelta(minutes=1),
        )

        self.assertEqual(len(second.submissions), 2)
        self.assertEqual(
            first.submissions[0]["submission_id"],
            "test-session-01-submission-001",
        )
        self.assertEqual(
            second.submissions[1]["submission_id"],
            "test-session-01-submission-002",
        )
        self.assertEqual(
            second.submissions[0]["final_comment"],
            "Eerste inzending.",
        )
        self.assertNotEqual(
            json.dumps(second.submissions[0], sort_keys=True),
            json.dumps(second.submissions[1], sort_keys=True),
        )

    def test_tampered_submission_event_is_rejected(self) -> None:
        self.storage.submit_response(
            session_id="test-session-01",
            study_version="pilot-1",
            is_test=True,
            profile={"age": 37},
            responses={"G01": {"ratings": []}},
            final_comment="",
            now=self.first_time,
        )
        with self.path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        events = json.loads(rows[0]["submissions_json"])
        events[0]["submission_id"] = "tampered"
        rows[0]["submissions_json"] = json.dumps(events)
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

        with self.assertRaisesRegex(
            ProgressStorageError,
            "invalid submission event",
        ):
            self.storage.load_progress("test-session-01")


if __name__ == "__main__":
    unittest.main()
