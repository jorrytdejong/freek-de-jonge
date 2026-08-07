"""Deterministic, local-only reward provider used during development."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from app.rewards.base import RewardClaim


class FakeRewardProvider:
    """Create stable fake claims without network access or monetary value."""

    provider_name = "fake"

    def create_claim(
        self, *, participant_reference: str, amount: Decimal, currency: str
    ) -> RewardClaim:
        if not participant_reference.strip():
            raise ValueError("participant_reference mag niet leeg zijn.")
        if amount <= 0:
            raise ValueError("amount moet groter dan nul zijn.")
        normalized_currency = currency.strip().upper()
        if len(normalized_currency) != 3 or not normalized_currency.isalpha():
            raise ValueError("currency moet een ISO-valutacode van drie letters zijn.")
        claim_input = (
            f"fake-reward-v1|{participant_reference}|{amount}|{normalized_currency}"
        )
        reference = "fake-" + hashlib.sha256(claim_input.encode()).hexdigest()[:16]
        return RewardClaim(
            reference=reference,
            amount=amount,
            currency=normalized_currency,
            provider=self.provider_name,
            is_test=True,
        )

    def get_redemption_link(self, reward_id: str) -> None:
        """Fake claims have no external redemption destination."""
        return None

    def get_reward_status(self, reward_id: str) -> str:
        """A deterministic fake claim is immediately available."""
        return "SUCCEEDED"
