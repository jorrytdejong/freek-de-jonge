"""Tremendous reward providers with strict sandbox/production separation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from app.rewards.base import RewardClaim

TREMENDOUS_SANDBOX_API = "https://testflight.tremendous.com/api/v2"
TREMENDOUS_SANDBOX_ORDERS_URL = f"{TREMENDOUS_SANDBOX_API}/orders"
TREMENDOUS_PRODUCTION_API = "https://api.tremendous.com/api/v2"
TREMENDOUS_PRODUCTION_ORDERS_URL = f"{TREMENDOUS_PRODUCTION_API}/orders"
SANDBOX_REDEMPTION_HOSTS = frozenset(
    {
        "testflight.tremendous.com",
        "app.testflight.tremendous.com",
        "reward.testflight.tremendous.com",
    }
)
PRODUCTION_REDEMPTION_HOSTS = frozenset(
    {
        "tremendous.com",
        "www.tremendous.com",
        "app.tremendous.com",
        "reward.tremendous.com",
    }
)


class TremendousAPIError(RuntimeError):
    """A safe, credential-free description of a Tremendous API failure."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        uncertain: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.uncertain = uncertain


class JSONTransport(Protocol):
    def get_json(
        self, *, url: str, headers: Mapping[str, str], timeout: float
    ) -> tuple[int, dict[str, object]]: ...

    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout: float,
    ) -> tuple[int, dict[str, object]]: ...


class UrllibJSONTransport:
    """Small standard-library JSON transport to keep dependencies minimal."""

    @staticmethod
    def _request_json(
        request: Request, *, timeout: float
    ) -> tuple[int, dict[str, object]]:
        try:
            with urlopen(request, timeout=timeout) as response:
                status = response.status
                raw_body = response.read()
        except HTTPError as error:
            raise TremendousAPIError(
                f"Tremendous returned HTTP {error.code}.",
                status_code=error.code,
                retryable=error.code == 409 or error.code == 429 or error.code >= 500,
            ) from error
        except (TimeoutError, URLError) as error:
            raise TremendousAPIError(
                "Tremendous could not be reached.", retryable=True
            ) from error
        try:
            decoded = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise TremendousAPIError(
                "Tremendous returned invalid JSON.",
                status_code=status,
                retryable=True,
            ) from error
        if not isinstance(decoded, dict):
            raise TremendousAPIError(
                "Tremendous returned an invalid response.",
                status_code=status,
                retryable=True,
            )
        return status, decoded

    def get_json(
        self, *, url: str, headers: Mapping[str, str], timeout: float
    ) -> tuple[int, dict[str, object]]:
        return self._request_json(
            Request(url, headers=dict(headers), method="GET"), timeout=timeout
        )

    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout: float,
    ) -> tuple[int, dict[str, object]]:
        return self._request_json(
            Request(
                url,
                data=json.dumps(payload, separators=(",", ":")).encode(),
                headers=dict(headers),
                method="POST",
            ),
            timeout=timeout,
        )


def _reward(payload: Mapping[str, object]) -> Mapping[str, object]:
    order = payload.get("order")
    if not isinstance(order, Mapping):
        raise TremendousAPIError("Tremendous response has no order.")
    rewards = order.get("rewards")
    if not isinstance(rewards, list) or len(rewards) != 1:
        raise TremendousAPIError("Tremendous response has no single reward.")
    reward = rewards[0]
    if not isinstance(reward, Mapping):
        raise TremendousAPIError("Tremendous response has an invalid reward.")
    return reward


def _reward_id(payload: Mapping[str, object]) -> str:
    reward_id = _reward(payload).get("id")
    if not isinstance(reward_id, str) or not reward_id.strip():
        raise TremendousAPIError("Tremendous response has no reward ID.")
    return reward_id


def _validate_link(link: object, allowed_hosts: frozenset[str]) -> str:
    if not isinstance(link, str) or not link.strip():
        raise TremendousAPIError("Tremendous response has no redemption link.")
    parsed_link = urlparse(link)
    if parsed_link.scheme != "https" or parsed_link.hostname not in allowed_hosts:
        raise TremendousAPIError("Tremendous returned an unexpected redemption link.")
    return link


def _generated_link(
    payload: Mapping[str, object], allowed_hosts: frozenset[str]
) -> str:
    reward = payload.get("reward")
    if not isinstance(reward, Mapping):
        raise TremendousAPIError("Tremendous response has no reward.")
    return _validate_link(reward.get("link"), allowed_hosts)


def _delivery_status(payload: Mapping[str, object]) -> str:
    reward = payload.get("reward")
    if not isinstance(reward, Mapping):
        raise TremendousAPIError("Tremendous response has no reward.")
    delivery = reward.get("delivery")
    status = delivery.get("status") if isinstance(delivery, Mapping) else None
    if not isinstance(status, str) or not status.strip():
        raise TremendousAPIError("Tremendous response has no delivery status.")
    normalized = status.strip().upper()
    if normalized not in {"PENDING", "SCHEDULED", "SUCCEEDED", "FAILED"}:
        raise TremendousAPIError("Tremendous returned an unknown delivery status.")
    return normalized


def _status_error(status: int) -> TremendousAPIError:
    if status == 402:
        return TremendousAPIError(
            "Tremendous has insufficient funding.", status_code=status
        )
    if status in {401, 403}:
        return TremendousAPIError(
            "Tremendous credentials were rejected.", status_code=status
        )
    if status == 422:
        return TremendousAPIError(
            "Tremendous rejected the reward configuration.", status_code=status
        )
    retryable = status == 409 or status == 429 or status >= 500
    return TremendousAPIError(
        f"Tremendous returned HTTP {status}.",
        status_code=status,
        retryable=retryable,
    )


