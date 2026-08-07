"""Tremendous sandbox reward provider with no production capability."""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.rewards.base import RewardClaim

TREMENDOUS_SANDBOX_ORDERS_URL = "https://testflight.tremendous.com/api/v2/orders"
SANDBOX_REDEMPTION_HOSTS = frozenset(
    {"testflight.tremendous.com", "app.testflight.tremendous.com"}
)


class TremendousAPIError(RuntimeError):
    """A safe, credential-free description of a sandbox API failure."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class JSONTransport(Protocol):
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

    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout: float,
    ) -> tuple[int, dict[str, object]]:
        request = Request(
            url,
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                status = response.status
                raw_body = response.read()
        except HTTPError as error:
            raise TremendousAPIError(
                f"Tremendous sandbox returned HTTP {error.code}.",
                status_code=error.code,
            ) from error
        except (TimeoutError, URLError) as error:
            raise TremendousAPIError(
                "Tremendous sandbox could not be reached."
            ) from error
        try:
            decoded = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise TremendousAPIError(
                "Tremendous sandbox returned invalid JSON.", status_code=status
            ) from error
        if not isinstance(decoded, dict):
            raise TremendousAPIError(
                "Tremendous sandbox returned an invalid response.", status_code=status
            )
        return status, decoded


def _response_reward(payload: Mapping[str, object]) -> tuple[str, str]:
    order = payload.get("order")
    if not isinstance(order, Mapping):
        raise TremendousAPIError("Tremendous response has no order.")
    rewards = order.get("rewards")
    if not isinstance(rewards, list) or len(rewards) != 1:
        raise TremendousAPIError("Tremendous response has no single reward.")
    reward = rewards[0]
    if not isinstance(reward, Mapping):
        raise TremendousAPIError("Tremendous response has an invalid reward.")
    reward_id = reward.get("id")
    delivery = reward.get("delivery")
    link = delivery.get("link") if isinstance(delivery, Mapping) else None
    if not isinstance(reward_id, str) or not reward_id.strip():
        raise TremendousAPIError("Tremendous response has no reward ID.")
    if not isinstance(link, str) or not link.strip():
        raise TremendousAPIError("Tremendous response has no redemption link.")
    parsed_link = urlparse(link)
    if (
        parsed_link.scheme != "https"
        or parsed_link.hostname not in SANDBOX_REDEMPTION_HOSTS
    ):
        raise TremendousAPIError("Tremendous returned a non-sandbox redemption link.")
    return reward_id, link


class TremendousSandboxRewardProvider:
    """Create idempotent link rewards using fake Tremendous sandbox funds."""

    provider_name = "tremendous_sandbox"

    def __init__(
        self,
        *,
        api_key: str,
        campaign_id: str,
        funding_source_id: str,
        transport: JSONTransport | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not api_key.startswith("TEST_"):
            raise ValueError("Tremendous sandbox requires a TEST_ API key.")
        if not campaign_id.strip() or not funding_source_id.strip():
            raise ValueError("Tremendous campaign and funding source are required.")
        self._api_key = api_key
        self.campaign_id = campaign_id
        self.funding_source_id = funding_source_id
        self.transport = transport or UrllibJSONTransport()
        self.timeout_seconds = timeout_seconds

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
                "delivery": {"method": "LINK"},
                "language": "nl",
            },
        }
        status, response = self.transport.post_json(
            url=TREMENDOUS_SANDBOX_ORDERS_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
            timeout=self.timeout_seconds,
        )
        if status not in {200, 201}:
            raise TremendousAPIError(
                f"Tremendous sandbox returned HTTP {status}.", status_code=status
            )
        reward_id, redemption_url = _response_reward(response)
        return RewardClaim(
            reference=reward_id,
            amount=amount,
            currency=normalized_currency,
            provider=self.provider_name,
            is_test=True,
            redemption_url=redemption_url,
        )
