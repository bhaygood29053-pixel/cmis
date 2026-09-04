import json
import os
import unittest

from liquidity_scout.providers.x1.ninja_pool_detail import fetch_pool_detail_raw


RUN_LIVE = os.getenv("RUN_X1_NINJA_461_POOL_DETAIL_LIVE") == "1"
POOL = "GwwCyLS4VEeZXyPWPYRNiVSuVur6ntioxBmjDQHHHv9x"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_461_POOL_DETAIL_LIVE=1 for direct pool-detail evidence",
)
class X1Ninja461PoolDetailLiveTests(unittest.TestCase):
    def test_direct_pool_detail_shape_and_rate_limit(self):
        result = fetch_pool_detail_raw(POOL)
        body = result["raw_response"]
        self.assertIsInstance(body, dict)

        def field_presence(value):
            if not isinstance(value, dict):
                return {}
            wanted = (
                "address",
                "poolAddress",
                "pool_address",
                "id",
                "liquidity",
                "priceUsd",
                "priceNative",
                "pooledBase",
                "pooledQuote",
                "lastSyncedAt",
                "lastUpdated",
                "xntPriceUsd",
            )
            return {name: value.get(name) for name in wanted if name in value}

        nested = {}
        for name in ("data", "pool", "result"):
            value = body.get(name)
            if isinstance(value, dict):
                nested[name] = {
                    "keys": sorted(value),
                    "selected_fields": field_presence(value),
                }

        evidence = {
            "schema": "x1_ninja_461_pool_detail_shape.v1",
            "chain": "x1",
            "pool_address": POOL,
            "endpoint": result["endpoint"],
            "observed_at": result["observed_at"],
            "top_level_keys": sorted(body),
            "top_level_selected_fields": field_presence(body),
            "nested_candidates": nested,
            "rate_limit": result["rate_limit"],
            "liquidity_fact_time_verified": False,
            "liquidity_freshness_verified": False,
            "cmis_promotable": False,
        }
        print("X1 #461 DIRECT NINJA POOL-DETAIL SHAPE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertFalse(evidence["liquidity_fact_time_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])


if __name__ == "__main__":
    unittest.main()
