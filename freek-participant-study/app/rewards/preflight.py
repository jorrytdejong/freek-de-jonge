"""Offline go-live checks for sandbox pilots and guarded production rewards."""

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
    ready_for_production: bool = False


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
    production_mode = settings.mode == "tremendous_production"
    environment_ok = (
        settings.deployment_environment == "production"
        and settings.real_rewards_acknowledged
    )
    participant_scope_ok = not production_mode or not any(
        record.is_test and record.status in {"issuing", "issued"} for record in records
    )
    canary_ok = not production_mode or (
        settings.production_canary_enabled
        and bool(settings.production_canary_reward_reference)
        and settings.max_issued_count == 1
        and settings.budget_eur == settings.amount_eur
    )
    checks = (
        RewardPreflightCheck(
            "Beloningsfunctie",
            settings.enabled,
            "Ingeschakeld" if settings.enabled else "Uitgeschakeld",
        ),
        RewardPreflightCheck(
            "API-omgeving",
            settings.mode in {"tremendous_sandbox", "tremendous_production"},
            (
                "Tremendous productie; uitsluitend PROD_-sleutels"
                if production_mode
                else "Tremendous Testflight; productiesleutels worden geweigerd"
            ),
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
            "Productieslot",
            environment_ok if production_mode else True,
            (
                "Ontgrendeld met productieomgeving en expliciete real-money bevestiging"
                if environment_ok
                else "Uitgeschakeld; sandbox kan geen echt geld versturen"
                if not production_mode
                else "Productieomgeving of expliciete real-money bevestiging ontbreekt"
            ),
        ),
        RewardPreflightCheck(
            "Deelnemersscope",
            participant_scope_ok,
            (
                "Geen testdeelnemers in het productielogboek"
                if production_mode
                else "Testdeelnemers zijn toegestaan in sandbox"
            ),
        ),
        RewardPreflightCheck(
            "Productiecanary",
            canary_ok,
            (
                "Eén vooraf geautoriseerde deelnemer; maximaal één beloning"
                if production_mode and canary_ok
                else "Uitgeschakeld in sandbox"
                if not production_mode
                else "Canary-allowlist of één-beloninglimiet ontbreekt"
            ),
        ),
    )
    all_passed = all(check.passed for check in checks)
    return RewardPreflightReport(
        checks=checks,
        ready_for_sandbox_pilot=all_passed and not production_mode,
        production_payments_enabled=all_passed and production_mode,
        ready_for_production=all_passed and production_mode,
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
