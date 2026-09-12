"""Read-only XDEX multi-hop quote discovery transport.

This module intentionally preserves the provider response verbatim until live
evidence pins exact response-field semantics. It never calls the matching
prepare endpoint and never constructs, signs, broadcasts, or executes a swap.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

import requests

from liquidity_scout.providers.x1.xdex import (
    XDEX_API_BASE_URL,
    XDEX_NETWORK_X1_MAINNET,
)

CHAIN = "x1"
SOURCE = "XDEX multi-hop public quote API"
MULTI_HOP_QUOTE_URL = f"{XDEX_API_BASE_URL}/api/xdex/swap/multi-hop/quote"
OBSERVATION_SCHEMA = "xdex_multi_hop_quote_observation.v1"
DEFAULT_VENUE = "all"
DEFAULT_MAX_HOPS = 6


class XDEXMultiHopError(RuntimeError):
    """Raised when a multi-hop quote observation cannot be collected safely."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a normalized non-empty string")
    text = value.strip()
    if not text or text != value:
        raise ValueError(f"{field} must be a normalized non-empty string")
    return text


def _amount_text(value: Any) -> str:
    if value is None or isinstance(value, bool):
        raise ValueError("token_in_amount must be a positive finite decimal")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise ValueError("token_in_amount must be a positive finite decimal") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("token_in_amount must be a positive finite decimal")
    return format(amount, "f")


def _max_hops(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("max_hops must be an integer from 1 through 6")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_hops must be an integer from 1 through 6") from exc
    if str(parsed) != str(value).strip() and not isinstance(value, int):
        raise ValueError("max_hops must be an integer from 1 through 6")
    if parsed < 1 or parsed > 6:
        raise ValueError("max_hops must be an integer from 1 through 6")
    return parsed


def _bounded_response_text(response: Any, *, limit: int = 500) -> str:
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        return ""
    if len(text) > limit:
        text = f"{text[:limit]}..."
    return text


def collect_multi_hop_quote_observation(
    token_in: str,
    token_out: str,
    token_in_amount: Any,
    *,
    venue: str = DEFAULT_VENUE,
    max_hops: int = DEFAULT_MAX_HOPS,
    network: str = XDEX_NETWORK_X1_MAINNET,
    session=requests,
    timeout: int = 15,
) -> dict[str, Any]:
    """Collect one exact read-only provider response without interpreting it."""

    token_in_text = _text(token_in, "token_in")
    token_out_text = _text(token_out, "token_out")
    if token_in_text == token_out_text:
        raise ValueError("token_in and token_out must differ")
    amount_text = _amount_text(token_in_amount)
    venue_text = _text(venue, "venue")
    network_text = _text(network, "network")
    hop_limit = _max_hops(max_hops)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise ValueError("timeout must be a positive integer")

    params = {
        "token_in": token_in_text,
        "token_out": token_out_text,
        "token_in_amount": amount_text,
        "venue": venue_text,
        "max_hops": str(hop_limit),
        "network": network_text,
    }
    response = None
    try:
        response = session.get(MULTI_HOP_QUOTE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        detail = _bounded_response_text(response)
        suffix = f" | response: {detail}" if detail else ""
        raise XDEXMultiHopError(f"XDEX multi-hop quote request failed: {exc}{suffix}") from exc

    if not isinstance(body, Mapping):
        raise XDEXMultiHopError("XDEX multi-hop quote response must be a JSON object")

    return {
        "schema": OBSERVATION_SCHEMA,
        "chain": CHAIN,
        "source": SOURCE,
        "endpoint": MULTI_HOP_QUOTE_URL,
        "request": params,
        "raw_response": dict(body),
        "provider_semantics_promoted": False,
        "prepare_called": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CHAIN",
    "DEFAULT_MAX_HOPS",
    "DEFAULT_VENUE",
    "MULTI_HOP_QUOTE_URL",
    "OBSERVATION_SCHEMA",
    "SOURCE",
    "XDEXMultiHopError",
    "collect_multi_hop_quote_observation",
]
