import csv
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.acl_assignment import build_assignment
from app.acl_sessions import load_sessions
from app.acl_stimuli import load_stimuli
from app.storage import CSVProgressStorage


class SubmittedRealSessionFlowTest(unittest.TestCase):
    def test_submitted_real_link_is_forced_to_read_only_debrief(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        app_path = project_root / "streamlit_app.py"
        stimuli = load_stimuli()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            sessions_path = temporary / "sessions.csv"
            progress_path = temporary / "progress.csv"
            with (project_root / "data" / "acl_sessions.csv").open(
                encoding="utf-8", newline=""
            ) as source:
                rows = list(csv.DictReader(source))
            real_row = {
                **rows[0],
                "session_id": "real-acl-demo-A1B2",
                "is_test": "false",
                "notes": "Automated real-session simulation",
            }
            rows.append(real_row)
            with sessions_path.open("w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            session = load_sessions(stimuli, sessions_path)[real_row["session_id"]]
            assignment = build_assignment(session, stimuli)
            responses = {
                item.item_id: {
                    "item_id": item.item_id,
                    "display_position": item.display_position,
                    "funniness": 3,
                    "freek_similarity": 3,
                    "coherence": 3,
                    "originality": 3,
                }
                for item in assignment.items
            }
            storage = CSVProgressStorage(progress_path)
            storage.submit_response(
                session_id=session.session_id,
                study_version="acl-1",
                is_test=False,
                profile={"age": 40, "freek_familiarity": 3, "consent": True},
                responses=responses,
                final_comment="Definitief.",
                now=datetime(2026, 8, 6, 12, 0, tzinfo=UTC),
            )
            with patch.dict(
                os.environ,
                {
                    "FREEK_STUDY_PROGRESS_PATH": str(progress_path),
                    "FREEK_STUDY_SESSIONS_PATH": str(sessions_path),
                },
            ):
                app = AppTest.from_file(app_path)
                app.query_params["session"] = session.session_id
                app.query_params["page"] = "item-1"
                app.run(timeout=20)
            self.assertFalse(app.exception)
            self.assertEqual(app.query_params["page"][0], "debrief")
            self.assertEqual(len(app.expander), 12)
            self.assertNotIn("Nieuwe testinzending", [b.label for b in app.button])
            self.assertFalse(any(b.label.startswith("Bewerk grap") for b in app.button))


if __name__ == "__main__":
    unittest.main()
