import os
import unittest

from liquidity_scout.providers.x1.xdex_direct_route_discovery import discover_direct_route
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import XENCAT_MINT, XNT_MINT


RUN_LIVE = os.getenv("RUN_XDEX_DIRECT_ROUTE_DISCOVERY_LIVE") == "1"
USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
PINNED_XENCAT_POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
PINNED_XENCAT_CONFIG = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_DIRECT_ROUTE_DISCOVERY_LIVE=1 to run read-only discovery evidence",
)
class XDEXDirectRouteDiscoveryLiveTests(unittest.TestCase):
    def test_pinned_xencat_xnt_pair_has_one_verified_direct_route(self):
        result = discover_direct_route(XENCAT_MINT, XNT_MINT)

        self.assertEqual(result["status"], "verified_unique")
        self.assertEqual(result["verified_candidate_count"], 1)
        self.assertEqual(result["selection_claim"], "unique_verified_direct_candidate")
        self.assertEqual(result["route"], {
            "token_in_mint": XENCAT_MINT,
            "token_out_mint": XNT_MINT,
            "pool": PINNED_XENCAT_POOL,
            "amm_config": PINNED_XENCAT_CONFIG,
        })
        self.assertTrue(result["read_only"])
        self.assertFalse(result["best_route_claimed"])
        self.assertFalse(result["global_optimality_claimed"])
        self.assertFalse(result["multi_hop_evaluated"])
        self.assertFalse(result["execution_authorized"])
        print({
            "pair": "XENCAT/XNT",
            "status": result["status"],
            "catalog_candidate_count": result["catalog_candidate_count"],
            "verified_candidate_count": result["verified_candidate_count"],
            "route": result["route"],
            "best_route_claimed": result["best_route_claimed"],
        })

    def test_xnt_usdcx_current_direct_topology_is_diagnostic_only(self):
        result = discover_direct_route(XNT_MINT, USDC_X_MINT)

        self.assertIn(result["status"], {"unavailable", "verified_unique", "ambiguous"})
        if result["status"] == "ambiguous":
            self.assertGreaterEqual(result["verified_candidate_count"], 2)
            self.assertIsNone(result["route"])
        elif result["status"] == "verified_unique":
            self.assertEqual(result["verified_candidate_count"], 1)
            self.assertIsNotNone(result["route"])
        else:
            self.assertEqual(result["verified_candidate_count"], 0)
            self.assertIsNone(result["route"])
        self.assertFalse(result["best_route_claimed"])
        self.assertFalse(result["execution_authorized"])
        print({
            "pair": "XNT/USDC.X",
            "status": result["status"],
            "catalog_candidate_count": result["catalog_candidate_count"],
            "verified_candidate_count": result["verified_candidate_count"],
            "candidate_pools": [item["pool"] for item in result["candidates"]],
            "route_selected": result["route"],
        })


if __name__ == "__main__":
    unittest.main()
