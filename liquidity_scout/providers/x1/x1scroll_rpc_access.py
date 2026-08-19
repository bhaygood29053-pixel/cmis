"""Bounded read-only access probe for X1Scroll's API-key RPC contract.

X1Scroll's current provider-owned contract publishes an authenticated RPC URL
shaped as ``https://rpc.x1scroll.io/v1/YOUR_API_KEY``. This module constructs
only that fixed host/path shape and probes only the read-only methods accepted
by CMIS's secondary-RPC classifier.

The probe creates a fresh credential-isolated Requests session for each call,
disables environment-derived authentication/proxies, disables redirects, and
requires the JSON-RPC response id to exactly match the request id before any
successful access classification.

A successful response proves only authenticated access to one method at one
observation time. It does not prove source independence, archival completeness,
retention depth, finality semantics, failover quality, historical method
coverage, or CMIS promotion. The API key is never returned or retained.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
import re
from typing import Any, Callable

import requests

from liquidity_scout.providers.x1.secondary_rpc_contract import (
    SecondaryRpcContractObservation,
    classify_secondary_rpc_response,
)


VERSION = "1.2"
SOURCE = "X1Scroll authenticated RPC"
X1SCROLL_RPC_BASE = "https://rpc.x1scroll.io/v1"
X1SCROLL_RPC_REDACTED_ENDPOINT = f"{X1SCROLL_RPC_BASE}/<redacted>"
SUPPORTED_ACCESS_METHODS = frozenset({"getHealth", "getSlot"})
_API_KEY_RE = re.compile(r"^[A-Za-z0-9._~-]+$")
_REQUEST_ID = 1
_AUTH_HEADER_NAMES = frozenset({"authorization", "proxy-authorization"})


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


def _clear_auth_headers(headers: Any) -> None:
    if not isinstance(headers, MutableMapping):
        return
    for key in list(headers.keys()):
        if str(key).casefold() in _AUTH_HEADER_NAMES:
            headers.pop(key, None)


def _prepare_transport(session_factory: Callable[[], Any]) -> Any:
    """Create and sanitize a per-probe transport before any credential is used."""
    try:
        session = session_factory()
    except Exception:
        raise X1ScrollRpcAccessError(
            "X1Scroll read-only RPC access probe failed"
        ) from None

    if session is None or not callable(getattr(session, "post", None)):
        close = getattr(session, "close", None)
        if callable(close):
            close()
        raise X1ScrollRpcAccessError(
            "X1Scroll read-only RPC access probe failed"
        ) from None

    # Requests consults .netrc and proxy environment settings only when
    # trust_env=True. A fresh session with trust_env=False prevents those
    # ambient credentials/settings from entering this evidence request.
    if hasattr(session, "trust_env"):
        session.trust_env = False
    if hasattr(session, "auth"):
        session.auth = None

    _clear_auth_headers(getattr(session, "headers", None))

    cookies = getattr(session, "cookies", None)
    clear_cookies = getattr(cookies, "clear", None)
    if callable(clear_cookies):
        clear_cookies()

    proxies = getattr(session, "proxies", None)
    clear_proxies = getattr(proxies, "clear", None)
    if callable(clear_proxies):
        clear_proxies()

    return session


def _response_id_matches(body: Mapping[str, Any]) -> bool:
    response_id = body.get("id")
    return (
        not isinstance(response_id, bool)
        and isinstance(response_id, int)
        and response_id == _REQUEST_ID
    )


def probe_x1scroll_rpc_access(
    *,
    api_key: str,
    method: str = "getHealth",
    timeout: int = 10,
    session_factory: Callable[[], Any] = requests.Session,
) -> dict[str, Any]:
    """Probe X1Scroll's exact published authenticated RPC transport.

    ``session_factory`` is a deterministic test seam; callers cannot supply an
    already-authenticated Session instance. The returned session is sanitized
    before the credential-bearing endpoint is constructed or contacted.
    """
    api_key = _api_key(api_key)
    method = _method(method)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise ValueError("timeout must be a positive integer")
    if not callable(session_factory):
        raise TypeError("session_factory must be callable")

    session = _prepare_transport(session_factory)
    response = None
    endpoint = f"{X1SCROLL_RPC_BASE}/{api_key}"
    payload = {
        "jsonrpc": "2.0",
        "id": _REQUEST_ID,
        "method": method,
        "params": [],
    }

    try:
        try:
            response = session.post(
                endpoint,
                json=payload,
                timeout=timeout,
                allow_redirects=False,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "CMIS-X1Scroll-readonly-access/1.2",
                },
            )
        except Exception:
            raise X1ScrollRpcAccessError(
                "X1Scroll read-only RPC access probe failed"
            ) from None

        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, bool) or not isinstance(status_code, int):
            raise X1ScrollRpcAccessError(
                "X1Scroll RPC HTTP status is missing or invalid"
            )

        result: dict[str, Any] = {
            "contract_version": VERSION,
            "source": SOURCE,
            "chain": "x1",
            "endpoint": X1SCROLL_RPC_REDACTED_ENDPOINT,
            "authentication": "api_key_path_segment",
            "method": method,
            "request_id": _REQUEST_ID,
            "http_status": status_code,
            "status": None,
            "access": None,
            "redirects_followed": False,
            "transport_environment_auth_disabled": True,
            "response_id_verified": False,
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

        if not _response_id_matches(body):
            result["status"] = "partial"
            result["access"] = "jsonrpc_id_mismatch"
            return result
        result["response_id_verified"] = True

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
        if response is not None:
            close_response = getattr(response, "close", None)
            if callable(close_response):
                close_response()
        close_session = getattr(session, "close", None)
        if callable(close_session):
            close_session()


__all__ = [
    "SOURCE",
    "SUPPORTED_ACCESS_METHODS",
    "VERSION",
    "X1SCROLL_RPC_BASE",
    "X1SCROLL_RPC_REDACTED_ENDPOINT",
    "X1ScrollRpcAccessError",
    "probe_x1scroll_rpc_access",
]
