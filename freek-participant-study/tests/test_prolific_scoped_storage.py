import tempfile
import unittest
from pathlib import Path

from app.storage.csv_storage import CSVProgressStorage
from app.storage.prolific_scoped import ProlificScopedProgressStorage


class ProlificScopedStorageTest(unittest.TestCase):
    def test_same_assignment_url_can_store_two_submissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backend = CSVProgressStorage(Path(directory) / "progress.csv")
            first = ProlificScopedProgressStorage(
                backend,
                assignment_session_id="acl-prolific-01-abcd1234",
                study_id="study_12345678",
                submission_id="submission_12345678",
            )
            profile_a = {
                "age": 31,
                "freek_familiarity": 2,
                "consent": True,
                "_prolific": {"submission_id": "submission_12345678"},
            }
            first.save_progress(
                session_id="acl-prolific-01-abcd1234",
                study_version="acl-1",
                is_test=False,
                current_page="intro",
                profile=profile_a,
                responses={},
                drafts={},
            )
            first.submit_response(
                session_id="acl-prolific-01-abcd1234",
                study_version="acl-1",
                is_test=False,
                profile=profile_a,
                responses={"T01-A1": {"item_id": "T01-A1"}},
                final_comment="",
            )

            second = ProlificScopedProgressStorage(
                backend,
                assignment_session_id="acl-prolific-01-abcd1234",
                study_id="study_12345678",
                submission_id="submission_87654321",
            )
            self.assertIsNone(second.load_progress("acl-prolific-01-abcd1234"))
            profile_b = {
                "age": 42,
                "freek_familiarity": 4,
                "consent": True,
                "_prolific": {"submission_id": "submission_87654321"},
            }
            second.submit_response(
                session_id="acl-prolific-01-abcd1234",
                study_version="acl-1",
                is_test=False,
                profile=profile_b,
                responses={"T01-A1": {"item_id": "T01-A1"}},
                final_comment="",
            )

            records = backend.list_progress()
            self.assertEqual(len(records), 2)
            self.assertEqual(
                {record.profile["_prolific"]["submission_id"] for record in records},
                {"submission_12345678", "submission_87654321"},
            )


if __name__ == "__main__":
    unittest.main()
