"""Read-only XDEX public API transport for the X1 provider layer.

This module intentionally owns transport and minimal response-shape validation
only. CMIS remains responsible for deterministic interpretation, historical
comparison, risk, and pre-trade policy.

The request shapes in this module are candidate contracts discovered from the
user-supplied XDEX endpoint catalog plus public X1 client implementations.
They must pass the opt-in live contract probe before CMIS may promote their
fields into verified historical/risk/pre-trade evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

import requests


CHAIN = "x1"
XDEX_SOURCE = "XDEX public API"
XDEX_API_BASE_URL = "https://api.xdex.xyz"
# XDEX's supplied API catalog documents mainnet/testnet/devnet as endpoint
# network values. Public clients using display names such as "X1 Mainnet" are
# not treated as transport-authoritative after live XDEX returned HTTP 400 for
# that form across price, history, and quote endpoints.
XDEX_NETWORK_X1_MAINNET = "mainnet"

TOKEN_PRICE_URL = f"{XDEX_API_BASE_URL}/api/token-price/price"
PRICE_HISTORY_URL = f"{XDEX_API_BASE_URL}/api/xendex/chart/history"
SWAP_QUOTE_URL = f"{XDEX_API_BASE_URL}/api/xendex/swap/quote"


class XDEXAPIError(RuntimeError):
    """Raised when XDEX transport or response shape cannot be trusted."""


def _nonempty_text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty.")
    return text


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return parsed


def _positive_decimal_text(name: str, value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive finite number.")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise ValueError(f"{name} must be a positive finite number.") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{name} must be a positive finite number.")
    return format(parsed, "f")


def _error_message(body: Mapping[str, Any]) -> str:
    raw = body.get("error")
    if isinstance(raw, Mapping):
        raw = raw.get("message") or raw.get("code")
    text = str(raw or body.get("message") or "").strip()
    return text or "XDEX reported an unsuccessful response."


def _http_error_detail(exc: Exception) -> str:
    """Expose bounded provider error text when requests attaches a response."""

    response = getattr(exc, "response", None)
    if response is None:
        return ""
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        return ""
    compact = " ".join(text.split())
    return f" | response: {compact[:1000]}"


def _parse_success_data(
    body: Any,
    *,
    expected_type: type,
    operation: str,
):
    if not isinstance(body, Mapping):
        raise XDEXAPIError(f"{operation} response must be a JSON object.")
    if body.get("success") is not True:
        raise XDEXAPIError(f"{operation} failed: {_error_message(body)}")

    data = body.get("data")
    if not isinstance(data, expected_type):
        raise XDEXAPIError(
            f"{operation} response data must be {expected_type.__name__}."
        )
    return data


def _get_json(
    url: str,
    *,
    params: Mapping[str, Any],
    session=requests,
    timeout: int = 15,
):
    try:
        response = session.get(url, params=dict(params), timeout=timeout)
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        if isinstance(exc, XDEXAPIError):
            raise
        detail = _http_error_detail(exc)
        raise XDEXAPIError(f"XDEX request failed for {url}: {exc}{detail}") from exc
    return body


def fetch_token_price(
    token_address: str,
    *,
    network: str = XDEX_NETWORK_X1_MAINNET,
    session=requests,
    timeout: int = 15,
) -> dict[str, Any]:
    """Fetch one token's raw XDEX price payload without numeric coercion."""

    token = _nonempty_text("token_address", token_address)
    network_name = _nonempty_text("network", network)
    body = _get_json(
        TOKEN_PRICE_URL,
        params={"network": network_name, "address": token},
        session=session,
        timeout=timeout,
    )
    data = _parse_success_data(
        body,
        expected_type=Mapping,
        operation="token price",
    )
    return dict(data)


