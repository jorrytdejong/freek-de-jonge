import csv
import tempfile
import unittest
from pathlib import Path

from scripts.validate_acl_study import validate_study


class QualityGateDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.stimuli_path = cls.project_root / "data" / "acl_jokes.csv"
        cls.staging_sessions_path = (
            cls.project_root / "data" / "acl_sessions.staging.csv"
        )

    def test_staging_registry_is_balanced_and_test_only(self) -> None:
        self.assertEqual(
            validate_study(
                stimuli_path=self.stimuli_path,
                sessions_path=self.staging_sessions_path,
                require_test_only=True,
            ),
            (120, 10, 200),
        )

    def test_staging_validation_rejects_a_real_session(self) -> None:
        with self.staging_sessions_path.open(encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            fieldnames = tuple(reader.fieldnames or ())
            rows = list(reader)
        rows[0]["is_test"] = "false"
        rows[0]["recruitment_source"] = "direct"
        with tempfile.TemporaryDirectory() as directory:
            sessions_path = Path(directory) / "sessions.csv"
            with sessions_path.open("w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "non-test session"):
                validate_study(
                    stimuli_path=self.stimuli_path,
                    sessions_path=sessions_path,
                    require_test_only=True,
                )


if __name__ == "__main__":
    unittest.main()
