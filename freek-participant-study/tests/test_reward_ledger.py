import csv
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.rewards import (
    CSVRewardLedger,
    FakeRewardProvider,
    RewardClaim,
    RewardNotEligibleError,
    RewardService,
    participant_reward_reference,
)
from app.rewards.ledger import REWARD_FIELDNAMES


class CountingFakeRewardProvider(FakeRewardProvider):
    def __init__(self) -> None:
        self.call_count = 0
        self._lock = threading.Lock()

    def create_claim(self, **kwargs):
        with self._lock:
            self.call_count += 1
        return super().create_claim(**kwargs)


class LinkRewardProvider:
    provider_name = "tremendous_sandbox"

    def create_claim(self, *, amount, currency, **kwargs):
        return RewardClaim(
            reference="REWARD-123",
            amount=amount,
            currency=currency,
            provider=self.provider_name,
            is_test=True,
            redemption_url="https://testflight.tremendous.com/rewards/test-123",
        )


class CSVRewardLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "rewards.csv"
        self.ledger = CSVRewardLedger(self.path)
        self.provider = CountingFakeRewardProvider()
        self.service = RewardService(self.ledger, self.provider)

    def claim(self, session_id: str = "real-session-one"):
        return self.service.claim_reward(
            session_id=session_id,
            study_version="acl-1",
            is_test=False,
            eligible=True,
            amount=Decimal("3.40"),
        )

    def test_claim_persists_without_raw_session_or_payment_fields(self) -> None:
        claim = self.claim()

        reopened = RewardService(CSVRewardLedger(self.path), FakeRewardProvider())
        loaded = reopened.load_claim(
            session_id="real-session-one",
            study_version="acl-1",
            is_test=False,
        )
        self.assertEqual(loaded, claim)
        with self.path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        self.assertEqual(tuple(reader.fieldnames or ()), REWARD_FIELDNAMES)
        self.assertEqual(len(rows), 1)
        self.assertNotIn("session_id", rows[0])
        self.assertNotIn("email", rows[0])
        self.assertNotIn("iban", rows[0])
        self.assertNotIn("real-session-one", self.path.read_text(encoding="utf-8"))

    def test_concurrent_claims_issue_exactly_once(self) -> None:
        barrier = threading.Barrier(2)

        def issue():
            barrier.wait()
            return self.claim()

        with ThreadPoolExecutor(max_workers=2) as executor:
            claims = list(executor.map(lambda _: issue(), range(2)))

        self.assertEqual(claims[0], claims[1])
        self.assertEqual(self.provider.call_count, 1)
        self.assertEqual(len(self.ledger.list_records()), 1)

    def test_sandbox_redemption_link_survives_fresh_ledger_instance(self) -> None:
        service = RewardService(self.ledger, LinkRewardProvider())
        issued = service.claim_reward(
            session_id="sandbox-participant",
            study_version="acl-1",
            is_test=True,
            eligible=True,
            amount=Decimal("3.40"),
        )

        reopened = RewardService(CSVRewardLedger(self.path), LinkRewardProvider())
        loaded = reopened.load_claim(
            session_id="sandbox-participant",
            study_version="acl-1",
            is_test=True,
        )
        self.assertEqual(loaded, issued)
        assert loaded is not None
        self.assertEqual(
            loaded.redemption_url,
            "https://testflight.tremendous.com/rewards/test-123",
        )

    def test_ineligible_participant_cannot_create_ledger_record(self) -> None:
        with self.assertRaises(RewardNotEligibleError):
            self.service.claim_reward(
                session_id="not-submitted",
                study_version="acl-1",
                is_test=False,
                eligible=False,
                amount=Decimal("3.40"),
            )

        self.assertFalse(self.path.exists())
        self.assertEqual(self.provider.call_count, 0)

    def test_failed_issue_is_recorded_and_can_retry_deterministically(self) -> None:
        reference = participant_reward_reference("real-session-one", "acl-1")
        now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)

        with self.assertRaisesRegex(RuntimeError, "simulated"):
            self.ledger.issue_once(
                reward_reference=reference,
                study_version="acl-1",
                is_test=False,
                provider="fake",
                amount=Decimal("3.40"),
                currency="EUR",
                issuer=lambda: (_ for _ in ()).throw(RuntimeError("simulated")),
                now=now,
            )

        failed = self.ledger.load(reference)
        assert failed is not None
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.error_code, "RuntimeError")
        claim = self.claim()
        issued = self.ledger.load(reference)
        assert issued is not None
        self.assertEqual(issued.status, "issued")
        self.assertEqual(issued.provider_reward_id, claim.reference)

    def test_reward_reference_is_stable_and_session_specific(self) -> None:
        first = participant_reward_reference("session-one", "acl-1")

        self.assertEqual(first, participant_reward_reference("session-one", "acl-1"))
        self.assertNotEqual(first, participant_reward_reference("session-two", "acl-1"))
        self.assertNotIn("session-one", first)


if __name__ == "__main__":
    unittest.main()
