"""Read-only X1.Ninja history transport beneath the X1 Provider.

This module promotes only provider facts that have been either publicly
documented or live-observed and regression-tested. The public X1.Ninja
Developer API documents Bearer authentication, the pool-trade-history path,
JSON responses, and rate-limit headers. A read-only live probe on 2026-08-16
verified the response container/row shape below.

The live observation does *not* establish financial semantics for ``type``,
amount/price units, USD derivation, LP-event meaning, transaction finality, or
pagination/range behavior. Those gates remain closed and the record remains
``cmis_promotable=False`` until separately verified.
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
OHLCV_PATH = "/v1/ohlcv/{address}"

SUPPORTED_OHLCV_TIMEFRAMES = frozenset({
    "1m",
    "5m",
    "15m",
    "1h",
    "4h",
    "1D",
})

# Live-observed read-only OHLCV structure, 2026-08-16.
# These are provider field names only. Their financial/time semantics remain
# explicitly unverified.
OBSERVED_OHLCV_TOP_LEVEL_KEYS = frozenset({
    "baseToken",
    "candleCount",
    "currentPrice",
    "currentPriceNative",
    "currentPriceUsd",
    "lastUpdated",
    "mode",
    "ohlcv",
    "pending",
    "poolAddress",
    "quoteToken",
    "timeframe",
})

OBSERVED_OHLCV_CANDLE_KEYS = frozenset({
    "time",
    "open",
    "high",
    "low",
    "close",
    "volume",
})

_REQUIRED_SUCCESS_RATE_LIMIT_HEADERS = (
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
)

# Live-observed read-only contract, 2026-08-16.  These names are provider
# structure only; their financial/chain semantics are deliberately not inferred.
OBSERVED_TRADE_HISTORY_TOP_LEVEL_KEYS = frozenset({
    "lastUpdated",
    "total",
    "trades",
})
OBSERVED_TRADE_ROW_KEYS = frozenset({
    "amountNative",
    "amountToken",
    "amountUsd",
    "id",
    "maker",
    "poolAddress",
    "priceNative",
    "priceUsd",
    "slot",
    "timestamp",
    "txHash",
    "type",
})


class X1NinjaAPIError(RuntimeError):
    """Raised when X1.Ninja transport or a promoted response contract fails."""


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


def _http_error(
    response: Any,
    exc: Exception,
    *,
    operation: str = "trade-history",
) -> X1NinjaAPIError:
    status = getattr(response, "status_code", None)
    retry_after = _header(response, "Retry-After")
    parts = [f"X1.Ninja {operation} request failed"]
    if status is not None:
        parts.append(f"HTTP {status}")
    if retry_after is not None:
        parts.append(f"Retry-After={retry_after}")
    detail = _bounded_response_text(response)
    return X1NinjaAPIError(" | ".join(parts) + f": {exc}{detail}")


def _validate_observed_trade_history_shape(body: Any) -> dict[str, Any]:
    """Validate only the live-observed provider container/row structure.

    This function intentionally does not coerce or interpret provider values.
    Empty ``trades`` is valid structural output; a non-empty list must contain
    JSON objects with the live-observed field names.
    """

    if not isinstance(body, Mapping):
        raise X1NinjaAPIError(
            "X1.Ninja trade-history response must be a JSON object under the "
            "live-observed contract."
        )

    missing_top = sorted(OBSERVED_TRADE_HISTORY_TOP_LEVEL_KEYS - set(body.keys()))
    if missing_top:
        raise X1NinjaAPIError(
            "X1.Ninja trade-history response is missing live-observed top-level "
            f"field(s): {', '.join(missing_top)}"
        )

    trades = body.get("trades")
    if not isinstance(trades, list):
        raise X1NinjaAPIError(
            "X1.Ninja trade-history 'trades' field must be a JSON array."
        )

    observed_row_keys = set()
    for index, row in enumerate(trades):
        if not isinstance(row, Mapping):
            raise X1NinjaAPIError(
                f"X1.Ninja trade-history row {index} must be a JSON object."
            )
        row_keys = set(row.keys())
        missing_row = sorted(OBSERVED_TRADE_ROW_KEYS - row_keys)
        if missing_row:
            raise X1NinjaAPIError(
                f"X1.Ninja trade-history row {index} is missing live-observed "
                f"field(s): {', '.join(missing_row)}"
            )
        observed_row_keys.update(str(key) for key in row.keys())

    return {
        "response_contract_verified": True,
        "trade_row_shape_verified": True,
        "top_level_keys": sorted(str(key) for key in body.keys()),
        "trade_row_keys": sorted(observed_row_keys or OBSERVED_TRADE_ROW_KEYS),
        "returned_trade_count": len(trades),
        # Preserve these provider values without assigning meaning/units.
        "provider_total_raw": body.get("total"),
        "provider_last_updated_raw": body.get("lastUpdated"),
    }


def fetch_pool_trades_raw(
    pool_address: str,
    api_key: Optional[str] = None,
    *,
    session=requests,
    timeout: int = 20,
    observed_at_fn=time.time,
) -> dict[str, Any]:
    """Fetch raw X1.Ninja trade history for one verified pool address.

    The response structure is now live-observed and validated. Trade values are
    still returned raw; no side, amount, USD, LP-event, signature/finality, or
    pagination semantics are promoted by this transport.
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

    contract = _validate_observed_trade_history_shape(body)
    rate_limit = _rate_limit_record(response)
    observed_at = observed_at_fn()

    return {
        "chain": CHAIN,
        "source": X1_NINJA_SOURCE,
        "endpoint": TRADE_HISTORY_PATH.format(address=address),
        "pool_address": address,
        "observed_at": observed_at,
        "response_shape": "object",
        "raw_response": body,
        "rate_limit": rate_limit,
        "contract": contract,
        "semantics": {
            "trade_rows_verified": True,
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




def _validate_observed_ohlcv_shape(
    body: Any,
    *,
    requested_pool_address: str,
    requested_timeframe: str,
) -> dict[str, Any]:
    """Validate the live-observed OHLCV structure and request scope."""

    if not isinstance(body, Mapping):
        raise X1NinjaAPIError(
            "X1.Ninja OHLCV response must be a JSON object under the "
            "live-observed contract."
        )

    missing_top = sorted(
        OBSERVED_OHLCV_TOP_LEVEL_KEYS - set(body.keys())
    )
    if missing_top:
        raise X1NinjaAPIError(
            "X1.Ninja OHLCV response is missing live-observed top-level "
            f"field(s): {', '.join(missing_top)}"
        )

    provider_pool_address = body.get("poolAddress")
    if provider_pool_address != requested_pool_address:
        raise X1NinjaAPIError(
            "X1.Ninja OHLCV poolAddress does not match the requested pool: "
            f"requested={requested_pool_address!r}, "
            f"provider={provider_pool_address!r}"
        )

    provider_timeframe = body.get("timeframe")
    if provider_timeframe != requested_timeframe:
        raise X1NinjaAPIError(
            "X1.Ninja OHLCV timeframe does not match the requested timeframe: "
            f"requested={requested_timeframe!r}, "
            f"provider={provider_timeframe!r}"
        )

    candles = body.get("ohlcv")
    if not isinstance(candles, list):
        raise X1NinjaAPIError(
            "X1.Ninja OHLCV 'ohlcv' field must be a JSON array."
        )

    observed_candle_keys = set()

    for index, row in enumerate(candles):
        if not isinstance(row, Mapping):
            raise X1NinjaAPIError(
                f"X1.Ninja OHLCV candle row {index} must be a JSON object."
            )

        row_keys = set(row.keys())
        missing_row = sorted(
            OBSERVED_OHLCV_CANDLE_KEYS - row_keys
        )
        if missing_row:
            raise X1NinjaAPIError(
                f"X1.Ninja OHLCV candle row {index} is missing "
                "live-observed field(s): "
                f"{', '.join(missing_row)}"
            )

        observed_candle_keys.update(
            str(key) for key in row.keys()
        )

    return {
        "request_contract_verified": True,
        "response_json_verified": True,
        "response_contract_verified": True,
        "candle_schema_verified": True,
        "candle_row_shape_verified": True,
        "request_scope_verified": True,
        "top_level_keys": sorted(
            str(key) for key in body.keys()
        ),
        "candle_row_keys": sorted(
            observed_candle_keys
            or OBSERVED_OHLCV_CANDLE_KEYS
        ),
        "returned_candle_count": len(candles),
        "provider_candle_count_raw": body.get("candleCount"),
        "provider_last_updated_raw": body.get("lastUpdated"),
        "provider_timeframe_raw": body.get("timeframe"),
        "provider_mode_raw": body.get("mode"),
        "provider_pool_address_raw": body.get("poolAddress"),
        "provider_base_token_raw": body.get("baseToken"),
        "provider_quote_token_raw": body.get("quoteToken"),
    }


def fetch_pool_ohlcv_raw(
    pool_address: str,
    api_key: Optional[str] = None,
    *,
    timeframe: str = "1h",
    limit: Optional[int] = None,
    session=requests,
    timeout: int = 20,
    observed_at_fn=time.time,
) -> dict[str, Any]:
    """Fetch raw X1.Ninja OHLCV JSON without promoting candle semantics.

    The documented request contract and live-observed response structure are
    verified here. Timestamp units, pair direction, quote units, interval
    semantics, range coverage, gap behavior, and stale/interpolated behavior
    remain explicitly unverified.
    """

    address = _nonempty_text("pool_address", pool_address)
    key = _api_key(api_key)

    tf = _nonempty_text("timeframe", timeframe)
    if tf not in SUPPORTED_OHLCV_TIMEFRAMES:
        supported = ", ".join(sorted(SUPPORTED_OHLCV_TIMEFRAMES))
        raise ValueError(
            f"Unsupported X1.Ninja OHLCV timeframe {tf!r}; "
            f"documented values are: {supported}."
        )

    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("OHLCV limit must be an integer when provided.")
        if limit > 300:
            raise ValueError(
                "OHLCV limit exceeds the documented maximum of 300."
            )

    url = (
        f"{X1_NINJA_API_BASE_URL}"
        f"{OHLCV_PATH.format(address=address)}"
    )
    params: dict[str, Any] = {"tf": tf}
    if limit is not None:
        params["limit"] = limit

    response = None
    try:
        response = session.get(
            url,
            headers={"Authorization": f"Bearer {key}"},
            params=params,
            timeout=timeout,
        )
        response.raise_for_status()
    except Exception as exc:
        raise _http_error(
            response,
            exc,
            operation="OHLCV",
        ) from exc

    try:
        body = response.json()
    except Exception as exc:
        detail = _bounded_response_text(response)
        raise X1NinjaAPIError(
            f"X1.Ninja OHLCV response was not valid JSON: {exc}{detail}"
        ) from exc

    contract = _validate_observed_ohlcv_shape(
        body,
        requested_pool_address=address,
        requested_timeframe=tf,
    )
    rate_limit = _rate_limit_record(response)
    observed_at = observed_at_fn()

    return {
        "chain": CHAIN,
        "source": X1_NINJA_SOURCE,
        "endpoint": OHLCV_PATH.format(address=address),
        "pool_address": address,
        "timeframe": tf,
        "requested_limit": limit,
        "observed_at": observed_at,
        "response_shape": "object",
        "raw_response": body,
        "rate_limit": rate_limit,
        "contract": contract,
        "semantics": {
            "timestamp_unit_verified": False,
            "pair_direction_verified": False,
            "quote_unit_verified": False,
            "interval_semantics_verified": False,
            "range_coverage_verified": False,
            "gap_behavior_verified": False,
            "stale_or_interpolated_behavior_verified": False,
        },
        "cmis_promotable": False,
    }


__all__ = [
    "CHAIN",
    "OBSERVED_TRADE_HISTORY_TOP_LEVEL_KEYS",
    "OBSERVED_TRADE_ROW_KEYS",
    "OBSERVED_OHLCV_CANDLE_KEYS",
    "OBSERVED_OHLCV_TOP_LEVEL_KEYS",
    "OHLCV_PATH",
    "SUPPORTED_OHLCV_TIMEFRAMES",
    "TRADE_HISTORY_PATH",
    "X1_NINJA_API_BASE_URL",
    "X1_NINJA_SOURCE",
    "X1NinjaAPIError",
    "fetch_pool_ohlcv_raw",
    "fetch_pool_trades_raw",
]
