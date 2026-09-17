import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class ProlificSplitFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.app_path = self.project_root / "streamlit_app.py"

    def write_split_registry(self, path: Path) -> tuple[str, str]:
        with (self.project_root / "data" / "acl_sessions.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            source_rows = list(csv.DictReader(handle))
        network_id = "network-participant-A1B2"
        prolific_id = "prolific-participant-C3D4"
        rows = [
            {
                **source_rows[0],
                "session_id": network_id,
                "is_test": "false",
                "recruitment_source": "network",
            },
            {
                **source_rows[1],
                "session_id": prolific_id,
                "is_test": "false",
                "recruitment_source": "prolific",
            },
        ]
        fieldnames = [*source_rows[0], "recruitment_source"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return network_id, prolific_id

    def test_only_prolific_source_requires_prolific_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sessions_path = root / "sessions.csv"
            progress_path = root / "progress.csv"
            network_id, prolific_id = self.write_split_registry(sessions_path)
            environment = {
                "FREEK_STUDY_SESSIONS_PATH": str(sessions_path),
                "FREEK_STUDY_PROGRESS_PATH": str(progress_path),
                "FREEK_STUDY_PROLIFIC_ENABLED": "true",
            }
            with patch.dict(os.environ, environment):
                network = AppTest.from_file(self.app_path)
                network.query_params["session"] = network_id
                network.query_params["page"] = "intro"
                network.run(timeout=20)
                self.assertFalse(network.exception)
                self.assertNotIn(
                    "Voor deelname via het persoonlijke netwerk is geen vergoeding.",
                    [caption.value for caption in network.caption],
                )

                prolific = AppTest.from_file(self.app_path)
                prolific.query_params["session"] = prolific_id
                prolific.run(timeout=20)
                self.assertFalse(prolific.exception)
                self.assertTrue(
                    any(
                        "Open dit onderzoek vanuit je Prolific-deelnemerspagina."
                        in error.value
                        for error in prolific.error
                    )
                )


if __name__ == "__main__":
    unittest.main()
