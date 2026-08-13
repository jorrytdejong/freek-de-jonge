import unittest

from app.prolific import (
    PROLIFIC_PROFILE_KEY,
    ProlificContext,
    ProlificContextError,
    attach_prolific_metadata,
    parse_prolific_context,
    read_profile_metadata,
    replaced_submission_ids,
)


class ProlificContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.params = {
            "PROLIFIC_PID": "participant_12345678",
            "STUDY_ID": "study_1234567890",
            "SESSION_ID": "submission_12345678",
        }

    def test_complete_context_is_parsed(self) -> None:
        context = parse_prolific_context(self.params, required=True)

        self.assertEqual(
            context,
            ProlificContext(
                participant_id="participant_12345678",
                study_id="study_1234567890",
                submission_id="submission_12345678",
            ),
        )

    def test_missing_optional_context_is_allowed(self) -> None:
        self.assertIsNone(parse_prolific_context({}, required=False))

    def test_missing_required_or_partial_context_is_rejected(self) -> None:
        with self.assertRaises(ProlificContextError):
            parse_prolific_context({}, required=True)
        with self.assertRaises(ProlificContextError):
            parse_prolific_context(
                {"PROLIFIC_PID": self.params["PROLIFIC_PID"]}, required=False
            )

    def test_metadata_tracks_replaced_submissions_without_mutating_profile(
        self,
    ) -> None:
        profile = {"age": 37, "freek_familiarity": 4, "consent": True}
        context = parse_prolific_context(self.params, required=True)
        assert context is not None

        enriched = attach_prolific_metadata(
            profile,
            context,
            replaced=("old_submission_123", "old_submission_123"),
        )

        self.assertNotIn(PROLIFIC_PROFILE_KEY, profile)
        metadata = read_profile_metadata(enriched)
        self.assertEqual(metadata["submission_id"], "submission_12345678")
        self.assertEqual(replaced_submission_ids(metadata), ("old_submission_123",))


if __name__ == "__main__":
    unittest.main()
