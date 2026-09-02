"""Current-end coverage proof for XDEX one-minute historical price bars.

XDEX historical bars use the bar-start Unix timestamp as the canonical fact
timestamp. A fully closed 60-second bar is therefore already at least 60
seconds old by that timestamp when it becomes final. CMIS applies its accepted
60-second current-price horizon after bar finalization, producing an explicit
120-second maximum bar-start age for this historical current-end proof.

The proof also verifies an exact closed-bar tail so a long continuity scan can
overlap this probe without leaving an unverified seam.

This is operator governance, not an XDEX SLA.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SCHEMA = "xdex_history_current_end.v2"
POLICY_ID = "cmis.x1.xdex.history_current_end.v2"
BAR_INTERVAL_SECONDS = 60
POST_FINALIZATION_CURRENT_HORIZON_SECONDS = 60
FRESHNESS_BOUND_SECONDS = (
    BAR_INTERVAL_SECONDS + POST_FINALIZATION_CURRENT_HORIZON_SECONDS
)


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nonnegative_int(name: str, value: Any) -> int:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a non-negative integer") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return parsed


def evaluate_xdex_history_current_end(
    *,
    base_mint: Any,
    quote_mint: Any,
    requested_time_from: Any,
    requested_closed_bar_start: Any,
    provider_rows: Any,
    evaluation_time: Any,
    interval_seconds: Any = BAR_INTERVAL_SECONDS,
    freshness_bound_seconds: Any = FRESHNESS_BOUND_SECONDS,
) -> dict[str, Any]:
    """Evaluate a pair-bound, fresh, exact closed-bar tail."""

    base = _text(base_mint)
    quote = _text(quote_mint)
    exact_pair_identity_bound = bool(base and quote and base != quote)

    start = _nonnegative_int("requested_time_from", requested_time_from)
    requested = _nonnegative_int(
        "requested_closed_bar_start",
        requested_closed_bar_start,
    )
    evaluated_at = _nonnegative_int("evaluation_time", evaluation_time)
    interval = _nonnegative_int("interval_seconds", interval_seconds)
    bound = _nonnegative_int(
        "freshness_bound_seconds",
        freshness_bound_seconds,
    )
    if interval <= 0:
        raise ValueError("interval_seconds must be positive")
    if bound <= 0:
        raise ValueError("freshness_bound_seconds must be positive")
    if start > requested:
        raise ValueError("requested_time_from must not exceed requested_closed_bar_start")
    if start % interval != 0 or requested % interval != 0:
        raise ValueError("requested bounds must align to interval_seconds")

    rows = provider_rows if isinstance(provider_rows, list) else []
    rows_valid = isinstance(provider_rows, list)
    rows_within_closed_scope = True
    conflicting_duplicate_timestamp_count = 0
    duplicate_timestamp_count = 0
    unexpected_timestamp_count = 0
    by_timestamp: dict[int, dict[str, Any]] = {}

    for row in rows:
        if not isinstance(row, Mapping):
            rows_valid = False
            rows_within_closed_scope = False
            unexpected_timestamp_count += 1
            continue
        ts = row.get("t")
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0:
            rows_valid = False
            rows_within_closed_scope = False
            unexpected_timestamp_count += 1
            continue
        if ts < start or ts > requested or (ts - start) % interval != 0:
            rows_within_closed_scope = False
            unexpected_timestamp_count += 1
            continue

        current = dict(row)
        existing = by_timestamp.get(ts)
        if existing is not None:
            duplicate_timestamp_count += 1
            if existing != current:
                conflicting_duplicate_timestamp_count += 1
            continue
        by_timestamp[ts] = current

    timestamps = sorted(by_timestamp)
    expected = set(range(start, requested + interval, interval))
    actual = set(timestamps)
    missing = sorted(expected - actual)

    latest = timestamps[-1] if timestamps else None
    latest_expected_closed_bar_verified = latest == requested
    tail_continuity_verified = bool(
        rows_valid
        and rows_within_closed_scope
        and unexpected_timestamp_count == 0
        and conflicting_duplicate_timestamp_count == 0
        and not missing
        and actual == expected
    )

    age_seconds = (
        evaluated_at - latest
        if latest is not None and evaluated_at >= latest
        else None
    )
    no_future_timestamp = latest is not None and evaluated_at >= latest
    freshness_verified = age_seconds is not None and age_seconds <= bound

    current_end_coverage_verified = bool(
        exact_pair_identity_bound
        and tail_continuity_verified
        and latest_expected_closed_bar_verified
        and no_future_timestamp
        and freshness_verified
    )

    limitations = [
        "current_end_tail_only_not_archive_completeness",
        "historical_quote_usd_equivalence_not_proven_here",
        "freshness_bound_is_cmis_operator_governance_not_xdex_sla",
    ]
    if not current_end_coverage_verified:
        limitations.append("current_end_coverage_unverified")

    return {
        "schema": SCHEMA,
        "policy_id": POLICY_ID,
        "base_mint": base,
        "quote_mint": quote,
        "exact_pair_identity_bound": exact_pair_identity_bound,
        "requested_time_from": start,
        "requested_closed_bar_start": requested,
        "provider_latest_observed_at": latest,
        "evaluation_time": evaluated_at,
        "interval_seconds": interval,
        "post_finalization_current_horizon_seconds": (
            POST_FINALIZATION_CURRENT_HORIZON_SECONDS
        ),
        "freshness_bound_seconds": bound,
        "age_seconds": age_seconds,
        "provider_rows_valid": rows_valid,
        "rows_within_closed_scope": rows_within_closed_scope,
        "expected_timestamp_count": len(expected),
        "unique_timestamp_count": len(actual),
        "missing_timestamp_count": len(missing),
        "missing_timestamp_sample": missing[:25],
        "unexpected_timestamp_count": unexpected_timestamp_count,
        "duplicate_timestamp_count": duplicate_timestamp_count,
        "conflicting_duplicate_timestamp_count": (
            conflicting_duplicate_timestamp_count
        ),
        "tail_continuity_verified": tail_continuity_verified,
        "latest_expected_closed_bar_verified": (
            latest_expected_closed_bar_verified
        ),
        "canonical_fact_timestamp_verified": (
            latest_expected_closed_bar_verified
        ),
        "freshness_verified": freshness_verified,
        "current_end_coverage_verified": current_end_coverage_verified,
        "provider_range_complete_verified": False,
        "continuous_coverage_verified": False,
        "full_asset_lifetime_verified": False,
        "limitations": limitations,
    }


__all__ = [
    "BAR_INTERVAL_SECONDS",
    "FRESHNESS_BOUND_SECONDS",
    "POLICY_ID",
    "POST_FINALIZATION_CURRENT_HORIZON_SECONDS",
    "SCHEMA",
    "evaluate_xdex_history_current_end",
]
