"""Current X1 network-snapshot provider boundary for CMIS.

The user supplied a representative current-cluster payload but not the exact
snapshot route. To avoid manufacturing an endpoint, transport requires an
explicit URL while deterministic payload parsing is available immediately.
"""

from typing import Any, Dict

import requests


CHAIN = "x1"
NETWORK_SOURCE = "api.x1.xyz current cluster snapshot"


class X1NetworkAPIError(RuntimeError):
    """Raised when a current X1 network snapshot cannot be verified."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def parse_network_snapshot(payload: Any) -> Dict[str, Any]:
    """Validate a current X1 cluster snapshot without reinterpreting units."""
    if not isinstance(payload, dict):
        raise X1NetworkAPIError("X1 network snapshot must be a JSON object.")

    network = _text(payload.get("network")).lower()
    if not network:
        raise X1NetworkAPIError("X1 network snapshot is missing network.")

    # The provider reports some very large quantities as decimal strings and
    # some counters/rates as JSON numbers. Preserve those representations
    # exactly; CMIS may normalize only after units are independently verified.
    result = dict(payload)
    result["network"] = network
    return result


def fetch_network_snapshot(
    *,
    url: str,
    network: str = "mainnet",
    timeout: int = 15,
    get=requests.get,
) -> Dict[str, Any]:
    """Fetch a current X1 cluster snapshot from an explicitly supplied route."""
    url = _text(url)
    network = _text(network).lower()
    if not url:
        raise ValueError("X1 current network-snapshot URL is required.")
    if not network:
        raise ValueError("X1 network is required.")

    try:
        response = get(
            url,
            params={"network": network},
            headers={"accept": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        parsed = parse_network_snapshot(response.json())
    except X1NetworkAPIError:
        raise
    except Exception as exc:
        raise X1NetworkAPIError(
            f"X1 current network-snapshot request failed: {exc}"
        ) from exc

    if parsed["network"] != network:
        raise X1NetworkAPIError(
            "X1 network snapshot response does not match requested network."
        )

    return {
        "chain": CHAIN,
        "network": network,
        "data": parsed,
        "source": NETWORK_SOURCE,
        "observed_at": parsed.get("createdAt"),
        "units_verified": False,
    }


class X1NetworkProvider:
    """Explicit facade for current X1 network snapshots.

    ``url`` is intentionally required until the exact official current-cluster
    route is supplied and verified.
    """

    chain = CHAIN
    source = NETWORK_SOURCE

    def __init__(
        self,
        *,
        url: str,
        network: str = "mainnet",
        timeout: int = 15,
        get=requests.get,
    ):
        self.url = _text(url)
        self.network = _text(network).lower()
        self.timeout = timeout
        self.get = get
        if not self.url:
            raise ValueError("X1 current network-snapshot URL is required.")
        if not self.network:
            raise ValueError("X1 network is required.")

    def get_snapshot(self) -> Dict[str, Any]:
        return fetch_network_snapshot(
            url=self.url,
            network=self.network,
            timeout=self.timeout,
            get=self.get,
        )


__all__ = [
    "CHAIN",
    "NETWORK_SOURCE",
    "X1NetworkAPIError",
    "X1NetworkProvider",
    "fetch_network_snapshot",
    "parse_network_snapshot",
]
