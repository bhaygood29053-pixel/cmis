"""Current-end coverage proof for XDEX one-minute historical price bars.

XDEX historical bars use the bar-start Unix timestamp as the canonical fact
timestamp. A fully closed 60-second bar is therefore already at least 60
seconds old by that timestamp when it becomes final. CMIS applies its accepted
60-second current-price horizon after bar finalization, producing an explicit
120-second maximum bar-start age for this historical current-end proof.

This is operator governance, not an XDEX SLA.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SCHEMA = "xdex_history_current_end.v1"
POLICY_ID = "cmis.x1.xdex.history_current_end.v1"
BAR_INTERVAL_SECONDS = 60
POST_FINALIZATION_CURRENT_HORIZON_SECONDS = 60
FRESHNESS_BOUND_SECONDS = (
    BAR_INTERVAL_SECONDS + POST_FINALIZATION_CURRENT_HORIZON_SECONDS
)


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
    requested_closed_bar_start: Any,
    provider_rows: Any,
    evaluation_time: Any,
    interval_seconds: Any = BAR_INTERVAL_SECONDS,
    freshness_bound_seconds: Any = FRESHNESS_BOUND_SECONDS,
) -> dict[str, Any]:
    """Evaluate whether provider history reaches a fresh fully closed bar."""

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
    if requested % interval != 0:
        raise ValueError("requested_closed_bar_start must align to interval_seconds")

    rows = provider_rows if isinstance(provider_rows, list) else []
    timestamps: list[int] = []
    rows_valid = isinstance(provider_rows, list)
    rows_within_closed_scope = True
    conflicting_duplicate_timestamp_count = 0
    by_timestamp: dict[int, dict[str, Any]] = {}

    for row in rows:
        if not isinstance(row, Mapping):
            rows_valid = False
            rows_within_closed_scope = False
            continue
        ts = row.get("t")
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0:
            rows_valid = False
            rows_within_closed_scope = False
            continue
        if ts > requested or ts % interval != 0:
            rows_within_closed_scope = False
            continue

        current = dict(row)
        existing = by_timestamp.get(ts)
        if existing is not None:
            if existing != current:
                conflicting_duplicate_timestamp_count += 1
            continue
        by_timestamp[ts] = current
        timestamps.append(ts)

    timestamps.sort()
    latest = timestamps[-1] if timestamps else None
    latest_expected_closed_bar_verified = latest == requested

    age_seconds = (
        evaluated_at - latest
        if latest is not None and evaluated_at >= latest
        else None
    )
    no_future_timestamp = (
        latest is not None and evaluated_at >= latest
    )
    freshness_verified = (
        age_seconds is not None and age_seconds <= bound
    )

    current_end_coverage_verified = bool(
        rows_valid
        and rows_within_closed_scope
        and conflicting_duplicate_timestamp_count == 0
        and latest_expected_closed_bar_verified
        and no_future_timestamp
        and freshness_verified
    )

    limitations = [
        "current_end_only_not_archive_completeness",
        "current_end_only_not_full_continuity",
        "historical_quote_usd_equivalence_not_proven_here",
        "freshness_bound_is_cmis_operator_governance_not_xdex_sla",
    ]
    if not current_end_coverage_verified:
        limitations.append("current_end_coverage_unverified")

    return {
        "schema": SCHEMA,
        "policy_id": POLICY_ID,
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
        "conflicting_duplicate_timestamp_count": (
            conflicting_duplicate_timestamp_count
        ),
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
