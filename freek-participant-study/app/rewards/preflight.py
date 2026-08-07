"""Offline go-live checks for the sandbox participant reward pilot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Iterable

from app.rewards.config import RewardSettings
from app.rewards.ledger import RewardControlState, RewardRecord


@dataclass(frozen=True)
class RewardPreflightCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class RewardPreflightReport:
    checks: tuple[RewardPreflightCheck, ...]
    ready_for_sandbox_pilot: bool
    production_payments_enabled: bool = False


def build_reward_preflight(
    settings: RewardSettings,
    records: Iterable[RewardRecord],
    control: RewardControlState,
    *,
    admin_password_configured: bool,
    now: datetime | None = None,
    reconciliation_max_age: timedelta = timedelta(hours=24),
) -> RewardPreflightReport:
    """Build a credential-free, network-free operational readiness report."""
    records = tuple(records)
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        raise ValueError("Reward preflight timestamp must include a timezone.")
    reserved = tuple(
        record for record in records if record.status in {"issuing", "issued"}
    )
    reserved_amount = sum((record.amount for record in reserved), start=Decimal("0"))
    issued = tuple(record for record in records if record.status == "issued")
    unchecked = tuple(
        record
        for record in issued
        if record.last_checked_at is None or not record.provider_status
    )
    stale = tuple(
        record
        for record in issued
        if record.last_checked_at is not None
        and current_time - record.last_checked_at > reconciliation_max_age
    )
    failed = tuple(record for record in records if record.status == "failed")
    provider_failed = tuple(
        record for record in issued if record.provider_status == "FAILED"
    )
    stuck = tuple(
        record
        for record in records
        if record.status == "issuing"
        and current_time - record.updated_at >= timedelta(minutes=10)
    )
    remaining_count = settings.max_issued_count - len(reserved)
    remaining_budget = settings.budget_eur - reserved_amount
    checks = (
        RewardPreflightCheck(
            "Beloningsfunctie",
            settings.enabled,
            "Ingeschakeld" if settings.enabled else "Uitgeschakeld",
        ),
        RewardPreflightCheck(
            "API-omgeving",
            settings.mode == "tremendous_sandbox",
            "Tremendous Testflight; productiesleutels worden geweigerd",
        ),
        RewardPreflightCheck(
            "Beheerwachtwoord",
            admin_password_configured,
            "Geconfigureerd" if admin_password_configured else "Ontbreekt",
        ),
        RewardPreflightCheck(
            "Noodstop",
            not control.paused,
            "Uitgifte actief" if not control.paused else "Uitgifte gepauzeerd",
        ),
        RewardPreflightCheck(
            "Capaciteit",
            remaining_count > 0 and remaining_budget >= settings.amount_eur,
            (
                f"{max(0, remaining_count)} beloningen en "
                f"€{max(Decimal('0'), remaining_budget):.2f} beschikbaar"
            ),
        ),
        RewardPreflightCheck(
            "Mislukte claims",
            not failed,
            f"{len(failed)} mislukt",
        ),
        RewardPreflightCheck(
            "Providerbezorging",
            not provider_failed,
            f"{len(provider_failed)} met Tremendous-status FAILED",
        ),
        RewardPreflightCheck(
            "Vastgelopen claims",
            not stuck,
            f"{len(stuck)} langer dan tien minuten bezig",
        ),
        RewardPreflightCheck(
            "Reconciliatie",
            not unchecked and not stale,
            f"{len(unchecked)} niet gecontroleerd; {len(stale)} ouder dan 24 uur",
        ),
        RewardPreflightCheck(
            "Productiebetalingen",
            True,
            "Uitgeschakeld; deze build accepteert uitsluitend TEST_-sleutels",
        ),
    )
    return RewardPreflightReport(
        checks=checks,
        ready_for_sandbox_pilot=all(check.passed for check in checks),
    )


def preflight_rows(report: RewardPreflightReport) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "Controle": check.name,
            "Status": "GEREED" if check.passed else "ACTIE NODIG",
            "Toelichting": check.detail,
        }
        for check in report.checks
    )
