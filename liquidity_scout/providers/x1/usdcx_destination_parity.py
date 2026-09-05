"""Fail-closed current destination-side parity evidence for X1 USDC.X.

This verifier does not infer economic parity from a symbol, route label, or
historical transfer. It accepts only a current exact Warp backing closure in
which the deterministic Solana USDC Warp vault balance equals the exact X1
USDC.X mint supply, decimals agree, and the destination mint authority is the
verified Warp mint-authority PDA.

That establishes current reserve backing only. It does not claim guaranteed
future redemption, historical parity, source independence, or execution
safety.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA = "x1_usdcx_destination_parity.v1"
SOLANA_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
X1_USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
WARP_USDC_ROUTE_ID = "warp-solana-x1-usdc"
EXPECTED_DECIMALS = 6


def evaluate_usdcx_destination_parity(
    backing_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate one current exact reserve-backing observation."""
    if not isinstance(backing_evidence, Mapping):
        raise TypeError("backing_evidence must be a mapping")

    source = backing_evidence.get("source")
    destination = backing_evidence.get("destination")
    source = source if isinstance(source, Mapping) else {}
    destination = destination if isinstance(destination, Mapping) else {}

    exact_route = bool(
        backing_evidence.get("route_id") == WARP_USDC_ROUTE_ID
        and source.get("chain") == "solana"
        and source.get("mint") == SOLANA_USDC_MINT
        and destination.get("chain") == "x1"
        and destination.get("mint") == X1_USDC_X_MINT
    )
    exact_identity = bool(
        source.get("identity_verified") is True
        and destination.get("identity_verified") is True
    )
    decimals_verified = bool(
        backing_evidence.get("decimals_verified") is True
        and source.get("decimals") == EXPECTED_DECIMALS
        and destination.get("decimals") == EXPECTED_DECIMALS
        and backing_evidence.get("decimals") == EXPECTED_DECIMALS
    )
    current_observation = bool(
        backing_evidence.get("observation_time_compatible") is True
        and backing_evidence.get("current_backing_closure_verified") is True
        and backing_evidence.get("bridged_supply_verified") is True
    )
    reserve_equality = bool(
        backing_evidence.get("source_vault_balance_equals_destination_supply")
        is True
        and source.get("amount_raw") == destination.get("raw_supply")
        and backing_evidence.get("amount_raw") == destination.get("raw_supply")
    )

    reserve_backing_verified = bool(
        exact_route
        and exact_identity
        and decimals_verified
        and current_observation
        and reserve_equality
    )

    return {
        "schema": SCHEMA,
        "proof_scope": "current",
        "source_chain": "solana",
        "source_mint": SOLANA_USDC_MINT,
        "destination_chain": "x1",
        "destination_mint": X1_USDC_X_MINT,
        "route_id": WARP_USDC_ROUTE_ID,
        "exact_route_identity_verified": exact_route,
        "source_destination_identity_verified": exact_identity,
        "decimals_verified": decimals_verified,
        "observation_time_compatible": bool(
            backing_evidence.get("observation_time_compatible") is True
        ),
        "current_reserve_backing_verified": reserve_backing_verified,
        "reserve_or_redemption_semantics_verified": reserve_backing_verified,
        "destination_representation_value_equivalence_verified": reserve_backing_verified,
        "proof_basis": (
            "exact_current_solana_usdc_warp_vault_balance_equals_"
            "exact_x1_usdcx_supply_with_verified_warp_mint_authority"
            if reserve_backing_verified
            else None
        ),
        "source_amount_raw": source.get("amount_raw"),
        "destination_supply_raw": destination.get("raw_supply"),
        "future_redemption_guaranteed": False,
        "historical_value_equivalence_verified": False,
        "source_independence_verified": False,
        "cmis_promotable": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "EXPECTED_DECIMALS",
    "SCHEMA",
    "SOLANA_USDC_MINT",
    "WARP_USDC_ROUTE_ID",
    "X1_USDC_X_MINT",
    "evaluate_usdcx_destination_parity",
]
