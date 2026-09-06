"""Reusable current USDC.X/USD evidence capture for X1 freshness proofs.

This module promotes no new semantics. It is the production form of the
already-accepted live composition previously embedded in the #461/#459 tests.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from liquidity_scout.providers.solana.pyth_freshness_policy import (
    accepted_pyth_freshness_policy,
    classify_pyth_freshness,
)
from liquidity_scout.providers.solana.pyth_push import (
    PythSolanaPushProvider,
    USDC_MINT,
)
from liquidity_scout.providers.solana.rpc import SolanaRPCProvider
from liquidity_scout.providers.x1.current_usdcx_usd_equivalence import (
    SOLANA_USDC_MINT,
    X1_USDC_X_MINT,
    evaluate_current_usdcx_usd_equivalence,
)
from liquidity_scout.providers.x1.usdcx_destination_parity import (
    WARP_USDC_ROUTE_ID,
    evaluate_usdcx_destination_parity,
)
from liquidity_scout.providers.x1.warp_bridged_supply_evidence import (
    build_warp_bridged_supply_evidence,
    capture_destination_mint_observation,
    capture_source_vault_observation,
)
from liquidity_scout.providers.x1.warp_config_semantics import (
    WARP_CONFIG_SEMANTIC_CONTRACT_ID,
    build_warp_config_route_observation,
)
from liquidity_scout.providers.x1.warp_message_retention_coverage import (
    fetch_official_warp_config,
)


SCHEMA = "x1_current_usdcx_usd_equivalence_capture/v1"


def _endpoint(chain: str, mint: str) -> dict[str, str]:
    return {"chain": chain, "asset_id": mint, "asset_id_kind": "mint"}


def _qualified_route_contract(route: dict[str, Any]) -> dict[str, Any]:
    source = route.get("source") or {}
    destination = route.get("destination") or {}
    exact_route = bool(
        route.get("route_id") == WARP_USDC_ROUTE_ID
        and route.get("semantic_contract_id") == WARP_CONFIG_SEMANTIC_CONTRACT_ID
        and source.get("chain") == "solana"
        and source.get("asset_id") == SOLANA_USDC_MINT
        and source.get("asset_id_kind") == "mint"
        and destination.get("chain") == "x1"
        and destination.get("asset_id") == X1_USDC_X_MINT
        and destination.get("asset_id_kind") == "mint"
    )
    route_status_verified = route.get("route_status") == "active"
    backing_model_verified = bool(
        route.get("source_is_native") is True
        and route.get("destination_is_native") is False
        and route.get("backing_model")
        == "provider_config_native_source_to_non_native_destination"
    )
    return {
        "warp_qualified": bool(
            exact_route and route_status_verified and backing_model_verified
        ),
        "exact_route_identity_verified": exact_route,
        "route_status_verified": route_status_verified,
        "backing_model_verified": backing_model_verified,
        "source_chain": "solana",
        "source_mint": SOLANA_USDC_MINT,
        "destination_chain": "x1",
        "destination_mint": X1_USDC_X_MINT,
    }


def capture_current_usdcx_usd_equivalence_evidence(
    *,
    clock: Callable[[], float] = time.time,
    official_config_fetcher: Callable[..., Any] = fetch_official_warp_config,
    source_vault_capturer: Callable[..., Any] = capture_source_vault_observation,
    destination_mint_capturer: Callable[..., Any] = capture_destination_mint_observation,
    pyth_provider: Any = None,
) -> dict[str, Any]:
    """Capture the accepted current USDC.X/USD composition."""

    if USDC_MINT != SOLANA_USDC_MINT:
        raise ValueError("Pyth USDC mint identity mismatch")

    # Fetch first, then timestamp the completed provider read. The official
    # response may carry a fetchedAt generated during the request; stamping
    # before the request can make collected_at incorrectly predate fetchedAt.
    config_response = official_config_fetcher()
    collected_at = float(clock())
    route = build_warp_config_route_observation(
        config_response=config_response,
        route_id=WARP_USDC_ROUTE_ID,
        source=_endpoint("solana", SOLANA_USDC_MINT),
        destination=_endpoint("x1", X1_USDC_X_MINT),
        collected_at=collected_at,
    )
    route_contract = _qualified_route_contract(route)
    if route_contract["warp_qualified"] is not True:
        raise ValueError("accepted Warp USDC route is not qualified")

    backing = build_warp_bridged_supply_evidence(
        route_observation=route,
        source_vault=source_vault_capturer(source_mint=SOLANA_USDC_MINT),
        destination_mint=destination_mint_capturer(
            destination_mint=X1_USDC_X_MINT
        ),
        evaluated_at=float(clock()),
    )
    parity = evaluate_usdcx_destination_parity(backing)

    provider = (
        PythSolanaPushProvider(SolanaRPCProvider())
        if pyth_provider is None
        else pyth_provider
    )
    pyth = provider.get_price(SOLANA_USDC_MINT)
    freshness = classify_pyth_freshness(
        pyth,
        policy=accepted_pyth_freshness_policy(),
    )
    equivalence = evaluate_current_usdcx_usd_equivalence(
        warp_route_evidence=route_contract,
        source_usdc_usd_evidence=pyth,
        source_usdc_freshness=freshness,
        destination_parity_evidence=parity,
    )

    return {
        "schema": SCHEMA,
        "chain": "x1",
        "captured_at": float(clock()),
        "route": route_contract,
        "source_usdc_usd": pyth,
        "source_usdc_freshness": freshness,
        "destination_parity": parity,
        "equivalence": equivalence,
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }


__all__ = [
    "SCHEMA",
    "capture_current_usdcx_usd_equivalence_evidence",
]
