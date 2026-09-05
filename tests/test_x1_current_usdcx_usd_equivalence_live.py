import json
import os
import time
import unittest

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

RUN_LIVE = os.getenv("RUN_X1_USDCX_USD_COMPOSED_LIVE") == "1"


def endpoint(chain, mint):
    return {"chain": chain, "asset_id": mint, "asset_id_kind": "mint"}


def _qualified_route_contract(route):
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


@unittest.skipUnless(RUN_LIVE, "set RUN_X1_USDCX_USD_COMPOSED_LIVE=1")
class X1CurrentUsdcxUsdEquivalenceLiveTests(unittest.TestCase):
    def test_compose_current_warp_parity_with_fresh_exact_mint_pyth_usdc_usd(self):
        self.assertEqual(USDC_MINT, SOLANA_USDC_MINT)

        route = build_warp_config_route_observation(
            config_response=fetch_official_warp_config(),
            route_id=WARP_USDC_ROUTE_ID,
            source=endpoint("solana", SOLANA_USDC_MINT),
            destination=endpoint("x1", X1_USDC_X_MINT),
            collected_at=time.time(),
        )
        route_contract = _qualified_route_contract(route)

        backing = build_warp_bridged_supply_evidence(
            route_observation=route,
            source_vault=capture_source_vault_observation(
                source_mint=SOLANA_USDC_MINT
            ),
            destination_mint=capture_destination_mint_observation(
                destination_mint=X1_USDC_X_MINT
            ),
            evaluated_at=time.time(),
        )
        parity = evaluate_usdcx_destination_parity(backing)

        pyth = PythSolanaPushProvider(SolanaRPCProvider()).get_price(
            SOLANA_USDC_MINT
        )
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

        evidence = {
            "schema": "x1_current_usdcx_usd_equivalence_live.v1",
            "route": route_contract,
            "source_usdc_usd": pyth,
            "source_usdc_freshness": freshness,
            "destination_parity": parity,
            "equivalence": equivalence,
            "x1_ninja_liquidity_usd_semantics_verified": False,
            "liquidity_freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        print("X1 #461 CURRENT USDC.X/USD COMPOSED LIVE EVIDENCE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertTrue(route_contract["warp_qualified"])
        self.assertTrue(parity["destination_representation_value_equivalence_verified"])
        self.assertEqual(pyth["unit"], "USD_per_USDC")
        self.assertTrue(freshness["pyth_current_price_eligible"])
        self.assertTrue(equivalence["source_usdc_usd_price_unit_verified"])
        self.assertTrue(equivalence["current_usdcx_usd_equivalence_verified"])
        self.assertFalse(equivalence["historical_usdcx_usd_equivalence_verified"])
        self.assertFalse(equivalence["cmis_promotable"])
        self.assertFalse(equivalence["execution_authorized"])
        self.assertFalse(evidence["x1_ninja_liquidity_usd_semantics_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["cmis_promotable"])
        self.assertFalse(evidence["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
