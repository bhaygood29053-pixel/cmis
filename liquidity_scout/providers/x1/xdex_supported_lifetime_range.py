"""Supported-lifetime XDEX price range completeness proof.

This proof does not claim that XDEX exposes every market or its global archive.
It proves a narrower statement for one exact pair: the provider price series is
complete across the already-verified supported market lifetime when all three
independent edges agree:

1. archive start is exhausted at the verified lifetime-start interval;
2. every expected cadence timestamp is present from that start through a
   completed forward scan;
3. a fresh, pair-bound closed-bar tail overlaps or directly continues the
   forward scan with no seam.

Historical quote/USD equivalence remains a separate gate.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SCHEMA = "xdex_supported_lifetime_range.v1"
POLICY_ID = "cmis.x1.xdex.supported_lifetime_range.v1"


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


def evaluate_xdex_supported_lifetime_range(
    *,
    archive_start: Any,
    continuity: Any,
    current_end: Any,
) -> dict[str, Any]:
    """Combine accepted edge proofs into exact supported-lifetime completeness."""

    archive = _mapping(archive_start)
    forward = _mapping(continuity)
    end = _mapping(current_end)
    anchor = _mapping(archive.get("lifetime_start_anchor"))

    archive_base = _text(archive.get("base_mint"))
    archive_quote = _text(archive.get("quote_mint"))
    forward_base = _text(forward.get("base_mint"))
    forward_quote = _text(forward.get("quote_mint"))
    end_base = _text(end.get("base_mint"))
    end_quote = _text(end.get("quote_mint"))

    exact_pair_identity_verified = bool(
        archive_base
        and archive_quote
        and archive_base != archive_quote
        and archive_base == forward_base == end_base
        and archive_quote == forward_quote == end_quote
        and end.get("exact_pair_identity_bound") is True
    )

    anchor_start = _nonnegative_int(anchor.get("observed_at"))
    anchor_interval = _positive_int(anchor.get("interval_seconds"))
    first_provider_observation = _nonnegative_int(
        archive.get("first_provider_observation")
    )

    archive_start_verified = bool(
        archive.get("archive_start_exhaustion_verified") is True
        and archive.get("archive_exhaustion_verified") is True
        and anchor.get("verified") is True
        and anchor.get("kind") == "first_verified_supported_market_interval"
        and anchor_start is not None
        and anchor_interval is not None
        and first_provider_observation == anchor_start
    )

    forward_start = _nonnegative_int(forward.get("time_from"))
    forward_end = _nonnegative_int(forward.get("time_to"))
    forward_interval = _positive_int(forward.get("interval_seconds"))
    expected_count = _nonnegative_int(forward.get("expected_timestamp_count"))
    unique_count = _nonnegative_int(
        forward.get("total_unique_timestamp_count")
    )
    missing_count = _nonnegative_int(forward.get("missing_timestamp_count"))
    unexpected_count = _nonnegative_int(
        forward.get("unexpected_timestamp_count")
    )
    conflict_count = _nonnegative_int(
        forward.get("conflicting_duplicate_timestamp_count")
    )
    observed_gap_count = _nonnegative_int(forward.get("observed_gap_count"))
    largest_gap = _nonnegative_int(
        forward.get("largest_observed_gap_seconds")
    )

    forward_continuity_verified = bool(
        forward.get("bounded_continuity_verified") is True
        and forward.get("scan_end_reached") is True
        and forward.get("all_windows_verified") is True
        and forward_start == anchor_start
        and forward_interval == anchor_interval
        and expected_count is not None
        and unique_count == expected_count
        and missing_count == 0
        and unexpected_count == 0
        and conflict_count == 0
        and observed_gap_count == 0
        and largest_gap == 0
        and forward_end is not None
    )

    end_start = _nonnegative_int(end.get("requested_time_from"))
    end_latest = _nonnegative_int(end.get("provider_latest_observed_at"))
    end_interval = _positive_int(end.get("interval_seconds"))

    current_end_verified = bool(
        end.get("current_end_coverage_verified") is True
        and end.get("tail_continuity_verified") is True
        and end.get("freshness_verified") is True
        and end.get("latest_expected_closed_bar_verified") is True
        and end.get("canonical_fact_timestamp_verified") is True
        and end_interval == anchor_interval
        and end_start is not None
        and end_latest is not None
    )

    seam_verified = bool(
        forward_continuity_verified
        and current_end_verified
        and forward_end is not None
        and end_start is not None
        and end_latest is not None
        and anchor_interval is not None
        and end_start <= forward_end + anchor_interval
        and end_latest >= forward_end
    )

    gates = {
        "exact_pair_identity_verified": exact_pair_identity_verified,
        "archive_start_verified": archive_start_verified,
        "forward_continuity_verified": forward_continuity_verified,
        "current_end_verified": current_end_verified,
        "forward_to_current_seam_verified": seam_verified,
    }
    supported_lifetime_range_complete_verified = all(gates.values())

    limitations = [
        "completeness_scope_is_exact_supported_pair_lifetime_only",
        "global_xdex_archive_completeness_not_claimed",
        "historical_quote_usd_equivalence_not_proven_here",
    ]
    if not supported_lifetime_range_complete_verified:
        limitations.append("supported_lifetime_range_incomplete")

    return {
        "schema": SCHEMA,
        "policy_id": POLICY_ID,
        "base_mint": archive_base,
        "quote_mint": archive_quote,
        "lifetime_start": anchor_start,
        "forward_scan_end": forward_end,
        "current_end": end_latest,
        "interval_seconds": anchor_interval,
        "supported_lifetime_range_complete_verified": (
            supported_lifetime_range_complete_verified
        ),
        "provider_range_complete_verified": (
            supported_lifetime_range_complete_verified
        ),
        "archive_exhaustion_verified": archive_start_verified,
        "price_bar_continuity_verified": bool(
            forward_continuity_verified and seam_verified
        ),
        "continuous_coverage_verified": False,
        "historical_quote_usd_equivalence_verified": False,
        "full_asset_lifetime_verified": False,
        "global_provider_archive_complete_verified": False,
        "gates": gates,
        "limitations": limitations,
    }


__all__ = [
    "POLICY_ID",
    "SCHEMA",
    "evaluate_xdex_supported_lifetime_range",
]
