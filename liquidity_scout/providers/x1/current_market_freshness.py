"""Deterministic current-market freshness assessment for X1 Instant X1 Scan.

Collection recency and provider fact-time are separate proof dimensions. The
assessment may promote current price freshness only when the current price is
bound to a recent timestamped provider-backed close under the accepted policy.
Liquidity, rolling volume, and rolling transaction count remain unverified for
fact-time freshness until field-specific timestamp contracts exist.
"""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

from liquidity_scout.providers.x1.instant_scan_freshness_policy import (
    normalize_instant_scan_freshness_policy,
)


FIELDS = ("price_usd", "liquidity_usd", "volume_24h_usd", "transactions_24h")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _age(
    *,
    observed_at: Any,
    evaluated_at: Any,
    max_age_seconds: int,
    max_future_skew_seconds: int,
) -> dict[str, Any]:
    observed = _finite(observed_at)
    evaluated = _finite(evaluated_at)
    if observed is None or evaluated is None:
        return {
            "verified": False,
            "age_seconds": None,
            "reason": "timestamp_unavailable",
        }
    age = evaluated - observed
    verified = (
        age <= float(max_age_seconds)
        and age >= -float(max_future_skew_seconds)
    )
    return {
        "verified": verified,
        "age_seconds": age,
        "reason": "within_policy" if verified else "outside_policy",
    }


def evaluate_current_market_freshness(
    market_envelope: Mapping[str, Any],
    provider_history_backfill: Mapping[str, Any],
    *,
    evaluated_at: Any,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(market_envelope, Mapping):
        raise TypeError("market_envelope must be a mapping")
    if not isinstance(provider_history_backfill, Mapping):
        raise TypeError("provider_history_backfill must be a mapping")

    normalized = normalize_instant_scan_freshness_policy(policy)
    data = _mapping(market_envelope.get("data"))
    completeness = _mapping(data.get("completeness"))
    provenance = _mapping(data.get("provenance"))

    collection = _age(
        observed_at=provenance.get("catalog_last_refresh_unix"),
        evaluated_at=evaluated_at,
        max_age_seconds=normalized["max_collection_age_seconds"],
        max_future_skew_seconds=normalized["max_future_skew_seconds"],
    )
    collection_freshness_verified = collection["verified"] is True

    latest_fact_time = provider_history_backfill.get(
        "last_imported_observed_at"
    )
    provider_fact_time = _age(
        observed_at=latest_fact_time,
        evaluated_at=evaluated_at,
        max_age_seconds=normalized["max_price_fact_age_seconds"],
        max_future_skew_seconds=normalized["max_future_skew_seconds"],
    )

    current_price = _finite(data.get("price_usd"))
    latest_price = _finite(
        provider_history_backfill.get("last_imported_price_usd")
    )
    price_value_link_verified = bool(
        completeness.get("price") is True
        and current_price is not None
        and latest_price is not None
        and math.isclose(
            current_price,
            latest_price,
            rel_tol=normalized["price_relative_tolerance"],
            abs_tol=1e-12,
        )
    )
    price_freshness_verified = bool(
        collection_freshness_verified
        and provider_history_backfill.get("provider_history_imported") is True
        and provider_fact_time["verified"] is True
        and price_value_link_verified
    )

    field_freshness = {
        "price_usd": {
            "freshness_verified": price_freshness_verified,
            "reason": (
                "timestamped_provider_price_matches_current_market_price"
                if price_freshness_verified
                else "current_price_freshness_proof_incomplete"
            ),
            "fact_observed_at": latest_fact_time,
            "fact_age_seconds": provider_fact_time.get("age_seconds"),
            "provider_fact_time_verified": provider_fact_time["verified"] is True,
            "current_price_value": current_price,
            "provider_backed_price_value": latest_price,
            "value_link_verified": price_value_link_verified,
        },
        "liquidity_usd": {
            "freshness_verified": False,
            "reason": "liquidity_provider_fact_time_not_verified",
        },
        "volume_24h_usd": {
            "freshness_verified": False,
            "reason": "rolling_volume_provider_fact_time_not_verified",
        },
        "transactions_24h": {
            "freshness_verified": False,
            "reason": "rolling_transactions_provider_fact_time_not_verified",
        },
    }

    verified_field_count = sum(
        1
        for value in field_freshness.values()
        if value.get("freshness_verified") is True
    )
    total_field_count = len(field_freshness)
    state = (
        "VERIFIED"
        if verified_field_count == total_field_count
        else ("PARTIAL" if verified_field_count > 0 else "NOT_VERIFIED")
    )

    return {
        "contract_version": "x1_current_market_freshness/v1",
        "policy": normalized,
        "scope": "instant_x1_scan.current_market",
        "evaluated_at": evaluated_at,
        "collection_observed_at": provenance.get("catalog_last_refresh_unix"),
        "collection_age_seconds": collection.get("age_seconds"),
        "collection_freshness_verified": collection_freshness_verified,
        "provider_price_fact_observed_at": latest_fact_time,
        "provider_price_fact_age_seconds": provider_fact_time.get("age_seconds"),
        "provider_price_fact_time_verified": provider_fact_time["verified"] is True,
        "current_market_freshness_verified": verified_field_count == total_field_count,
        "freshness_state": state,
        "verified_field_count": verified_field_count,
        "total_field_count": total_field_count,
        "fields": field_freshness,
        "limitations": [
            "collection_time_is_not_provider_fact_time",
            "price_freshness_requires_timestamped_provider_price_match",
            "liquidity_fact_time_not_verified",
            "rolling_volume_fact_time_not_verified",
            "rolling_transactions_fact_time_not_verified",
            "source_independence_separate_from_freshness",
        ],
    }


__all__ = ["FIELDS", "evaluate_current_market_freshness"]
