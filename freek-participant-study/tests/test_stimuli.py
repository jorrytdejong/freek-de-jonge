import csv
import tempfile
import unittest
from pathlib import Path

from app.stimuli import (
    EXPECTED_GROUP_COUNT,
    EXPECTED_VARIANTS_PER_GROUP,
    StimulusValidationError,
    load_stimuli,
)


class StimulusValidationTest(unittest.TestCase):
    def test_default_file_matches_study_contract(self) -> None:
        groups = load_stimuli()

        self.assertEqual(len(groups), EXPECTED_GROUP_COUNT)
        self.assertTrue(
            all(len(group.variants) == EXPECTED_VARIANTS_PER_GROUP for group in groups)
        )
        self.assertEqual(
            len({variant.variant_id for group in groups for variant in group.variants}),
            EXPECTED_GROUP_COUNT * EXPECTED_VARIANTS_PER_GROUP,
        )

    def test_missing_variant_is_rejected(self) -> None:
        source_path = Path(__file__).resolve().parents[1] / "data" / "jokes.csv"
        with source_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        with tempfile.TemporaryDirectory() as temp_directory:
            invalid_path = Path(temp_directory) / "jokes.csv"
            with invalid_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows[:-1])

            with self.assertRaisesRegex(
                StimulusValidationError,
                "G12 bevat 7 varianten",
            ):
                load_stimuli(invalid_path)

    def test_variant_linked_to_wrong_group_is_rejected(self) -> None:
        source_path = Path(__file__).resolve().parents[1] / "data" / "jokes.csv"
        with source_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["variant_id"] = "G02-V01"

        with tempfile.TemporaryDirectory() as temp_directory:
            invalid_path = Path(temp_directory) / "jokes.csv"
            with invalid_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            with self.assertRaisesRegex(
                StimulusValidationError,
                "die niet bij 'G01' hoort",
            ):
                load_stimuli(invalid_path)


if __name__ == "__main__":
    unittest.main()
