"""Bounded read-only X1Scroll archival RPC provider for CMIS.

X1Scroll publicly documents credential-backed HTTP JSON-RPC access and an
example getTransaction request for a known X1 transaction signature. This
module intentionally promotes only that exact provider-owned access surface.

It does not claim address-history discovery, archive completeness, source
independence, or lifetime coverage. Those require separate bounded live
verification before CMIS may rely on them.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from urllib.parse import quote

import requests


CHAIN = "x1"
X1SCROLL_PROVIDER_ID = "x1scroll"
X1SCROLL_SOURCE = "X1Scroll archival RPC"
DEFAULT_X1SCROLL_BASE_URL = "https://rpc.x1scroll.io/v1"
DOCUMENTED_METHODS = frozenset({"getTransaction"})


class X1ScrollArchiveError(RuntimeError):
    """Raised when the bounded X1Scroll archival RPC contract cannot be used."""


def _text(value):
    return str(value or "").strip()


def build_x1scroll_rpc_url(api_key, *, base_url=DEFAULT_X1SCROLL_BASE_URL):
    """Build the credential-in-path RPC URL without exposing the key elsewhere."""
    api_key = _text(api_key)
    base_url = _text(base_url).rstrip("/")
    if not api_key:
        raise ValueError("X1Scroll API key is required.")
    if not base_url:
        raise ValueError("X1Scroll base URL is required.")
    return f"{base_url}/{quote(api_key, safe='')}"


def x1scroll_rpc_request(
    method,
    params,
    *,
    rpc_url,
    retries=4,
    timeout=25,
    post=requests.post,
    sleep=time.sleep,
    allow_undocumented=False,
):
    """Perform one bounded X1Scroll JSON-RPC request.

    Provider methods not explicitly documented/qualified by CMIS are rejected
    by default. allow_undocumented exists only for explicit bounded probes and
    must not be treated as capability promotion.
    """
    method = _text(method)
    rpc_url = _text(rpc_url)

    if not method:
        raise ValueError("X1Scroll RPC method is required.")
    if not rpc_url:
        raise ValueError("X1Scroll RPC URL is required.")
    if retries < 1:
        raise ValueError("X1Scroll RPC retries must be at least 1.")
    if method not in DOCUMENTED_METHODS and not allow_undocumented:
        raise ValueError(
            f"X1Scroll RPC method {method!r} is not in the accepted documented method set."
        )

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }
    last_error = None

    for attempt in range(retries):
        try:
            response = post(
                rpc_url,
                json=payload,
                timeout=timeout,
            )
            status_code = getattr(response, "status_code", None)
            if status_code == 429 or (
                isinstance(status_code, int) and status_code >= 500
            ):
                raise X1ScrollArchiveError(
                    f"X1Scroll archival RPC HTTP {status_code}"
                )

            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise X1ScrollArchiveError(
                    "X1Scroll archival RPC returned a non-object response."
                )
            if data.get("error"):
                raise X1ScrollArchiveError(
                    f"X1Scroll archival RPC error: {data['error']}"
                )
            return data.get("result")
        except Exception as exc:
            last_error = exc
            if attempt == retries - 1:
                break
            sleep(0.75 * (2 ** attempt))

    # Never echo the underlying exception text here. HTTP client exceptions
    # commonly include the request URL, and the X1Scroll API key is embedded in
    # that URL path.
    failure_type = type(last_error).__name__ if last_error is not None else "UnknownError"
    raise X1ScrollArchiveError(
        f"X1Scroll archival RPC {method} failed after {retries} attempts "
        f"({failure_type})."
    ) from last_error


def parse_transaction_result(result, *, signature):
    """Normalize one known-signature transaction lookup with explicit provenance."""
    signature = _text(signature)
    if not signature:
        raise ValueError("Transaction signature is required.")
    if result is not None and not isinstance(result, dict):
        raise X1ScrollArchiveError(
            "X1Scroll archival RPC getTransaction returned a malformed result."
        )

    return {
        "provider": X1SCROLL_PROVIDER_ID,
        "source": f"{X1SCROLL_SOURCE} getTransaction",
        "chain": CHAIN,
        "signature": signature,
        "transaction_available": result is not None,
        "transaction": result,
        "read_only": True,
        "known_signature_lookup": True,
        "address_history_discovery_verified": False,
        "archive_completeness_verified": False,
        "source_independence_verified": False,
    }


class X1ScrollArchiveProvider:
    """Read-only X1Scroll facade for accepted archival transaction lookup."""

    chain = CHAIN
    provider_id = X1SCROLL_PROVIDER_ID
    source = X1SCROLL_SOURCE
    documented_methods = DOCUMENTED_METHODS

    def __init__(
        self,
        *,
        api_key=None,
        rpc_url=None,
        base_url=DEFAULT_X1SCROLL_BASE_URL,
        retries=4,
        timeout=25,
        post=requests.post,
        sleep=time.sleep,
    ):
        if rpc_url is None:
            self.rpc_url = build_x1scroll_rpc_url(api_key, base_url=base_url)
        else:
            self.rpc_url = _text(rpc_url)
            if not self.rpc_url:
                raise ValueError("X1Scroll RPC URL is required.")

        if retries < 1:
            raise ValueError("X1Scroll RPC retries must be at least 1.")

        self.retries = retries
        self.timeout = timeout
        self.post = post
        self.sleep = sleep

    def request(self, method, params, *, allow_undocumented=False):
        return x1scroll_rpc_request(
            method,
            params,
            rpc_url=self.rpc_url,
            retries=self.retries,
            timeout=self.timeout,
            post=self.post,
            sleep=self.sleep,
            allow_undocumented=allow_undocumented,
        )

    def get_transaction(self, signature, *, config=None):
        """Fetch one transaction by known signature.

        With no config this sends the exact provider-documented parameter shape.
        A config mapping may be supplied only when a caller has separately
        qualified those standard JSON-RPC transaction options.
        """
        signature = _text(signature)
        if not signature:
            raise ValueError("Transaction signature is required.")

        params = [signature]
        if config is not None:
            if not isinstance(config, Mapping):
                raise ValueError("getTransaction config must be a mapping.")
            params.append(dict(config))

        result = self.request("getTransaction", params)
        return parse_transaction_result(result, signature=signature)


__all__ = [
    "CHAIN",
    "DEFAULT_X1SCROLL_BASE_URL",
    "DOCUMENTED_METHODS",
    "X1SCROLL_PROVIDER_ID",
    "X1SCROLL_SOURCE",
    "X1ScrollArchiveError",
    "X1ScrollArchiveProvider",
    "build_x1scroll_rpc_url",
    "parse_transaction_result",
    "x1scroll_rpc_request",
]
