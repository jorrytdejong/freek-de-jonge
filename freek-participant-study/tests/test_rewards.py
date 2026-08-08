import unittest
from decimal import Decimal

from app.rewards import FakeRewardProvider, RewardConfigurationError, RewardSettings
from app.rewards.config import REAL_REWARD_ACKNOWLEDGEMENT


class RewardSettingsTest(unittest.TestCase):
    def test_rewards_are_disabled_by_default(self) -> None:
        settings = RewardSettings.from_sources(environ={}, secrets={})

        self.assertFalse(settings.enabled)
        self.assertEqual(settings.mode, "fake")
        self.assertEqual(settings.amount_eur, Decimal("3.40"))
        self.assertEqual(settings.max_issued_count, 25)
        self.assertEqual(settings.budget_eur, Decimal("85.00"))

    def test_environment_overrides_secrets(self) -> None:
        settings = RewardSettings.from_sources(
            environ={
                "FREEK_STUDY_REWARDS_ENABLED": "true",
                "FREEK_STUDY_REWARD_AMOUNT_EUR": "4.50",
                "FREEK_STUDY_REWARD_MAX_ISSUED": "10",
                "FREEK_STUDY_REWARD_BUDGET_EUR": "45.00",
            },
            secrets={"rewards_enabled": False, "reward_amount_eur": "8.00"},
        )

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.amount_eur, Decimal("4.50"))
        self.assertEqual(settings.max_issued_count, 10)
        self.assertEqual(settings.budget_eur, Decimal("45.00"))

    def test_production_mode_requires_prod_key_and_all_explicit_gates(self) -> None:
        with self.assertRaisesRegex(RewardConfigurationError, "PROD_"):
            RewardSettings.from_sources(
                environ={"FREEK_STUDY_REWARD_MODE": "tremendous_production"},
                secrets={},
            )

        base = {
            "FREEK_STUDY_REWARD_MODE": "tremendous_production",
            "TREMENDOUS_API_KEY": "PROD_safe-placeholder",
            "TREMENDOUS_CAMPAIGN_ID": "CAMPAIGN-1",
            "TREMENDOUS_FUNDING_SOURCE_ID": "BALANCE",
            "FREEK_STUDY_REWARD_LEDGER_PATH": "data/runtime/rewards.production.csv",
            "FREEK_STUDY_REWARD_MAX_ISSUED": "1",
            "FREEK_STUDY_REWARD_BUDGET_EUR": "3.40",
            "FREEK_STUDY_PRODUCTION_CANARY_ENABLED": "true",
            "FREEK_STUDY_PRODUCTION_CANARY_REWARD_REFERENCE": (
                "reward-0123456789abcdef01234567"
            ),
        }
        with self.assertRaisesRegex(RewardConfigurationError, "ENVIRONMENT"):
            RewardSettings.from_sources(environ=base, secrets={})
        with self.assertRaisesRegex(RewardConfigurationError, "real-money"):
            RewardSettings.from_sources(
                environ={**base, "FREEK_STUDY_DEPLOYMENT_ENVIRONMENT": "production"},
                secrets={},
            )

        settings = RewardSettings.from_sources(
            environ={
                **base,
                "FREEK_STUDY_DEPLOYMENT_ENVIRONMENT": "production",
                "FREEK_STUDY_REAL_REWARDS_ACK": REAL_REWARD_ACKNOWLEDGEMENT,
            },
            secrets={},
        )
        self.assertEqual(settings.mode, "tremendous_production")
        self.assertTrue(settings.real_rewards_acknowledged)
        self.assertNotIn("PROD_safe-placeholder", repr(settings))

    def test_production_mode_rejects_sandbox_ledger(self) -> None:
        with self.assertRaisesRegex(RewardConfigurationError, "productielogboek"):
            RewardSettings.from_sources(
                environ={
                    "FREEK_STUDY_REWARD_MODE": "tremendous_production",
                    "FREEK_STUDY_DEPLOYMENT_ENVIRONMENT": "production",
                    "FREEK_STUDY_REAL_REWARDS_ACK": REAL_REWARD_ACKNOWLEDGEMENT,
                    "FREEK_STUDY_REWARD_LEDGER_PATH": "rewards-sandbox.csv",
                    "FREEK_STUDY_REWARD_MAX_ISSUED": "1",
                    "FREEK_STUDY_REWARD_BUDGET_EUR": "3.40",
                    "FREEK_STUDY_PRODUCTION_CANARY_ENABLED": "true",
                    "FREEK_STUDY_PRODUCTION_CANARY_REWARD_REFERENCE": (
                        "reward-0123456789abcdef01234567"
                    ),
                    "TREMENDOUS_API_KEY": "PROD_safe-placeholder",
                    "TREMENDOUS_CAMPAIGN_ID": "CAMPAIGN-1",
                    "TREMENDOUS_FUNDING_SOURCE_ID": "BALANCE",
                },
                secrets={},
            )

    def test_production_canary_rejects_broad_limits(self) -> None:
        with self.assertRaisesRegex(RewardConfigurationError, "max_issued=1"):
            RewardSettings.from_sources(
                environ={
                    "FREEK_STUDY_REWARD_MODE": "tremendous_production",
                    "FREEK_STUDY_DEPLOYMENT_ENVIRONMENT": "production",
                    "FREEK_STUDY_REAL_REWARDS_ACK": REAL_REWARD_ACKNOWLEDGEMENT,
                    "FREEK_STUDY_REWARD_LEDGER_PATH": "rewards.production.csv",
                    "FREEK_STUDY_PRODUCTION_CANARY_ENABLED": "true",
                    "FREEK_STUDY_PRODUCTION_CANARY_REWARD_REFERENCE": (
                        "reward-0123456789abcdef01234567"
                    ),
                    "TREMENDOUS_API_KEY": "PROD_safe-placeholder",
                    "TREMENDOUS_CAMPAIGN_ID": "CAMPAIGN-1",
                    "TREMENDOUS_FUNDING_SOURCE_ID": "BALANCE",
                },
                secrets={},
            )

    def test_sandbox_mode_requires_complete_test_credentials(self) -> None:
        with self.assertRaisesRegex(RewardConfigurationError, "TEST_"):
            RewardSettings.from_sources(
                environ={"FREEK_STUDY_REWARD_MODE": "tremendous_sandbox"},
                secrets={},
            )
        with self.assertRaisesRegex(RewardConfigurationError, "campaign_id"):
            RewardSettings.from_sources(
                environ={
                    "FREEK_STUDY_REWARD_MODE": "tremendous_sandbox",
                    "TREMENDOUS_API_KEY": "TEST_safe",
                },
                secrets={},
            )

    def test_sandbox_credentials_can_come_from_nested_secrets(self) -> None:
        settings = RewardSettings.from_sources(
            environ={"FREEK_STUDY_REWARD_MODE": "tremendous_sandbox"},
            secrets={
                "tremendous": {
                    "api_key": "TEST_safe",
                    "campaign_id": "CAMPAIGN-1",
                    "funding_source_id": "BALANCE",
                }
            },
        )

        self.assertEqual(settings.mode, "tremendous_sandbox")
        self.assertEqual(settings.tremendous_campaign_id, "CAMPAIGN-1")
        self.assertEqual(settings.tremendous_funding_source_id, "BALANCE")
        self.assertNotIn("TEST_safe", repr(settings))

    def test_invalid_amount_is_rejected(self) -> None:
        for amount in ("0", "-1", "five", "5.001"):
            with self.subTest(amount=amount):
                with self.assertRaises(RewardConfigurationError):
                    RewardSettings.from_sources(
                        environ={"FREEK_STUDY_REWARD_AMOUNT_EUR": amount},
                        secrets={},
                    )

    def test_invalid_reward_limits_are_rejected(self) -> None:
        for value in ("0", "-1", "2.5", "many"):
            with self.subTest(value=value):
                with self.assertRaises(RewardConfigurationError):
                    RewardSettings.from_sources(
                        environ={"FREEK_STUDY_REWARD_MAX_ISSUED": value},
                        secrets={},
                    )
        with self.assertRaisesRegex(RewardConfigurationError, "minstens één"):
            RewardSettings.from_sources(
                environ={
                    "FREEK_STUDY_REWARDS_ENABLED": "true",
                    "FREEK_STUDY_REWARD_AMOUNT_EUR": "3.40",
                    "FREEK_STUDY_REWARD_BUDGET_EUR": "3.39",
                },
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
