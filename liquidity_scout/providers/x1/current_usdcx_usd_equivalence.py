"""Current X1 USDC.X/USD equivalence policy.

This policy deliberately separates three claims:

1. the exact Warp route maps canonical Solana USDC to the exact X1 USDC.X mint;
2. the source Solana USDC has a fresh, verified USD-per-USDC price observation;
3. the destination representation is economically value-equivalent to the
   source token under a separately verified reserve/redemption/parity proof.

The accepted Warp config currently proves exact route representation topology,
not reserve sufficiency or one-for-one redemption. Therefore exact route
identity plus a fresh Pyth USDC/USD observation is insufficient by itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

SCHEMA = "x1_current_usdcx_usd_equivalence.v1"
SOLANA_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
X1_USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
PYTH_USDC_USD_UNIT = "USD_per_USDC"
DEFAULT_ABSOLUTE_USD_DEVIATION = Decimal("0.01")


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


def evaluate_current_usdcx_usd_equivalence(
    *,
    warp_route_evidence: Mapping[str, Any],
    source_usdc_usd_evidence: Mapping[str, Any],
    source_usdc_freshness: Mapping[str, Any],
    destination_parity_evidence: Mapping[str, Any] | None = None,
    absolute_usd_deviation: Any = DEFAULT_ABSOLUTE_USD_DEVIATION,
) -> dict[str, Any]:
    """Evaluate current USDC.X/USD equivalence and fail closed."""

    route = _mapping(warp_route_evidence)
    source_price = _mapping(source_usdc_usd_evidence)
    freshness = _mapping(source_usdc_freshness)
    parity = _mapping(destination_parity_evidence)

    tolerance = _decimal(absolute_usd_deviation, name="absolute_usd_deviation")
    if tolerance <= 0:
        raise ValueError("absolute_usd_deviation must be positive")

    route_identity_verified = bool(
        route.get("warp_qualified") is True
        and route.get("exact_route_identity_verified") is True
        and route.get("route_status_verified") is True
        and route.get("backing_model_verified") is True
        and route.get("source_chain") == "solana"
        and route.get("source_mint") == SOLANA_USDC_MINT
        and route.get("destination_chain") == "x1"
        and route.get("destination_mint") == X1_USDC_X_MINT
    )

    source_price_unit_verified = source_price.get("unit") == PYTH_USDC_USD_UNIT
    source_price_identity_verified = bool(
        source_price.get("chain") == "solana"
        and source_price.get("source") == "pyth_core_solana_push"
        and source_price.get("mint") == SOLANA_USDC_MINT
        and source_price.get("mapping_verified") is True
        and source_price.get("price_integrity_verified") is True
        and source_price.get("fact_time_verified") is True
        and source_price_unit_verified
    )

    price = None
    price_close_to_one = False
    if source_price_identity_verified:
        try:
            price = _decimal(source_price.get("price_usd"), name="price_usd")
        except ValueError:
            price = None
        if price is not None and price > 0:
            price_close_to_one = abs(price - Decimal(1)) <= tolerance

    source_price_fresh = bool(
        freshness.get("classification") == "FRESH"
        and freshness.get("classification_verified") is True
        and freshness.get("pyth_freshness_verified") is True
        and freshness.get("pyth_current_price_eligible") is True
    )

    destination_parity_verified = bool(
        parity.get("destination_representation_value_equivalence_verified") is True
        and parity.get("source_mint") == SOLANA_USDC_MINT
        and parity.get("destination_mint") == X1_USDC_X_MINT
        and parity.get("proof_scope") == "current"
        and parity.get("reserve_or_redemption_semantics_verified") is True
    )

    verified = bool(
        route_identity_verified
        and source_price_identity_verified
        and source_price_fresh
        and price_close_to_one
        and destination_parity_verified
    )

    missing_gates = []
    if not route_identity_verified:
        missing_gates.append("exact_active_warp_usdc_route")
    if not source_price_identity_verified:
        missing_gates.append("verified_solana_usdc_usd_price")
    if not source_price_fresh:
        missing_gates.append("fresh_solana_usdc_usd_price")
    if not price_close_to_one:
        missing_gates.append("source_usdc_within_usd_tolerance")
    if not destination_parity_verified:
        missing_gates.append("destination_representation_value_equivalence")

    return {
        "schema": SCHEMA,
        "chain": "x1",
        "status": "verified" if verified else "partial",
        "source_chain": "solana",
        "source_mint": SOLANA_USDC_MINT,
        "destination_chain": "x1",
        "destination_mint": X1_USDC_X_MINT,
        "route_identity_verified": route_identity_verified,
        "source_usdc_usd_price_unit_verified": source_price_unit_verified,
        "source_usdc_usd_price_identity_verified": source_price_identity_verified,
        "source_usdc_usd_price_fresh": source_price_fresh,
        "source_usdc_usd_price": format(price, "f") if price is not None else None,
        "absolute_usd_deviation_policy": format(tolerance, "f"),
        "source_usdc_within_usd_tolerance": price_close_to_one,
        "destination_representation_value_equivalence_verified": destination_parity_verified,
        "current_usdcx_usd_equivalence_verified": verified,
        "missing_gates": missing_gates,
        "historical_usdcx_usd_equivalence_verified": False,
        "source_independence_verified": False,
        "cmis_promotable": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "DEFAULT_ABSOLUTE_USD_DEVIATION",
    "PYTH_USDC_USD_UNIT",
    "SCHEMA",
    "SOLANA_USDC_MINT",
    "X1_USDC_X_MINT",
    "evaluate_current_usdcx_usd_equivalence",
]
