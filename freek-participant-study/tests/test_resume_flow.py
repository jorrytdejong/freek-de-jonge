import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.storage import CSVProgressStorage


class ResumeFlowTest(unittest.TestCase):
    def test_partial_group_is_restored_from_anonymous_link(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with tempfile.TemporaryDirectory() as temporary_directory:
            progress_path = Path(temporary_directory) / "progress.csv"
            environment = {
                "FREEK_STUDY_PROGRESS_PATH": str(progress_path),
                "FREEK_STUDY_IN_PROCESS_NAVIGATION": "true",
            }
            with patch.dict(os.environ, environment):
                app = AppTest.from_file(app_path)
                app.query_params["session"] = "test-10-KvPvblxx"
                app.query_params["page"] = "intro"
                app.run(timeout=15)
                self.assertFalse(app.exception)

                app.number_input[0].set_value(37)
                app.radio[0].set_value(4)
                app.checkbox[0].check()
                app.button[0].click().run(timeout=15)
                self.assertEqual(
                    app.query_params["page"][0],
                    "profile-complete",
                )

                app.button[0].click().run(timeout=15)
                self.assertEqual(app.query_params["page"][0], "group-1")
                self.assertEqual(len(app.select_slider), 16)

                app.select_slider[0].set_value(2).run(timeout=15)
                app.select_slider[1].set_value(4).run(timeout=15)
                app.text_area[0].set_value("Halverwege opgeslagen.").run(timeout=15)

                storage = CSVProgressStorage(progress_path)
                saved = storage.load_progress("test-10-KvPvblxx")
                assert saved is not None
                self.assertEqual(saved.current_page, "group-1")
                self.assertEqual(saved.profile["age"], 37)
                self.assertEqual(len(saved.drafts), 1)

                resumed = AppTest.from_file(app_path)
                resumed.query_params["session"] = "test-10-KvPvblxx"
                resumed.run(timeout=15)
                self.assertFalse(resumed.exception)
                self.assertEqual(
                    resumed.query_params["page"][0],
                    "group-1",
                )
                self.assertEqual(resumed.select_slider[0].value, 2)
                self.assertEqual(resumed.select_slider[1].value, 4)
                self.assertEqual(
                    resumed.text_area[0].value,
                    "Halverwege opgeslagen.",
                )

                for slider in resumed.select_slider:
                    if slider.value == 0:
                        slider.set_value(3)
                resumed.run(timeout=15)
                resumed.button[-1].click().run(timeout=15)
                self.assertEqual(
                    resumed.query_params["page"][0],
                    "group-2",
                )

                reopened = AppTest.from_file(app_path)
                reopened.query_params["session"] = "test-10-KvPvblxx"
                reopened.run(timeout=15)
                self.assertFalse(reopened.exception)
                self.assertEqual(
                    reopened.query_params["page"][0],
                    "group-2",
                )
                completed = storage.load_progress("test-10-KvPvblxx")
                assert completed is not None
                self.assertEqual(len(completed.responses), 1)
                self.assertFalse(completed.drafts)

                for group_number in range(2, 6):
                    for slider in reopened.select_slider:
                        if slider.value == 0:
                            slider.set_value(3)
                    reopened.run(timeout=15)
                    next_label = (
                        "Groepen afronden" if group_number == 5 else "Volgende groep"
                    )
                    next(
                        button
                        for button in reopened.button
                        if button.label == next_label
                    ).click().run(timeout=15)

                self.assertEqual(
                    reopened.query_params["page"][0],
                    "review",
                )
                self.assertEqual(len(reopened.expander), 5)
                next(
                    button
                    for button in reopened.button
                    if button.label == "Bewerk jokegroep 2"
                ).click().run(timeout=15)
                self.assertEqual(
                    reopened.query_params["page"][0],
                    "group-2",
                )
                reopened.select_slider[0].set_value(5).run(timeout=15)
                next(
                    button
                    for button in reopened.button
                    if button.label == "Terug naar controle"
                ).click().run(timeout=15)
                self.assertEqual(
                    reopened.query_params["page"][0],
                    "review",
                )

                reopened.text_area[0].set_value("Algemene testopmerking.").run(
                    timeout=15
                )
                next(
                    button
                    for button in reopened.button
                    if button.label == "Definitief indienen"
                ).click().run(timeout=15)

                self.assertEqual(
                    reopened.query_params["page"][0],
                    "debrief",
                )
                first_submission = storage.load_progress("test-10-KvPvblxx")
                assert first_submission is not None
                self.assertEqual(first_submission.status, "submitted")
                self.assertEqual(len(first_submission.submissions), 1)
                self.assertEqual(
                    first_submission.final_comment,
                    "Algemene testopmerking.",
                )

                next(
                    button
                    for button in reopened.button
                    if button.label == "Nieuwe testinzending"
                ).click().run(timeout=15)
                next(
                    button
                    for button in reopened.button
                    if button.label == "Definitief indienen"
                ).click().run(timeout=15)

                second_submission = storage.load_progress("test-10-KvPvblxx")
                assert second_submission is not None
                self.assertEqual(len(second_submission.submissions), 2)
                self.assertNotEqual(
                    second_submission.submissions[0]["submission_id"],
                    second_submission.submissions[1]["submission_id"],
                )


if __name__ == "__main__":
    unittest.main()
