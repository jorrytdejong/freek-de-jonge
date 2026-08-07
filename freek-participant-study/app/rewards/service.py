"""Eligibility and one-claim orchestration for participant rewards."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from app.rewards.base import RewardClaim, RewardProvider
from app.rewards.ledger import CSVRewardLedger, RewardControlState, RewardRecord


class RewardNotEligibleError(RuntimeError):
    """Raised when a reward is requested before a valid submission."""


def participant_reward_reference(session_id: str, study_version: str) -> str:
    """Derive a stable pseudonym without storing the raw participant session ID."""
    material = f"reward-v1|{study_version}|{session_id}".encode()
    return "reward-" + hashlib.sha256(material).hexdigest()[:24]


class RewardService:
    """Coordinate eligibility, persistence, and a deterministic provider."""

    def __init__(
        self,
        ledger: CSVRewardLedger,
        provider: RewardProvider,
        *,
        max_issued_count: int = 25,
        budget_limit: Decimal = Decimal("85.00"),
    ) -> None:
        self.ledger = ledger
        self.provider = provider
        if max_issued_count <= 0 or budget_limit <= 0:
            raise ValueError("Reward limits must be greater than zero.")
        self.max_issued_count = max_issued_count
        self.budget_limit = budget_limit

    def load_control(self) -> RewardControlState:
        return self.ledger.load_control()

    def set_paused(self, paused: bool) -> RewardControlState:
        return self.ledger.set_paused(paused)

    def _claim_from_record(self, record: RewardRecord) -> RewardClaim | None:
        if record.status != "issued":
            return None
        redemption_url = self.provider.get_redemption_link(record.provider_reward_id)
        return RewardClaim(
            reference=record.provider_reward_id,
            amount=record.amount,
            currency=record.currency,
            provider=record.provider,
            is_test=record.provider in {"fake", "tremendous_sandbox"},
            redemption_url=redemption_url,
        )

    def load_claim(
        self, *, session_id: str, study_version: str, is_test: bool
    ) -> RewardClaim | None:
        reference = participant_reward_reference(session_id, study_version)
        record = self.ledger.load(reference)
        if record is None:
            return None
        if record.study_version != study_version or record.is_test is not is_test:
            raise RuntimeError("Stored reward context does not match the participant.")
        return self._claim_from_record(record)

    def load_status(
        self, *, session_id: str, study_version: str, is_test: bool
    ) -> str | None:
        reference = participant_reward_reference(session_id, study_version)
        record = self.ledger.load(reference)
        if record is None:
            return None
        if record.study_version != study_version or record.is_test is not is_test:
            raise RuntimeError("Stored reward context does not match the participant.")
        return record.status

    def decline_reward(
        self,
        *,
        session_id: str,
        study_version: str,
        is_test: bool,
        eligible: bool,
        amount: Decimal,
        currency: str = "EUR",
    ) -> str:
        if not eligible:
            raise RewardNotEligibleError(
                "A completed survey submission is required for a reward decision."
            )
        record = self.ledger.decline(
            reward_reference=participant_reward_reference(session_id, study_version),
            study_version=study_version,
            is_test=is_test,
            provider=self.provider.provider_name,
            amount=amount,
            currency=currency,
        )
        return record.status

    def claim_reward(
        self,
        *,
        session_id: str,
        study_version: str,
        is_test: bool,
        eligible: bool,
        amount: Decimal,
        currency: str = "EUR",
    ) -> RewardClaim:
        if not eligible:
            raise RewardNotEligibleError(
                "A completed survey submission is required for a reward."
            )
        reference = participant_reward_reference(session_id, study_version)
        provider_name = self.provider.provider_name
        record = self.ledger.issue_once(
            reward_reference=reference,
            study_version=study_version,
            is_test=is_test,
            provider=provider_name,
            amount=amount,
            currency=currency,
            max_issued_count=self.max_issued_count,
            budget_limit=self.budget_limit,
            issuer=lambda: self.provider.create_claim(
                participant_reference=reference,
                amount=amount,
                currency=currency,
            ),
        )
        claim = self._claim_from_record(record)
        if claim is None:
            raise RuntimeError("Reward issuance did not produce an issued claim.")
        return claim
