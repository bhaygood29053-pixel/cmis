"""Read-only X1.Ninja Developer API pool-catalog contract probe.

This module verifies only the currently documented transport/authentication
contract and the minimum live JSON container shape needed for later semantic
verification. It deliberately does not promote provider price, liquidity,
volume, market-cap, holder, identity, pagination, or freshness semantics.

Provider documentation:
    GET https://api.x1.ninja/v1/pools
    Authorization: Bearer <api key>

Successful responses are expected to be JSON and to include the documented
rate-limit headers. Provider field names are preserved as raw evidence only.
"""

from __future__ import annotations

from collections.abc import Mapping
import time
from typing import Any, Optional

import requests

from config import SETTINGS


CHAIN = "x1"
SOURCE = "X1.Ninja Developer API"
BASE_URL = "https://api.x1.ninja"
POOLS_PATH = "/v1/pools"

_REQUIRED_SUCCESS_RATE_LIMIT_HEADERS = (
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
)

_PAGINATION_CANDIDATE_FIELDS = (
    "total",
    "totalCount",
    "limit",
    "offset",
    "page",
    "pageSize",
    "next",
    "nextOffset",
    "hasMore",
)


class X1NinjaCatalogError(RuntimeError):
    """Raised when the documented pool-catalog contract fails closed."""


def _nonempty_api_key(value: Optional[str]) -> str:
    resolved = value if value is not None else SETTINGS.api_key
    text = str(resolved or "").strip()
    if not text:
        raise RuntimeError("X1_NINJA_API_KEY is missing from .env")
    return text


def _header(response: Any, name: str) -> Optional[str]:
    headers = getattr(response, "headers", None)
    if not isinstance(headers, Mapping):
        return None

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
        raise X1NinjaCatalogError(
            "X1.Ninja successful pool-catalog response is missing documented "
            f"rate-limit header(s): {', '.join(missing)}"
        )

    result: dict[str, Optional[str]] = {
        "limit": _header(response, "X-RateLimit-Limit"),
        "remaining": _header(response, "X-RateLimit-Remaining"),
        "reset": _header(response, "X-RateLimit-Reset"),
    }
    window = _header(response, "X-RateLimit-Window")
    service = _header(response, "X-API-Service")
    if window is not None:
        result["window"] = window
    if service is not None:
        result["service"] = service
    return result


def _bounded_response_text(response: Any, *, limit: int = 500) -> str:
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        return ""
    if len(text) > limit:
        text = f"{text[:limit]}..."
    return f" | response: {text}"


def _http_error(response: Any, exc: Exception) -> X1NinjaCatalogError:
    status = getattr(response, "status_code", None)
    retry_after = _header(response, "Retry-After")
    parts = ["X1.Ninja pool-catalog request failed"]
    if status is not None:
        parts.append(f"HTTP {status}")
    if retry_after is not None:
        parts.append(f"Retry-After={retry_after}")
    return X1NinjaCatalogError(
        " | ".join(parts) + f": {exc}{_bounded_response_text(response)}"
    )


def _validate_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer")
    if limit < 1:
        raise ValueError("limit must be positive")
    return limit


def _validate_pool_container(body: Any) -> dict[str, Any]:
    if not isinstance(body, Mapping):
        raise X1NinjaCatalogError(
            "X1.Ninja pool-catalog response must be a JSON object."
        )

    pools = body.get("pools")
    if not isinstance(pools, list):
        raise X1NinjaCatalogError(
            "X1.Ninja pool-catalog 'pools' field must be a JSON array."
        )

    row_keys: set[str] = set()
    for index, row in enumerate(pools):
        if not isinstance(row, Mapping):
            raise X1NinjaCatalogError(
                f"X1.Ninja pool-catalog row {index} must be a JSON object."
            )
        row_keys.update(str(key) for key in row.keys())

    pagination_raw = {
        field: body.get(field)
        for field in _PAGINATION_CANDIDATE_FIELDS
        if field in body
    }

    return {
        "request_contract_verified": True,
        "response_json_verified": True,
        "pool_array_verified": True,
        "pool_row_object_shape_verified": True,
        "returned_pool_count": len(pools),
        "top_level_keys": sorted(str(key) for key in body.keys()),
        "pool_row_keys": sorted(row_keys),
        "pagination_candidate_values_raw": pagination_raw,
    }


def fetch_pool_catalog_raw(
    *,
    limit: int = 10,
    api_key: Optional[str] = None,
    session=requests,
    timeout: int = 20,
    observed_at_fn=time.time,
) -> dict[str, Any]:
    """Fetch a bounded X1.Ninja pool-catalog sample without semantic promotion."""

    requested_limit = _validate_limit(limit)
    key = _nonempty_api_key(api_key)
    url = f"{BASE_URL}{POOLS_PATH}"
    response = None

    try:
        response = session.get(
            url,
            params={"limit": requested_limit},
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )
        response.raise_for_status()
    except Exception as exc:
        raise _http_error(response, exc) from exc

    try:
        body = response.json()
    except Exception as exc:
        raise X1NinjaCatalogError(
            "X1.Ninja pool-catalog response was not valid JSON:"
            f" {exc}{_bounded_response_text(response)}"
        ) from exc

    contract = _validate_pool_container(body)
    rate_limit = _rate_limit_record(response)

    return {
        "chain": CHAIN,
        "source": SOURCE,
        "endpoint": POOLS_PATH,
        "requested_limit": requested_limit,
        "observed_at": observed_at_fn(),
        "raw_response": body,
        "rate_limit": rate_limit,
        "contract": contract,
        "identity": {
            "pool_identity_verified": False,
            "token_side_identity_verified": False,
        },
        "semantics": {
            "pagination_semantics_verified": False,
            "price_semantics_verified": False,
            "price_quote_unit_verified": False,
            "liquidity_semantics_verified": False,
            "liquidity_units_verified": False,
            "volume_semantics_verified": False,
            "volume_window_verified": False,
            "market_cap_semantics_verified": False,
            "provider_fact_time_verified": False,
            "freshness_verified": False,
            "source_independence_verified": False,
        },
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "BASE_URL",
    "CHAIN",
    "POOLS_PATH",
    "SOURCE",
    "X1NinjaCatalogError",
    "fetch_pool_catalog_raw",
]
