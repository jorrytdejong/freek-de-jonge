import csv
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.assignment import build_assignment
from app.ratings import build_displayed_variants
from app.sessions import DEFAULT_SESSIONS_PATH, load_sessions
from app.stimuli import load_stimuli
from app.storage import CSVProgressStorage


class SubmittedRealSessionFlowTest(unittest.TestCase):
    def test_submitted_real_link_is_forced_to_read_only_debrief(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        groups = load_stimuli()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_path = Path(temporary_directory)
            sessions_path = temp_path / "sessions.csv"
            progress_path = temp_path / "progress.csv"

            with DEFAULT_SESSIONS_PATH.open(
                encoding="utf-8",
                newline="",
            ) as source:
                rows = list(csv.DictReader(source))
            rows.append(
                {
                    "session_id": "real-demo-A1B2C3",
                    "is_test": "false",
                    "active": "true",
                    "assignment_groups": "G01|G02|G03|G04|G05",
                    "created_at": "2026-07-30",
                    "notes": "Automated real-session simulation",
                }
            )
            with sessions_path.open(
                "w",
                encoding="utf-8",
                newline="",
            ) as target:
                writer = csv.DictWriter(
                    target,
                    fieldnames=rows[0].keys(),
                )
                writer.writeheader()
                writer.writerows(rows)

            sessions = load_sessions(
                {group.group_id for group in groups},
                sessions_path,
            )
            session = sessions["real-demo-A1B2C3"]
            assignment = build_assignment(session, groups)
            responses = {}
            for assigned_group in assignment.groups:
                joke_group = next(
                    group
                    for group in groups
                    if group.group_id == assigned_group.group_id
                )
                displayed = build_displayed_variants(
                    assigned_group,
                    joke_group,
                )
                responses[assigned_group.group_id] = {
                    "group_id": assigned_group.group_id,
                    "ratings": [
                        {
                            "display_label": variant.display_label,
                            "display_position": variant.display_position,
                            "variant_id": variant.variant_id,
                            "funniness": 3,
                            "freek_similarity": 3,
                        }
                        for variant in displayed
                    ],
                    "comment": "",
                }

            storage = CSVProgressStorage(progress_path)
            storage.submit_response(
                session_id=session.session_id,
                study_version="pilot-1",
                is_test=False,
                profile={
                    "age": 40,
                    "freek_familiarity": 3,
                    "consent": True,
                },
                responses=responses,
                final_comment="Definitief.",
                now=datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
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
                app.query_params["page"] = "group-1"
                app.run(timeout=15)

            self.assertFalse(app.exception)
            self.assertEqual(app.query_params["page"][0], "debrief")
            self.assertEqual(len(app.expander), 5)
            self.assertNotIn(
                "Nieuwe testinzending",
                [button.label for button in app.button],
            )
            self.assertFalse(
                any(
                    button.label.startswith("Bewerk jokegroep") for button in app.button
                )
            )
            saved = storage.load_progress(session.session_id)
            assert saved is not None
            self.assertEqual(len(saved.submissions), 1)


if __name__ == "__main__":
    unittest.main()
