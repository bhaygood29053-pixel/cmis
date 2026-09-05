"""Current aggregate X1.Ninja liquidity freshness evidence for CMIS #459.

The accepted #461/#470 semantic proof established a bounded formula for exact
wrapped-XNT pools. This module applies that accepted formula to *current* X1 RPC
reserve state across the exact LP set contributing to one CMIS market report.

Freshness is proven by reproducing the current provider liquidity value from
fresh chain state and a fresh independently-qualified XNT/USD basis. Provider
catalog collection time is never promoted into provider fact time.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.providers.x1.current_usdcx_usd_equivalence import (
    SCHEMA as USDCX_EQUIVALENCE_SCHEMA,
    X1_USDC_X_MINT,
)
from liquidity_scout.providers.x1.ninja_liquidity_usd_semantics import (
    DEFAULT_ABSOLUTE_TOLERANCE_USD,
    DEFAULT_RELATIVE_TOLERANCE,
    VERSION as LIQUIDITY_SEMANTICS_VERSION,
)
from liquidity_scout.providers.x1.ninja_pooled_reserve_semantics import (
    DEFAULT_ABSOLUTE_TOLERANCE as RESERVE_ABSOLUTE_TOLERANCE,
    DEFAULT_RELATIVE_TOLERANCE as RESERVE_RELATIVE_TOLERANCE,
)
from liquidity_scout.providers.x1.xdex_price_history_import import WRAPPED_XNT_MINT


VERSION = "x1_ninja_liquidity_freshness/v1"
REFERENCE_POOL_ADDRESS = "CAJeVEoSm1QQZccnCqYu9cnNF7TTD2fcUA3E5HQoxRvR"
ACCEPTED_SEMANTIC_PR = 470
ACCEPTED_SEMANTIC_MERGE_COMMIT = "e39182295d1c6c7da295280ef05a0bd457f12d93"
ACCEPTED_SEMANTIC_LIVE_RUN = 68
DEFAULT_MAX_POOLS = 150
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


def _positive(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _nonnegative(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name)
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def _comparison(
    observed: Decimal,
    expected: Decimal,
    *,
    relative_tolerance: Decimal,
    absolute_tolerance: Decimal,
) -> dict[str, Any]:
    error = abs(observed - expected)
    allowed = max(absolute_tolerance, abs(expected) * relative_tolerance)
    relative = (
        error / abs(expected)
        if expected != 0
        else (Decimal(0) if error == 0 else None)
    )
    return {
        "observed": format(observed, "f"),
        "expected": format(expected, "f"),
        "absolute_error": format(error, "f"),
        "relative_error": format(relative, "e") if relative is not None else None,
        "allowed_absolute_error": format(allowed, "f"),
        "within_tolerance": error <= allowed,
    }


def _rpc_bracket(
    snapshot: Mapping[str, Any],
    *,
    evaluated_at: float,
    max_rpc_age_seconds: int,
    max_future_skew_seconds: int,
) -> dict[str, Any]:
    bracket = _mapping(snapshot.get("rpc_slot_bracket"))
    rows = []
    for label in ("before", "after"):
        raw = _mapping(bracket.get(label))
        slot = raw.get("slot")
        block_time = raw.get("block_time")
        verified = (
            isinstance(slot, int)
            and not isinstance(slot, bool)
            and slot >= 0
            and raw.get("block_time_verified") is True
        )
        age = None
        fresh = False
        try:
            if verified:
                bt = float(block_time)
                age = float(evaluated_at) - bt
                fresh = (
                    age <= float(max_rpc_age_seconds)
                    and age >= -float(max_future_skew_seconds)
                )
        except (TypeError, ValueError):
            fresh = False
        rows.append(
            {
                "label": label,
                "slot": slot,
                "block_time": block_time,
                "block_time_verified": verified,
                "age_seconds": age,
                "fresh": fresh,
            }
        )

    ordered = bool(
        len(rows) == 2
        and isinstance(rows[0]["slot"], int)
        and isinstance(rows[1]["slot"], int)
        and rows[0]["slot"] <= rows[1]["slot"]
    )
    verified = bool(ordered and all(row["block_time_verified"] for row in rows))
    fresh = bool(verified and all(row["fresh"] for row in rows))
    return {
        "slot_bracket_verified": verified,
        "rpc_block_time_fresh": fresh,
        "rows": rows,
        "max_rpc_age_seconds": max_rpc_age_seconds,
        "max_future_skew_seconds": max_future_skew_seconds,
    }


def _contributing_pool_addresses(market_envelope: Mapping[str, Any]) -> list[str]:
    data = _mapping(market_envelope.get("data"))
    raw = data.get("contributing_pools")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return []
    addresses = []
    seen = set()
    for row in raw:
        if not isinstance(row, Mapping):
            return []
        address = _text(row.get("address"))
        if not address or address in seen:
            return []
        seen.add(address)
        addresses.append(address)
    return addresses


def _snapshot_index(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = snapshot.get("pools")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for row in raw:
        if not isinstance(row, Mapping):
            continue
        address = _text(row.get("pool_address"))
        if address and address not in result:
            result[address] = row
    return result


def _current_usdc_usd(equivalence: Mapping[str, Any]) -> Decimal:
    if equivalence.get("schema") != USDCX_EQUIVALENCE_SCHEMA:
        raise ValueError("current USDC.X/USD evidence contract is not accepted")
    required = (
        "route_identity_verified",
        "source_usdc_usd_price_unit_verified",
        "source_usdc_usd_price_identity_verified",
        "source_usdc_usd_price_fresh",
        "source_usdc_within_usd_tolerance",
        "destination_representation_value_equivalence_verified",
        "current_usdcx_usd_equivalence_verified",
    )
    missing = [name for name in required if equivalence.get(name) is not True]
    if missing:
        raise ValueError(
            "current USDC.X/USD evidence missing gate(s): " + ", ".join(missing)
        )
    return _positive(
        equivalence.get("source_usdc_usd_price"),
        name="fresh source USDC/USD price",
    )


def _xnt_usd_from_reference(
    reference_row: Mapping[str, Any],
    *,
    usdc_usd: Decimal,
) -> tuple[Decimal, dict[str, Any]]:
    if reference_row.get("status") != "ok":
        raise ValueError("reference pool snapshot is unavailable")
    rpc = _mapping(reference_row.get("rpc"))
    if rpc.get("rpc_reserve_ratio_verified") is not True:
        raise ValueError("reference RPC reserve ratio is unverified")

    mint_0 = _text(rpc.get("mint_0"))
    mint_1 = _text(rpc.get("mint_1"))
    reserve_0 = _positive(rpc.get("gross_reserve_0"), name="reference reserve_0")
    reserve_1 = _positive(rpc.get("gross_reserve_1"), name="reference reserve_1")

    if {mint_0, mint_1} != {WRAPPED_XNT_MINT, X1_USDC_X_MINT}:
        raise ValueError("reference pool mint identity mismatch")

    if mint_0 == WRAPPED_XNT_MINT:
        xnt_reserve, usdcx_reserve = reserve_0, reserve_1
    else:
        xnt_reserve, usdcx_reserve = reserve_1, reserve_0

    usdcx_per_xnt = usdcx_reserve / xnt_reserve
    xnt_usd = usdcx_per_xnt * usdc_usd
    return xnt_usd, {
        "reference_pool_address": REFERENCE_POOL_ADDRESS,
        "mint_0": mint_0,
        "mint_1": mint_1,
        "xnt_reserve": format(xnt_reserve, "f"),
        "usdcx_reserve": format(usdcx_reserve, "f"),
        "usdcx_per_xnt": format(usdcx_per_xnt, "f"),
        "fresh_usdc_usd": format(usdc_usd, "f"),
        "derived_xnt_usd": format(xnt_usd, "f"),
        "reference_pool_identity_verified": True,
        "reference_reserves_verified": True,
    }


def evaluate_x1_ninja_liquidity_freshness(
    *,
    market_envelope: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    current_usdcx_usd_equivalence: Mapping[str, Any],
    evaluated_at: float,
    max_pools: int = DEFAULT_MAX_POOLS,
    max_rpc_age_seconds: int = DEFAULT_MAX_RPC_AGE_SECONDS,
    max_future_skew_seconds: int = DEFAULT_MAX_FUTURE_SKEW_SECONDS,
    relative_tolerance: Any = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance_usd: Any = DEFAULT_ABSOLUTE_TOLERANCE_USD,
    reserve_relative_tolerance: Any = RESERVE_RELATIVE_TOLERANCE,
    reserve_absolute_tolerance: Any = RESERVE_ABSOLUTE_TOLERANCE,
) -> dict[str, Any]:
    """Reproduce current aggregate liquidity from exact fresh chain state."""

    if isinstance(max_pools, bool) or not isinstance(max_pools, int):
        raise ValueError("max_pools must be an integer")
    if max_pools < 1 or max_pools > 500:
        raise ValueError("max_pools must be between 1 and 500")

    rel = _nonnegative(relative_tolerance, name="relative_tolerance")
    abs_usd = _nonnegative(absolute_tolerance_usd, name="absolute_tolerance_usd")
    reserve_rel = _nonnegative(
        reserve_relative_tolerance,
        name="reserve_relative_tolerance",
    )
    reserve_abs = _nonnegative(
        reserve_absolute_tolerance,
        name="reserve_absolute_tolerance",
    )

    data = _mapping(market_envelope.get("data"))
    completeness = _mapping(data.get("completeness"))
    addresses = _contributing_pool_addresses(market_envelope)
    lp_count = data.get("lp_count", data.get("#LPs"))
    try:
        lp_count_int = int(lp_count)
    except (TypeError, ValueError):
        lp_count_int = -1

    failures: list[str] = []
    if completeness.get("liquidity") is not True:
        failures.append("market_liquidity_incomplete")
    if not addresses:
        failures.append("contributing_pool_set_unavailable")
    if lp_count_int != len(addresses):
        failures.append("contributing_pool_count_mismatch")
    if len(addresses) > max_pools:
        failures.append("contributing_pool_count_exceeds_corroboration_bound")

    bracket = _rpc_bracket(
        snapshot,
        evaluated_at=evaluated_at,
        max_rpc_age_seconds=max_rpc_age_seconds,
        max_future_skew_seconds=max_future_skew_seconds,
    )
    if bracket["slot_bracket_verified"] is not True:
        failures.append("rpc_slot_bracket_unverified")
    if bracket["rpc_block_time_fresh"] is not True:
        failures.append("rpc_block_time_stale_or_unverified")

    index = _snapshot_index(snapshot)
    required_snapshot_addresses = set(addresses) | {REFERENCE_POOL_ADDRESS}
    if not required_snapshot_addresses.issubset(index):
        failures.append("snapshot_missing_required_pool")

    usdc_usd = None
    xnt_usd = None
    reference = {}
    try:
        usdc_usd = _current_usdc_usd(current_usdcx_usd_equivalence)
        reference_row = index.get(REFERENCE_POOL_ADDRESS)
        if not isinstance(reference_row, Mapping):
            raise ValueError("reference pool snapshot missing")
        xnt_usd, reference = _xnt_usd_from_reference(
            reference_row,
            usdc_usd=usdc_usd,
        )
    except ValueError as exc:
        failures.append(f"xnt_usd_basis_unverified:{exc}")

    pool_results = []
    provider_total = Decimal(0)
    derived_total = Decimal(0)

    if xnt_usd is not None:
        for address in addresses:
            row = index.get(address)
            reasons: list[str] = []
            if not isinstance(row, Mapping) or row.get("status") != "ok":
                pool_results.append(
                    {
                        "pool_address": address,
                        "liquidity_freshness_verified": False,
                        "rejection_reasons": ["current_pool_snapshot_unavailable"],
                    }
                )
                continue

            provider = _mapping(row.get("provider"))
            rpc = _mapping(row.get("rpc"))
            try:
                if rpc.get("rpc_reserve_ratio_verified") is not True:
                    raise ValueError("rpc_reserve_ratio_unverified")
                mint_0 = _text(rpc.get("mint_0"))
                mint_1 = _text(rpc.get("mint_1"))
                if mint_0 != WRAPPED_XNT_MINT or mint_1 in {None, WRAPPED_XNT_MINT}:
                    raise ValueError(
                        "accepted_liquidity_semantics_require_wrapped_xnt_in_mint_0"
                    )

                xnt_reserve = _positive(
                    rpc.get("gross_reserve_0"),
                    name="rpc wrapped-XNT reserve",
                )
                asset_reserve = _positive(
                    rpc.get("gross_reserve_1"),
                    name="rpc asset reserve",
                )
                pooled_base = _positive(
                    provider.get("pooledBase"),
                    name="provider pooledBase",
                )
                pooled_quote = _positive(
                    provider.get("pooledQuote"),
                    name="provider pooledQuote",
                )
                provider_liquidity = _positive(
                    provider.get("liquidity"),
                    name="provider liquidity",
                )

                base_cmp = _comparison(
                    pooled_base,
                    asset_reserve,
                    relative_tolerance=reserve_rel,
                    absolute_tolerance=reserve_abs,
                )
                quote_cmp = _comparison(
                    pooled_quote,
                    xnt_reserve,
                    relative_tolerance=reserve_rel,
                    absolute_tolerance=reserve_abs,
                )
                if base_cmp["within_tolerance"] is not True:
                    reasons.append("provider_pooledBase_does_not_match_rpc_asset_reserve")
                if quote_cmp["within_tolerance"] is not True:
                    reasons.append("provider_pooledQuote_does_not_match_rpc_xnt_reserve")

                native_per_asset = xnt_reserve / asset_reserve
                asset_usd = native_per_asset * xnt_usd
                asset_side = asset_reserve * asset_usd
                xnt_side = xnt_reserve * xnt_usd
                derived_liquidity = asset_side + xnt_side
                liquidity_cmp = _comparison(
                    provider_liquidity,
                    derived_liquidity,
                    relative_tolerance=rel,
                    absolute_tolerance=abs_usd,
                )
                if liquidity_cmp["within_tolerance"] is not True:
                    reasons.append(
                        "provider_liquidity_does_not_match_current_rpc_valuation"
                    )

                provider_total += provider_liquidity
                derived_total += derived_liquidity
                pool_results.append(
                    {
                        "pool_address": address,
                        "mint_0": mint_0,
                        "mint_1": mint_1,
                        "rpc_xnt_reserve": format(xnt_reserve, "f"),
                        "rpc_asset_reserve": format(asset_reserve, "f"),
                        "derived_native_per_asset": format(native_per_asset, "f"),
                        "derived_asset_usd": format(asset_usd, "f"),
                        "derived_liquidity_usd": format(derived_liquidity, "f"),
                        "provider_liquidity_usd": format(provider_liquidity, "f"),
                        "pooledBase_rpc_comparison": base_cmp,
                        "pooledQuote_rpc_comparison": quote_cmp,
                        "liquidity_comparison": liquidity_cmp,
                        "liquidity_freshness_verified": not reasons,
                        "rejection_reasons": reasons,
                    }
                )
            except ValueError as exc:
                pool_results.append(
                    {
                        "pool_address": address,
                        "liquidity_freshness_verified": False,
                        "rejection_reasons": [str(exc)],
                    }
                )

    all_pools_verified = bool(
        addresses
        and len(pool_results) == len(addresses)
        and all(row.get("liquidity_freshness_verified") is True for row in pool_results)
    )

    market_liquidity_cmp = None
    provider_aggregate_cmp = None
    try:
        market_liquidity = _nonnegative(
            data.get("liquidity_usd"),
            name="market aggregate liquidity",
        )
        market_liquidity_cmp = _comparison(
            market_liquidity,
            derived_total,
            relative_tolerance=rel,
            absolute_tolerance=abs_usd,
        )
        provider_aggregate_cmp = _comparison(
            market_liquidity,
            provider_total,
            relative_tolerance=rel,
            absolute_tolerance=abs_usd,
        )
        if market_liquidity_cmp["within_tolerance"] is not True:
            failures.append("market_liquidity_does_not_match_derived_current_total")
        if provider_aggregate_cmp["within_tolerance"] is not True:
            failures.append("market_liquidity_does_not_match_current_provider_pool_sum")
    except ValueError as exc:
        failures.append(f"market_liquidity_unusable:{exc}")

    if not all_pools_verified:
        failures.append("one_or_more_contributing_pools_unverified")

    verified = not failures
    return {
        "contract_version": VERSION,
        "chain": "x1",
        "status": "verified" if verified else "partial",
        "scope": "exact_market_report_contributing_pool_set",
        "accepted_liquidity_semantics": {
            "contract": LIQUIDITY_SEMANTICS_VERSION,
            "acceptance_pr": ACCEPTED_SEMANTIC_PR,
            "acceptance_merge_commit": ACCEPTED_SEMANTIC_MERGE_COMMIT,
            "acceptance_live_run": ACCEPTED_SEMANTIC_LIVE_RUN,
            "formula_scope": "exact_wrapped_xnt_mint_0_pools_only",
            "semantic_acceptance_verified": True,
        },
        "contributing_pool_count": len(addresses),
        "max_pool_count": max_pools,
        "all_contributing_pools_corroborated": all_pools_verified,
        "rpc_freshness": bracket,
        "current_usdcx_usd_equivalence_verified": (
            current_usdcx_usd_equivalence.get(
                "current_usdcx_usd_equivalence_verified"
            )
            is True
        ),
        "xnt_usd_basis": reference,
        "pool_results": pool_results,
        "provider_pool_liquidity_sum_usd": format(provider_total, "f"),
        "derived_current_liquidity_sum_usd": format(derived_total, "f"),
        "market_vs_provider_aggregate": provider_aggregate_cmp,
        "market_vs_derived_current_aggregate": market_liquidity_cmp,
        "current_value_reproduced_from_fresh_chain_state": verified,
        "provider_fact_time_verified": False,
        "liquidity_freshness_verified": verified,
        "source_independence_verified": False,
        "failures": list(dict.fromkeys(failures)),
        "cmis_promotable": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "ACCEPTED_SEMANTIC_LIVE_RUN",
    "ACCEPTED_SEMANTIC_MERGE_COMMIT",
    "ACCEPTED_SEMANTIC_PR",
    "DEFAULT_MAX_POOLS",
    "DEFAULT_MAX_RPC_AGE_SECONDS",
    "DEFAULT_MAX_FUTURE_SKEW_SECONDS",
    "REFERENCE_POOL_ADDRESS",
    "VERSION",
    "evaluate_x1_ninja_liquidity_freshness",
]
