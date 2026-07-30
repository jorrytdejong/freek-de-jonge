import unittest

from app.assignment import build_assignment
from app.ratings import (
    DISPLAY_LABELS,
    GroupRatingResponse,
    GroupRatingValidationError,
    build_displayed_variants,
    validate_group_response,
)
from app.sessions import load_sessions
from app.stimuli import load_stimuli


class GroupRatingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.groups = load_stimuli()
        sessions = load_sessions({group.group_id for group in cls.groups})
        cls.session = next(iter(sessions.values()))
        cls.assignment = build_assignment(cls.session, cls.groups)
        cls.assigned_group = cls.assignment.groups[0]
        cls.joke_group = next(
            group
            for group in cls.groups
            if group.group_id == cls.assigned_group.group_id
        )
        cls.displayed = build_displayed_variants(
            cls.assigned_group,
            cls.joke_group,
        )

    def test_assignment_order_maps_to_neutral_labels(self) -> None:
        self.assertEqual(
            tuple(variant.display_label for variant in self.displayed),
            DISPLAY_LABELS,
        )
        self.assertEqual(
            tuple(variant.variant_id for variant in self.displayed),
            self.assigned_group.variant_ids,
        )
        self.assertEqual(
            tuple(variant.display_position for variant in self.displayed),
            tuple(range(1, 9)),
        )

    def test_all_unanswered_scores_are_reported(self) -> None:
        raw_ratings = {
            variant.variant_id: {
                "funniness": None,
                "freek_similarity": None,
            }
            for variant in self.displayed
        }

        with self.assertRaises(GroupRatingValidationError) as context:
            validate_group_response(
                group_id=self.joke_group.group_id,
                displayed_variants=self.displayed,
                raw_ratings=raw_ratings,
                comment="",
            )

        self.assertEqual(len(context.exception.messages), 16)
        self.assertIn(
            "Versie A: kies een score voor Grappigheid.",
            context.exception.messages,
        )
        self.assertIn(
            "Versie H: kies een score voor Lijkt op Freek de Jonge.",
            context.exception.messages,
        )

    def test_complete_neutral_scores_are_valid(self) -> None:
        raw_ratings = {
            variant.variant_id: {
                "funniness": 3,
                "freek_similarity": 3,
            }
            for variant in self.displayed
        }

        response = validate_group_response(
            group_id=self.joke_group.group_id,
            displayed_variants=self.displayed,
            raw_ratings=raw_ratings,
            comment="  Algemene opmerking.  ",
        )

        self.assertIsInstance(response, GroupRatingResponse)
        self.assertEqual(len(response.ratings), 8)
        self.assertEqual(response.comment, "Algemene opmerking.")
        self.assertTrue(
            all(rating.funniness == 3 for rating in response.ratings)
        )

    def test_out_of_range_score_is_rejected(self) -> None:
        raw_ratings = {
            variant.variant_id: {
                "funniness": 3,
                "freek_similarity": 3,
            }
            for variant in self.displayed
        }
        raw_ratings[self.displayed[0].variant_id]["funniness"] = 0

        with self.assertRaisesRegex(
            GroupRatingValidationError,
            "Grappigheid moet tussen 1 en 5 liggen",
        ):
            validate_group_response(
                group_id=self.joke_group.group_id,
                displayed_variants=self.displayed,
                raw_ratings=raw_ratings,
                comment="",
            )


if __name__ == "__main__":
    unittest.main()

