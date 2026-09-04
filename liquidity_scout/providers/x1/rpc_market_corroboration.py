"""Deterministic X1.Ninja + X1 RPC current-market corroboration.

This contract binds the exact primary XDEX pool used by the CMIS market report
to one bounded X1.Ninja/RPC snapshot. It proves only same-observation chain
corroboration: exact pool identity, fresh RPC slot/block-time bracketing,
verified vault state, provider reserve agreement, and (when it matches) the
provider priceNative/native reserve-ratio relationship.

It does not convert RPC collection time into provider fact time and does not
by itself promote price, USD liquidity, rolling 24h volume, or rolling
transaction freshness.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.providers.x1.ninja_pooled_reserve_semantics import (
    DEFAULT_ABSOLUTE_TOLERANCE as RESERVE_ABSOLUTE_TOLERANCE,
    DEFAULT_RELATIVE_TOLERANCE as RESERVE_RELATIVE_TOLERANCE,
)
from liquidity_scout.providers.x1.ninja_price_native_semantics import (
    DEFAULT_ABSOLUTE_TOLERANCE as PRICE_ABSOLUTE_TOLERANCE,
    DEFAULT_RELATIVE_TOLERANCE as PRICE_RELATIVE_TOLERANCE,
)


VERSION = "x1_rpc_market_corroboration/v1"
DEFAULT_MAX_RPC_AGE_SECONDS = 60
DEFAULT_MAX_FUTURE_SKEW_SECONDS = 5


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _decimal(value: Any, *, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be a finite number")
    return parsed


def _positive_decimal(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _compare(
    observed: Decimal,
    expected: Decimal,
    *,
    relative_tolerance: Decimal,
    absolute_tolerance: Decimal,
) -> dict[str, Any]:
    absolute_error = abs(observed - expected)
    scale = abs(expected)
    allowed_error = max(absolute_tolerance, scale * relative_tolerance)
    relative_error = absolute_error / scale if scale else None
    return {
        "observed": format(observed, "f"),
        "expected": format(expected, "f"),
        "absolute_error": format(absolute_error, "f"),
        "relative_error": (
            format(relative_error, "e") if relative_error is not None else None
        ),
        "allowed_absolute_error": format(allowed_error, "f"),
        "within_tolerance": absolute_error <= allowed_error,
    }


def _timestamp_age(
    value: Any,
    *,
    evaluated_at: Decimal,
    max_age_seconds: int,
    max_future_skew_seconds: int,
) -> dict[str, Any]:
    try:
        observed = _decimal(value, name="block_time")
    except ValueError:
        return {"verified": False, "age_seconds": None, "reason": "block_time_unavailable"}
    age = evaluated_at - observed
    verified = (
        age <= Decimal(max_age_seconds)
        and age >= -Decimal(max_future_skew_seconds)
    )
    return {
        "verified": verified,
        "age_seconds": float(age),
        "reason": "within_policy" if verified else "outside_policy",
    }


def _primary_pool_address(market_envelope: Mapping[str, Any]) -> str | None:
    data = _mapping(market_envelope.get("data"))
    primary = _mapping(data.get("primary_pool"))
    return _text(primary.get("address"))


def _snapshot_pool(snapshot: Mapping[str, Any], address: str) -> Mapping[str, Any] | None:
    pools = snapshot.get("pools")
    if not isinstance(pools, list):
        return None
    matches = [
        row for row in pools
        if isinstance(row, Mapping) and _text(row.get("pool_address")) == address
    ]
    return matches[0] if len(matches) == 1 else None


def evaluate_rpc_market_corroboration(
    market_envelope: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    *,
    evaluated_at: Any,
    max_rpc_age_seconds: int = DEFAULT_MAX_RPC_AGE_SECONDS,
    max_future_skew_seconds: int = DEFAULT_MAX_FUTURE_SKEW_SECONDS,
) -> dict[str, Any]:
    """Evaluate one exact primary-pool provider/RPC observation fail-closed."""

    if not isinstance(market_envelope, Mapping):
        raise TypeError("market_envelope must be a mapping")
    if not isinstance(snapshot, Mapping):
        raise TypeError("snapshot must be a mapping")
    if isinstance(max_rpc_age_seconds, bool) or not isinstance(max_rpc_age_seconds, int) or max_rpc_age_seconds < 0:
        raise ValueError("max_rpc_age_seconds must be a non-negative integer")
    if isinstance(max_future_skew_seconds, bool) or not isinstance(max_future_skew_seconds, int) or max_future_skew_seconds < 0:
        raise ValueError("max_future_skew_seconds must be a non-negative integer")

    evaluated = _decimal(evaluated_at, name="evaluated_at")
    primary_pool = _primary_pool_address(market_envelope)
    snapshot_contract_ok = (
        snapshot.get("service") == "x1_ninja_price_fact_time_snapshot"
        and snapshot.get("chain") == "x1"
    )
    row = (
        _snapshot_pool(snapshot, primary_pool)
        if snapshot_contract_ok and primary_pool
        else None
    )
    primary_pool_identity_verified = bool(
        primary_pool
        and row is not None
        and row.get("status") == "ok"
    )

    bracket = _mapping(snapshot.get("rpc_slot_bracket"))
    before = _mapping(bracket.get("before"))
    after = _mapping(bracket.get("after"))
    before_slot = before.get("slot")
    after_slot = after.get("slot")
    slots_valid = bool(
        isinstance(before_slot, int)
        and not isinstance(before_slot, bool)
        and isinstance(after_slot, int)
        and not isinstance(after_slot, bool)
        and before_slot >= 0
        and after_slot >= before_slot
    )
    before_age = _timestamp_age(
        before.get("block_time"),
        evaluated_at=evaluated,
        max_age_seconds=max_rpc_age_seconds,
        max_future_skew_seconds=max_future_skew_seconds,
    )
    after_age = _timestamp_age(
        after.get("block_time"),
        evaluated_at=evaluated,
        max_age_seconds=max_rpc_age_seconds,
        max_future_skew_seconds=max_future_skew_seconds,
    )
    block_times_verified = bool(
        before.get("block_time_verified") is True
        and after.get("block_time_verified") is True
    )
    rpc_slot_bracket_verified = bool(slots_valid and block_times_verified)
    rpc_block_time_fresh = bool(
        rpc_slot_bracket_verified
        and before_age["verified"] is True
        and after_age["verified"] is True
    )

    rpc = _mapping(row.get("rpc")) if row is not None else {}
    provider = _mapping(row.get("provider")) if row is not None else {}
    rpc_state_verified = bool(
        primary_pool_identity_verified
        and rpc.get("rpc_reserve_ratio_verified") is True
        and _text(rpc.get("mint_0"))
        and _text(rpc.get("mint_1"))
        and _text(rpc.get("vault_0"))
        and _text(rpc.get("vault_1"))
    )

    reserve_comparisons: dict[str, Any] = {}
    price_comparison: dict[str, Any] = {}
    try:
        pooled_base = _positive_decimal(provider.get("pooledBase"), name="pooledBase")
        pooled_quote = _positive_decimal(provider.get("pooledQuote"), name="pooledQuote")
        rpc_reserve_0 = _positive_decimal(rpc.get("gross_reserve_0"), name="gross_reserve_0")
        rpc_reserve_1 = _positive_decimal(rpc.get("gross_reserve_1"), name="gross_reserve_1")
        reserve_comparisons = {
            "pooledBase_vs_rpc_vault_1": _compare(
                pooled_base,
                rpc_reserve_1,
                relative_tolerance=RESERVE_RELATIVE_TOLERANCE,
                absolute_tolerance=RESERVE_ABSOLUTE_TOLERANCE,
            ),
            "pooledQuote_vs_rpc_vault_0": _compare(
                pooled_quote,
                rpc_reserve_0,
                relative_tolerance=RESERVE_RELATIVE_TOLERANCE,
                absolute_tolerance=RESERVE_ABSOLUTE_TOLERANCE,
            ),
        }
    except ValueError:
        reserve_comparisons = {}

    provider_reserve_values_match_rpc = bool(
        rpc_state_verified
        and reserve_comparisons
        and all(value.get("within_tolerance") is True for value in reserve_comparisons.values())
    )

    try:
        provider_price = _positive_decimal(provider.get("priceNative"), name="priceNative")
        rpc_ratio = _positive_decimal(
            rpc.get("gross_quote_per_base_ratio"),
            name="gross_quote_per_base_ratio",
        )
        price_comparison = _compare(
            provider_price,
            rpc_ratio,
            relative_tolerance=PRICE_RELATIVE_TOLERANCE,
            absolute_tolerance=PRICE_ABSOLUTE_TOLERANCE,
        )
    except ValueError:
        price_comparison = {}

    provider_price_native_matches_rpc_ratio = bool(
        rpc_state_verified
        and price_comparison.get("within_tolerance") is True
    )

    reserve_chain_corroboration_verified = bool(
        primary_pool_identity_verified
        and rpc_block_time_fresh
        and rpc_state_verified
        and provider_reserve_values_match_rpc
    )
    price_native_chain_corroboration_verified = bool(
        reserve_chain_corroboration_verified
        and provider_price_native_matches_rpc_ratio
    )

    failures: list[str] = []
    if not snapshot_contract_ok:
        failures.append("snapshot_contract_unverified")
    if not primary_pool_identity_verified:
        failures.append("primary_pool_identity_unverified")
    if not rpc_slot_bracket_verified:
        failures.append("rpc_slot_bracket_unverified")
    if not rpc_block_time_fresh:
        failures.append("rpc_block_time_not_fresh")
    if not rpc_state_verified:
        failures.append("rpc_vault_reserve_state_unverified")
    if not provider_reserve_values_match_rpc:
        failures.append("provider_reserve_values_do_not_match_rpc")
    if not provider_price_native_matches_rpc_ratio:
        failures.append("provider_price_native_does_not_match_rpc_ratio")

    return {
        "contract_version": VERSION,
        "chain": "x1",
        "scope": "exact_primary_xdex_pool_current_state",
        "evaluated_at": float(evaluated),
        "primary_pool_address": primary_pool,
        "primary_pool_identity_verified": primary_pool_identity_verified,
        "rpc_slot_bracket_verified": rpc_slot_bracket_verified,
        "rpc_block_time_fresh": rpc_block_time_fresh,
        "rpc_slot_bracket": {
            "before": {
                "slot": before_slot if isinstance(before_slot, int) and not isinstance(before_slot, bool) else None,
                "block_time": before.get("block_time"),
                "age_seconds": before_age.get("age_seconds"),
            },
            "after": {
                "slot": after_slot if isinstance(after_slot, int) and not isinstance(after_slot, bool) else None,
                "block_time": after.get("block_time"),
                "age_seconds": after_age.get("age_seconds"),
            },
        },
        "vault_identity_verified": rpc_state_verified,
        "reserve_state_verified": rpc_state_verified,
        "provider_reserve_values_match_rpc": provider_reserve_values_match_rpc,
        "reserve_comparisons": reserve_comparisons,
        "provider_price_native_matches_rpc_ratio": provider_price_native_matches_rpc_ratio,
        "price_native_comparison": price_comparison,
        "reserve_chain_corroboration_verified": reserve_chain_corroboration_verified,
        "price_native_chain_corroboration_verified": price_native_chain_corroboration_verified,
        "chain_corroboration_verified": price_native_chain_corroboration_verified,
        "provider_fact_time_verified": False,
        "price_usd_freshness_promoted": False,
        "liquidity_usd_freshness_promoted": False,
        "volume_24h_freshness_promoted": False,
        "transactions_24h_freshness_promoted": False,
        "freshness_verified": False,
        "same_fact_corroboration_is_source_independence": False,
        "source_independence_verified": False,
        "failures": failures,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "DEFAULT_MAX_FUTURE_SKEW_SECONDS",
    "DEFAULT_MAX_RPC_AGE_SECONDS",
    "VERSION",
    "evaluate_rpc_market_corroboration",
]
