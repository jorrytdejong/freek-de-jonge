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


class RewardProvider(Protocol):
    """Create a participant reward claim without exposing payment details."""

    provider_name: str

    def create_claim(
        self, *, participant_reference: str, amount: Decimal, currency: str
    ) -> RewardClaim:
        """Create or retrieve the claim for one participant reference."""
