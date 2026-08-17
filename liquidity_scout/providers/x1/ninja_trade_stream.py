"""Probe X1.Ninja trade-stream HTTP/SSE access without consuming events.

The public provider research identifies ``/v1/stream/trades`` as a documented
Server-Sent Events endpoint whose current tier/access remains unverified. This
module performs only the initial HTTP handshake and classifies access. It never
reads an SSE event body, never infers event schema/order/finality/backfill, and
never turns stream availability into CMIS market data.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

import requests

from config import SETTINGS


CHAIN = "x1"
SOURCE = "X1.Ninja Developer API"
API_BASE_URL = "https://api.x1.ninja"
STREAM_PATH = "/v1/stream/trades"


class X1NinjaTradeStreamError(RuntimeError):
    """Raised when the bounded stream-access request itself cannot be completed."""


def _api_key(value: Optional[str]) -> str:
    resolved = value if value is not None else SETTINGS.api_key
    text = str(resolved or "").strip()
    if not text:
        raise RuntimeError("X1_NINJA_API_KEY is missing from .env")
    return text


def _header(headers: Any, name: str) -> str | None:
    if not isinstance(headers, Mapping):
        return None
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            text = str(value).strip()
            return text or None
    return None


def _classification(status_code: int, content_type: str | None) -> tuple[str, str]:
    if status_code == 200:
        if content_type and "text/event-stream" in content_type.casefold():
            return "ok", "available_sse_handshake"
        return "partial", "unexpected_success_content_type"
    if status_code in {401, 403}:
        return "unavailable", "access_denied"
    if status_code == 404:
        return "unavailable", "endpoint_not_found"
    if status_code == 429:
        return "unavailable", "rate_limited"
    if 500 <= status_code <= 599:
        return "unavailable", "provider_error"
    if 400 <= status_code <= 499:
        return "unavailable", "http_client_error"
    return "partial", "unexpected_http_status"


def probe_trade_stream_access(
    *,
    api_key: Optional[str] = None,
    session=requests,
    connect_timeout: int = 5,
    read_timeout: int = 5,
) -> dict[str, Any]:
    """Classify the SSE HTTP handshake without consuming event data."""
    key = _api_key(api_key)
    url = f"{API_BASE_URL}{STREAM_PATH}"

    try:
        response = session.get(
            url,
            headers={
                "Authorization": f"Bearer {key}",
                "Accept": "text/event-stream",
            },
            stream=True,
            timeout=(connect_timeout, read_timeout),
        )
    except Exception as exc:
        raise X1NinjaTradeStreamError(
            "X1.Ninja trade-stream access probe request failed."
        ) from exc

    try:
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, bool) or not isinstance(status_code, int):
            raise X1NinjaTradeStreamError(
                "X1.Ninja trade-stream response status is missing or invalid."
            )

        headers = getattr(response, "headers", None)
        content_type = _header(headers, "Content-Type")
        status, access = _classification(status_code, content_type)
        sse_handshake_verified = (
            status_code == 200
            and content_type is not None
            and "text/event-stream" in content_type.casefold()
        )

        rate_limit = {
            "limit": _header(headers, "X-RateLimit-Limit"),
            "remaining": _header(headers, "X-RateLimit-Remaining"),
            "reset": _header(headers, "X-RateLimit-Reset"),
            "window": _header(headers, "X-RateLimit-Window"),
            "service": _header(headers, "X-API-Service"),
        }
        rate_limit = {key: value for key, value in rate_limit.items() if value is not None}

        warnings: list[str] = []
        if access == "access_denied":
            warnings.append("current_credentials_do_not_establish_stream_access")
        elif access == "rate_limited":
            warnings.append("stream_access_probe_rate_limited")
        elif access == "unexpected_success_content_type":
            warnings.append("http_200_without_text_event_stream_content_type")
        elif access not in {"available_sse_handshake"}:
            warnings.append("stream_access_not_verified")

        return {
            "service": "x1_ninja_trade_stream_access",
            "version": "1.0",
            "chain": CHAIN,
            "source": SOURCE,
            "endpoint": STREAM_PATH,
            "status": status,
            "access": access,
            "http_status": status_code,
            "content_type": content_type,
            "rate_limit": rate_limit,
            "sse_handshake_verified": sse_handshake_verified,
            "event_body_consumed": False,
            "event_schema_verified": False,
            "event_ordering_verified": False,
            "event_finality_verified": False,
            "reconnect_semantics_verified": False,
            "backfill_semantics_verified": False,
            "dropped_event_detection_verified": False,
            "stream_freshness_verified": False,
            "cmis_promotable": False,
            "warnings": warnings,
            "errors": [],
        }
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


__all__ = [
    "API_BASE_URL",
    "CHAIN",
    "SOURCE",
    "STREAM_PATH",
    "X1NinjaTradeStreamError",
    "probe_trade_stream_access",
]
