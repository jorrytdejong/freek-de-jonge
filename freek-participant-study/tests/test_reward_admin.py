import csv
import io
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.rewards import (
    RewardRecord,
    build_reward_operations_overview,
    filter_reward_records,
    reward_audit_csv,
    reward_audit_rows,
)


def reward_record(
    reference: str,
    status: str,
    *,
    is_test: bool = True,
    updated_at: datetime | None = None,
) -> RewardRecord:
    timestamp = updated_at or datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    return RewardRecord(
        reward_reference=reference,
        study_version="acl-1",
        is_test=is_test,
        status=status,
        provider="tremendous_sandbox",
        provider_reward_id="REWARD-123" if status == "issued" else "",
        amount=Decimal("3.40"),
        currency="EUR",
        error_code="TremendousAPIError" if status == "failed" else "",
        created_at=timestamp,
        updated_at=timestamp,
    )


class RewardOperationsTest(unittest.TestCase):
    def test_overview_counts_value_and_stuck_issuance(self) -> None:
        now = datetime(2026, 8, 7, 13, 0, tzinfo=UTC)
        records = (
            reward_record("issued", "issued"),
            replace(reward_record("issued-2", "issued"), amount=Decimal("2.00")),
            reward_record("declined", "declined"),
            reward_record("failed", "failed"),
            reward_record("stuck", "issuing", updated_at=now - timedelta(minutes=11)),
            reward_record("recent", "issuing", updated_at=now - timedelta(minutes=2)),
        )

        overview = build_reward_operations_overview(records, now=now)

        self.assertEqual(overview.total_count, 6)
        self.assertEqual(overview.issued_count, 2)
        self.assertEqual(overview.declined_count, 1)
        self.assertEqual(overview.failed_count, 1)
        self.assertEqual(overview.issuing_count, 2)
        self.assertEqual(overview.stuck_count, 1)
        self.assertEqual(overview.issued_amount, Decimal("5.40"))
        self.assertEqual(overview.reserved_count, 4)
        self.assertEqual(overview.reserved_amount, Decimal("12.20"))
        self.assertEqual(overview.currency, "EUR")

    def test_scope_filter_separates_real_and_test_rewards(self) -> None:
        records = (
            reward_record("test", "issued", is_test=True),
            reward_record("real", "issued", is_test=False),
        )

        self.assertEqual(
            [
                record.reward_reference
                for record in filter_reward_records(records, include_test=True)
            ],
            ["test"],
        )
        self.assertEqual(
            [
                record.reward_reference
                for record in filter_reward_records(records, include_test=False)
            ],
            ["real"],
        )
        self.assertEqual(len(filter_reward_records(records, include_test=None)), 2)

    def test_audit_export_contains_no_sessions_or_redemption_links(self) -> None:
        records = (reward_record("reward-pseudonym", "issued"),)

        rows = reward_audit_rows(records)
        exported = reward_audit_csv(records)
        parsed = list(csv.DictReader(io.StringIO(exported)))

        self.assertEqual(len(rows), 1)
        self.assertEqual(parsed[0]["reward_reference"], "reward-pseudonym")
        self.assertNotIn("session_id", exported)
        self.assertNotIn("redemption_url", exported)
        self.assertNotIn("https://", exported)


if __name__ == "__main__":
    unittest.main()
