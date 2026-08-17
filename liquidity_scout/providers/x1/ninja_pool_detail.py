"""Read-only X1.Ninja single-pool detail contract probe.

The public Developer API documents ``GET /v1/pools/{address}`` as a single
pool detail endpoint that includes reserves, token metadata, and holders.  It
does not document the JSON field schema or reserve units.  This module
therefore verifies only the documented transport contract and preserves the
raw response for later live semantic verification.

No field whose name contains ``reserve`` is treated as a financial reserve by
this module.  Such fields are exposed only as lexical candidates so a live
probe can identify what must be independently proved against X1 RPC evidence.
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
POOL_DETAIL_PATH = "/v1/pools/{address}"

_REQUIRED_SUCCESS_RATE_LIMIT_HEADERS = (
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
)


class X1NinjaPoolDetailError(RuntimeError):
    """Raised when the documented pool-detail transport contract fails."""


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
        raise X1NinjaPoolDetailError(
            "X1.Ninja successful pool-detail response is missing documented "
            f"rate-limit header(s): {', '.join(missing)}"
        )

    record: dict[str, Optional[str]] = {
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


def _lexical_reserve_field_paths(value: Any, prefix: str = "") -> list[str]:
    """Return paths whose *field names* contain ``reserve``.

    This is deliberately lexical discovery, not semantic promotion.  Nested
    JSON objects and arrays are traversed only so the live probe can surface
    provider field names that require later proof.
    """

    found: set[str] = set()

    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if "reserve" in key_text.casefold():
                found.add(path)
            found.update(_lexical_reserve_field_paths(child, path))
    elif isinstance(value, list):
        for child in value:
            found.update(_lexical_reserve_field_paths(child, f"{prefix}[]"))

    return sorted(found)


def _raw_identity_candidates(body: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve common identifier-looking fields without assigning semantics."""

    names = ("address", "poolAddress", "pool_address", "id")
    return {name: body.get(name) for name in names if name in body}


def fetch_pool_detail_raw(
    address: str,
    *,
    api_key: Optional[str] = None,
    session=requests,
    timeout: int = 20,
) -> dict[str, Any]:
    """Fetch one X1.Ninja pool detail record without reserve promotion."""

    pool_address = _nonempty_text("address", address)
    key = _api_key(api_key)
    url = f"{X1_NINJA_API_BASE_URL}{POOL_DETAIL_PATH.format(address=pool_address)}"

    try:
        response = session.get(
            url,
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )
        response.raise_for_status()
    except Exception as exc:
        raise X1NinjaPoolDetailError(
            f"X1.Ninja pool-detail request failed for {pool_address}: {exc}"
        ) from exc

    try:
        body = response.json()
    except Exception as exc:
        raise X1NinjaPoolDetailError(
            "X1.Ninja pool-detail response was not valid JSON."
        ) from exc

    if not isinstance(body, Mapping):
        raise X1NinjaPoolDetailError(
            "X1.Ninja pool-detail response must be a JSON object."
        )

    rate_limit = _rate_limit_record(response)
    lexical_reserve_fields = _lexical_reserve_field_paths(body)

    return {
        "chain": CHAIN,
        "source": X1_NINJA_SOURCE,
        "endpoint": POOL_DETAIL_PATH,
        "pool_address_requested": pool_address,
        "observed_at": time.time(),
        "raw_response": body,
        "rate_limit": rate_limit,
        "contract": {
            "request_contract_verified": True,
            "response_json_verified": True,
            "rate_limit_headers_verified": True,
            "top_level_keys": sorted(str(key) for key in body.keys()),
            "lexical_reserve_field_paths": lexical_reserve_fields,
        },
        "identity": {
            "raw_identifier_candidates": _raw_identity_candidates(body),
            "pool_identity_verified": False,
        },
        "semantics": {
            "reserve_field_roles_verified": False,
            "reserve_units_verified": False,
            "token_decimals_verified": False,
            "observation_time_semantics_verified": False,
        },
        "cmis_promotable": False,
    }


__all__ = [
    "CHAIN",
    "POOL_DETAIL_PATH",
    "X1_NINJA_API_BASE_URL",
    "X1_NINJA_SOURCE",
    "X1NinjaPoolDetailError",
    "fetch_pool_detail_raw",
]
