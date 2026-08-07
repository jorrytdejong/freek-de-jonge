#!/usr/bin/env python3
"""Run the reward pilot preflight without making network requests."""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rewards import CSVRewardLedger, RewardSettings
from app.rewards.preflight import build_reward_preflight


def local_secrets() -> dict[str, object]:
    path = PROJECT_ROOT / ".streamlit" / "secrets.toml"
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    secrets = local_secrets()
    settings = RewardSettings.from_sources(environ=dict(os.environ), secrets=secrets)
    ledger_path = (
        settings.ledger_path
        if settings.ledger_path.is_absolute()
        else PROJECT_ROOT / settings.ledger_path
    )
    ledger = CSVRewardLedger(ledger_path)
    report = build_reward_preflight(
        settings,
        ledger.list_records(),
        ledger.load_control(),
        admin_password_configured=bool(
            os.environ.get("FREEK_STUDY_ADMIN_PASSWORD")
            or secrets.get("admin_password")
        ),
    )
    for check in report.checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"[{marker}] {check.name}: {check.detail}")
    print(
        "READY: sandbox pilot"
        if report.ready_for_sandbox_pilot
        else "NOT READY: resolve failed checks"
    )
    print("PRODUCTION PAYMENTS: disabled")
    return 0 if report.ready_for_sandbox_pilot else 1


if __name__ == "__main__":
    raise SystemExit(main())
