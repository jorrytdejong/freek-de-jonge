import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class AdminFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"

    def run_admin(self, progress_path: Path) -> AppTest:
        app = AppTest.from_file(self.app_path)
        app.query_params["admin"] = "1"
        app.run(timeout=15)
        return app

    def test_wrong_password_is_rejected_and_correct_password_opens_dashboard(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "FREEK_STUDY_ADMIN_PASSWORD": "correct-password",
                    "FREEK_STUDY_PROGRESS_PATH": str(Path(directory) / "progress.csv"),
                    "FREEK_STUDY_REWARDS_ENABLED": "true",
                    "FREEK_STUDY_REWARD_MODE": "tremendous_sandbox",
                    "FREEK_STUDY_REWARD_LEDGER_PATH": str(
                        Path(directory) / "rewards.csv"
                    ),
                    "TREMENDOUS_API_KEY": "TEST_safe",
                    "TREMENDOUS_CAMPAIGN_ID": "CAMPAIGN-1",
                    "TREMENDOUS_FUNDING_SOURCE_ID": "BALANCE",
                },
            ),
        ):
            app = self.run_admin(Path(directory) / "progress.csv")
            self.assertFalse(app.exception)
            self.assertEqual(app.text_input[0].label, "Wachtwoord")

            app.text_input[0].set_value("wrong-password")
            app.button[0].click().run(timeout=15)
            self.assertTrue(any("niet correct" in error.value for error in app.error))
            self.assertEqual(app.text_input[0].label, "Wachtwoord")

            app.text_input[0].set_value("correct-password")
            app.button[0].click().run(timeout=15)
            self.assertFalse(app.exception)
            self.assertTrue(app.session_state["admin_authenticated"])
            self.assertTrue(
                any("Onderzoeksdashboard" in title.value for title in app.title)
            )
            self.assertEqual(len(app.metric), 16)
            self.assertTrue(any(metric.label == "Aangemaakt" for metric in app.metric))
            self.assertTrue(
                any("Beloningsoperaties" in markdown.value for markdown in app.markdown)
            )
            self.assertTrue(
                any(
                    control.label == "Beloningsselectie" and control.value == "Alles"
                    for control in app.segmented_control
                )
            )
            self.assertTrue(
                any(
                    metric.label == "Resterende beloningen" and metric.value == "25"
                    for metric in app.metric
                )
            )
            self.assertTrue(
                any(
                    success.value == "Nieuwe uitgifte is actief."
                    for success in app.success
                )
            )
            self.assertTrue(
                any(
                    checkbox.label.startswith("Ik bevestig")
                    for checkbox in app.checkbox
                )
            )
            self.assertTrue(
                any(
                    button.label == "Tremendous-bezorgstatussen vernieuwen"
                    for button in app.button
                )
            )
            self.assertTrue(
                any(
                    "productie-preflight" in markdown.value for markdown in app.markdown
                )
            )
            self.assertEqual(len(app.get("download_button")), 3)

    def test_participant_route_does_not_expose_admin_controls(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "FREEK_STUDY_ADMIN_PASSWORD": "correct-password",
                    "FREEK_STUDY_PROGRESS_PATH": str(Path(directory) / "progress.csv"),
                    "FREEK_STUDY_REWARDS_ENABLED": "false",
                },
            ),
        ):
            app = AppTest.from_file(self.app_path)
            app.query_params["session"] = "acl-test-02-979d4f77"
            app.run(timeout=15)

            self.assertFalse(app.exception)
            self.assertFalse(app.text_input)
            self.assertFalse(app.get("download_button"))
            self.assertFalse(
                any("Beheeromgeving" in markdown.value for markdown in app.markdown)
            )


if __name__ == "__main__":
    unittest.main()
