"""Read-only XDEX public API transport for the X1 provider layer.

This module owns transport and minimal response-shape validation only. CMIS
remains responsible for deterministic interpretation, historical comparison,
risk, and pre-trade policy.

Request shapes are promoted here only when supported by accepted API/live
evidence. Field semantics remain subject to their separate CMIS evidence gates.
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
XDEX_POOL_NETWORK_MAINNET = "mainnet"

POOL_LIST_URL = f"{XDEX_API_BASE_URL}/api/xendex/pool/list"
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


def _nonnegative_decimal_text(name: str, value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative finite number.")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise ValueError(f"{name} must be a non-negative finite number.") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{name} must be a non-negative finite number.")
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


def _parse_price_history_data(body: Any) -> list[Any]:
    """Return the raw history list from either observed XDEX envelope shape."""

    if not isinstance(body, Mapping):
        raise XDEXAPIError("price history response must be a JSON object.")

    if body.get("success") is True:
        data = body.get("data")
        if not isinstance(data, list):
            raise XDEXAPIError("price history response data must be list.")
        return data

    if "bars" in body:
        bars = body.get("bars")
        if not isinstance(bars, list):
            raise XDEXAPIError("price history response bars must be list.")
        return bars

    raise XDEXAPIError(f"price history failed: {_error_message(body)}")


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


def fetch_pool_list(
    *,
    network: str = XDEX_POOL_NETWORK_MAINNET,
    session=requests,
    timeout: int = 15,
) -> list[dict[str, Any]]:
    """Fetch XDEX's public pool list without requiring X1.Ninja credentials."""

    network_name = _nonempty_text("network", network)
    body = _get_json(
        POOL_LIST_URL,
        params={"network": network_name},
        session=session,
        timeout=timeout,
    )
    data = _parse_success_data(
        body,
        expected_type=list,
        operation="pool list",
    )

    pools: list[dict[str, Any]] = []
    for index, pool in enumerate(data):
        if not isinstance(pool, Mapping):
            raise XDEXAPIError(f"pool list item {index} must be a JSON object.")
        pools.append(dict(pool))
    return pools


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
    """Fetch raw pair price-history observations for an explicit time window."""

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
    data = _parse_price_history_data(body)

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
    slippage: Any = None,
    amm_config_address: str | None = None,
    network: str = XDEX_NETWORK_X1_MAINNET,
    session=requests,
    timeout: int = 15,
) -> dict[str, Any]:
    """Fetch a read-only XDEX swap quote.

    ``slippage`` and ``amm_config_address`` are optional read-only quote scoping
    parameters accepted from the separately verified XDEX contract. Supplying
    them still performs quote retrieval only: this function never calls a swap
    preparation endpoint and never constructs, signs, or broadcasts a
    transaction.
    """

    token_in_text = _nonempty_text("token_in", token_in)
    token_out_text = _nonempty_text("token_out", token_out)
    if token_in_text == token_out_text:
        raise ValueError("token_in and token_out must be different.")
    amount_text = _positive_decimal_text("token_in_amount", token_in_amount)
    if not isinstance(is_exact_amount_in, bool):
        raise ValueError("is_exact_amount_in must be a boolean.")
    network_name = _nonempty_text("network", network)

    params: dict[str, Any] = {
        "network": network_name,
        "token_in": token_in_text,
        "token_out": token_out_text,
        "token_in_amount": amount_text,
        "is_exact_amount_in": str(is_exact_amount_in).lower(),
    }
    if slippage is not None:
        params["slippage"] = _nonnegative_decimal_text("slippage", slippage)
    if amm_config_address is not None:
        params["amm_config_address"] = _nonempty_text(
            "amm_config_address", amm_config_address
        )

    body = _get_json(
        SWAP_QUOTE_URL,
        params=params,
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
        pool_network: str = XDEX_POOL_NETWORK_MAINNET,
        session=requests,
        timeout: int = 15,
    ):
        self.network = _nonempty_text("network", network)
        self.pool_network = _nonempty_text("pool_network", pool_network)
        self.session = session
        self.timeout = _positive_int("timeout", timeout)

    def pool_list(self) -> list[dict[str, Any]]:
        return fetch_pool_list(
            network=self.pool_network,
            session=self.session,
            timeout=self.timeout,
        )

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
        slippage: Any = None,
        amm_config_address: str | None = None,
    ) -> dict[str, Any]:
        return fetch_swap_quote(
            token_in,
            token_out,
            token_in_amount,
            is_exact_amount_in=is_exact_amount_in,
            slippage=slippage,
            amm_config_address=amm_config_address,
            network=self.network,
            session=self.session,
            timeout=self.timeout,
        )


__all__ = [
    "CHAIN",
    "POOL_LIST_URL",
    "PRICE_HISTORY_URL",
    "SWAP_QUOTE_URL",
    "TOKEN_PRICE_URL",
    "XDEX_API_BASE_URL",
    "XDEX_NETWORK_X1_MAINNET",
    "XDEX_POOL_NETWORK_MAINNET",
    "XDEX_SOURCE",
    "XDEXAPIError",
    "XDEXReadOnlyProvider",
    "fetch_pool_list",
    "fetch_price_history",
    "fetch_swap_quote",
    "fetch_token_price",
]
