"""Read-only XDEX price-history range discovery for X1.

This module sweeps explicit historical request windows backwards to a supplied
verified lower bound. It records what the provider returned, but it does not
infer archive completeness merely because the sweep is long, gap-free, or
contains an empty window.

Promotion of provider-range completeness requires a separately accepted
provider contract proving that the history route exhaustively honors requested
ranges without silent truncation/retention behavior, plus a verified search
floor that predates the supported market lifetime being investigated.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from .xdex import fetch_price_history


SCHEMA = "xdex_price_history_range_discovery.v1"
CHAIN = "x1"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _row_timestamp(row: Any) -> int | None:
    if not isinstance(row, Mapping):
        return None
    value = row.get("t")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def discover_xdex_price_history_range(
    base_mint: Any,
    quote_mint: Any,
    *,
    search_floor: Any,
    search_end: Any,
    window_seconds: Any,
    max_windows: Any = 128,
    fetcher: Callable[..., Any] = fetch_price_history,
    provider_range_semantics_verified: bool = False,
    search_floor_precedes_supported_market_lifetime_verified: bool = False,
) -> dict[str, Any]:
    """Sweep contiguous XDEX history windows backwards and fail closed.

    provider_range_semantics_verified is intentionally external to this
    discovery function. It may only be true after a separate accepted
    contract proves that the XDEX route exhaustively honors each requested
    interval and does not silently truncate or hide retained data.

    search_floor_precedes_supported_market_lifetime_verified means the supplied
    lower bound is proven to be at or before any supported market observation
    for the exact pair under investigation. It is a lower-bound fact only;
    it is not itself the market-lifetime start.
    """

    base = _text(base_mint)
    quote = _text(quote_mint)
    if not base or not quote or base == quote:
        raise ValueError("distinct base_mint and quote_mint are required")

    floor = _positive_int("search_floor", search_floor)
    end = _positive_int("search_end", search_end)
    width = _positive_int("window_seconds", window_seconds)
    limit = _positive_int("max_windows", max_windows)

    if end <= floor:
        raise ValueError("search_end must be greater than search_floor")

    windows: list[dict[str, Any]] = []
    by_timestamp: dict[int, dict[str, Any]] = {}
    cursor = end
    failure_reason = None
    conflicting_duplicate_timestamp_count = 0

    for _index in range(limit):
        if cursor <= floor:
            break

        start = max(floor, cursor - width)
        requested = {"time_from": start, "time_to": cursor}

        try:
            raw = fetcher(base, quote, time_from=start, time_to=cursor)
        except Exception as exc:
            failure_reason = (
                "provider_request_failed:"
                f"{type(exc).__name__}:{exc}"
            )
            windows.append({
                **requested,
                "status": "error",
                "returned_count": None,
                "first_returned_at": None,
                "last_returned_at": None,
                "rows_within_requested_range": False,
            })
            break

        if not isinstance(raw, list):
            failure_reason = "provider_history_response_not_list"
            windows.append({
                **requested,
                "status": "invalid",
                "returned_count": None,
                "first_returned_at": None,
                "last_returned_at": None,
                "rows_within_requested_range": False,
            })
            break

        timestamps: list[int] = []
        rows_within_range = True
        for row in raw:
            ts = _row_timestamp(row)
            if ts is None or ts < start or ts > cursor:
                rows_within_range = False
                continue

            timestamps.append(ts)
            existing = by_timestamp.get(ts)
            current = dict(row)
            if existing is not None and existing != current:
                conflicting_duplicate_timestamp_count += 1
                rows_within_range = False
            else:
                by_timestamp.setdefault(ts, current)

        if not rows_within_range:
            failure_reason = "provider_rows_outside_or_conflicting_requested_range"

        windows.append({
            **requested,
            "status": "ok" if rows_within_range else "invalid",
            "returned_count": len(raw),
            "first_returned_at": min(timestamps) if timestamps else None,
            "last_returned_at": max(timestamps) if timestamps else None,
            "rows_within_requested_range": rows_within_range,
        })

        if failure_reason is not None:
            break

        cursor = start

    search_floor_reached = cursor <= floor and failure_reason is None
    all_window_scopes_verified = bool(windows) and all(
        item.get("rows_within_requested_range") is True
        for item in windows
    )
    range_sweep_complete = (
        search_floor_reached
        and all_window_scopes_verified
        and failure_reason is None
    )

    timestamps = sorted(by_timestamp)
    earliest = timestamps[0] if timestamps else None
    latest = timestamps[-1] if timestamps else None
    empty_window_count = sum(
        1 for item in windows if item.get("returned_count") == 0
    )

    provider_range_complete_verified = (
        range_sweep_complete
        and provider_range_semantics_verified is True
        and search_floor_precedes_supported_market_lifetime_verified is True
    )

    limitations = []
    if provider_range_semantics_verified is not True:
        limitations.append(
            "xdex_requested_range_exhaustiveness_semantics_not_verified"
        )
    if search_floor_precedes_supported_market_lifetime_verified is not True:
        limitations.append("search_floor_pre_market_lower_bound_not_verified")
    if not search_floor_reached:
        limitations.append("search_floor_not_reached")
    if failure_reason is not None:
        limitations.append("range_sweep_failed")
    if not timestamps:
        limitations.append("no_provider_price_observations_discovered")

    return {
        "schema": SCHEMA,
        "chain": CHAIN,
        "status": (
            "verified"
            if provider_range_complete_verified
            else ("partial" if windows else "unavailable")
        ),
        "base_mint": base,
        "quote_mint": quote,
        "search_floor": floor,
        "search_end": end,
        "window_seconds": width,
        "max_windows": limit,
        "requested_window_count": len(windows),
        "search_floor_reached": search_floor_reached,
        "range_sweep_complete": range_sweep_complete,
        "all_window_scopes_verified": all_window_scopes_verified,
        "provider_range_semantics_verified": (
            provider_range_semantics_verified is True
        ),
        "search_floor_precedes_supported_market_lifetime_verified": (
            search_floor_precedes_supported_market_lifetime_verified is True
        ),
        "provider_range_complete_verified": provider_range_complete_verified,
        "archive_exhaustion_verified": provider_range_complete_verified,
        "earliest_provider_observation_candidate": earliest,
        "latest_provider_observation_candidate": latest,
        "discovered_unique_timestamp_count": len(timestamps),
        "empty_window_count": empty_window_count,
        "conflicting_duplicate_timestamp_count": (
            conflicting_duplicate_timestamp_count
        ),
        "failure_reason": failure_reason,
        "windows": windows,
        "limitations": limitations,
    }
