"""Comparable wSOL.X USD value basis for CMIS #410.

The destination representation is valued only when:
- exact Warp wSOL -> wSOL.X backing closure is verified;
- source and destination decimals are equal;
- the canonical wrapped-SOL source mint is exact; and
- an exact on-chain Pyth SOL/USD observation passes the accepted source-specific
  freshness policy.

This is a route-scoped comparable value basis, not global current-price
promotion and not source-independence proof.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.providers.solana.pyth_freshness_policy import (
    FRESH,
    classify_pyth_freshness,
)
from liquidity_scout.providers.solana.pyth_push import (
    SOL_USD_FEED_ID,
    WSOL_MINT,
)
from liquidity_scout.providers.x1.warp_bridged_supply_evidence import (
    CONTRACT as WARP_SUPPLY_CONTRACT,
    WSOL_ROUTE_ID,
    WSOL_X_DESTINATION_MINT,
)
from liquidity_scout.services.cmis_bridge_to_xdex_utilization import (
    VALUE_BASIS_CONTRACT,
)

CONTRACT = VALUE_BASIS_CONTRACT

WSOLX_PYTH_FRESHNESS_POLICY = {
    "policy_id": "cmis.issue410.pyth_sol_usd.current_value_basis_freshness.v1",
    "max_age_seconds": 60,
    "max_age_provenance": (
        "CMIS #410 requires the SOL/USD source fact used to value current "
        "bridged wSOL.X supply to be no older than 60 seconds at collection "
        "completion. This is an operator-owned current-value bound, not a "
        "Pyth SLA and not inferred from observed passing samples."
    ),
    "max_future_skew_seconds": 5,
    "future_skew_provenance": (
        "CMIS #410 allows at most five seconds of positive publish-time skew "
        "against the collection clock. This is an operator-owned clock bound."
    ),
}


class WSOLXValueBasisError(RuntimeError):
    pass


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WSOLXValueBasisError(f"{field} must be a mapping")
    return value


def _positive_decimal(value: Any, field: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise WSOLXValueBasisError(f"{field} must be positive")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise WSOLXValueBasisError(f"{field} must be positive") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise WSOLXValueBasisError(f"{field} must be positive")
    return parsed


def build_wsolx_value_basis(
    *,
    bridged_supply: Any,
    pyth_sol_usd: Any,
) -> dict[str, Any]:
    supply = _mapping(bridged_supply, "bridged_supply")
    pyth = _mapping(pyth_sol_usd, "pyth_sol_usd")

    if supply.get("contract") != WARP_SUPPLY_CONTRACT:
        raise WSOLXValueBasisError(
            f"bridged_supply must use {WARP_SUPPLY_CONTRACT}"
        )
    if supply.get("route_id") != WSOL_ROUTE_ID:
        raise WSOLXValueBasisError("exact wSOL Warp route is required")
    if supply.get("current_backing_closure_verified") is not True:
        raise WSOLXValueBasisError("current Warp backing closure is unverified")
    if supply.get("bridged_supply_verified") is not True:
        raise WSOLXValueBasisError("bridged supply is unverified")
    if supply.get("source_native_destination_wrapped_verified") is not True:
        raise WSOLXValueBasisError("source-native/destination-wrapped topology unverified")
    if supply.get("decimals_verified") is not True:
        raise WSOLXValueBasisError("source/destination decimals are unverified")
    if supply.get("source_vault_balance_equals_destination_supply") is not True:
        raise WSOLXValueBasisError("source reserve does not close destination supply")

    source = _mapping(supply.get("source"), "bridged_supply.source")
    destination = _mapping(supply.get("destination"), "bridged_supply.destination")
    if source.get("mint") != WSOL_MINT:
        raise WSOLXValueBasisError("source mint is not canonical wrapped SOL")
    if destination.get("mint") != WSOL_X_DESTINATION_MINT:
        raise WSOLXValueBasisError("destination mint is not exact wSOL.X")
    if source.get("identity_verified") is not True:
        raise WSOLXValueBasisError("source Warp identity is unverified")
    if destination.get("identity_verified") is not True:
        raise WSOLXValueBasisError("destination Warp identity is unverified")
    if source.get("decimals") != destination.get("decimals"):
        raise WSOLXValueBasisError("source/destination decimal mismatch")

    if pyth.get("chain") != "solana":
        raise WSOLXValueBasisError("Pyth observation must be Solana")
    if pyth.get("source") != "pyth_core_solana_push":
        raise WSOLXValueBasisError("Pyth source provenance mismatch")
    if pyth.get("mint") != WSOL_MINT:
        raise WSOLXValueBasisError("Pyth observation mint mismatch")
    if pyth.get("feed_id") != SOL_USD_FEED_ID:
        raise WSOLXValueBasisError("Pyth SOL/USD feed id mismatch")
    for field in (
        "mapping_verified",
        "feed_id_verified",
        "account_owner_verified",
        "write_authority_matches_feed_account",
        "full_verification",
        "price_available",
        "fact_time_verified",
        "collection_time_verified",
        "price_integrity_verified",
    ):
        if pyth.get(field) is not True:
            raise WSOLXValueBasisError(f"pyth_sol_usd.{field} must be true")
    if pyth.get("feed_alias") != "SOL/USD":
        raise WSOLXValueBasisError("Pyth feed alias must be SOL/USD")
    if pyth.get("price_subject") != "SOL":
        raise WSOLXValueBasisError("Pyth price subject must be SOL")
    if pyth.get("unit") != "USD_per_SOL":
        raise WSOLXValueBasisError("Pyth price unit must be USD_per_SOL")
    if pyth.get("execution_authorized") is not False:
        raise WSOLXValueBasisError("Pyth observation must remain read-only")

    freshness = classify_pyth_freshness(
        pyth,
        policy=WSOLX_PYTH_FRESHNESS_POLICY,
    )
    if freshness.get("classification") != FRESH:
        raise WSOLXValueBasisError("Pyth SOL/USD observation is not fresh")
    if freshness.get("pyth_current_price_eligible") is not True:
        raise WSOLXValueBasisError("Pyth SOL/USD observation is not current-price eligible")

    price = _positive_decimal(pyth.get("price_usd"), "pyth_sol_usd.price_usd")
    observed_at = freshness.get("fact_time_unix")
    if not isinstance(observed_at, (int, float)) or isinstance(observed_at, bool):
        raise WSOLXValueBasisError("verified Pyth fact time is required")

    return {
        "contract": CONTRACT,
        "evidence_id": (
            f"warp-wsolx-pyth-sol-usd:{pyth.get('account_address')}:{int(observed_at)}"
        ),
        "route_id": WSOL_ROUTE_ID,
        "asset_mint": WSOL_X_DESTINATION_MINT,
        "source_asset_mint": WSOL_MINT,
        "unit": "USD",
        "price_per_token": format(price, "f"),
        "observed_at": float(observed_at),
        "source_price_feed": {
            "source": "pyth_core_solana_push",
            "feed_alias": "SOL/USD",
            "feed_id": SOL_USD_FEED_ID,
            "account_address": pyth.get("account_address"),
            "price_usd": format(price, "f"),
            "publish_time_unix": float(observed_at),
            "freshness_classification": freshness["classification"],
            "freshness_policy_id": freshness["policy"]["policy_id"],
        },
        "source_native_wsol_sol_value_equivalence_verified": True,
        "warp_source_destination_unit_equivalence_verified": True,
        "warp_current_backing_closure_verified": True,
        "price_semantics_verified": True,
        "price_freshness_verified": True,
        "comparable_value_basis_verified": True,
        "source_independence_verified": False,
        "global_current_price_promoted": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT",
    "WSOLXValueBasisError",
    "WSOLX_PYTH_FRESHNESS_POLICY",
    "build_wsolx_value_basis",
]
