import unittest
from decimal import Decimal

from app.rewards import FakeRewardProvider, RewardConfigurationError, RewardSettings


class RewardSettingsTest(unittest.TestCase):
    def test_rewards_are_disabled_by_default(self) -> None:
        settings = RewardSettings.from_sources(environ={}, secrets={})

        self.assertFalse(settings.enabled)
        self.assertEqual(settings.mode, "fake")
        self.assertEqual(settings.amount_eur, Decimal("3.40"))

    def test_environment_overrides_secrets(self) -> None:
        settings = RewardSettings.from_sources(
            environ={
                "FREEK_STUDY_REWARDS_ENABLED": "true",
                "FREEK_STUDY_REWARD_AMOUNT_EUR": "4.50",
            },
            secrets={"rewards_enabled": False, "reward_amount_eur": "8.00"},
        )

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.amount_eur, Decimal("4.50"))

    def test_non_fake_mode_is_rejected_at_checkpoint_one(self) -> None:
        with self.assertRaisesRegex(RewardConfigurationError, "uitsluitend"):
            RewardSettings.from_sources(
                environ={"FREEK_STUDY_REWARD_MODE": "production"}, secrets={}
            )

    def test_invalid_amount_is_rejected(self) -> None:
        for amount in ("0", "-1", "five", "5.001"):
            with self.subTest(amount=amount):
                with self.assertRaises(RewardConfigurationError):
                    RewardSettings.from_sources(
                        environ={"FREEK_STUDY_REWARD_AMOUNT_EUR": amount},
                        secrets={},
                    )


class FakeRewardProviderTest(unittest.TestCase):
    def test_claim_is_deterministic_and_explicitly_fake(self) -> None:
        provider = FakeRewardProvider()

        first = provider.create_claim(
            participant_reference="acl-test-01",
            amount=Decimal("5.00"),
            currency="eur",
        )
        second = provider.create_claim(
            participant_reference="acl-test-01",
            amount=Decimal("5.00"),
            currency="EUR",
        )

        self.assertEqual(first, second)
        self.assertTrue(first.reference.startswith("fake-"))
        self.assertEqual(first.provider, "fake")
        self.assertTrue(first.is_test)

    def test_different_participants_receive_different_references(self) -> None:
        provider = FakeRewardProvider()

        first = provider.create_claim(
            participant_reference="participant-a",
            amount=Decimal("5.00"),
            currency="EUR",
        )
        second = provider.create_claim(
            participant_reference="participant-b",
            amount=Decimal("5.00"),
            currency="EUR",
        )

        self.assertNotEqual(first.reference, second.reference)


if __name__ == "__main__":
    unittest.main()