class _TremendousRewardProvider:
    """Shared idempotent link-reward implementation for one fixed environment."""

    provider_name = "tremendous"
    is_real_money = False
    api_base = ""
    api_key_prefix = ""
    redemption_hosts: frozenset[str] = frozenset()

    def __init__(
        self,
        *,
        api_key: str,
        campaign_id: str,
        funding_source_id: str,
        transport: JSONTransport | None = None,
        timeout_seconds: float = 15.0,
        allow_real_money: bool = False,
    ) -> None:
        if self.is_real_money and not allow_real_money:
            raise ValueError(
                "Tremendous production requires an explicit real-money opt-in."
            )
        if not api_key.startswith(self.api_key_prefix):
            raise ValueError(
                f"{self.provider_name} requires a {self.api_key_prefix} API key."
            )
        if not campaign_id.strip() or not funding_source_id.strip():
            raise ValueError("Tremendous campaign and funding source are required.")
        self._api_key = api_key
        self.campaign_id = campaign_id
        self.funding_source_id = funding_source_id
        self.transport = transport or UrllibJSONTransport()
        self.timeout_seconds = timeout_seconds

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _recover_order(
        self, external_id: str, original: TremendousAPIError
    ) -> RewardClaim:
        try:
            status, response = self.transport.get_json(
                url=f"{self.api_base}/orders/{quote(external_id, safe='')}",
                headers=self._headers,
                timeout=self.timeout_seconds,
            )
        except TremendousAPIError as recovery_error:
            if recovery_error.status_code == 404:
                raise original
            raise TremendousAPIError(
                "The Tremendous order status is temporarily uncertain.",
                retryable=True,
                uncertain=True,
            ) from recovery_error
        if status == 404:
            raise original
        if status != 200:
            raise TremendousAPIError(
                "The Tremendous order status is temporarily uncertain.",
                status_code=status,
                retryable=True,
                uncertain=True,
            )
        reward_id = _reward_id(response)
        link = self.get_redemption_link(reward_id)
        return RewardClaim(
            reference=reward_id,
            amount=Decimal("0"),
            currency="",
            provider=self.provider_name,
            is_test=not self.is_real_money,
            redemption_url=link,
        )

    def get_redemption_link(self, reward_id: str) -> str:
        if not reward_id.strip():
            raise TremendousAPIError("A Tremendous reward ID is required.")
        status, response = self.transport.post_json(
            url=(f"{self.api_base}/rewards/{quote(reward_id, safe='')}/generate_link"),
            headers=self._headers,
            payload={},
            timeout=self.timeout_seconds,
        )
        if status not in {200, 201}:
            raise _status_error(status)
        return _generated_link(response, self.redemption_hosts)

    def get_reward_status(self, reward_id: str) -> str:
        if not reward_id.strip():
            raise TremendousAPIError("A Tremendous reward ID is required.")
        status, response = self.transport.get_json(
            url=f"{self.api_base}/rewards/{quote(reward_id, safe='')}",
            headers=self._headers,
            timeout=self.timeout_seconds,
        )
        if status != 200:
            raise _status_error(status)
        return _delivery_status(response)

    def create_claim(
        self, *, participant_reference: str, amount: Decimal, currency: str
    ) -> RewardClaim:
        normalized_currency = currency.strip().upper()
        payload: dict[str, object] = {
            "external_id": participant_reference,
            "payment": {"funding_source_id": self.funding_source_id},
            "reward": {
                "campaign_id": self.campaign_id,
                "value": {
                    "denomination": float(amount),
                    "currency_code": normalized_currency,
                },
                "recipient": {"name": "Deelnemer"},
                "delivery": {"method": "LINK"},
                "language": "nl",
            },
        }
        try:
            status, response = self.transport.post_json(
                url=f"{self.api_base}/orders",
                headers=self._headers,
                payload=payload,
                timeout=self.timeout_seconds,
            )
            if status not in {200, 201}:
                raise _status_error(status)
        except TremendousAPIError as error:
            if not error.retryable:
                raise
            recovered = self._recover_order(participant_reference, error)
            return RewardClaim(
                reference=recovered.reference,
                amount=amount,
                currency=normalized_currency,
                provider=self.provider_name,
                is_test=True,
                redemption_url=recovered.redemption_url,
            )
        reward_id = _reward_id(response)
        reward = _reward(response)
        delivery = reward.get("delivery")
        response_link = delivery.get("link") if isinstance(delivery, Mapping) else None
        redemption_url = (
            _validate_link(response_link, self.redemption_hosts)
            if response_link
            else self.get_redemption_link(reward_id)
        )
        return RewardClaim(
            reference=reward_id,
            amount=amount,
            currency=normalized_currency,
            provider=self.provider_name,
            is_test=not self.is_real_money,
            redemption_url=redemption_url,
        )


class TremendousSandboxRewardProvider(_TremendousRewardProvider):
    """Create idempotent link rewards using fake Tremendous sandbox funds."""

    provider_name = "tremendous_sandbox"
    is_real_money = False
    api_base = TREMENDOUS_SANDBOX_API
    api_key_prefix = "TEST_"
    redemption_hosts = SANDBOX_REDEMPTION_HOSTS


class TremendousProductionRewardProvider(_TremendousRewardProvider):
    """Create real rewards, only after configuration has passed production gates."""

    provider_name = "tremendous_production"
    is_real_money = True
    api_base = TREMENDOUS_PRODUCTION_API
    api_key_prefix = "PROD_"
    redemption_hosts = PRODUCTION_REDEMPTION_HOSTS
