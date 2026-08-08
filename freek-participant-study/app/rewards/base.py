"""Provider-neutral reward contract."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class RewardClaim:
    """A provider-issued claim that can be shown to a participant."""

    reference: str
    amount: Decimal
    currency: str
    provider: str
    is_test: bool
    redemption_url: str | None = None


class RewardProvider(Protocol):
    """Create a participant reward claim without exposing payment details."""

    provider_name: str
    is_real_money: bool

    def create_claim(
        self, *, participant_reference: str, amount: Decimal, currency: str
    ) -> RewardClaim:
        """Create or retrieve the claim for one participant reference."""

    def get_redemption_link(self, reward_id: str) -> str | None:
        """Return a fresh redemption link when the provider supports one."""

    def get_reward_status(self, reward_id: str) -> str:
        """Return the provider's current delivery status for a reward."""
