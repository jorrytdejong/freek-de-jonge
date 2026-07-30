import unittest

from app.participant import (
    ParticipantProfile,
    ProfileValidationError,
    validate_profile,
)


class ParticipantProfileTest(unittest.TestCase):
    def test_valid_profile_is_normalized(self) -> None:
        profile = validate_profile(
            age=37,
            freek_familiarity=4,
            consent=True,
        )

        self.assertEqual(
            profile,
            ParticipantProfile(age=37, freek_familiarity=4, consent=True),
        )

    def test_all_missing_fields_are_reported_together(self) -> None:
        with self.assertRaises(ProfileValidationError) as context:
            validate_profile(
                age=None,
                freek_familiarity=None,
                consent=False,
            )

        self.assertEqual(len(context.exception.messages), 3)
        self.assertIn("Vul je leeftijd in.", context.exception.messages)
        self.assertIn(
            "Geef aan hoe goed je het werk van Freek de Jonge kent.",
            context.exception.messages,
        )
        self.assertIn(
            "Geef toestemming om vrijwillig deel te nemen.",
            context.exception.messages,
        )

    def test_age_must_be_a_whole_year_in_range(self) -> None:
        for invalid_age in (0, 121, 24.5, True):
            with self.subTest(age=invalid_age):
                with self.assertRaises(ProfileValidationError):
                    validate_profile(
                        age=invalid_age,
                        freek_familiarity=3,
                        consent=True,
                    )

    def test_familiarity_must_be_between_one_and_five(self) -> None:
        for invalid_familiarity in (0, 6, 2.5, False):
            with self.subTest(familiarity=invalid_familiarity):
                with self.assertRaises(ProfileValidationError):
                    validate_profile(
                        age=37,
                        freek_familiarity=invalid_familiarity,
                        consent=True,
                    )


if __name__ == "__main__":
    unittest.main()

