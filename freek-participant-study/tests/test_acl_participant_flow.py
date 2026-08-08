import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.storage import CSVProgressStorage


class ACLParticipantFlowTest(unittest.TestCase):
    def test_twenty_four_items_can_be_rated_reviewed_and_submitted(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        session_id = "acl-test-01-062f6e4e"
        with tempfile.TemporaryDirectory() as temporary_directory:
            progress_path = Path(temporary_directory) / "progress.csv"
            storage = CSVProgressStorage(progress_path)
            storage.save_progress(
                session_id=session_id,
                study_version="acl-1",
                is_test=True,
                current_page="item-1",
                profile={"age": 35, "freek_familiarity": 3, "consent": True},
                responses={},
                drafts={},
            )
            with patch.dict(
                os.environ,
                {
                    "FREEK_STUDY_PROGRESS_PATH": str(progress_path),
                    "FREEK_STUDY_IN_PROCESS_NAVIGATION": "true",
                },
            ):
                app = AppTest.from_file(app_path)
                app.query_params["session"] = session_id
                app.query_params["page"] = "item-1"
                app.run(timeout=20)
                for position in range(1, 25):
                    self.assertEqual(len(app.select_slider), 4)
                    for slider in app.select_slider:
                        slider.set_value(3)
                    app.run(timeout=20)
                    label = "Naar controle" if position == 24 else "Volgende grap"
                    next(
                        button for button in app.button if button.label == label
                    ).click().run(timeout=20)
                self.assertEqual(app.query_params["page"][0], "review")
                self.assertEqual(len(app.expander), 24)
                app.text_area[0].set_value("Algemene testopmerking.").run(timeout=20)
                next(
                    button
                    for button in app.button
                    if button.label == "Definitief indienen"
                ).click().run(timeout=20)
                self.assertEqual(app.query_params["page"][0], "debrief")
            saved = storage.load_progress(session_id)
            assert saved is not None
            self.assertEqual(saved.status, "submitted")
            self.assertEqual(len(saved.responses), 24)
            self.assertEqual(saved.final_comment, "Algemene testopmerking.")
            self.assertEqual(len(saved.submissions), 1)


if __name__ == "__main__":
    unittest.main()
