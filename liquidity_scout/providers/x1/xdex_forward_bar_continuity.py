"""Deterministic forward continuity proof for XDEX X1 price bars.

This module scans an explicit aligned time range in fixed windows and verifies
that every expected bar timestamp exists exactly once on the accepted cadence.
It is deliberately a bounded continuity proof, not a provider archive/range
completeness proof and not a current-price freshness proof.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from .xdex import fetch_price_history


SCHEMA = "xdex_forward_bar_continuity.v1"
POLICY_ID = "cmis.x1.xdex.forward_bar_continuity.v1"
CHAIN = "x1"
DEFAULT_INTERVAL_SECONDS = 60


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


def _nonnegative_int(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a non-negative integer") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return parsed


def scan_xdex_forward_bar_continuity(
    base_mint: Any,
    quote_mint: Any,
    *,
    time_from: Any,
    time_to: Any,
    interval_seconds: Any = DEFAULT_INTERVAL_SECONDS,
    window_intervals: Any = 1440,
    max_windows: Any = 400,
    fetcher: Callable[..., Any] = fetch_price_history,
    missing_sample_limit: Any = 25,
) -> dict[str, Any]:
    """Verify exact expected provider timestamps over an explicit range.

    Windows are inclusive and non-overlapping on the bar grid. For example, a
    60-second cadence with window_intervals=1440 requests exactly 1440 expected
    timestamps per full window.

    A successful result proves bounded continuity only for [time_from,time_to].
    It does not by itself prove archive exhaustion, provider range semantics,
    historical quote/USD equivalence, current-end freshness, or full lifetime.
    """

    base = _text(base_mint)
    quote = _text(quote_mint)
    if not base or not quote or base == quote:
        raise ValueError("distinct base_mint and quote_mint are required")

    start = _nonnegative_int("time_from", time_from)
    end = _nonnegative_int("time_to", time_to)
    interval = _positive_int("interval_seconds", interval_seconds)
    per_window = _positive_int("window_intervals", window_intervals)
    window_limit = _positive_int("max_windows", max_windows)
    sample_limit = _positive_int("missing_sample_limit", missing_sample_limit)

    if end < start:
        raise ValueError("time_to must be greater than or equal to time_from")
    if start % interval != 0 or end % interval != 0:
        raise ValueError("time bounds must align to interval_seconds")
    if (end - start) % interval != 0:
        raise ValueError("time range must align to interval_seconds")

    total_expected = ((end - start) // interval) + 1
    windows: list[dict[str, Any]] = []
    cursor = start
    failure_reason = None

    missing_timestamp_count = 0
    missing_timestamp_sample: list[int] = []
    unexpected_timestamp_count = 0
    conflicting_duplicate_timestamp_count = 0
    duplicate_timestamp_count = 0
    total_returned_rows = 0
    total_unique_rows = 0
    prior_last_timestamp = None
    observed_gap_count = 0
    largest_observed_gap_seconds = 0

    for index in range(window_limit):
        if cursor > end:
            break

        window_end = min(
            end,
            cursor + interval * (per_window - 1),
        )
        expected_count = ((window_end - cursor) // interval) + 1

        try:
            raw = fetcher(
                base,
                quote,
                time_from=cursor,
                time_to=window_end,
            )
        except Exception as exc:
            failure_reason = (
                "provider_request_failed:"
                f"{type(exc).__name__}:{exc}"
            )
            windows.append({
                "index": index,
                "time_from": cursor,
                "time_to": window_end,
                "expected_count": expected_count,
                "returned_count": None,
                "unique_timestamp_count": 0,
                "missing_timestamp_count": expected_count,
                "unexpected_timestamp_count": None,
                "rows_within_requested_range": False,
                "cadence_grid_verified": False,
                "status": "error",
            })
            break

        if not isinstance(raw, list):
            failure_reason = "provider_history_response_not_list"
            windows.append({
                "index": index,
                "time_from": cursor,
                "time_to": window_end,
                "expected_count": expected_count,
                "returned_count": None,
                "unique_timestamp_count": 0,
                "missing_timestamp_count": expected_count,
                "unexpected_timestamp_count": None,
                "rows_within_requested_range": False,
                "cadence_grid_verified": False,
                "status": "invalid",
            })
            break

        total_returned_rows += len(raw)
        by_timestamp: dict[int, dict[str, Any]] = {}
        rows_within_requested_range = True
        cadence_grid_verified = True
        local_unexpected = 0
        local_conflicts = 0
        local_duplicates = 0

        for row in raw:
            if not isinstance(row, Mapping):
                rows_within_requested_range = False
                cadence_grid_verified = False
                local_unexpected += 1
                continue

            ts = row.get("t")
            if isinstance(ts, bool) or not isinstance(ts, int):
                rows_within_requested_range = False
                cadence_grid_verified = False
                local_unexpected += 1
                continue

            if ts < cursor or ts > window_end:
                rows_within_requested_range = False
                local_unexpected += 1
                continue

            if (ts - start) % interval != 0:
                cadence_grid_verified = False
                local_unexpected += 1
                continue

            current = dict(row)
            existing = by_timestamp.get(ts)
            if existing is not None:
                local_duplicates += 1
                if existing != current:
                    local_conflicts += 1
                continue
            by_timestamp[ts] = current

        timestamps = sorted(by_timestamp)
        total_unique_rows += len(timestamps)
        unexpected_timestamp_count += local_unexpected
        conflicting_duplicate_timestamp_count += local_conflicts
        duplicate_timestamp_count += local_duplicates

        expected = set(range(cursor, window_end + interval, interval))
        actual = set(timestamps)
        missing = sorted(expected - actual)
        local_missing_count = len(missing)
        missing_timestamp_count += local_missing_count
        if len(missing_timestamp_sample) < sample_limit:
            remaining = sample_limit - len(missing_timestamp_sample)
            missing_timestamp_sample.extend(missing[:remaining])

        combined_for_gap = timestamps
        if (
            prior_last_timestamp is not None
            and timestamps
            and timestamps[0] > prior_last_timestamp
        ):
            combined_for_gap = [prior_last_timestamp, *timestamps]

        for left, right in zip(combined_for_gap, combined_for_gap[1:]):
            delta = right - left
            if delta > interval:
                observed_gap_count += 1
                largest_observed_gap_seconds = max(
                    largest_observed_gap_seconds,
                    delta - interval,
                )

        if timestamps:
            prior_last_timestamp = timestamps[-1]

        window_verified = bool(
            rows_within_requested_range
            and cadence_grid_verified
            and local_unexpected == 0
            and local_conflicts == 0
            and local_missing_count == 0
            and len(timestamps) == expected_count
        )

        windows.append({
            "index": index,
            "time_from": cursor,
            "time_to": window_end,
            "expected_count": expected_count,
            "returned_count": len(raw),
            "unique_timestamp_count": len(timestamps),
            "first_returned_at": timestamps[0] if timestamps else None,
            "last_returned_at": timestamps[-1] if timestamps else None,
            "missing_timestamp_count": local_missing_count,
            "unexpected_timestamp_count": local_unexpected,
            "conflicting_duplicate_timestamp_count": local_conflicts,
            "duplicate_timestamp_count": local_duplicates,
            "rows_within_requested_range": rows_within_requested_range,
            "cadence_grid_verified": cadence_grid_verified,
            "window_continuity_verified": window_verified,
            "status": "verified" if window_verified else "partial",
        })

        if not window_verified:
            failure_reason = "window_continuity_unverified"
            break

        cursor = window_end + interval

    scan_end_reached = cursor > end and failure_reason is None
    expected_window_count = (
        (total_expected + per_window - 1) // per_window
    )

    all_windows_verified = bool(windows) and all(
        item.get("window_continuity_verified") is True
        for item in windows
    )

    bounded_continuity_verified = bool(
        scan_end_reached
        and all_windows_verified
        and len(windows) == expected_window_count
        and missing_timestamp_count == 0
        and unexpected_timestamp_count == 0
        and conflicting_duplicate_timestamp_count == 0
        and total_unique_rows == total_expected
    )

    limitations = [
        "bounded_continuity_only_for_explicit_requested_range",
        "archive_exhaustion_not_proven_here",
        "provider_range_completeness_not_proven_here",
        "current_end_freshness_not_proven_here",
        "historical_quote_usd_equivalence_not_proven_here",
    ]
    if not scan_end_reached:
        limitations.append("requested_end_not_reached")
    if failure_reason:
        limitations.append("continuity_scan_failed")

    return {
        "schema": SCHEMA,
        "policy_id": POLICY_ID,
        "chain": CHAIN,
        "base_mint": base,
        "quote_mint": quote,
        "time_from": start,
        "time_to": end,
        "interval_seconds": interval,
        "window_intervals": per_window,
        "max_windows": window_limit,
        "expected_timestamp_count": total_expected,
        "expected_window_count": expected_window_count,
        "requested_window_count": len(windows),
        "total_returned_rows": total_returned_rows,
        "total_unique_timestamp_count": total_unique_rows,
        "missing_timestamp_count": missing_timestamp_count,
        "missing_timestamp_sample": missing_timestamp_sample,
        "unexpected_timestamp_count": unexpected_timestamp_count,
        "duplicate_timestamp_count": duplicate_timestamp_count,
        "conflicting_duplicate_timestamp_count": (
            conflicting_duplicate_timestamp_count
        ),
        "observed_gap_count": observed_gap_count,
        "largest_observed_gap_seconds": largest_observed_gap_seconds,
        "scan_end_reached": scan_end_reached,
        "all_windows_verified": all_windows_verified,
        "cadence_policy_verified": True,
        "bounded_continuity_verified": bounded_continuity_verified,
        "continuous_coverage_verified": False,
        "provider_range_complete_verified": False,
        "full_asset_lifetime_verified": False,
        "failure_reason": failure_reason,
        "windows": windows,
        "limitations": limitations,
    }


__all__ = [
    "CHAIN",
    "DEFAULT_INTERVAL_SECONDS",
    "POLICY_ID",
    "SCHEMA",
    "scan_xdex_forward_bar_continuity",
]
