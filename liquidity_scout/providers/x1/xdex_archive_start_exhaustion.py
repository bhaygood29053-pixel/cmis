"""Bounded XDEX archive-start exhaustion proof for X1 price history.

This proof is intentionally narrower than provider-range completeness.

It answers one question only: does the exact provider price series reach the
already-verified supported market-lifetime start interval without exposing an
earlier local boundary row or showing split/repeat instability at that edge?

A successful result may set archive_exhaustion_verified=true for the archive
START boundary. It does not prove that every later historical range is complete,
that the full series is continuous, or that the current end is fresh.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


SCHEMA = "xdex_archive_start_exhaustion.v1"
PROOF_ID = "cmis.x1.xdex.archive_start_exhaustion.v1"
CHAIN = "x1"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nonnegative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _positive_int(value: Any) -> int | None:
    parsed = _nonnegative_int(value)
    return parsed if parsed is not None and parsed > 0 else None


def _window_rows(value: Any) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    window = _mapping(value)
    start = _nonnegative_int(window.get("time_from"))
    end = _nonnegative_int(window.get("time_to"))
    rows = window.get("rows")

    shape_verified = bool(
        start is not None
        and end is not None
        and end >= start
        and isinstance(rows, Sequence)
        and not isinstance(rows, (str, bytes, bytearray))
    )

    by_timestamp: dict[int, dict[str, Any]] = {}
    rows_within_requested_range = shape_verified
    conflicting_duplicate_timestamp_count = 0

    if shape_verified:
        for row in rows:
            if not isinstance(row, Mapping):
                rows_within_requested_range = False
                continue
            ts = row.get("t")
            if isinstance(ts, bool) or not isinstance(ts, int):
                rows_within_requested_range = False
                continue
            if ts < start or ts > end:
                rows_within_requested_range = False
                continue
            current = dict(row)
            existing = by_timestamp.get(ts)
            if existing is not None and existing != current:
                conflicting_duplicate_timestamp_count += 1
                rows_within_requested_range = False
                continue
            by_timestamp.setdefault(ts, current)

    timestamps = sorted(by_timestamp)
    summary = {
        "time_from": start,
        "time_to": end,
        "shape_verified": shape_verified,
        "rows_within_requested_range": rows_within_requested_range,
        "returned_count": len(rows) if shape_verified else None,
        "unique_timestamp_count": len(timestamps),
        "first_returned_at": timestamps[0] if timestamps else None,
        "last_returned_at": timestamps[-1] if timestamps else None,
        "conflicting_duplicate_timestamp_count": conflicting_duplicate_timestamp_count,
    }
    return summary, by_timestamp


def evaluate_xdex_archive_start_exhaustion(
    lifetime_start_anchor: Any,
    *,
    base_mint: Any,
    quote_mint: Any,
    pre_window: Any,
    crossing_window: Any,
    post_window: Any,
    repeat_crossing_window: Any,
) -> dict[str, Any]:
    """Evaluate a local archive-start boundary proof and fail closed.

    Required boundary geometry:

    - the accepted lifetime anchor is a verified first supported market interval;
    - the pre-window ends before the anchor bar starts;
    - the crossing window spans the pre-window and the post-window;
    - the post-window starts exactly at the anchor bar start;
    - crossing == pre U post by exact timestamp+row content;
    - a repeated crossing request is byte-for-field stable at row level;
    - the pre-window is empty;
    - the first post/crossing row is exactly the anchor interval start;
    - the first two provider observations are one anchor interval apart.

    The proof is deliberately local to the archive start. It does not establish
    provider_range_complete_verified, continuous_coverage_verified, or
    full_asset_lifetime_verified.
    """

    anchor = _mapping(lifetime_start_anchor)
    base = _text(base_mint)
    quote = _text(quote_mint)

    anchor_start = _nonnegative_int(anchor.get("observed_at"))
    interval = _positive_int(anchor.get("interval_seconds"))
    market_open = _nonnegative_int(anchor.get("market_open_at"))

    anchor_verified = bool(
        anchor.get("verified") is True
        and anchor.get("kind") == "first_verified_supported_market_interval"
        and anchor_start is not None
        and interval is not None
        and market_open is not None
        and anchor_start <= market_open < anchor_start + interval
        and anchor.get("open_time_semantics_verified") is True
    )
    exact_pair_identity_bound = bool(base and quote and base != quote)

    pre_summary, pre_rows = _window_rows(pre_window)
    crossing_summary, crossing_rows = _window_rows(crossing_window)
    post_summary, post_rows = _window_rows(post_window)
    repeat_summary, repeat_rows = _window_rows(repeat_crossing_window)

    all_window_scopes_verified = all(
        summary.get("rows_within_requested_range") is True
        for summary in (
            pre_summary,
            crossing_summary,
            post_summary,
            repeat_summary,
        )
    )

    boundary_geometry_verified = bool(
        anchor_start is not None
        and pre_summary.get("time_from") is not None
        and pre_summary.get("time_to") is not None
        and crossing_summary.get("time_from") is not None
        and crossing_summary.get("time_to") is not None
        and post_summary.get("time_from") is not None
        and post_summary.get("time_to") is not None
        and repeat_summary.get("time_from") is not None
        and repeat_summary.get("time_to") is not None
        and pre_summary["time_to"] < anchor_start
        and post_summary["time_from"] == anchor_start
        and crossing_summary["time_from"] == pre_summary["time_from"]
        and crossing_summary["time_to"] == post_summary["time_to"]
        and repeat_summary["time_from"] == crossing_summary["time_from"]
        and repeat_summary["time_to"] == crossing_summary["time_to"]
    )

    pre_anchor_empty_verified = bool(
        all_window_scopes_verified
        and pre_summary.get("returned_count") == 0
        and not pre_rows
    )

    partition_rows = dict(pre_rows)
    partition_conflict = False
    for ts, row in post_rows.items():
        existing = partition_rows.get(ts)
        if existing is not None and existing != row:
            partition_conflict = True
        partition_rows[ts] = row

    split_partition_exact_verified = bool(
        all_window_scopes_verified
        and boundary_geometry_verified
        and not partition_conflict
        and crossing_rows == partition_rows
    )
    repeated_request_stable_verified = bool(
        all_window_scopes_verified
        and boundary_geometry_verified
        and crossing_rows == repeat_rows
    )

    crossing_timestamps = sorted(crossing_rows)
    post_timestamps = sorted(post_rows)
    first_boundary_row_verified = bool(
        anchor_start is not None
        and crossing_timestamps
        and post_timestamps
        and crossing_timestamps[0] == anchor_start
        and post_timestamps[0] == anchor_start
    )

    first_two_intervals_verified = bool(
        interval is not None
        and len(post_timestamps) >= 2
        and post_timestamps[0] == anchor_start
        and post_timestamps[1] - post_timestamps[0] == interval
    )

    gates = {
        "lifetime_start_anchor_verified": anchor_verified,
        "exact_pair_identity_bound": exact_pair_identity_bound,
        "all_window_scopes_verified": all_window_scopes_verified,
        "boundary_geometry_verified": boundary_geometry_verified,
        "pre_anchor_empty_verified": pre_anchor_empty_verified,
        "split_partition_exact_verified": split_partition_exact_verified,
        "repeated_request_stable_verified": repeated_request_stable_verified,
        "first_boundary_row_verified": first_boundary_row_verified,
        "first_two_intervals_verified": first_two_intervals_verified,
    }
    archive_start_exhaustion_verified = all(gates.values())

    limitations = [
        "archive_exhaustion_is_start_boundary_only",
        "provider_range_completeness_not_proven_here",
        "continuous_price_coverage_not_proven_here",
        "current_end_coverage_not_proven_here",
        "historical_quote_usd_equivalence_not_proven_here",
        "pre_anchor_probe_is_local_boundary_evidence_not_global_retention_scan",
    ]

    return {
        "schema": SCHEMA,
        "proof_id": PROOF_ID,
        "chain": CHAIN,
        "base_mint": base,
        "quote_mint": quote,
        "lifetime_start_anchor": dict(anchor),
        "archive_start_exhaustion_verified": archive_start_exhaustion_verified,
        "archive_exhaustion_verified": archive_start_exhaustion_verified,
        "provider_range_complete_verified": False,
        "continuous_coverage_verified": False,
        "full_asset_lifetime_verified": False,
        "gates": gates,
        "pre_window": pre_summary,
        "crossing_window": crossing_summary,
        "post_window": post_summary,
        "repeat_crossing_window": repeat_summary,
        "first_provider_observation": (
            crossing_timestamps[0] if crossing_timestamps else None
        ),
        "second_provider_observation": (
            crossing_timestamps[1] if len(crossing_timestamps) >= 2 else None
        ),
        "limitations": limitations,
    }


__all__ = [
    "CHAIN",
    "PROOF_ID",
    "SCHEMA",
    "evaluate_xdex_archive_start_exhaustion",
]
