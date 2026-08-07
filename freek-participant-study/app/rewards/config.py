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
REAL_REWARD_ACKNOWLEDGEMENT = "I_UNDERSTAND_THIS_SENDS_REAL_MONEY"


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


def _parse_amount(
    value: object, *, setting: str = "FREEK_STUDY_REWARD_AMOUNT_EUR"
) -> Decimal:
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation as error:
        raise RewardConfigurationError(
            f"{setting} moet een geldig bedrag zijn."
        ) from error
    if not amount.is_finite() or amount <= 0:
        raise RewardConfigurationError(f"{setting} moet groter dan nul zijn.")
    if amount.as_tuple().exponent < -2:
        raise RewardConfigurationError(f"{setting} mag maximaal twee decimalen hebben.")
    return amount


def _parse_positive_integer(value: object, *, setting: str) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError as error:
        raise RewardConfigurationError(
            f"{setting} moet een geheel getal zijn."
        ) from error
    if parsed <= 0:
        raise RewardConfigurationError(f"{setting} moet groter dan nul zijn.")
    return parsed


@dataclass(frozen=True)
class RewardSettings:
    """Validated runtime settings for fake, sandbox, or locked production rewards."""

    enabled: bool = False
    mode: str = "fake"
    amount_eur: Decimal = Decimal("3.40")
    max_issued_count: int = 25
    budget_eur: Decimal = Decimal("85.00")
    ledger_path: Path = DEFAULT_REWARD_LEDGER_PATH
    tremendous_api_key: str = field(default="", repr=False)
    tremendous_campaign_id: str = ""
    tremendous_funding_source_id: str = ""
    deployment_environment: str = "local"
    real_rewards_acknowledged: bool = False

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
        if mode not in {"fake", "tremendous_sandbox", "tremendous_production"}:
            raise RewardConfigurationError(
                "Beloningsmodus moet fake, tremendous_sandbox of "
                "tremendous_production zijn."
            )
        deployment_environment = (
            str(
                _configured_value(
                    environ,
                    secrets,
                    "FREEK_STUDY_DEPLOYMENT_ENVIRONMENT",
                    "deployment_environment",
                    "local",
                )
            )
            .strip()
            .lower()
        )
        acknowledgement = str(
            _configured_value(
                environ,
                secrets,
                "FREEK_STUDY_REAL_REWARDS_ACK",
                "real_rewards_ack",
                "",
            )
        ).strip()
        real_rewards_acknowledged = acknowledgement == REAL_REWARD_ACKNOWLEDGEMENT
        amount = _parse_amount(
            _configured_value(
                environ,
                secrets,
                "FREEK_STUDY_REWARD_AMOUNT_EUR",
                "reward_amount_eur",
                "3.40",
            )
        )
        max_issued_count = _parse_positive_integer(
            _configured_value(
                environ,
                secrets,
                "FREEK_STUDY_REWARD_MAX_ISSUED",
                "reward_max_issued",
                25,
            ),
            setting="FREEK_STUDY_REWARD_MAX_ISSUED",
        )
        budget_eur = _parse_amount(
            _configured_value(
                environ,
                secrets,
                "FREEK_STUDY_REWARD_BUDGET_EUR",
                "reward_budget_eur",
                "85.00",
            ),
            setting="FREEK_STUDY_REWARD_BUDGET_EUR",
        )
        if enabled and budget_eur < amount:
            raise RewardConfigurationError(
                "FREEK_STUDY_REWARD_BUDGET_EUR moet minstens één beloning dekken."
            )
        ledger_path_configured = (
            "FREEK_STUDY_REWARD_LEDGER_PATH" in environ
            or "reward_ledger_path" in secrets
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
        if mode == "tremendous_production":
            if not api_key.startswith("PROD_"):
                raise RewardConfigurationError(
                    "Tremendous productie vereist een PROD_ API-sleutel."
                )
            if not campaign_id or not funding_source_id:
                raise RewardConfigurationError(
                    "Tremendous productie vereist campaign_id en funding_source_id."
                )
            if deployment_environment != "production":
                raise RewardConfigurationError(
                    "Tremendous productie vereist "
                    "FREEK_STUDY_DEPLOYMENT_ENVIRONMENT=production."
                )
            if not real_rewards_acknowledged:
                raise RewardConfigurationError(
                    "Tremendous productie vereist de expliciete real-money bevestiging."
                )
            if not ledger_path_configured or "sandbox" in str(ledger_path).lower():
                raise RewardConfigurationError(
                    "Tremendous productie vereist een afzonderlijk productielogboek."
                )
        return cls(
            enabled=enabled,
            mode=mode,
            amount_eur=amount,
            max_issued_count=max_issued_count,
            budget_eur=budget_eur,
            ledger_path=ledger_path,
            tremendous_api_key=api_key,
            tremendous_campaign_id=campaign_id,
            tremendous_funding_source_id=funding_source_id,
            deployment_environment=deployment_environment,
            real_rewards_acknowledged=real_rewards_acknowledged,
        )
