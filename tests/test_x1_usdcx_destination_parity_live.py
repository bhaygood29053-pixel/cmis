import json
import os
import time
import unittest

from liquidity_scout.providers.x1.usdcx_destination_parity import (
    SOLANA_USDC_MINT,
    WARP_USDC_ROUTE_ID,
    X1_USDC_X_MINT,
    evaluate_usdcx_destination_parity,
)
from liquidity_scout.providers.x1.warp_bridged_supply_evidence import (
    build_warp_bridged_supply_evidence,
    capture_destination_mint_observation,
    capture_source_vault_observation,
)
from liquidity_scout.providers.x1.warp_config_semantics import (
    build_warp_config_route_observation,
)
from liquidity_scout.providers.x1.warp_message_retention_coverage import (
    fetch_official_warp_config,
)

RUN_LIVE = os.getenv("RUN_X1_USDCX_DESTINATION_PARITY_LIVE") == "1"


def endpoint(chain, mint):
    return {
        "chain": chain,
        "asset_id": mint,
        "asset_id_kind": "mint",
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_USDCX_DESTINATION_PARITY_LIVE=1 for current backing evidence",
)
class X1UsdcxDestinationParityLiveTests(unittest.TestCase):
    def test_current_exact_usdc_backing_closure(self):
        official = fetch_official_warp_config()
        route = build_warp_config_route_observation(
            config_response=official,
            route_id=WARP_USDC_ROUTE_ID,
            source=endpoint("solana", SOLANA_USDC_MINT),
            destination=endpoint("x1", X1_USDC_X_MINT),
        )
        source = capture_source_vault_observation(source_mint=SOLANA_USDC_MINT)
        destination = capture_destination_mint_observation(
            destination_mint=X1_USDC_X_MINT
        )
        backing = build_warp_bridged_supply_evidence(
            route_observation=route,
            source_vault=source,
            destination_mint=destination,
            evaluated_at=time.time(),
        )
        parity = evaluate_usdcx_destination_parity(backing)

        evidence = {
            "schema": "x1_usdcx_destination_parity_live.v1",
            "route_id": WARP_USDC_ROUTE_ID,
            "source": backing["source"],
            "destination": backing["destination"],
            "observation_skew_seconds": backing["observation_skew_seconds"],
            "source_vault_balance_equals_destination_supply": backing[
                "source_vault_balance_equals_destination_supply"
            ],
            "current_backing_closure_verified": backing[
                "current_backing_closure_verified"
            ],
            "parity": parity,
            # This slice proves the previously missing destination-side backing
            # primitive. The broader #461 USD-equivalence and liquidity gates
            # remain false until their complete accepted composition is wired.
            "current_usdcx_usd_equivalence_verified": False,
            "x1_ninja_liquidity_usd_semantics_verified": False,
            "liquidity_freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        print("X1 #461 CURRENT USDC.X DESTINATION PARITY EVIDENCE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertTrue(backing["current_backing_closure_verified"])
        self.assertTrue(backing["bridged_supply_verified"])
        self.assertTrue(backing["source_vault_balance_equals_destination_supply"])
        self.assertTrue(parity["current_reserve_backing_verified"])
        self.assertTrue(parity["reserve_or_redemption_semantics_verified"])
        self.assertTrue(
            parity["destination_representation_value_equivalence_verified"]
        )
        self.assertFalse(parity["future_redemption_guaranteed"])
        self.assertFalse(parity["historical_value_equivalence_verified"])
        self.assertFalse(evidence["current_usdcx_usd_equivalence_verified"])
        self.assertFalse(evidence["x1_ninja_liquidity_usd_semantics_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["cmis_promotable"])
        self.assertFalse(evidence["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
