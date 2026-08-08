import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.storage import CSVProgressStorage


class ResumeFlowTest(unittest.TestCase):
    def test_partial_item_is_restored_from_anonymous_link(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        session_id = "acl-test-10-70b41995"
        with tempfile.TemporaryDirectory() as temporary_directory:
            progress_path = Path(temporary_directory) / "progress.csv"
            storage = CSVProgressStorage(progress_path)
            storage.save_progress(
                session_id=session_id,
                study_version="acl-1",
                is_test=True,
                current_page="item-1",
                profile={"age": 37, "freek_familiarity": 4, "consent": True},
                responses={},
                drafts={},
            )
            environment = {
                "FREEK_STUDY_PROGRESS_PATH": str(progress_path),
                "FREEK_STUDY_IN_PROCESS_NAVIGATION": "true",
            }
            with patch.dict(os.environ, environment):
                app = AppTest.from_file(app_path)
                app.query_params["session"] = session_id
                app.query_params["page"] = "item-1"
                app.run(timeout=20)
                self.assertFalse(app.exception)
                self.assertEqual(len(app.select_slider), 4)

                app.select_slider[0].set_value(2).run(timeout=20)
                app.select_slider[1].set_value(4).run(timeout=20)
                saved = storage.load_progress(session_id)
                assert saved is not None
                self.assertEqual(saved.current_page, "item-1")
                self.assertEqual(saved.profile["age"], 37)
                self.assertEqual(len(saved.drafts), 1)

                resumed = AppTest.from_file(app_path)
                resumed.query_params["session"] = session_id
                resumed.run(timeout=20)
                self.assertFalse(resumed.exception)
                self.assertEqual(resumed.query_params["page"][0], "item-1")
                self.assertEqual(resumed.select_slider[0].value, 2)
                self.assertEqual(resumed.select_slider[1].value, 4)
                for slider in resumed.select_slider:
                    if slider.value == 0:
                        slider.set_value(3)
                resumed.run(timeout=20)
                next(
                    button
                    for button in resumed.button
                    if button.label == "Volgende grap"
                ).click().run(timeout=20)
                self.assertEqual(resumed.query_params["page"][0], "item-2")
                completed = storage.load_progress(session_id)
                assert completed is not None
                self.assertEqual(len(completed.responses), 1)
                self.assertFalse(completed.drafts)


if __name__ == "__main__":
    unittest.main()
