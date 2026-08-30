import json
import os
import unittest

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.xdex import fetch_pool_list
from liquidity_scout.providers.x1.xdex_token_position_mapping import (
    verify_xdex_token_position_mapping,
)


RUN_LIVE = os.getenv("RUN_XDEX_TOKEN_POSITION_MAPPING_LIVE") == "1"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_TOKEN_POSITION_MAPPING_LIVE=1 to run read-only evidence",
)
class XDEXTokenPositionMappingLiveTests(unittest.TestCase):
    def test_live_mapping_is_stable_across_multiple_exact_common_pools(self):
        ninja_pools, _ = fetch_all_pools(sleep_seconds=0)
        xdex_pools = fetch_pool_list(network="X1 Mainnet")

        self.assertTrue(ninja_pools, "X1.Ninja returned no current pools")
        self.assertTrue(xdex_pools, "XDEX returned no X1 Mainnet pools")

        result = verify_xdex_token_position_mapping(
            ninja_pools=ninja_pools,
            xdex_pools=xdex_pools,
            min_verified_pools=3,
            max_samples=5,
            signature_limit=1,
        )

        public = {
            "status": result["status"],
            "common_pool_count_observed": result["common_pool_count_observed"],
            "sample_count": result["sample_count"],
            "verified_sample_count": result["verified_sample_count"],
            "minimum_verified_pool_count": result[
                "minimum_verified_pool_count"
            ],
            "stable_mapping": result["stable_mapping"],
            "position_mapping_verified": result["position_mapping_verified"],
            "base_quote_semantics_verified": result[
                "base_quote_semantics_verified"
            ],
            "samples": result["samples"],
            "semantics": result["semantics"],
            "cmis_promotable": result["cmis_promotable"],
            "execution_authorized": result["execution_authorized"],
        }
        print(
            "[XDEX token-position mapping evidence] "
            + json.dumps(public, sort_keys=True, default=str)
        )

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["position_mapping_verified"])
        self.assertGreaterEqual(result["verified_sample_count"], 3)
        self.assertIn(
            result["stable_mapping"],
            {
                "token1_to_mint0__token2_to_mint1",
                "token1_to_mint1__token2_to_mint0",
            },
        )
        self.assertFalse(result["base_quote_semantics_verified"])
        self.assertFalse(result["provider_base_quote_orientation_verified"])
        self.assertFalse(
            result["onchain_mint_slot_base_quote_semantics_verified"]
        )
        self.assertTrue(all(v is False for v in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
