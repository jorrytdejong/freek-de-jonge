"""Reward providers and configuration for participant thank-you rewards."""

from app.rewards.base import RewardClaim, RewardProvider
from app.rewards.config import RewardConfigurationError, RewardSettings
from app.rewards.fake import FakeRewardProvider
from app.rewards.ledger import CSVRewardLedger, RewardLedgerError, RewardRecord
from app.rewards.service import (
    RewardNotEligibleError,
    RewardService,
    participant_reward_reference,
)
from app.rewards.tremendous import (
    TremendousAPIError,
    TremendousSandboxRewardProvider,
)

__all__ = [
    "CSVRewardLedger",
    "FakeRewardProvider",
    "RewardClaim",
    "RewardConfigurationError",
    "RewardLedgerError",
    "RewardNotEligibleError",
    "RewardProvider",
    "RewardRecord",
    "RewardService",
    "RewardSettings",
    "TremendousAPIError",
    "TremendousSandboxRewardProvider",
    "participant_reward_reference",
]
