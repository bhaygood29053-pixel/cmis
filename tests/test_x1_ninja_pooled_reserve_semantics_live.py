import json
import os
import unittest

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_pooled_reserve_semantics import (
    DIRECT_MAPPING,
    verify_ninja_pooled_reserve_semantics,
)
from liquidity_scout.providers.x1.xdex import fetch_pool_list


RUN_LIVE = os.getenv("RUN_X1_NINJA_POOLED_RESERVE_SEMANTICS_LIVE") == "1"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_POOLED_RESERVE_SEMANTICS_LIVE=1 to run read-only evidence",
)
class NinjaPooledReserveSemanticsLiveTests(unittest.TestCase):
    def test_live_pooled_fields_match_exact_rpc_reserves_across_five_pools(self):
        ninja_pools, _ = fetch_all_pools(sleep_seconds=0)
        xdex_pools = fetch_pool_list(network="X1 Mainnet")

        self.assertTrue(ninja_pools, "X1.Ninja returned no current pools")
        self.assertTrue(xdex_pools, "XDEX returned no X1 Mainnet pools")

        result = verify_ninja_pooled_reserve_semantics(
            ninja_pools=ninja_pools,
            xdex_pools=xdex_pools,
            min_verified_pools=5,
            max_samples=5,
            signature_limit=1,
        )

        public = {
            "status": result["status"],
            "sample_count": result["sample_count"],
            "verified_sample_count": result["verified_sample_count"],
            "minimum_verified_pool_count": result[
                "minimum_verified_pool_count"
            ],
            "stable_mapping": result["stable_mapping"],
            "pooled_reserve_field_roles_verified": result[
                "pooled_reserve_field_roles_verified"
            ],
            "pooled_reserve_units_verified": result[
                "pooled_reserve_units_verified"
            ],
            "pooled_reserve_semantics_verified": result[
                "pooled_reserve_semantics_verified"
            ],
            "general_base_quote_semantics_verified": result[
                "general_base_quote_semantics_verified"
            ],
            "comparison_policy": result["comparison_policy"],
            "samples": result["samples"],
            "semantics": result["semantics"],
            "cmis_promotable": result["cmis_promotable"],
            "execution_authorized": result["execution_authorized"],
        }
        print(
            "[X1.Ninja pooled-reserve semantic evidence] "
            + json.dumps(public, sort_keys=True, default=str)
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["verified_sample_count"], 5)
        self.assertEqual(result["stable_mapping"], DIRECT_MAPPING)
        self.assertTrue(result["pooled_reserve_field_roles_verified"])
        self.assertTrue(result["pooled_reserve_units_verified"])
        self.assertTrue(result["pooled_reserve_semantics_verified"])
        self.assertFalse(result["general_base_quote_semantics_verified"])
        self.assertTrue(all(v is False for v in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
