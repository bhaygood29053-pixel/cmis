"""Fail-closed current destination-side reserve evidence for X1 USDC.X.

This verifier does not infer parity from a symbol, route label, or historical
transfer. It evaluates whether the exact deterministic Solana USDC Warp vault
currently contains at least as many 6-decimal source units as the exact X1
USDC.X mint has outstanding, while both endpoint identities and the Warp mint
authority are verified by the underlying backing-evidence contract.

Reserve sufficiency is deliberately separated from exact supply equality and
from guaranteed future redemption. The latter claims remain unverified.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA = "x1_usdcx_destination_parity.v1"
SOLANA_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
X1_USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
WARP_USDC_ROUTE_ID = "warp-solana-x1-usdc"
EXPECTED_DECIMALS = 6


def _raw_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def evaluate_usdcx_destination_parity(
    backing_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate one current exact reserve-sufficiency observation."""
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
    observation_time_compatible = bool(
        backing_evidence.get("observation_time_compatible") is True
    )

    source_amount = _raw_int(source.get("amount_raw"))
    destination_supply = _raw_int(destination.get("raw_supply"))
    reserve_sufficient = bool(
        source_amount is not None
        and destination_supply is not None
        and source_amount >= destination_supply
    )
    reserve_surplus_raw = (
        source_amount - destination_supply
        if source_amount is not None and destination_supply is not None
        else None
    )
    exact_closure_verified = bool(
        backing_evidence.get("current_backing_closure_verified") is True
        and backing_evidence.get("source_vault_balance_equals_destination_supply")
        is True
    )

    current_reserve_backing_verified = bool(
        exact_route
        and exact_identity
        and decimals_verified
        and observation_time_compatible
        and reserve_sufficient
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
        "observation_time_compatible": observation_time_compatible,
        "source_amount_raw": source_amount,
        "destination_supply_raw": destination_supply,
        "reserve_surplus_raw": reserve_surplus_raw,
        "source_reserve_gte_destination_supply": reserve_sufficient,
        "exact_backing_closure_verified": exact_closure_verified,
        "current_reserve_backing_verified": current_reserve_backing_verified,
        "reserve_or_redemption_semantics_verified": current_reserve_backing_verified,
        "destination_representation_value_equivalence_verified": current_reserve_backing_verified,
        "proof_basis": (
            "exact_current_solana_usdc_warp_reserve_covers_"
            "exact_x1_usdcx_supply_at_equal_decimals_with_verified_identities"
            if current_reserve_backing_verified
            else None
        ),
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
