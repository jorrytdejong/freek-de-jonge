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
    RewardBudgetExceededError,
    RewardClaim,
    RewardIssuancePausedError,
    RewardLedgerError,
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

    def __init__(self) -> None:
        self.link_count = 0

    def create_claim(self, *, amount, currency, **kwargs):
        return RewardClaim(
            reference="REWARD-123",
            amount=amount,
            currency=currency,
            provider=self.provider_name,
            is_test=True,
            redemption_url="https://testflight.tremendous.com/rewards/test-123",
        )

    def get_redemption_link(self, reward_id):
        self.link_count += 1
        return f"https://testflight.tremendous.com/rewards/fresh-{self.link_count}"


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

    def test_sandbox_link_is_regenerated_and_never_stored_in_ledger(self) -> None:
        provider = LinkRewardProvider()
        service = RewardService(self.ledger, provider)
        issued = service.claim_reward(
            session_id="sandbox-participant",
            study_version="acl-1",
            is_test=True,
            eligible=True,
            amount=Decimal("3.40"),
        )

        reopened = RewardService(CSVRewardLedger(self.path), provider)
        loaded = reopened.load_claim(
            session_id="sandbox-participant",
            study_version="acl-1",
            is_test=True,
        )
        assert loaded is not None
        self.assertNotEqual(loaded.redemption_url, issued.redemption_url)
        ledger_text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("redemption_url", ledger_text)
        self.assertNotIn("https://", ledger_text)

    def test_legacy_redemption_links_are_scrubbed(self) -> None:
        provider = LinkRewardProvider()
        RewardService(self.ledger, provider).claim_reward(
            session_id="sandbox-participant",
            study_version="acl-1",
            is_test=True,
            eligible=True,
            amount=Decimal("3.40"),
        )
        rows = self.ledger.list_records()
        legacy_fields = list(REWARD_FIELDNAMES)
        legacy_fields.insert(6, "redemption_url")
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=legacy_fields)
            writer.writeheader()
            row = {
                key: value
                for key, value in zip(
                    REWARD_FIELDNAMES,
                    (
                        rows[0].reward_reference,
                        rows[0].study_version,
                        "true",
                        rows[0].status,
                        rows[0].provider,
                        rows[0].provider_reward_id,
                        str(rows[0].amount),
                        rows[0].currency,
                        rows[0].error_code,
                        rows[0].created_at.isoformat(),
                        rows[0].updated_at.isoformat(),
                    ),
                    strict=True,
                )
            }
            row["redemption_url"] = "https://example.invalid/bearer-secret"
            writer.writerow(row)

        self.assertTrue(self.ledger.scrub_legacy_links())
        self.assertNotIn("bearer-secret", self.path.read_text(encoding="utf-8"))
        self.assertFalse(self.ledger.scrub_legacy_links())

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

    def test_decline_persists_and_participant_can_change_their_mind(self) -> None:
        status = self.service.decline_reward(
            session_id="real-session-one",
            study_version="acl-1",
            is_test=False,
            eligible=True,
            amount=Decimal("3.40"),
        )

        self.assertEqual(status, "declined")
        self.assertEqual(self.provider.call_count, 0)
        reopened = RewardService(CSVRewardLedger(self.path), self.provider)
        self.assertEqual(
            reopened.load_status(
                session_id="real-session-one",
                study_version="acl-1",
                is_test=False,
            ),
            "declined",
        )
        claim = reopened.claim_reward(
            session_id="real-session-one",
            study_version="acl-1",
            is_test=False,
            eligible=True,
            amount=Decimal("3.40"),
        )
        self.assertTrue(claim.reference.startswith("fake-"))
        self.assertEqual(self.provider.call_count, 1)
        self.assertEqual(
            reopened.load_status(
                session_id="real-session-one",
                study_version="acl-1",
                is_test=False,
            ),
            "issued",
        )

    def test_ineligible_participant_cannot_decline_reward(self) -> None:
        with self.assertRaises(RewardNotEligibleError):
            self.service.decline_reward(
                session_id="not-submitted",
                study_version="acl-1",
                is_test=False,
                eligible=False,
                amount=Decimal("3.40"),
            )

        self.assertFalse(self.path.exists())

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

    def test_reward_count_limit_blocks_provider_before_issuance(self) -> None:
        limited = RewardService(
            self.ledger,
            self.provider,
            max_issued_count=1,
            budget_limit=Decimal("85.00"),
        )
        limited.claim_reward(
            session_id="first-session",
            study_version="acl-1",
            is_test=False,
            eligible=True,
            amount=Decimal("3.40"),
        )

        with self.assertRaises(RewardBudgetExceededError):
            limited.claim_reward(
                session_id="second-session",
                study_version="acl-1",
                is_test=False,
                eligible=True,
                amount=Decimal("3.40"),
            )

        self.assertEqual(self.provider.call_count, 1)
        self.assertEqual(len(self.ledger.list_records()), 1)

    def test_total_budget_blocks_provider_before_issuance(self) -> None:
        limited = RewardService(
            self.ledger,
            self.provider,
            max_issued_count=25,
            budget_limit=Decimal("5.00"),
        )
        first = limited.claim_reward(
            session_id="first-session",
            study_version="acl-1",
            is_test=False,
            eligible=True,
            amount=Decimal("3.40"),
        )

        with self.assertRaises(RewardBudgetExceededError):
            limited.claim_reward(
                session_id="second-session",
                study_version="acl-1",
                is_test=False,
                eligible=True,
                amount=Decimal("3.40"),
            )

        same = limited.claim_reward(
            session_id="first-session",
            study_version="acl-1",
            is_test=False,
            eligible=True,
            amount=Decimal("3.40"),
        )
        self.assertEqual(same, first)
        self.assertEqual(self.provider.call_count, 1)

    def test_operator_pause_blocks_new_claims_but_not_existing_claims(self) -> None:
        existing = self.claim("existing-session")
        paused = self.service.set_paused(True)

        self.assertTrue(paused.paused)
        self.assertTrue(CSVRewardLedger(self.path).load_control().paused)
        with self.assertRaises(RewardIssuancePausedError):
            self.claim("new-session")
        self.assertEqual(self.provider.call_count, 1)
        self.assertEqual(self.claim("existing-session"), existing)
        self.assertEqual(self.provider.call_count, 1)

        resumed = self.service.set_paused(False)
        self.assertFalse(resumed.paused)
        self.claim("new-session")
        self.assertEqual(self.provider.call_count, 2)

    def test_invalid_control_file_fails_closed(self) -> None:
        self.ledger.control_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.control_path.write_text("not-json", encoding="utf-8")

        with self.assertRaises(RewardLedgerError):
            self.ledger.load_control()
        with self.assertRaises(RewardLedgerError):
            self.claim("new-session")
        self.assertEqual(self.provider.call_count, 0)

    def test_interrupted_issuing_record_can_resume_with_same_reference(self) -> None:
        reference = participant_reward_reference("interrupted-session", "acl-1")
        arguments = {
            "reward_reference": reference,
            "study_version": "acl-1",
            "is_test": False,
            "provider": "fake",
            "amount": Decimal("3.40"),
            "currency": "EUR",
        }

        with self.assertRaises(KeyboardInterrupt):
            self.ledger.issue_once(
                **arguments,
                issuer=lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
            )
        interrupted = self.ledger.load(reference)
        assert interrupted is not None
        self.assertEqual(interrupted.status, "issuing")

        claim = self.service.claim_reward(
            session_id="interrupted-session",
            study_version="acl-1",
            is_test=False,
            eligible=True,
            amount=Decimal("3.40"),
        )
        self.assertTrue(claim.reference.startswith("fake-"))
        self.assertEqual(self.ledger.load(reference).status, "issued")

    def test_reward_reference_is_stable_and_session_specific(self) -> None:
        first = participant_reward_reference("session-one", "acl-1")

        self.assertEqual(first, participant_reward_reference("session-one", "acl-1"))
        self.assertNotEqual(first, participant_reward_reference("session-two", "acl-1"))
        self.assertNotIn("session-one", first)


if __name__ == "__main__":
    unittest.main()
