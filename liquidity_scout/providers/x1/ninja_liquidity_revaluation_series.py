"""Aggregate repeated X1.Ninja liquidity revaluation evidence.

This policy sits above x1_ninja_liquidity_revaluation/v1. It separates:

1. repeated provider-internal revaluation support;
2. repeated same-fact alignment to an independent X1 RPC XNT/USDC.X
   reserve-ratio reference;
3. final USD-liquidity semantics, which additionally requires a separate
   current USDC.X/USD equivalence proof and at least five distinct pools.

The policy never promotes freshness, source independence, CMIS/public-service
use, or execution authority by itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA = "x1_ninja_liquidity_revaluation_series.v1"
WRAPPED_XNT_MINT = "So11111111111111111111111111111111111111112"
USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
REFERENCE_SOURCE = "x1_rpc_exact_pool_reserve_ratio"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def evaluate_ninja_liquidity_revaluation_series(
    events: Sequence[Mapping[str, Any]],
    *,
    current_usdcx_usd_equivalence_verified: bool = False,
    minimum_repeated_events: int = 3,
    minimum_repeated_pools: int = 2,
    minimum_usd_semantic_pools: int = 5,
) -> dict[str, Any]:
    """Evaluate repeated event evidence without inventing fact-time or USD truth."""

    required_events = _positive_int(
        minimum_repeated_events,
        name="minimum_repeated_events",
    )
    required_repeated_pools = _positive_int(
        minimum_repeated_pools,
        name="minimum_repeated_pools",
    )
    required_usd_pools = _positive_int(
        minimum_usd_semantic_pools,
        name="minimum_usd_semantic_pools",
    )
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
        raise TypeError("events must be a sequence of mappings")

    normalized = []
    seen_keys: set[str] = set()
    duplicate_keys: list[str] = []

    for index, raw in enumerate(events):
        if not isinstance(raw, Mapping):
            raise TypeError(f"events[{index}] must be a mapping")

        event_key = _text(raw.get("event_key"))
        pool_address = _text(raw.get("pool_address"))
        if event_key is None:
            raise ValueError(f"events[{index}].event_key is required")
        if pool_address is None:
            raise ValueError(f"events[{index}].pool_address is required")
        if event_key in seen_keys:
            duplicate_keys.append(event_key)
        seen_keys.add(event_key)

        revaluation = _mapping(
            raw.get("revaluation") or raw.get("price_only_revaluation")
        )
        reference = _mapping(raw.get("reference_alignment"))

        event_revaluation_verified = bool(
            revaluation.get("price_only_liquidity_revaluation_verified") is True
            and revaluation.get("provider_internal_liquidity_formula_supported")
            is True
            and revaluation.get("liquidity_usd_semantics_verified") is False
            and revaluation.get("liquidity_freshness_verified") is False
            and revaluation.get("cmis_promotable") is False
            and revaluation.get("execution_authorized") is False
        )

        exact_reference_identity = bool(
            reference.get("source") == REFERENCE_SOURCE
            and reference.get("base_mint") == WRAPPED_XNT_MINT
            and reference.get("quote_mint") == USDC_X_MINT
            and reference.get("exact_pool_identity_verified") is True
            and reference.get("rpc_reserves_verified") is True
        )
        reference_time_verified = bool(
            reference.get("reference_fact_time_verified") is True
            and reference.get("same_fact_temporal_alignment_verified") is True
        )
        numerical_alignment_verified = bool(
            reference.get("provider_reference_price_matches_rpc") is True
        )
        same_fact_reference_verified = bool(
            event_revaluation_verified
            and exact_reference_identity
            and reference_time_verified
            and numerical_alignment_verified
        )

        normalized.append(
            {
                "event_key": event_key,
                "pool_address": pool_address,
                "event_revaluation_verified": event_revaluation_verified,
                "exact_reference_identity_verified": exact_reference_identity,
                "reference_fact_time_verified": reference_time_verified,
                "reference_price_alignment_verified": numerical_alignment_verified,
                "same_fact_reference_verified": same_fact_reference_verified,
            }
        )

    unique_events = not duplicate_keys
    verified_revaluation_rows = [
        row for row in normalized if row["event_revaluation_verified"]
    ]
    same_fact_rows = [
        row for row in normalized if row["same_fact_reference_verified"]
    ]

    verified_event_count = len(verified_revaluation_rows)
    verified_pool_count = len(
        {row["pool_address"] for row in verified_revaluation_rows}
    )
    same_fact_event_count = len(same_fact_rows)
    same_fact_pool_count = len(
        {row["pool_address"] for row in same_fact_rows}
    )

    repeated_revaluation_supported = bool(
        unique_events
        and verified_event_count >= required_events
        and verified_pool_count >= required_repeated_pools
    )

    liquidity_fact_time_verified = bool(
        repeated_revaluation_supported
        and same_fact_event_count >= required_events
        and same_fact_pool_count >= required_repeated_pools
    )

    usd_equivalence = current_usdcx_usd_equivalence_verified is True
    x1_ninja_liquidity_usd_semantics_verified = bool(
        liquidity_fact_time_verified
        and usd_equivalence
        and same_fact_pool_count >= required_usd_pools
    )

    missing_gates = []
    if not unique_events:
        missing_gates.append("unique_event_keys")
    if verified_event_count < required_events:
        missing_gates.append("minimum_verified_revaluation_events")
    if verified_pool_count < required_repeated_pools:
        missing_gates.append("minimum_distinct_revaluation_pools")
    if same_fact_event_count < required_events:
        missing_gates.append("minimum_same_fact_reference_events")
    if same_fact_pool_count < required_repeated_pools:
        missing_gates.append("minimum_same_fact_reference_pools")
    if not usd_equivalence:
        missing_gates.append("current_usdcx_usd_equivalence")
    if same_fact_pool_count < required_usd_pools:
        missing_gates.append("minimum_five_distinct_usd_semantic_pools")

    return {
        "schema": SCHEMA,
        "chain": "x1",
        "status": (
            "verified"
            if x1_ninja_liquidity_usd_semantics_verified
            else "partial"
        ),
        "event_count": len(normalized),
        "unique_event_keys": unique_events,
        "duplicate_event_keys": sorted(set(duplicate_keys)),
        "verified_revaluation_event_count": verified_event_count,
        "verified_revaluation_pool_count": verified_pool_count,
        "same_fact_reference_event_count": same_fact_event_count,
        "same_fact_reference_pool_count": same_fact_pool_count,
        "minimum_repeated_events": required_events,
        "minimum_repeated_pools": required_repeated_pools,
        "minimum_usd_semantic_pools": required_usd_pools,
        "repeated_revaluation_pattern_supported": repeated_revaluation_supported,
        "liquidity_fact_time_verified": liquidity_fact_time_verified,
        "current_usdcx_usd_equivalence_verified": usd_equivalence,
        "x1_ninja_liquidity_usd_semantics_verified": (
            x1_ninja_liquidity_usd_semantics_verified
        ),
        "events": normalized,
        "missing_gates": missing_gates,
        "liquidity_freshness_verified": False,
        "source_independence_verified": False,
        "cmis_promotable": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "REFERENCE_SOURCE",
    "SCHEMA",
    "USDC_X_MINT",
    "WRAPPED_XNT_MINT",
    "evaluate_ninja_liquidity_revaluation_series",
]
