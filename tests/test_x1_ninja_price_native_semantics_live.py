import json
import os
import unittest

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_price_native_semantics import (
    QUOTE_PER_BASE,
    verify_ninja_price_native_semantics,
)
from liquidity_scout.providers.x1.xdex import fetch_pool_list


RUN_LIVE = os.getenv("RUN_X1_NINJA_PRICE_NATIVE_LIVE") == "1"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_PRICE_NATIVE_LIVE=1 to run read-only evidence",
)
class NinjaPriceNativeSemanticsLiveTests(unittest.TestCase):
    def test_live_price_native_matches_one_verified_reserve_ratio(self):
        ninja_pools, _ = fetch_all_pools(sleep_seconds=0)
        xdex_pools = fetch_pool_list(network="X1 Mainnet")

        self.assertTrue(ninja_pools, "X1.Ninja returned no current pools")
        self.assertTrue(xdex_pools, "XDEX returned no X1 Mainnet pools")

        result = verify_ninja_price_native_semantics(
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
            "stable_direction": result["stable_direction"],
            "price_native_pair_direction_verified": result[
                "price_native_pair_direction_verified"
            ],
            "price_native_reserve_ratio_verified": result[
                "price_native_reserve_ratio_verified"
            ],
            "price_native_semantics_verified": result[
                "price_native_semantics_verified"
            ],
            "price_native_unit_verified": result[
                "price_native_unit_verified"
            ],
            "price_native_is_usd_verified": result[
                "price_native_is_usd_verified"
            ],
            "comparison_policy": result["comparison_policy"],
            "samples": result["samples"],
            "semantics": result["semantics"],
            "cmis_promotable": result["cmis_promotable"],
            "execution_authorized": result["execution_authorized"],
        }
        print(
            "[X1.Ninja priceNative semantic evidence] "
            + json.dumps(public, sort_keys=True, default=str)
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["verified_sample_count"], 5)
        self.assertEqual(result["stable_direction"], QUOTE_PER_BASE)
        self.assertTrue(result["price_native_pair_direction_verified"])
        self.assertTrue(result["price_native_reserve_ratio_verified"])
        self.assertTrue(result["price_native_semantics_verified"])
        self.assertTrue(result["price_native_unit_verified"])
        self.assertFalse(result["price_native_is_usd_verified"])
        self.assertTrue(all(v is False for v in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