def fetch_price_history(
    token_address: str,
    *,
    days: int = 7,
    network: str = XDEX_NETWORK_X1_MAINNET,
    session=requests,
    timeout: int = 15,
) -> list[dict[str, Any]]:
    """Fetch raw XDEX chart history points.

    No point field is promoted as a verified timestamp/price contract here.
    Each row must at least be a mapping so later verification can inspect it
    without silently accepting malformed scalar/list content.
    """

    token = _nonempty_text("token_address", token_address)
    network_name = _nonempty_text("network", network)
    day_count = _positive_int("days", days)
    body = _get_json(
        PRICE_HISTORY_URL,
        params={
            "network": network_name,
            "token": token,
            "days": day_count,
        },
        session=session,
        timeout=timeout,
    )
    data = _parse_success_data(
        body,
        expected_type=list,
        operation="price history",
    )

    points: list[dict[str, Any]] = []
    for index, point in enumerate(data):
        if not isinstance(point, Mapping):
            raise XDEXAPIError(
                f"price history point {index} must be a JSON object."
            )
        points.append(dict(point))
    return points


def fetch_swap_quote(
    token_in: str,
    token_out: str,
    token_in_amount: Any,
    *,
    is_exact_amount_in: bool = True,
    network: str = XDEX_NETWORK_X1_MAINNET,
    session=requests,
    timeout: int = 15,
) -> dict[str, Any]:
    """Fetch a read-only XDEX swap quote.

    This does not prepare, sign, or broadcast a transaction. Quote field
    semantics remain unpromoted until the live contract probe verifies units.
    """

    token_in_text = _nonempty_text("token_in", token_in)
    token_out_text = _nonempty_text("token_out", token_out)
    if token_in_text == token_out_text:
        raise ValueError("token_in and token_out must be different.")
    amount_text = _positive_decimal_text("token_in_amount", token_in_amount)
    if not isinstance(is_exact_amount_in, bool):
        raise ValueError("is_exact_amount_in must be a boolean.")
    network_name = _nonempty_text("network", network)

    body = _get_json(
        SWAP_QUOTE_URL,
        params={
            "network": network_name,
            "token_in": token_in_text,
            "token_out": token_out_text,
            "token_in_amount": amount_text,
            "is_exact_amount_in": str(is_exact_amount_in).lower(),
        },
        session=session,
        timeout=timeout,
    )
    data = _parse_success_data(
        body,
        expected_type=Mapping,
        operation="swap quote",
    )
    return dict(data)


class XDEXReadOnlyProvider:
    """Read-only direct XDEX transport beneath CMIS for X1."""

    chain = CHAIN
    source = XDEX_SOURCE

    def __init__(
        self,
        *,
        network: str = XDEX_NETWORK_X1_MAINNET,
        session=requests,
        timeout: int = 15,
    ):
        self.network = _nonempty_text("network", network)
        self.session = session
        self.timeout = _positive_int("timeout", timeout)

    def token_price(self, token_address: str) -> dict[str, Any]:
        return fetch_token_price(
            token_address,
            network=self.network,
            session=self.session,
            timeout=self.timeout,
        )

    def price_history(
        self,
        token_address: str,
        *,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        return fetch_price_history(
            token_address,
            days=days,
            network=self.network,
            session=self.session,
            timeout=self.timeout,
        )

    def swap_quote(
        self,
        token_in: str,
        token_out: str,
        token_in_amount: Any,
        *,
        is_exact_amount_in: bool = True,
    ) -> dict[str, Any]:
        return fetch_swap_quote(
            token_in,
            token_out,
            token_in_amount,
            is_exact_amount_in=is_exact_amount_in,
            network=self.network,
            session=self.session,
            timeout=self.timeout,
        )


__all__ = [
    "CHAIN",
    "PRICE_HISTORY_URL",
    "SWAP_QUOTE_URL",
    "TOKEN_PRICE_URL",
    "XDEX_API_BASE_URL",
    "XDEX_NETWORK_X1_MAINNET",
    "XDEX_SOURCE",
    "XDEXAPIError",
    "XDEXReadOnlyProvider",
    "fetch_price_history",
    "fetch_swap_quote",
    "fetch_token_price",
]
