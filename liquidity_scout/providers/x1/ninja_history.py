"""Read-only X1.Ninja history transport beneath the X1 Provider.

This module intentionally promotes only the transport facts documented by the
public X1.Ninja Developer API: Bearer authentication, the pool-trade-history
path, JSON responses, and rate-limit headers. The public documentation does not
publish the trade-row field schema, so CMIS must not infer side, amounts, USD
value, LP-event semantics, transaction identity, or finality from this adapter.

A later opt-in live contract probe may promote individual fields only after the
observed response contract is recorded and deterministic tests are added.
"""

from __future__ import annotations

from collections.abc import Mapping
import time
from typing import Any, Optional

import requests

from config import SETTINGS


CHAIN = "x1"
X1_NINJA_SOURCE = "X1.Ninja Developer API"
X1_NINJA_API_BASE_URL = "https://api.x1.ninja"
TRADE_HISTORY_PATH = "/v1/trades/{address}"

_REQUIRED_SUCCESS_RATE_LIMIT_HEADERS = (
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
)
_OPTIONAL_RATE_LIMIT_HEADERS = (
    "X-RateLimit-Window",
    "X-API-Service",
)


class X1NinjaAPIError(RuntimeError):
    """Raised when X1.Ninja transport or the documented response contract fails."""


def _nonempty_text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty.")
    return text


def _api_key(value: Optional[str]) -> str:
    resolved = value if value is not None else SETTINGS.api_key
    text = str(resolved or "").strip()
    if not text:
        raise RuntimeError("X1_NINJA_API_KEY is missing from .env")
    return text


def _header(response: Any, name: str) -> Optional[str]:
    headers = getattr(response, "headers", None)
    if not isinstance(headers, Mapping):
        return None

    direct = headers.get(name)
    if direct is not None:
        text = str(direct).strip()
        return text or None

    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            text = str(value).strip()
            return text or None
    return None


def _rate_limit_record(response: Any) -> dict[str, Optional[str]]:
    missing = [
        name
        for name in _REQUIRED_SUCCESS_RATE_LIMIT_HEADERS
        if _header(response, name) is None
    ]
    if missing:
        raise X1NinjaAPIError(
            "X1.Ninja successful response is missing documented rate-limit "
            f"header(s): {', '.join(missing)}"
        )

    record = {
        "limit": _header(response, "X-RateLimit-Limit"),
        "remaining": _header(response, "X-RateLimit-Remaining"),
        "reset": _header(response, "X-RateLimit-Reset"),
    }
    window = _header(response, "X-RateLimit-Window")
    service = _header(response, "X-API-Service")
    if window is not None:
        record["window"] = window
    if service is not None:
        record["service"] = service
    return record


def _bounded_response_text(response: Any, *, limit: int = 500) -> str:
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        return ""
    if len(text) > limit:
        text = f"{text[:limit]}..."
    return f" | response: {text}"


def _http_error(response: Any, exc: Exception) -> X1NinjaAPIError:
    status = getattr(response, "status_code", None)
    retry_after = _header(response, "Retry-After")
    parts = ["X1.Ninja trade-history request failed"]
    if status is not None:
        parts.append(f"HTTP {status}")
    if retry_after is not None:
        parts.append(f"Retry-After={retry_after}")
    detail = _bounded_response_text(response)
    return X1NinjaAPIError(" | ".join(parts) + f": {exc}{detail}")


def _response_shape(body: Any) -> str:
    if isinstance(body, Mapping):
        return "object"
    if isinstance(body, list):
        return "array"
    if body is None:
        return "null"
    if isinstance(body, bool):
        return "boolean"
    if isinstance(body, (int, float)):
        return "number"
    if isinstance(body, str):
        return "string"
    return type(body).__name__


def fetch_pool_trades_raw(
    pool_address: str,
    api_key: Optional[str] = None,
    *,
    session=requests,
    timeout: int = 20,
    observed_at_fn=time.time,
) -> dict[str, Any]:
    """Fetch raw X1.Ninja trade history for one verified pool address.

    No trade fields are interpreted. The returned record preserves the raw JSON,
    documented rate-limit metadata, source, endpoint, and observation time while
    explicitly marking semantic promotion gates as unverified.
    """

    address = _nonempty_text("pool_address", pool_address)
    key = _api_key(api_key)
    url = f"{X1_NINJA_API_BASE_URL}{TRADE_HISTORY_PATH.format(address=address)}"
    response = None

    try:
        response = session.get(
            url,
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )
        response.raise_for_status()
    except Exception as exc:
        raise _http_error(response, exc) from exc

    try:
        body = response.json()
    except Exception as exc:
        detail = _bounded_response_text(response)
        raise X1NinjaAPIError(
            f"X1.Ninja trade-history response was not valid JSON: {exc}{detail}"
        ) from exc

    rate_limit = _rate_limit_record(response)
    observed_at = observed_at_fn()

    return {
        "chain": CHAIN,
        "source": X1_NINJA_SOURCE,
        "endpoint": TRADE_HISTORY_PATH.format(address=address),
        "pool_address": address,
        "observed_at": observed_at,
        "response_shape": _response_shape(body),
        "raw_response": body,
        "rate_limit": rate_limit,
        "semantics": {
            "trade_rows_verified": False,
            "side_classification_verified": False,
            "token_amount_units_verified": False,
            "usd_value_source_verified": False,
            "lp_event_semantics_verified": False,
            "transaction_signature_verified": False,
            "finality_verified": False,
            "pagination_or_range_verified": False,
        },
        "cmis_promotable": False,
    }


__all__ = [
    "CHAIN",
    "TRADE_HISTORY_PATH",
    "X1_NINJA_API_BASE_URL",
    "X1_NINJA_SOURCE",
    "X1NinjaAPIError",
    "fetch_pool_trades_raw",
]
