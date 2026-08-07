import unittest
from decimal import Decimal

from app.rewards import TremendousAPIError, TremendousSandboxRewardProvider
from app.rewards.tremendous import TREMENDOUS_SANDBOX_ORDERS_URL


class RecordingTransport:
    def __init__(self, status: int = 200, response: dict | None = None) -> None:
        self.status = status
        self.response = response or {
            "order": {
                "rewards": [
                    {
                        "id": "REWARD-123",
                        "delivery": {
                            "link": "https://testflight.tremendous.com/rewards/test-123"
                        },
                    }
                ]
            }
        }
        self.calls: list[dict] = []

    def post_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.status, self.response


class TremendousSandboxRewardProviderTest(unittest.TestCase):
    def provider(self, transport: RecordingTransport):
        return TremendousSandboxRewardProvider(
            api_key="TEST_secret-value",
            campaign_id="CAMPAIGN-1",
            funding_source_id="BALANCE",
            transport=transport,
        )

    def test_creates_dutch_eur_link_reward_with_idempotent_external_id(self) -> None:
        transport = RecordingTransport()

        claim = self.provider(transport).create_claim(
            participant_reference="reward-pseudonym-123",
            amount=Decimal("3.40"),
            currency="eur",
        )

        self.assertEqual(claim.reference, "REWARD-123")
        self.assertEqual(claim.provider, "tremendous_sandbox")
        self.assertTrue(claim.is_test)
        self.assertEqual(
            claim.redemption_url,
            "https://testflight.tremendous.com/rewards/test-123",
        )
        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertEqual(call["url"], TREMENDOUS_SANDBOX_ORDERS_URL)
        self.assertEqual(call["headers"]["Authorization"], "Bearer TEST_secret-value")
        self.assertEqual(call["payload"]["external_id"], "reward-pseudonym-123")
        self.assertEqual(call["payload"]["payment"], {"funding_source_id": "BALANCE"})
        reward = call["payload"]["reward"]
        self.assertEqual(reward["campaign_id"], "CAMPAIGN-1")
        self.assertEqual(reward["value"], {"denomination": 3.4, "currency_code": "EUR"})
        self.assertEqual(reward["delivery"], {"method": "LINK"})
        self.assertEqual(reward["language"], "nl")
        self.assertNotIn("recipient", reward)

    def test_duplicate_201_response_is_treated_as_same_success(self) -> None:
        claim = self.provider(RecordingTransport(status=201)).create_claim(
            participant_reference="same-external-id",
            amount=Decimal("3.40"),
            currency="EUR",
        )

        self.assertEqual(claim.reference, "REWARD-123")

    def test_production_key_is_rejected_before_any_request(self) -> None:
        with self.assertRaisesRegex(ValueError, "TEST_"):
            TremendousSandboxRewardProvider(
                api_key="PROD_forbidden",
                campaign_id="CAMPAIGN-1",
                funding_source_id="BALANCE",
            )

    def test_api_error_status_is_safe_and_preserves_status_code(self) -> None:
        with self.assertRaises(TremendousAPIError) as caught:
            self.provider(RecordingTransport(status=402)).create_claim(
                participant_reference="reward-reference",
                amount=Decimal("3.40"),
                currency="EUR",
            )

        self.assertEqual(caught.exception.status_code, 402)
        self.assertNotIn("TEST_secret-value", str(caught.exception))

    def test_non_sandbox_redemption_url_is_rejected(self) -> None:
        transport = RecordingTransport(
            response={
                "order": {
                    "rewards": [
                        {
                            "id": "REWARD-123",
                            "delivery": {"link": "https://example.com/stolen"},
                        }
                    ]
                }
            }
        )

        with self.assertRaisesRegex(TremendousAPIError, "non-sandbox"):
            self.provider(transport).create_claim(
                participant_reference="reward-reference",
                amount=Decimal("3.40"),
                currency="EUR",
            )


if __name__ == "__main__":
    unittest.main()
