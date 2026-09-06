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
V1_CONTRACT = "x1_current_market_freshness/v1"
V2_CONTRACT = "x1_current_market_freshness/v2"
V3_CONTRACT = "x1_current_market_freshness/v3"


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
        "contract_version": V1_CONTRACT,
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


def evaluate_current_market_freshness_v2(
    market_envelope: Mapping[str, Any],
    provider_history_backfill: Mapping[str, Any],
    *,
    evaluated_at: Any,
    policy: Mapping[str, Any],
    chain_corroboration: Mapping[str, Any] | None = None,
    liquidity_freshness_evidence: Mapping[str, Any] | None = None,
    rolling_activity_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose v1 price freshness with accepted field-specific current evidence.

    v1 remains unchanged and callable. v2 may promote liquidity only from the
    exact x1_ninja_liquidity_freshness/v1 contract. Rolling activity remains
    false unless a separately accepted exact rolling-window contract is supplied.
    """

    base = evaluate_current_market_freshness(
        market_envelope,
        provider_history_backfill,
        evaluated_at=evaluated_at,
        policy=policy,
    )
    fields = {
        name: dict(_mapping(base.get("fields")).get(name) or {})
        for name in FIELDS
    }

    corroboration = _mapping(chain_corroboration)
    liquidity = _mapping(liquidity_freshness_evidence)
    rolling = _mapping(rolling_activity_evidence)

    liquidity_verified = bool(
        liquidity.get("contract_version") == "x1_ninja_liquidity_freshness/v1"
        and liquidity.get("liquidity_freshness_verified") is True
        and liquidity.get("current_value_reproduced_from_fresh_chain_state") is True
        and liquidity.get("all_contributing_pools_corroborated") is True
        and liquidity.get("current_usdcx_usd_equivalence_verified") is True
        and liquidity.get("execution_authorized") is False
    )
    fields["liquidity_usd"] = {
        "freshness_verified": liquidity_verified,
        "reason": (
            "aggregate_liquidity_reproduced_from_fresh_chain_state"
            if liquidity_verified
            else "aggregate_liquidity_current_chain_proof_incomplete"
        ),
        "provider_fact_time_verified": False,
        "current_value_reproduced_from_fresh_chain_state": (
            liquidity.get("current_value_reproduced_from_fresh_chain_state") is True
        ),
        "all_contributing_pools_corroborated": (
            liquidity.get("all_contributing_pools_corroborated") is True
        ),
        "evidence_contract": liquidity.get("contract_version"),
    }

    rolling_contract_ok = (
        rolling.get("contract_version") == "x1_rolling_24h_market_activity/v1"
        and rolling.get("execution_authorized") is False
    )
    volume_verified = bool(
        rolling_contract_ok
        and rolling.get("volume_24h_freshness_verified") is True
        and rolling.get("volume_24h_window_coverage_verified") is True
        and rolling.get("volume_24h_semantics_verified") is True
    )
    tx_verified = bool(
        rolling_contract_ok
        and rolling.get("transactions_24h_freshness_verified") is True
        and rolling.get("transactions_24h_window_coverage_verified") is True
        and rolling.get("transactions_24h_semantics_verified") is True
    )
    fields["volume_24h_usd"] = {
        "freshness_verified": volume_verified,
        "reason": (
            "exact_24h_chain_window_volume_matches_provider"
            if volume_verified
            else "rolling_volume_exact_chain_window_proof_incomplete"
        ),
        "evidence_contract": rolling.get("contract_version"),
    }
    fields["transactions_24h"] = {
        "freshness_verified": tx_verified,
        "reason": (
            "exact_24h_chain_window_transaction_count_matches_provider"
            if tx_verified
            else "rolling_transactions_exact_chain_window_proof_incomplete"
        ),
        "evidence_contract": rolling.get("contract_version"),
    }

    verified_field_count = sum(
        1 for row in fields.values() if row.get("freshness_verified") is True
    )
    total_field_count = len(FIELDS)
    state = (
        "VERIFIED"
        if verified_field_count == total_field_count
        else ("PARTIAL" if verified_field_count > 0 else "NOT_VERIFIED")
    )

    limitations = [
        item
        for item in list(base.get("limitations") or [])
        if item not in {
            "liquidity_fact_time_not_verified",
            "rolling_volume_fact_time_not_verified",
            "rolling_transactions_fact_time_not_verified",
        }
    ]
    if not liquidity_verified:
        limitations.append("aggregate_liquidity_current_chain_proof_incomplete")
    if not volume_verified:
        limitations.append("rolling_volume_exact_chain_window_proof_incomplete")
    if not tx_verified:
        limitations.append("rolling_transactions_exact_chain_window_proof_incomplete")
    limitations.extend(
        [
            "provider_collection_time_is_not_promoted_to_liquidity_fact_time",
            "source_independence_separate_from_freshness",
        ]
    )

    result = dict(base)
    result.update(
        {
            "contract_version": V2_CONTRACT,
            "fields": fields,
            "verified_field_count": verified_field_count,
            "total_field_count": total_field_count,
            "freshness_state": state,
            "current_market_freshness_verified": (
                verified_field_count == total_field_count
            ),
            "chain_corroboration": dict(corroboration),
            "liquidity_freshness_evidence": dict(liquidity),
            "rolling_activity_evidence": dict(rolling),
            "limitations": list(dict.fromkeys(limitations)),
        }
    )
    return result




def evaluate_current_market_freshness_v3(
    market_envelope: Mapping[str, Any],
    provider_history_backfill: Mapping[str, Any],
    *,
    evaluated_at: Any,
    policy: Mapping[str, Any],
    chain_corroboration: Mapping[str, Any] | None = None,
    liquidity_freshness_evidence: Mapping[str, Any] | None = None,
    liquidity_freshness_evidence_v2: Mapping[str, Any] | None = None,
    rolling_activity_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Extend v2 with explicit provider-nominal and independent-USD liquidity.

    The legacy liquidity_usd field keeps the exact v2 meaning. The new fields
    may be promoted only from x1_ninja_liquidity_freshness/v2 and do not imply
    provider fact-time or source independence.
    """

    base = evaluate_current_market_freshness_v2(
        market_envelope,
        provider_history_backfill,
        evaluated_at=evaluated_at,
        policy=policy,
        chain_corroboration=chain_corroboration,
        liquidity_freshness_evidence=liquidity_freshness_evidence,
        rolling_activity_evidence=rolling_activity_evidence,
    )
    fields = {
        name: dict(row)
        for name, row in _mapping(base.get("fields")).items()
        if isinstance(row, Mapping)
    }

    split = _mapping(liquidity_freshness_evidence_v2)
    split_contract_ok = bool(
        split.get("contract_version") == "x1_ninja_liquidity_freshness/v2"
        and split.get("execution_authorized") is False
        and split.get("provider_fact_time_verified") is False
        and split.get("source_independence_verified") is False
    )

    provider_nominal_verified = bool(
        split_contract_ok
        and split.get("provider_nominal_liquidity_freshness_verified") is True
        and split.get("provider_market_matches_nominal_basis") is True
        and split.get("provider_numerical_unit") == "USDC.X_nominal_quote_basis"
    )
    independent_usd_verified = bool(
        split_contract_ok
        and split.get("independent_liquidity_usd_freshness_verified") is True
        and split.get("current_usdcx_usd_equivalence_verified") is True
    )

    fields["provider_nominal_liquidity"] = {
        "freshness_verified": provider_nominal_verified,
        "reason": (
            "provider_nominal_liquidity_reproduced_from_fresh_chain_state"
            if provider_nominal_verified
            else "provider_nominal_liquidity_current_chain_proof_incomplete"
        ),
        "value": split.get("provider_nominal_liquidity_value"),
        "unit": (
            split.get("provider_numerical_unit")
            if split_contract_ok
            else None
        ),
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "evidence_contract": split.get("contract_version"),
    }
    fields["independent_liquidity_usd"] = {
        "freshness_verified": independent_usd_verified,
        "reason": (
            "independent_current_usd_liquidity_valued_from_fresh_chain_state"
            if independent_usd_verified
            else "independent_current_usd_liquidity_proof_incomplete"
        ),
        "value": split.get("independent_liquidity_usd_value"),
        "unit": "USD" if independent_usd_verified else None,
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "evidence_contract": split.get("contract_version"),
    }

    verified_field_count = sum(
        1 for row in fields.values() if row.get("freshness_verified") is True
    )
    total_field_count = len(fields)
    state = (
        "VERIFIED"
        if verified_field_count == total_field_count
        else ("PARTIAL" if verified_field_count > 0 else "NOT_VERIFIED")
    )

    limitations = list(base.get("limitations") or [])
    if not provider_nominal_verified:
        limitations.append(
            "provider_nominal_liquidity_current_chain_proof_incomplete"
        )
    if not independent_usd_verified:
        limitations.append(
            "independent_current_usd_liquidity_proof_incomplete"
        )
    limitations.extend(
        [
            "provider_nominal_liquidity_is_not_independent_external_usd",
            "legacy_liquidity_usd_freshness_semantics_preserved_from_v2",
        ]
    )

    result = dict(base)
    result.update(
        {
            "contract_version": V3_CONTRACT,
            "fields": fields,
            "verified_field_count": verified_field_count,
            "total_field_count": total_field_count,
            "freshness_state": state,
            "current_market_freshness_verified": (
                verified_field_count == total_field_count
            ),
            "liquidity_freshness_evidence_v2": dict(split),
            "provider_nominal_liquidity_freshness_verified": (
                provider_nominal_verified
            ),
            "independent_liquidity_usd_freshness_verified": (
                independent_usd_verified
            ),
            "limitations": list(dict.fromkeys(limitations)),
            "execution_authorized": False,
        }
    )
    return result


__all__ = [
    "FIELDS",
    "V1_CONTRACT",
    "V2_CONTRACT",
    "V3_CONTRACT",
    "evaluate_current_market_freshness",
    "evaluate_current_market_freshness_v2",
    "evaluate_current_market_freshness_v3",
]
