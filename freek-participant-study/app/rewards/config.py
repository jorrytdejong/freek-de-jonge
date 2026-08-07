"""Configuration parsing for the optional participant reward feature."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping

from app.rewards.ledger import DEFAULT_REWARD_LEDGER_PATH


class RewardConfigurationError(ValueError):
    """Raised when reward configuration is unsafe or invalid."""


TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _configured_value(
    environ: Mapping[str, str],
    secrets: Mapping[str, object],
    environment_name: str,
    secret_name: str,
    default: object,
) -> object:
    if environment_name in environ:
        return environ[environment_name]
    return secrets.get(secret_name, default)


def _parse_enabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise RewardConfigurationError(
        "FREEK_STUDY_REWARDS_ENABLED moet true of false zijn."
    )


def _parse_amount(value: object) -> Decimal:
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation as error:
        raise RewardConfigurationError(
            "FREEK_STUDY_REWARD_AMOUNT_EUR moet een geldig bedrag zijn."
        ) from error
    if not amount.is_finite() or amount <= 0:
        raise RewardConfigurationError(
            "FREEK_STUDY_REWARD_AMOUNT_EUR moet groter dan nul zijn."
        )
    if amount.as_tuple().exponent < -2:
        raise RewardConfigurationError(
            "FREEK_STUDY_REWARD_AMOUNT_EUR mag maximaal twee decimalen hebben."
        )
    return amount


@dataclass(frozen=True)
class RewardSettings:
    """Validated runtime settings for the Checkpoint 2 fake reward flow."""

    enabled: bool = False
    mode: str = "fake"
    amount_eur: Decimal = Decimal("3.40")
    ledger_path: Path = DEFAULT_REWARD_LEDGER_PATH

    @classmethod
    def from_sources(
        cls,
        *,
        environ: Mapping[str, str],
        secrets: Mapping[str, object],
    ) -> RewardSettings:
        enabled = _parse_enabled(
            _configured_value(
                environ,
                secrets,
                "FREEK_STUDY_REWARDS_ENABLED",
                "rewards_enabled",
                False,
            )
        )
        mode = (
            str(
                _configured_value(
                    environ,
                    secrets,
                    "FREEK_STUDY_REWARD_MODE",
                    "reward_mode",
                    "fake",
                )
            )
            .strip()
            .lower()
        )
        if mode != "fake":
            raise RewardConfigurationError(
                "Checkpoint 2 ondersteunt uitsluitend FREEK_STUDY_REWARD_MODE=fake."
            )
        amount = _parse_amount(
            _configured_value(
                environ,
                secrets,
                "FREEK_STUDY_REWARD_AMOUNT_EUR",
                "reward_amount_eur",
                "3.40",
            )
        )
        ledger_path = Path(
            str(
                _configured_value(
                    environ,
                    secrets,
                    "FREEK_STUDY_REWARD_LEDGER_PATH",
                    "reward_ledger_path",
                    DEFAULT_REWARD_LEDGER_PATH,
                )
            )
        )
        return cls(
            enabled=enabled,
            mode=mode,
            amount_eur=amount,
            ledger_path=ledger_path,
        )
