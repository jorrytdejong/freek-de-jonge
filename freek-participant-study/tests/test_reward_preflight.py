import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.rewards import (
    RewardControlState,
    RewardRecord,
    RewardSettings,
    build_reward_preflight,
    preflight_rows,
)

NOW = datetime(2026, 8, 7, 18, 0, tzinfo=UTC)


def settings() -> RewardSettings:
    return RewardSettings(
        enabled=True,
        mode="tremendous_sandbox",
        amount_eur=Decimal("3.40"),
        max_issued_count=25,
        budget_eur=Decimal("85.00"),
    )


def issued_record() -> RewardRecord:
    return RewardRecord(
        reward_reference="reward-pseudonym",
        study_version="acl-1",
        is_test=True,
        status="issued",
        provider="tremendous_sandbox",
        provider_reward_id="REWARD123",
        amount=Decimal("3.40"),
        currency="EUR",
        error_code="",
        created_at=NOW - timedelta(hours=2),
        updated_at=NOW - timedelta(minutes=5),
        provider_status="SUCCEEDED",
        last_checked_at=NOW - timedelta(minutes=5),
    )


class RewardPreflightTest(unittest.TestCase):
    def test_ready_report_contains_no_production_activation(self) -> None:
        report = build_reward_preflight(
            settings(),
            (issued_record(),),
            RewardControlState(paused=False),
            admin_password_configured=True,
            now=NOW,
        )

        self.assertTrue(report.ready_for_sandbox_pilot)
        self.assertFalse(report.production_payments_enabled)
        self.assertTrue(all(check.passed for check in report.checks))
        rows = preflight_rows(report)
        self.assertTrue(all(row["Status"] == "GEREED" for row in rows))
        self.assertNotIn("TEST_secret", str(rows))

    def test_pause_stale_reconciliation_and_provider_failure_block_readiness(
        self,
    ) -> None:
        problematic = replace(
            issued_record(),
            provider_status="FAILED",
            last_checked_at=NOW - timedelta(hours=25),
        )

        report = build_reward_preflight(
            settings(),
            (problematic,),
            RewardControlState(paused=True, updated_at=NOW),
            admin_password_configured=False,
            now=NOW,
        )

        self.assertFalse(report.ready_for_sandbox_pilot)
        failed_names = {check.name for check in report.checks if not check.passed}
        self.assertEqual(
            failed_names,
            {"Beheerwachtwoord", "Noodstop", "Providerbezorging", "Reconciliatie"},
        )

    def test_exhausted_capacity_blocks_readiness(self) -> None:
        limited = replace(settings(), max_issued_count=1, budget_eur=Decimal("3.40"))

        report = build_reward_preflight(
            limited,
            (issued_record(),),
            RewardControlState(),
            admin_password_configured=True,
            now=NOW,
        )

        capacity = next(check for check in report.checks if check.name == "Capaciteit")
        self.assertFalse(capacity.passed)
        self.assertFalse(report.ready_for_sandbox_pilot)


if __name__ == "__main__":
    unittest.main()
