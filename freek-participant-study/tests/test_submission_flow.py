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
    def test_reward_is_not_visible_before_submission(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with tempfile.TemporaryDirectory() as temporary_directory:
            progress_path = Path(temporary_directory) / "progress.csv"
            reward_path = Path(temporary_directory) / "rewards.csv"
            with patch.dict(
                os.environ,
                {
                    "FREEK_STUDY_PROGRESS_PATH": str(progress_path),
                    "FREEK_STUDY_REWARDS_ENABLED": "true",
                    "FREEK_STUDY_REWARD_MODE": "fake",
                    "FREEK_STUDY_REWARD_LEDGER_PATH": str(reward_path),
                },
            ):
                app = AppTest.from_file(app_path)
                app.query_params["session"] = "acl-test-01-d4df9936"
                app.query_params["page"] = "debrief"
                app.run(timeout=20)

                self.assertFalse(app.exception)
                self.assertFalse(
                    any(
                        "coffee-watercolor-background" in markdown.value
                        for markdown in app.markdown
                    )
                )
                self.assertNotIn(
                    "Ontvang mijn testbeloning", [button.label for button in app.button]
                )
                self.assertFalse(app.warning)

    def test_submitted_test_link_can_exercise_fake_reward_flow(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        app_path = project_root / "streamlit_app.py"
        stimuli = load_stimuli()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            sessions_path = temporary / "sessions.csv"
            progress_path = temporary / "progress.csv"
            reward_path = temporary / "rewards.csv"
            with (project_root / "data" / "acl_sessions.csv").open(
                encoding="utf-8", newline=""
            ) as source:
                rows = list(csv.DictReader(source))
            test_row = {
                **rows[0],
                "session_id": "test-acl-reward-A1B2",
                "is_test": "true",
                "notes": "Automated test reward simulation",
            }
            rows.append(test_row)
            with sessions_path.open("w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            session = load_sessions(stimuli, sessions_path)[test_row["session_id"]]
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
                is_test=True,
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
                    "FREEK_STUDY_REWARDS_ENABLED": "true",
                    "FREEK_STUDY_REWARD_MODE": "fake",
                    "FREEK_STUDY_REWARD_AMOUNT_EUR": "3.40",
                    "FREEK_STUDY_REWARD_LEDGER_PATH": str(reward_path),
                },
            ):
                app = AppTest.from_file(app_path)
                app.query_params["session"] = session.session_id
                app.query_params["page"] = "debrief"
                app.run(timeout=20)
                self.assertFalse(app.exception)
                self.assertEqual(app.query_params["page"][0], "debrief")
                self.assertTrue(
                    any(
                        "coffee-watercolor-background" in markdown.value
                        for markdown in app.markdown
                    )
                )
                self.assertEqual(len(app.expander), 20)
                self.assertIn("Nieuwe testinzending", [b.label for b in app.button])
                self.assertFalse(
                    any(b.label.startswith("Bewerk grap") for b in app.button)
                )
                self.assertIn(
                    "Ontvang mijn testvergoeding",
                    [button.label for button in app.button],
                )
                decline_button = next(
                    button
                    for button in app.button
                    if button.label == "Geen testvergoeding, bedankt"
                )
                decline_button.click().run(timeout=20)
                self.assertFalse(app.exception)
                self.assertTrue(
                    any("geen testvergoeding" in info.value for info in app.info)
                )
                reconsider_button = next(
                    button
                    for button in app.button
                    if button.label == "Toch een testvergoeding ontvangen"
                )
                reconsider_button.click().run(timeout=20)
                self.assertFalse(app.exception)
                self.assertTrue(
                    any("TESTBELONING" in warning.value for warning in app.warning)
                )
                self.assertTrue(
                    any("€3,40" in success.value for success in app.success)
                )
                reopened = AppTest.from_file(app_path)
                reopened.query_params["session"] = session.session_id
                reopened.query_params["page"] = "debrief"
                reopened.run(timeout=20)
                self.assertFalse(reopened.exception)
                self.assertNotIn(
                    "Ontvang mijn testvergoeding",
                    [button.label for button in reopened.button],
                )
                self.assertTrue(
                    any("€3,40" in success.value for success in reopened.success)
                )
                with reward_path.open(encoding="utf-8", newline="") as handle:
                    reward_rows = list(csv.DictReader(handle))
                self.assertEqual(len(reward_rows), 1)
                self.assertNotIn(session.session_id, reward_path.read_text())

    def test_real_link_gets_plain_debrief_without_coffee_controls(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        app_path = project_root / "streamlit_app.py"
        stimuli = load_stimuli()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            sessions_path = temporary / "sessions.csv"
            progress_path = temporary / "progress.csv"
            reward_path = temporary / "rewards.csv"
            with (project_root / "data" / "acl_sessions.csv").open(
                encoding="utf-8", newline=""
            ) as source:
                rows = list(csv.DictReader(source))
            reward_free_row = {
                **rows[0],
                "session_id": "real-no-coffee-A1B2",
                "is_test": "false",
                # Production links remain coffee-free even when an older
                # deployed registry still marks them as reward eligible.
                "reward_eligible": "true",
                "notes": "Automated production session simulation",
            }
            rows.append(reward_free_row)
            with sessions_path.open("w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            session = load_sessions(stimuli, sessions_path)[
                reward_free_row["session_id"]
            ]
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
            CSVProgressStorage(progress_path).submit_response(
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
                    "FREEK_STUDY_REWARDS_ENABLED": "true",
                    "FREEK_STUDY_REWARD_MODE": "fake",
                    "FREEK_STUDY_REWARD_AMOUNT_EUR": "3.40",
                    "FREEK_STUDY_REWARD_LEDGER_PATH": str(reward_path),
                },
            ):
                app = AppTest.from_file(app_path)
                app.query_params["session"] = session.session_id
                app.query_params["page"] = "debrief"
                app.run(timeout=20)

                self.assertFalse(app.exception)
                self.assertIn(
                    "Bedankt voor je deelname",
                    [title.value for title in app.title],
                )
                self.assertFalse(
                    any(
                        "coffee-watercolor-background" in markdown.value
                        for markdown in app.markdown
                    )
                )
                button_labels = [button.label for button in app.button]
                self.assertNotIn("Ontvang mijn testvergoeding", button_labels)
                self.assertNotIn("Geen testvergoeding, bedankt", button_labels)
                self.assertFalse(reward_path.exists())


if __name__ == "__main__":
    unittest.main()
