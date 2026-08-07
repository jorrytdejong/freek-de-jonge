"""Configuration parsing for the optional participant reward feature."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    """Validated runtime settings for fake or Tremendous sandbox rewards."""

    enabled: bool = False
    mode: str = "fake"
    amount_eur: Decimal = Decimal("3.40")
    ledger_path: Path = DEFAULT_REWARD_LEDGER_PATH
    tremendous_api_key: str = field(default="", repr=False)
    tremendous_campaign_id: str = ""
    tremendous_funding_source_id: str = ""

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
        if mode not in {"fake", "tremendous_sandbox"}:
            raise RewardConfigurationError(
                "Checkpoint 3 ondersteunt alleen fake of tremendous_sandbox."
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
        tremendous_section = secrets.get("tremendous", {})
        if not isinstance(tremendous_section, Mapping):
            raise RewardConfigurationError(
                "De Tremendous-configuratie in secrets is ongeldig."
            )
        api_key = str(
            environ.get(
                "TREMENDOUS_API_KEY",
                tremendous_section.get("api_key", ""),
            )
        ).strip()
        campaign_id = str(
            environ.get(
                "TREMENDOUS_CAMPAIGN_ID",
                tremendous_section.get("campaign_id", ""),
            )
        ).strip()
        funding_source_id = str(
            environ.get(
                "TREMENDOUS_FUNDING_SOURCE_ID",
                tremendous_section.get("funding_source_id", ""),
            )
        ).strip()
        if mode == "tremendous_sandbox":
            if not api_key.startswith("TEST_"):
                raise RewardConfigurationError(
                    "Tremendous sandbox vereist een TEST_ API-sleutel."
                )
            if not campaign_id or not funding_source_id:
                raise RewardConfigurationError(
                    "Tremendous sandbox vereist campaign_id en funding_source_id."
                )
        return cls(
            enabled=enabled,
            mode=mode,
            amount_eur=amount,
            ledger_path=ledger_path,
            tremendous_api_key=api_key,
            tremendous_campaign_id=campaign_id,
            tremendous_funding_source_id=funding_source_id,
        )
