import csv
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.storage import CSVProgressStorage, ProgressStorageError


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


if __name__ == "__main__":
    unittest.main()
