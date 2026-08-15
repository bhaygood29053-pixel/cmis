"""Official X1 network-supply provider primitives for CMIS.

This module owns read-only collection from the public ``api.x1.xyz`` supply
endpoints. These endpoints are network-scoped rather than mint-scoped, so the
facts exposed here are explicitly treated as native X1/XNT network supply
facts and must not be reused for arbitrary X1 token mints.

The API currently returns plain-text integer values. CMIS preserves that value
exactly and does not invent decimal scaling or derive additional tokenomics
facts in this provider layer.
"""

from typing import Any, Dict

import requests


CHAIN = "x1"
ASSET = "XNT"
DEFAULT_NETWORK = "mainnet"
SUPPLY_API_BASE_URL = "https://api.x1.xyz/v1/supply"
SUPPLY_SOURCE = "api.x1.xyz"


class X1SupplyAPIError(RuntimeError):
    """Raised when a verified X1 network-supply request cannot be completed."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def parse_supply_text(value: Any) -> str:
    """Return an exact non-negative integer string or fail closed.

    No decimal scaling is applied because the provider response itself is the
    source-of-truth representation for this boundary.
    """
    text = _text(value)
    if not text or not text.isdigit():
        raise X1SupplyAPIError("X1 supply API returned a non-integer value.")
    return text.lstrip("0") or "0"


def fetch_supply(
    metric: str,
    *,
    network: str = DEFAULT_NETWORK,
    base_url: str = SUPPLY_API_BASE_URL,
    timeout: int = 15,
    get=requests.get,
) -> Dict[str, Any]:
    """Fetch one official X1 network-supply metric.

    Supported metrics are ``circulating`` and ``total``. The returned supply
    is preserved as an exact integer string and is not scaled or interpreted
    as arbitrary-token mint supply.
    """
    metric = _text(metric).lower()
    network = _text(network).lower()
    base_url = _text(base_url).rstrip("/")

    if metric not in {"circulating", "total"}:
        raise ValueError("X1 supply metric must be 'circulating' or 'total'.")
    if not network:
        raise ValueError("X1 supply network is required.")
    if not base_url:
        raise ValueError("X1 supply API base URL is required.")

    url = f"{base_url}/{metric}"

    try:
        response = get(
            url,
            params={"network": network},
            headers={"accept": "text/plain"},
            timeout=timeout,
        )
        response.raise_for_status()
        supply = parse_supply_text(getattr(response, "text", None))
    except X1SupplyAPIError:
        raise
    except Exception as exc:
        raise X1SupplyAPIError(
            f"X1 supply API {metric} request failed: {exc}"
        ) from exc

    return {
        "chain": CHAIN,
        "asset": ASSET,
        "network": network,
        "metric": f"{metric}_supply",
        "supply": supply,
        "supply_verified": True,
        "representation": "provider_integer_text",
        "source": f"{SUPPLY_SOURCE} /v1/supply/{metric}",
    }


def get_circulating_supply(**kwargs) -> Dict[str, Any]:
    """Return the official X1/XNT circulating network-supply observation."""
    return fetch_supply("circulating", **kwargs)


def get_total_supply(**kwargs) -> Dict[str, Any]:
    """Return the official X1/XNT total network-supply observation."""
    return fetch_supply("total", **kwargs)


class X1SupplyProvider:
    """Explicit provider facade for official X1/XNT network-supply facts."""

    chain = CHAIN
    asset = ASSET
    source = SUPPLY_SOURCE

    def __init__(
        self,
        *,
        network: str = DEFAULT_NETWORK,
        base_url: str = SUPPLY_API_BASE_URL,
        timeout: int = 15,
        get=requests.get,
    ):
        self.network = _text(network).lower()
        self.base_url = _text(base_url).rstrip("/")
        self.timeout = timeout
        self.get = get

        if not self.network:
            raise ValueError("X1 supply network is required.")
        if not self.base_url:
            raise ValueError("X1 supply API base URL is required.")

    def get_circulating_supply(self) -> Dict[str, Any]:
        return get_circulating_supply(
            network=self.network,
            base_url=self.base_url,
            timeout=self.timeout,
            get=self.get,
        )

    def get_total_supply(self) -> Dict[str, Any]:
        return get_total_supply(
            network=self.network,
            base_url=self.base_url,
            timeout=self.timeout,
            get=self.get,
        )

    def get_supply(self) -> Dict[str, Any]:
        """Return both independently fetched official network-supply facts."""
        return {
            "chain": self.chain,
            "asset": self.asset,
            "network": self.network,
            "circulating": self.get_circulating_supply(),
            "total": self.get_total_supply(),
        }


__all__ = [
    "ASSET",
    "CHAIN",
    "DEFAULT_NETWORK",
    "SUPPLY_API_BASE_URL",
    "SUPPLY_SOURCE",
    "X1SupplyAPIError",
    "X1SupplyProvider",
    "fetch_supply",
    "get_circulating_supply",
    "get_total_supply",
    "parse_supply_text",
]
