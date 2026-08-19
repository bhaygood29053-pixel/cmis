"""Bounded read-only access probe for X1Scroll's published API-key RPC contract.

X1Scroll's current provider-owned public contract publishes an authenticated RPC
URL shaped as ``https://rpc.x1scroll.io/v1/YOUR_API_KEY``. This module constructs
only that fixed host/path shape and probes only read-only JSON-RPC methods already
accepted by CMIS's secondary-RPC classifier.

A successful response proves authenticated access to one method at one observation
time. It never proves source independence, archival completeness, retention depth,
finality semantics, failover quality, historical method coverage, or CMIS
promotion. The API key is never returned or retained in the structured result.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

import requests

from liquidity_scout.providers.x1.secondary_rpc_contract import (
    SecondaryRpcContractObservation,
    classify_secondary_rpc_response,
)

VERSION = "1.1"
SOURCE = "X1Scroll authenticated RPC"
X1SCROLL_RPC_BASE = "https://rpc.x1scroll.io/v1"
X1SCROLL_RPC_REDACTED_ENDPOINT = f"{X1SCROLL_RPC_BASE}/<redacted>"
SUPPORTED_ACCESS_METHODS = frozenset({"getHealth", "getSlot"})
_API_KEY_RE = re.compile(r"^[A-Za-z0-9._~-]+$")


class X1ScrollRpcAccessError(RuntimeError):
    """Sanitized bounded-probe transport failure."""


def _api_key(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("api_key must be a non-empty string")
    if not _API_KEY_RE.fullmatch(value):
        raise ValueError("api_key contains unsupported characters")
    return value


def _method(value: Any) -> str:
    if not isinstance(value, str) or value not in SUPPORTED_ACCESS_METHODS:
        raise ValueError("method must be getHealth or getSlot")
    return value


def _http_classification(status_code: int) -> tuple[str, str]:
    if status_code in {401, 403}:
        return "unavailable", "access_denied"
    if status_code == 404:
        return "unavailable", "endpoint_not_found"
    if status_code == 429:
        return "unavailable", "rate_limited"
    if 500 <= status_code <= 599:
        return "unavailable", "provider_error"
    if status_code != 200:
        return "partial", "unexpected_http_status"
    return "partial", "http_200_contract_unverified"


def probe_x1scroll_rpc_access(
    *,
    api_key: str,
    method: str = "getHealth",
    session=requests,
    timeout: int = 10,
) -> dict[str, Any]:
    """Probe X1Scroll's exact published authenticated RPC transport.

    The API key is accepted only as a conservative URL-path token and is used only
    to construct the provider-owned ``/v1/{api_key}`` URL. Returned evidence always
    exposes the redacted endpoint template instead of the credential-bearing URL.

    The response body is parsed only for HTTP 200 and immediately classified by
    the accepted fail-closed secondary-RPC contract. Non-200 response bodies are
    not retained. Provider exception details are deliberately suppressed.
    """
    api_key = _api_key(api_key)
    method = _method(method)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise ValueError("timeout must be a positive integer")

    endpoint = f"{X1SCROLL_RPC_BASE}/{api_key}"
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": []}
    try:
        response = session.post(
            endpoint,
            json=payload,
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "CMIS-X1Scroll-readonly-access/1.1",
            },
        )
    except Exception:
        raise X1ScrollRpcAccessError(
            "X1Scroll read-only RPC access probe failed"
        ) from None

    try:
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, bool) or not isinstance(status_code, int):
            raise X1ScrollRpcAccessError("X1Scroll RPC HTTP status is missing or invalid")

        result: dict[str, Any] = {
            "contract_version": VERSION,
            "source": SOURCE,
            "chain": "x1",
            "endpoint": X1SCROLL_RPC_REDACTED_ENDPOINT,
            "authentication": "api_key_path_segment",
            "method": method,
            "http_status": status_code,
            "status": None,
            "access": None,
            "jsonrpc_envelope_verified": False,
            "result_shape_verified": False,
            "observed_slot": None,
            "rpc_error_code": None,
            "credentials_supplied": True,
            "credentials_retained": False,
            "source_independence_verified": False,
            "archival_completeness_verified": False,
            "retention_verified": False,
            "finality_semantics_verified": False,
            "historical_method_coverage_verified": False,
            "cmis_promotable": False,
        }

        if status_code != 200:
            status, access = _http_classification(status_code)
            result["status"] = status
            result["access"] = access
            return result

        try:
            body = response.json()
        except Exception:
            result["status"] = "partial"
            result["access"] = "invalid_json_response"
            return result
        if not isinstance(body, Mapping):
            result["status"] = "partial"
            result["access"] = "invalid_jsonrpc_response"
            return result

        observation: SecondaryRpcContractObservation = classify_secondary_rpc_response(
            source=SOURCE,
            method=method,
            payload=body,
        )
        result["jsonrpc_envelope_verified"] = observation.jsonrpc_envelope_verified
        result["result_shape_verified"] = observation.result_shape_verified
        result["observed_slot"] = observation.observed_slot
        result["rpc_error_code"] = observation.error_code

        if observation.transport_ok and observation.result_shape_verified:
            result["status"] = "ok"
            result["access"] = "available_authenticated"
        elif observation.jsonrpc_envelope_verified and observation.error_code is not None:
            result["status"] = "unavailable"
            result["access"] = "jsonrpc_error"
        else:
            result["status"] = "partial"
            result["access"] = "jsonrpc_contract_unverified"
        return result
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


__all__ = [
    "SOURCE",
    "SUPPORTED_ACCESS_METHODS",
    "VERSION",
    "X1SCROLL_RPC_BASE",
    "X1SCROLL_RPC_REDACTED_ENDPOINT",
    "X1ScrollRpcAccessError",
    "probe_x1scroll_rpc_access",
]
