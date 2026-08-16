"""Read-only XDEX public API transport for the X1 provider layer.

This module owns transport and minimal response-shape validation only. CMIS
remains responsible for deterministic interpretation, historical comparison,
risk, and pre-trade policy.

Request shapes are promoted here only when supported by user-supplied API
documentation or live XDEX error/response evidence. Field units and semantics
remain gated until the opt-in live contract probe verifies them.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

import requests


CHAIN = "x1"
XDEX_SOURCE = "XDEX public API"
XDEX_API_BASE_URL = "https://api.xdex.xyz"
XDEX_NETWORK_X1_MAINNET = "X1 Mainnet"

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
    if text:
        return text

    detail = repr(dict(body)).strip()
    if len(detail) > 500:
        detail = f"{detail[:500]}..."
    if detail:
        return f"XDEX reported an unsuccessful response: {detail}"
    return "XDEX reported an unsuccessful response."


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


def _bounded_response_text(response: Any, *, limit: int = 500) -> str:
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        return ""
    if len(text) > limit:
        text = f"{text[:limit]}..."
    return f" | response: {text}"


def _get_json(
    url: str,
    *,
    params: Mapping[str, Any],
    session=requests,
    timeout: int = 15,
):
    response = None
    try:
        response = session.get(url, params=dict(params), timeout=timeout)
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        if isinstance(exc, XDEXAPIError):
            raise
        detail = _bounded_response_text(response)
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
        params={"network": network_name, "token_address": token},
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
    from_token: str,
    to_token: str,
    *,
    time_from: Any,
    time_to: Any,
    network: str = XDEX_NETWORK_X1_MAINNET,
    session=requests,
    timeout: int = 15,
) -> list[dict[str, Any]]:
    """Fetch raw pair price-history points for an explicit time window.

    XDEX live error evidence confirms the required parameter names. The time
    unit is intentionally not interpreted here; the opt-in live probe currently
    tests Unix seconds and must verify the returned contract before CMIS use.
    """

    from_token_text = _nonempty_text("from_token", from_token)
    to_token_text = _nonempty_text("to_token", to_token)
    if from_token_text == to_token_text:
        raise ValueError("from_token and to_token must be different.")

    start = _positive_int("time_from", time_from)
    end = _positive_int("time_to", time_to)
    if end <= start:
        raise ValueError("time_to must be greater than time_from.")

    network_name = _nonempty_text("network", network)
    body = _get_json(
        PRICE_HISTORY_URL,
        params={
            "network": network_name,
            "from_token": from_token_text,
            "to_token": to_token_text,
            "time_from": start,
            "time_to": end,
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
        from_token: str,
        to_token: str,
        *,
        time_from: Any,
        time_to: Any,
    ) -> list[dict[str, Any]]:
        return fetch_price_history(
            from_token,
            to_token,
            time_from=time_from,
            time_to=time_to,
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
