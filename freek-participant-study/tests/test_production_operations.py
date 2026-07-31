import csv
import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app.storage import CSVProgressStorage
from scripts.backup_progress import write_backup
from scripts.generate_production_sessions import generate_rows, read_rows, write_rows


class ProductionOperationsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.test_rows = read_rows(self.project_root / "data" / "sessions.staging.csv")

    def test_production_generator_creates_balanced_private_capacity(self) -> None:
        counter = iter(range(1, 100))
        rows = generate_rows(
            real_count=40,
            test_rows=self.test_rows,
            created_at=date(2026, 7, 31),
            id_factory=lambda: f"participant-secret-{next(counter):03d}",
        )

        self.assertEqual(len(rows), 50)
        self.assertEqual(sum(row["is_test"] == "false" for row in rows), 40)
        self.assertEqual(len({row["session_id"] for row in rows}), 50)
        exposure = Counter(
            group_id for row in rows for group_id in row["assignment_groups"].split("|")
        )
        self.assertLessEqual(max(exposure.values()) - min(exposure.values()), 1)

    def test_generator_refuses_to_overwrite_private_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sessions.csv"
            write_rows(path, self.test_rows)

            with self.assertRaises(FileExistsError):
                write_rows(path, self.test_rows)

    def test_raw_csv_backup_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            progress_path = Path(directory) / "progress.csv"
            backup_path = Path(directory) / "backup.csv"
            storage = CSVProgressStorage(progress_path)
            storage.save_progress(
                session_id="test-session-01",
                study_version="pilot-1",
                is_test=True,
                current_page="group-1",
                profile={"age": 37},
                responses={},
                drafts={},
            )

            with patch.dict(
                "os.environ",
                {
                    "FREEK_STUDY_STORAGE": "csv",
                    "FREEK_STUDY_PROGRESS_PATH": str(progress_path),
                },
                clear=True,
            ):
                count = write_backup(backup_path)

            self.assertEqual(count, 1)
            with backup_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["session_id"], "test-session-01")


if __name__ == "__main__":
    unittest.main()
