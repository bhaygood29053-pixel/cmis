"""Deterministic X1.Ninja structured discovery.

This module recognizes the existing read-only X1.Ninja Developer API routes
already represented by CMIS provider/evidence modules. It validates URL/query
syntax only and never performs an authenticated request.

Bearer credentials remain provider transport configuration. Credential-like URL
query material fails closed and is never preserved as candidate evidence.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, unquote, urlparse

from liquidity_scout.providers.x1.ninja_history import SUPPORTED_OHLCV_TIMEFRAMES

from .base import DISCOVERED
from .x1_ninja import X1_NINJA_WEB_SOURCE


STRUCTURED_CONTRACT = "x1_ninja_structured_discovery/v1"

POOL_CATALOG_PATH = "/v1/pools"
POOL_DETAIL_PREFIX = "/v1/pools/"
TRADE_HISTORY_PREFIX = "/v1/trades/"
OHLCV_PREFIX = "/v1/ohlcv/"
TRADE_STREAM_PATH = "/v1/stream/trades"

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {char: index for index, char in enumerate(_BASE58_ALPHABET)}

_CREDENTIAL_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "bearer",
        "credential",
        "key",
        "password",
        "secret",
        "session",
        "token",
    }
)


def _base58_decoded_length(value: str) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None

    number = 0
    leading_zeros = 0
    for index, char in enumerate(text):
        digit = _BASE58_INDEX.get(char)
        if digit is None:
            return None
        if index == leading_zeros and char == "1":
            leading_zeros += 1
        number = number * 58 + digit

    payload_length = (number.bit_length() + 7) // 8 if number else 0
    return leading_zeros + payload_length


def _valid_pool_address(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or _base58_decoded_length(text) != 32:
        return None
    return text


def _positive_integer(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text or not text.isdigit():
        return None
    parsed = int(text)
    return parsed if parsed > 0 else None


def _nonnegative_integer(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def _query_map(query: str) -> tuple[dict[str, str], str | None]:
    pairs = parse_qsl(query, keep_blank_values=True)
    result: dict[str, str] = {}
    for key, value in pairs:
        normalized_key = str(key).strip()
        if not normalized_key:
            return {}, "empty_query_parameter_name"
        if normalized_key in result:
            return {}, "duplicate_query_parameter"
        if normalized_key.casefold() in _CREDENTIAL_QUERY_KEYS:
            return {}, "credential_like_query_parameter_rejected"
        result[normalized_key] = str(value)
    return result, None


def _truth_state(*, route_verified: bool) -> dict[str, Any]:
    return {
        "discovery_state": DISCOVERED,
        "x1_ninja_route_verified": route_verified,
        "pool_identity_verified": False,
        "provider_response_verified": False,
        "price_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "history_semantics_verified": False,
        "freshness_verified": False,
        "web_claim_verified": False,
        "cmis_verified": False,
        "source_independence_verified": False,
    }


def _unsupported(
    *,
    url: str,
    reason: str,
    endpoint_type: str | None = None,
    raw_query: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "contract": STRUCTURED_CONTRACT,
        "supported": False,
        "reason": reason,
        "url": url,
        "transport_method": "GET",
        "endpoint_type": endpoint_type,
        "parameters": None,
        "raw_query": dict(raw_query or {}),
        "verification_handoff": [],
        "truth_state": _truth_state(route_verified=False),
        "authentication_required_by_provider_fetch": False,
        "authentication_material_retained": False,
        "read_only": True,
        "event_body_consumption_authorized": False,
        "request_replay_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def _handoff(endpoint_type: str) -> list[dict[str, Any]]:
    if endpoint_type == "pool_catalog":
        return [
            {
                "target": "ninja_pool_catalog.fetch_pool_catalog_raw",
                "purpose": "verify documented authenticated transport and bounded raw pool container",
                "required": True,
            },
            {
                "target": "market.fetch_all_pools",
                "purpose": "existing X1.Ninja/XDEX catalog transport and pagination behavior",
                "required": False,
            },
            {
                "target": "existing X1.Ninja pool/liquidity/freshness semantic gates",
                "purpose": "verify field identity, units, fact time, and freshness before promotion",
                "required": True,
            },
        ]

    if endpoint_type == "pool_detail":
        return [
            {
                "target": "ninja_pool_detail.fetch_pool_detail_raw",
                "purpose": "fetch one raw pool-detail object under existing transport contract",
                "required": True,
            },
            {
                "target": "existing pooled-reserve/vault/X1 RPC corroboration",
                "purpose": "verify reserve roles, units, vault mapping, and pool identity",
                "required": True,
            },
        ]

    if endpoint_type == "trade_history":
        return [
            {
                "target": "ninja_history.fetch_pool_trades_raw",
                "purpose": "fetch live-observed trade-history container/row shape",
                "required": True,
            },
            {
                "target": "existing trade-history membership/execution/X1 RPC evidence",
                "purpose": "verify pool membership, signatures, execution fields, and scoped semantics",
                "required": True,
            },
        ]

    if endpoint_type == "ohlcv":
        return [
            {
                "target": "ninja_history.fetch_pool_ohlcv_raw",
                "purpose": "fetch live-observed OHLCV structure under exact pool/timeframe request scope",
                "required": True,
            },
            {
                "target": "existing X1.Ninja/XDEX history semantic and verified-history gates",
                "purpose": "verify timestamp, pair direction, quote units, coverage, and freshness before promotion",
                "required": True,
            },
        ]

    if endpoint_type == "trade_stream_access":
        return [
            {
                "target": "ninja_trade_stream.probe_trade_stream_access",
                "purpose": "classify HTTP/SSE handshake only without consuming event data",
                "required": True,
            }
        ]

    if endpoint_type == "website":
        return [
            {
                "target": "CMIS Web Discovery X1.Ninja page collector",
                "purpose": "retain bounded public webpage candidate evidence only",
                "required": False,
            }
        ]

    raise ValueError(f"unsupported endpoint_type {endpoint_type!r}")


def _supported(
    *,
    url: str,
    endpoint_type: str,
    parameters: dict[str, Any],
    raw_query: dict[str, str],
    authentication_required: bool,
) -> dict[str, Any]:
    return {
        "contract": STRUCTURED_CONTRACT,
        "supported": True,
        "reason": None,
        "url": url,
        "transport_method": "GET",
        "endpoint_type": endpoint_type,
        "parameters": parameters,
        "raw_query": raw_query,
        "verification_handoff": _handoff(endpoint_type),
        "truth_state": _truth_state(route_verified=True),
        "authentication_required_by_provider_fetch": authentication_required,
        "authentication_material_retained": False,
        "read_only": True,
        "event_body_consumption_authorized": False,
        "stream_event_semantics_verified": False,
        "request_replay_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def _path_identifier(path: str, prefix: str) -> str | None:
    if not path.startswith(prefix):
        return None
    tail = unquote(path[len(prefix):]).strip()
    if not tail or "/" in tail:
        return None
    return tail


def parse_x1_ninja_url(url: str) -> dict[str, Any]:
    """Classify one allowlisted X1.Ninja URL without fetching it."""

    normalized = X1_NINJA_WEB_SOURCE.validate_url(url)
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").casefold()
    path = parsed.path or "/"

    query, query_error = _query_map(parsed.query)
    if query_error is not None:
        return _unsupported(
            url=normalized,
            reason=query_error,
            raw_query=query,
        )

    if host == "x1.ninja":
        if query:
            return _unsupported(
                url=normalized,
                reason="website_query_parameters_not_supported",
                endpoint_type="website",
                raw_query=query,
            )
        return _supported(
            url=normalized,
            endpoint_type="website",
            parameters={
                "path": unquote(path),
                "website_semantics_verified": False,
            },
            raw_query={},
            authentication_required=False,
        )

    if host != "api.x1.ninja":
        return _unsupported(
            url=normalized,
            reason="unsupported_x1_ninja_host",
            raw_query=query,
        )

    if path == POOL_CATALOG_PATH:
        allowed = {"limit", "offset"}
        if set(query) - allowed:
            return _unsupported(
                url=normalized,
                reason="unknown_query_parameter",
                endpoint_type="pool_catalog",
                raw_query=query,
            )

        parameters: dict[str, Any] = {
            "pagination_semantics_verified": False,
        }
        if "limit" in query:
            limit = _positive_integer(query["limit"])
            if limit is None:
                return _unsupported(
                    url=normalized,
                    reason="limit_must_be_positive_integer",
                    endpoint_type="pool_catalog",
                    raw_query=query,
                )
            parameters["limit"] = limit

        if "offset" in query:
            offset = _nonnegative_integer(query["offset"])
            if offset is None:
                return _unsupported(
                    url=normalized,
                    reason="offset_must_be_nonnegative_integer",
                    endpoint_type="pool_catalog",
                    raw_query=query,
                )
            parameters["offset"] = offset

        return _supported(
            url=normalized,
            endpoint_type="pool_catalog",
            parameters=parameters,
            raw_query=query,
            authentication_required=True,
        )

    pool_detail_id = _path_identifier(path, POOL_DETAIL_PREFIX)
    if pool_detail_id is not None:
        if query:
            return _unsupported(
                url=normalized,
                reason="pool_detail_query_parameters_not_supported",
                endpoint_type="pool_detail",
                raw_query=query,
            )
        address = _valid_pool_address(pool_detail_id)
        if address is None:
            return _unsupported(
                url=normalized,
                reason="pool_address_must_decode_to_32_bytes",
                endpoint_type="pool_detail",
            )
        return _supported(
            url=normalized,
            endpoint_type="pool_detail",
            parameters={
                "pool_address": address,
                "pool_identity_verified": False,
            },
            raw_query={},
            authentication_required=True,
        )

    trade_history_id = _path_identifier(path, TRADE_HISTORY_PREFIX)
    if trade_history_id is not None:
        if query:
            return _unsupported(
                url=normalized,
                reason="trade_history_query_parameters_not_supported",
                endpoint_type="trade_history",
                raw_query=query,
            )
        address = _valid_pool_address(trade_history_id)
        if address is None:
            return _unsupported(
                url=normalized,
                reason="pool_address_must_decode_to_32_bytes",
                endpoint_type="trade_history",
            )
        return _supported(
            url=normalized,
            endpoint_type="trade_history",
            parameters={
                "pool_address": address,
                "pagination_or_range_verified": False,
            },
            raw_query={},
            authentication_required=True,
        )

    ohlcv_id = _path_identifier(path, OHLCV_PREFIX)
    if ohlcv_id is not None:
        allowed = {"tf", "limit"}
        if set(query) - allowed:
            return _unsupported(
                url=normalized,
                reason="unknown_query_parameter",
                endpoint_type="ohlcv",
                raw_query=query,
            )
        if "tf" not in query or not str(query["tf"]).strip():
            return _unsupported(
                url=normalized,
                reason="missing_required_timeframe",
                endpoint_type="ohlcv",
                raw_query=query,
            )

        address = _valid_pool_address(ohlcv_id)
        if address is None:
            return _unsupported(
                url=normalized,
                reason="pool_address_must_decode_to_32_bytes",
                endpoint_type="ohlcv",
                raw_query=query,
            )

        timeframe = str(query["tf"]).strip()
        if timeframe not in SUPPORTED_OHLCV_TIMEFRAMES:
            return _unsupported(
                url=normalized,
                reason="unsupported_ohlcv_timeframe",
                endpoint_type="ohlcv",
                raw_query=query,
            )

        parameters = {
            "pool_address": address,
            "timeframe": timeframe,
        }

        if "limit" in query:
            limit = _positive_integer(query["limit"])
            if limit is None or limit > 300:
                return _unsupported(
                    url=normalized,
                    reason="ohlcv_limit_must_be_between_1_and_300",
                    endpoint_type="ohlcv",
                    raw_query=query,
                )
            parameters["limit"] = limit

        return _supported(
            url=normalized,
            endpoint_type="ohlcv",
            parameters=parameters,
            raw_query=query,
            authentication_required=True,
        )

    if path == TRADE_STREAM_PATH:
        if query:
            return _unsupported(
                url=normalized,
                reason="trade_stream_query_parameters_not_supported",
                endpoint_type="trade_stream_access",
                raw_query=query,
            )
        return _supported(
            url=normalized,
            endpoint_type="trade_stream_access",
            parameters={
                "handshake_only": True,
                "event_body_consumption_authorized": False,
                "event_schema_verified": False,
                "event_ordering_verified": False,
                "event_finality_verified": False,
                "reconnect_semantics_verified": False,
                "backfill_semantics_verified": False,
                "stream_freshness_verified": False,
            },
            raw_query={},
            authentication_required=True,
        )

    return _unsupported(
        url=normalized,
        reason="unsupported_x1_ninja_api_path",
        raw_query=query,
    )


__all__ = [
    "OHLCV_PREFIX",
    "POOL_CATALOG_PATH",
    "POOL_DETAIL_PREFIX",
    "STRUCTURED_CONTRACT",
    "TRADE_HISTORY_PREFIX",
    "TRADE_STREAM_PATH",
    "parse_x1_ninja_url",
]
