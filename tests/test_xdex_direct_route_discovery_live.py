import os
import unittest

import requests

from liquidity_scout.providers.x1.xdex import fetch_pool_list
from liquidity_scout.providers.x1.xdex_direct_route_discovery import discover_direct_route
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import XENCAT_MINT, XNT_MINT


RUN_LIVE = os.getenv("RUN_XDEX_DIRECT_ROUTE_DISCOVERY_LIVE") == "1"
USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
PINNED_XENCAT_POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
PINNED_XENCAT_CONFIG = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"
PAIR_POOL_BASE = "https://api.xdex.xyz/api/xendex/pool/tokens"


def pair_probe(token_a, token_b):
    response = requests.get(
        f"{PAIR_POOL_BASE}/{token_a}/{token_b}",
        params={"network": "mainnet"},
        timeout=15,
    )
    body = None
    try:
        body = response.json()
    except Exception:
        body = response.text[:1000]
    return {"status_code": response.status_code, "body": body}


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_DIRECT_ROUTE_DISCOVERY_LIVE=1 to run read-only discovery evidence",
)
class XDEXDirectRouteDiscoveryLiveTests(unittest.TestCase):
    def test_pinned_xencat_xnt_pair_has_one_verified_direct_route(self):
        pools = fetch_pool_list()
        pinned_rows = [
            row for row in pools
            if isinstance(row, dict) and row.get("address") == PINNED_XENCAT_POOL
        ]
        xencat_rows = [row for row in pools if XENCAT_MINT in repr(row)]
        print({
            "catalog_total": len(pools),
            "pinned_pool_rows": pinned_rows,
            "rows_containing_xencat_mint": xencat_rows[:5],
            "pair_endpoint_forward": pair_probe(XENCAT_MINT, XNT_MINT),
            "pair_endpoint_reverse": pair_probe(XNT_MINT, XENCAT_MINT),
        })

        result = discover_direct_route(
            XENCAT_MINT,
            XNT_MINT,
            pool_fetcher=lambda: pools,
        )

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

    def test_xnt_usdcx_current_direct_topology_is_diagnostic_only(self):
        result = discover_direct_route(XNT_MINT, USDC_X_MINT)
        self.assertIn(result["status"], {"unavailable", "verified_unique", "ambiguous"})
        self.assertFalse(result["best_route_claimed"])
        self.assertFalse(result["execution_authorized"])
        print({
            "pair": "XNT/USDC.X",
            "status": result["status"],
            "catalog_candidate_count": result["catalog_candidate_count"],
            "verified_candidate_count": result["verified_candidate_count"],
            "candidate_pools": [item["pool"] for item in result["candidates"]],
            "route_selected": result["route"],
            "pair_endpoint": pair_probe(XNT_MINT, USDC_X_MINT),
        })


if __name__ == "__main__":
    unittest.main()
