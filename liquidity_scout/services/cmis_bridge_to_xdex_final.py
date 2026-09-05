"""Final zero-pool composition path for CMIS #410.

This narrow helper binds the evidence classes that #410 intentionally kept
separate:
- accepted #409 Warp bridge-flow integration;
- exact verified current XDEX zero pool universe;
- exact verified 24h XDEX-program zero-activity window; and
- fresh comparable wSOL.X USD value basis.

It does not add any new factual authority. It only validates that the evidence
identities/scopes match and delegates the arithmetic to
bridge_to_xdex_utilization/v1.
"""

from __future__ import annotations

from typing import Any

from liquidity_scout.providers.x1.xdex_representation_pool_universe import (
    apply_verified_program_window_to_zero_universe,
)
from liquidity_scout.services.cmis_bridge_to_xdex_utilization import (
    build_bridge_to_xdex_utilization,
)


def build_zero_pool_bridge_to_xdex_utilization(
    *,
    bridge_integration: Any,
    pool_universe: Any,
    program_window_activity: Any,
    value_basis: Any,
) -> dict[str, Any]:
    enriched = apply_verified_program_window_to_zero_universe(
        pool_universe=pool_universe,
        program_window_activity=program_window_activity,
    )
    result = build_bridge_to_xdex_utilization(
        bridge_integration=bridge_integration,
        pool_universe=enriched,
        pool_metrics=[],
        value_basis=value_basis,
    )
    if result.get("verified_zero_pool_set") is not True:
        raise ValueError("final #410 zero-pool composition lost zero-set identity")
    if result.get("current_liquidity_zero_verified") is not True:
        raise ValueError("final #410 current zero liquidity is unverified")
    if result.get("volume_24h_window_coverage_verified") is not True:
        raise ValueError("final #410 24h window is unverified")
    if result.get("verified_xdex_liquidity_value") != "0":
        raise ValueError("final #410 zero-pool liquidity must equal zero")
    if result.get("verified_xdex_volume_24h_value") != "0":
        raise ValueError("final #410 verified 24h volume must equal zero")
    if result.get("market_activity_24h_verified") is not True:
        raise ValueError("final #410 24h market activity is unverified")
    if result.get("comparable_value_basis_verified") is not True:
        raise ValueError("final #410 comparable value basis is unverified")
    if result.get("issue_410_acceptance_verified") is not True:
        raise ValueError("final #410 acceptance contract did not verify")
    if result.get("execution_authorized") is not False:
        raise ValueError("final #410 evidence must remain read-only")
    return {
        **result,
        "final_zero_pool_composition_verified": True,
        "program_window_activity_contract": program_window_activity.get("contract")
        if isinstance(program_window_activity, dict)
        else None,
        "program_window_activity_evidence_scope": (
            "verified_xdex_program_family_24h"
        ),
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = ["build_zero_pool_bridge_to_xdex_utilization"]
