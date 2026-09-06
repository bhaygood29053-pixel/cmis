"""Versioned X1.Ninja liquidity freshness semantics for CMIS #517.

v2 preserves the accepted v1 evaluator unchanged and adds two explicitly
separate current-value claims:

- provider nominal liquidity freshness in the provider's USDC.X quote basis;
- independently valued current USD liquidity freshness.

A mismatch between those two correctly scoped values does not invalidate either
claim by itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.providers.x1.liquidity_freshness import (
    POOL_SCOPE_VERSION,
    evaluate_x1_ninja_liquidity_freshness,
)
from liquidity_scout.providers.x1.ninja_liquidity_unit_semantics import (
    evaluate_x1_ninja_liquidity_unit_semantics,
)


VERSION = "x1_ninja_liquidity_freshness/v2"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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


def _snapshot_provider_index(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = snapshot.get("pools")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        address = str(raw.get("pool_address") or "").strip()
        provider = _mapping(raw.get("provider"))
        if address and provider and address not in result:
            result[address] = provider
    return result


def evaluate_x1_ninja_liquidity_freshness_v2(
    *,
    market_envelope: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    current_usdcx_usd_equivalence: Mapping[str, Any],
    pool_scope_evidence: Mapping[str, Any],
    evaluated_at: float,
    max_pools: int = 150,
) -> dict[str, Any]:
    """Produce separate nominal-provider and independent-USD freshness claims."""

    legacy = evaluate_x1_ninja_liquidity_freshness(
        market_envelope=market_envelope,
        snapshot=snapshot,
        current_usdcx_usd_equivalence=current_usdcx_usd_equivalence,
        pool_scope_evidence=pool_scope_evidence,
        evaluated_at=evaluated_at,
        max_pools=max_pools,
    )

    failures: list[str] = []
    scope = _mapping(pool_scope_evidence)
    scope_verified = bool(
        scope.get("contract_version") == POOL_SCOPE_VERSION
        and scope.get("provider_scoped_pool_universe_verified") is True
        and scope.get("execution_authorized") is False
    )
    if not scope_verified:
        failures.append("provider_scoped_pool_universe_unverified")

    rpc = _mapping(legacy.get("rpc_freshness"))
    rpc_fresh = bool(
        rpc.get("slot_bracket_verified") is True
        and rpc.get("rpc_block_time_fresh") is True
    )
    if not rpc_fresh:
        failures.append("rpc_current_state_freshness_unverified")

    reference = _mapping(legacy.get("xnt_usd_basis"))
    reference_identity_verified = bool(
        reference.get("reference_pool_identity_verified") is True
        and reference.get("reference_reserves_verified") is True
    )
    if not reference_identity_verified:
        failures.append("xnt_usdcx_reference_unverified")

    provider_xnt_price = snapshot.get("provider_xnt_price_usd")
    try:
        provider_xnt_price_dec = _decimal(
            provider_xnt_price,
            name="snapshot provider_xnt_price_usd",
        )
    except ValueError as exc:
        provider_xnt_price_dec = None
        failures.append(f"provider_xnt_reference_unavailable:{exc}")

    usdcx_equivalence_verified = (
        current_usdcx_usd_equivalence.get(
            "current_usdcx_usd_equivalence_verified"
        )
        is True
    )
    if not usdcx_equivalence_verified:
        failures.append("current_usdcx_usd_equivalence_unverified")

    try:
        reference_ratio = _decimal(
            reference.get("usdcx_per_xnt"),
            name="reference usdcx_per_xnt",
        )
        source_usdc_usd = _decimal(
            reference.get("fresh_usdc_usd"),
            name="fresh source USDC/USD",
        )
    except ValueError as exc:
        reference_ratio = None
        source_usdc_usd = None
        failures.append(f"independent_usd_basis_unavailable:{exc}")

    provider_index = _snapshot_provider_index(snapshot)
    pool_rows = legacy.get("pool_results")
    pool_rows = (
        list(pool_rows)
        if isinstance(pool_rows, Sequence)
        and not isinstance(pool_rows, (str, bytes, bytearray))
        else []
    )

    unit_results: list[dict[str, Any]] = []
    provider_nominal_total = Decimal(0)
    independent_usd_total = Decimal(0)

    for row in pool_rows:
        if not isinstance(row, Mapping):
            continue
        address = str(row.get("pool_address") or "").strip()
        provider = provider_index.get(address)
        reasons: list[str] = []

        if not address or not isinstance(provider, Mapping):
            unit_results.append(
                {
                    "pool_address": address or None,
                    "provider_nominal_liquidity_freshness_verified": False,
                    "independent_liquidity_usd_freshness_verified": False,
                    "rejection_reasons": ["provider_snapshot_row_unavailable"],
                }
            )
            continue

        pooled_base_cmp = _mapping(row.get("pooledBase_rpc_comparison"))
        pooled_quote_cmp = _mapping(row.get("pooledQuote_rpc_comparison"))
        reserve_mapping_verified = bool(
            pooled_base_cmp.get("within_tolerance") is True
            and pooled_quote_cmp.get("within_tolerance") is True
        )
        if not reserve_mapping_verified:
            reasons.append("provider_pooled_reserves_do_not_match_rpc")

        try:
            if provider_xnt_price_dec is None:
                raise ValueError("provider XNT reference unavailable")
            if reference_ratio is None or source_usdc_usd is None:
                raise ValueError("independent reference basis unavailable")

            semantic = evaluate_x1_ninja_liquidity_unit_semantics(
                provider_liquidity=provider.get("liquidity"),
                provider_xnt_price_usd=provider_xnt_price_dec,
                rpc_xnt_reserve=row.get("rpc_xnt_reserve"),
                rpc_asset_reserve=row.get("rpc_asset_reserve"),
                reference_usdcx_per_xnt=reference_ratio,
                source_usdc_usd_price=source_usdc_usd,
                exact_pool_identity_verified=scope_verified,
                wrapped_xnt_position_verified=bool(
                    row.get("mint_0")
                    and row.get("mint_1")
                    and row.get("mint_0") != row.get("mint_1")
                ),
                reference_pool_identity_verified=reference_identity_verified,
                current_usdcx_usd_equivalence_verified=(
                    usdcx_equivalence_verified
                ),
            )
            nominal = _mapping(semantic.get("provider_nominal_basis"))
            independent = _mapping(semantic.get("independent_current_usd"))

            nominal_verified = bool(
                reserve_mapping_verified
                and rpc_fresh
                and nominal.get(
                    "provider_nominal_liquidity_semantics_verified"
                )
                is True
            )
            independent_verified = bool(
                reserve_mapping_verified
                and rpc_fresh
                and independent.get("independent_usd_valuation_verified") is True
            )

            if not nominal_verified:
                reasons.append("provider_nominal_liquidity_unverified")
            if not independent_verified:
                reasons.append("independent_current_usd_unverified")

            if nominal_verified:
                provider_nominal_total += _decimal(
                    nominal.get("derived_provider_nominal_liquidity"),
                    name="derived provider nominal liquidity",
                )
            if independent_verified:
                independent_usd_total += _decimal(
                    independent.get("independent_liquidity_usd"),
                    name="independent liquidity USD",
                )

            unit_results.append(
                {
                    "pool_address": address,
                    "reserve_mapping_verified": reserve_mapping_verified,
                    "provider_nominal_liquidity_freshness_verified": (
                        nominal_verified
                    ),
                    "independent_liquidity_usd_freshness_verified": (
                        independent_verified
                    ),
                    "unit_semantics": semantic,
                    "rejection_reasons": reasons,
                }
            )
        except ValueError as exc:
            reasons.append(str(exc))
            unit_results.append(
                {
                    "pool_address": address,
                    "reserve_mapping_verified": reserve_mapping_verified,
                    "provider_nominal_liquidity_freshness_verified": False,
                    "independent_liquidity_usd_freshness_verified": False,
                    "rejection_reasons": reasons,
                }
            )

    expected_count = int(legacy.get("contributing_pool_count") or 0)
    provider_nominal_verified = bool(
        expected_count > 0
        and len(unit_results) == expected_count
        and all(
            row.get("provider_nominal_liquidity_freshness_verified") is True
            for row in unit_results
        )
    )
    independent_usd_verified = bool(
        expected_count > 0
        and len(unit_results) == expected_count
        and all(
            row.get("independent_liquidity_usd_freshness_verified") is True
            for row in unit_results
        )
    )

    data = _mapping(market_envelope.get("data"))
    provider_market_value = data.get("liquidity_usd")

    if provider_nominal_verified:
        try:
            provider_market_dec = _decimal(
                provider_market_value,
                name="market provider liquidity",
            )
            provider_market_matches_nominal = bool(
                abs(provider_market_dec - provider_nominal_total)
                <= max(
                    Decimal("0.01"),
                    abs(provider_nominal_total) * Decimal("1e-4"),
                )
            )
        except ValueError:
            provider_market_matches_nominal = False
    else:
        provider_market_matches_nominal = False

    provider_nominal_freshness_verified = bool(
        provider_nominal_verified and provider_market_matches_nominal
    )
    independent_liquidity_usd_freshness_verified = bool(
        independent_usd_verified
    )

    if not provider_nominal_freshness_verified:
        failures.append("provider_nominal_liquidity_freshness_unverified")
    if not independent_liquidity_usd_freshness_verified:
        failures.append("independent_liquidity_usd_freshness_unverified")

    return {
        "contract_version": VERSION,
        "chain": "x1",
        "status": (
            "verified"
            if provider_nominal_freshness_verified
            and independent_liquidity_usd_freshness_verified
            else "partial"
        ),
        "legacy_v1_evidence": legacy,
        "pool_scope_evidence": dict(scope),
        "rpc_freshness": dict(rpc),
        "provider_numerical_unit": "USDC.X_nominal_quote_basis",
        "provider_nominal_liquidity_value": provider_market_value,
        "derived_provider_nominal_liquidity_sum": format(
            provider_nominal_total,
            "f",
        ),
        "provider_market_matches_nominal_basis": (
            provider_market_matches_nominal
        ),
        "provider_nominal_liquidity_freshness_verified": (
            provider_nominal_freshness_verified
        ),
        "independent_liquidity_usd_value": format(
            independent_usd_total,
            "f",
        ),
        "independent_liquidity_usd_freshness_verified": (
            independent_liquidity_usd_freshness_verified
        ),
        "current_usdcx_usd_equivalence_verified": (
            usdcx_equivalence_verified
        ),
        "pool_results": unit_results,
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "stable_name_implies_one_usd": False,
        "provider_price_reused_as_independent_usd_proof": False,
        "legacy_liquidity_freshness_verified": (
            legacy.get("liquidity_freshness_verified") is True
        ),
        "failures": list(dict.fromkeys(failures)),
        "execution_authorized": False,
    }


__all__ = [
    "VERSION",
    "evaluate_x1_ninja_liquidity_freshness_v2",
]
