"""Deterministic X1 price historical-coverage proof policy.

This module does not discover provider history and does not infer completeness
from a long or gap-free sample. It evaluates only explicit proof inputs that
have already been established by accepted provider/service contracts.

The policy is price-specific by design. Liquidity, volume, transactions, and
other metrics require their own independent proof before promotion.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


POLICY_ID = "cmis.x1.price_historical_coverage.v1"
LIFETIME_SCOPE = "first_verified_supported_market_observation_to_current"

_REQUIRED_GATES = (
    "lifetime_start_anchor_verified",
    "provider_range_complete_verified",
    "archive_exhaustion_verified",
    "exact_pair_quote_identity_verified",
    "canonical_fact_timestamps_verified",
    "cadence_policy_verified",
    "bounded_continuity_verified",
    "current_end_coverage_verified",
    "historical_quote_usd_equivalence_verified",
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _positive_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _nonnegative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def evaluate_x1_price_historical_coverage(
    proof: Any,
    *,
    metric_profile: Any = None,
) -> dict[str, Any]:
    """Evaluate explicit price-history proof inputs and fail closed.

    Expected proof sections:

    - lifetime_start_anchor:
        kind == "first_verified_supported_market_observation"
        verified == True
        observed_at == canonical first price observation
    - archive:
        provider_range_complete_verified == True
        archive_exhaustion_verified == True
    - identity:
        exact_pair_quote_identity_verified == True
    - timestamps:
        canonical_fact_timestamps_verified == True
    - cadence:
        policy_verified == True
        expected_interval_seconds > 0
        maximum_allowed_gap_seconds > 0
        observed_gap_count >= 0
        largest_observed_gap_seconds >= 0
        bounded_continuity_verified == True
    - current_end:
        verified == True
        observed_at is canonical current-end observation
        age_seconds >= 0
        freshness_bound_seconds > 0
    - quote:
        historical_quote_usd_equivalence_verified == True

    A metric profile may be supplied to bind the proof to the exact first/last
    observations exposed by historical_compare.
    """

    candidate = _mapping(proof)
    profile = _mapping(metric_profile)

    anchor = _mapping(candidate.get("lifetime_start_anchor"))
    archive = _mapping(candidate.get("archive"))
    identity = _mapping(candidate.get("identity"))
    timestamps = _mapping(candidate.get("timestamps"))
    cadence = _mapping(candidate.get("cadence"))
    current_end = _mapping(candidate.get("current_end"))
    quote = _mapping(candidate.get("quote"))

    anchor_observed_at = _nonnegative_int(anchor.get("observed_at"))
    current_end_observed_at = _nonnegative_int(current_end.get("observed_at"))

    expected_interval = _positive_int(cadence.get("expected_interval_seconds"))
    maximum_allowed_gap = _positive_int(cadence.get("maximum_allowed_gap_seconds"))
    observed_gap_count = _nonnegative_int(cadence.get("observed_gap_count"))
    largest_observed_gap = _nonnegative_int(
        cadence.get("largest_observed_gap_seconds")
    )

    current_end_age = _nonnegative_int(current_end.get("age_seconds"))
    freshness_bound = _positive_int(current_end.get("freshness_bound_seconds"))

    profile_first = _nonnegative_int(profile.get("first_observed_at"))
    profile_last = _nonnegative_int(profile.get("last_observed_at"))

    anchor_profile_bound = (
        anchor_observed_at is not None
        and (profile_first is None or profile_first == anchor_observed_at)
    )
    current_profile_bound = (
        current_end_observed_at is not None
        and (profile_last is None or profile_last == current_end_observed_at)
    )

    cadence_shape_complete = all(
        value is not None
        for value in (
            expected_interval,
            maximum_allowed_gap,
            observed_gap_count,
            largest_observed_gap,
        )
    )
    bounded_gap_state = (
        cadence_shape_complete
        and observed_gap_count == 0
        and largest_observed_gap <= maximum_allowed_gap
    )

    current_freshness_passes = (
        current_end_age is not None
        and freshness_bound is not None
        and current_end_age <= freshness_bound
    )

    gates = {
        "lifetime_start_anchor_verified": (
            anchor.get("verified") is True
            and anchor.get("kind")
            == "first_verified_supported_market_observation"
            and anchor_profile_bound
        ),
        "provider_range_complete_verified": (
            archive.get("provider_range_complete_verified") is True
        ),
        "archive_exhaustion_verified": (
            archive.get("archive_exhaustion_verified") is True
        ),
        "exact_pair_quote_identity_verified": (
            identity.get("exact_pair_quote_identity_verified") is True
        ),
        "canonical_fact_timestamps_verified": (
            timestamps.get("canonical_fact_timestamps_verified") is True
        ),
        "cadence_policy_verified": (
            cadence.get("policy_verified") is True
            and cadence_shape_complete
        ),
        "bounded_continuity_verified": (
            cadence.get("bounded_continuity_verified") is True
            and bounded_gap_state
        ),
        "current_end_coverage_verified": (
            current_end.get("verified") is True
            and current_profile_bound
            and current_freshness_passes
        ),
        "historical_quote_usd_equivalence_verified": (
            quote.get("historical_quote_usd_equivalence_verified") is True
        ),
    }

    missing_gates = [name for name in _REQUIRED_GATES if gates[name] is not True]
    fully_verified = not missing_gates

    return {
        "policy_id": POLICY_ID,
        "metric": "price",
        "lifetime_scope": LIFETIME_SCOPE,
        "status": "verified" if fully_verified else "partial",
        "promotion_eligible": fully_verified,
        "asset_lifetime_start_verified": gates[
            "lifetime_start_anchor_verified"
        ],
        "full_asset_lifetime_verified": fully_verified,
        "continuous_coverage_verified": fully_verified,
        "gates": gates,
        "missing_gates": missing_gates,
        "first_verified_supported_market_observation": anchor_observed_at,
        "current_end_observed_at": current_end_observed_at,
        "expected_interval_seconds": expected_interval,
        "maximum_allowed_gap_seconds": maximum_allowed_gap,
        "observed_gap_count": observed_gap_count,
        "largest_observed_gap_seconds": largest_observed_gap,
        "freshness_bound_seconds": freshness_bound,
        "current_end_age_seconds": current_end_age,
    }
