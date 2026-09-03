import json
import os
import time
import unittest

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_price_fact_time import (
    classify_ninja_current_market_fact_time_series,
    classify_ninja_price_fact_time_series,
    collect_ninja_price_fact_time_snapshot,
)
from liquidity_scout.providers.x1.ninja_price_native_semantics import (
    verify_ninja_price_native_semantics,
)
from liquidity_scout.providers.x1.xdex import fetch_pool_list


RUN_LIVE = os.getenv("RUN_X1_NINJA_PRICE_FACT_TIME_LIVE") == "1"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_PRICE_FACT_TIME_LIVE=1 to run read-only evidence",
)
class NinjaPriceFactTimeLiveTests(unittest.TestCase):
    def test_repeated_slot_bracketed_price_fact_time_evidence(self):
        ninja_pools, _ = fetch_all_pools(sleep_seconds=0)
        xdex_pools = fetch_pool_list(network="X1 Mainnet")
        initial = verify_ninja_price_native_semantics(
            ninja_pools=ninja_pools,
            xdex_pools=xdex_pools,
            min_verified_pools=5,
            max_samples=5,
            signature_limit=1,
        )

        addresses = [
            row["pool_address"]
            for row in initial["samples"]
            if row.get("pool_address")
        ]
        self.assertEqual(len(addresses), 5)

        snapshots = []
        for index in range(3):
            snapshots.append(
                collect_ninja_price_fact_time_snapshot(
                    pool_addresses=addresses,
                )
            )
            if index < 2:
                time.sleep(5)

        result = classify_ninja_price_fact_time_series(snapshots)
        current_market = classify_ninja_current_market_fact_time_series(
            snapshots
        )

        print(
            "[X1.Ninja price fact-time snapshots] "
            + json.dumps(snapshots, sort_keys=True, default=str)
        )
        print(
            "[X1.Ninja price fact-time series] "
            + json.dumps(result, sort_keys=True, default=str)
        )
        print(
            "[X1.Ninja current-market fact-time series] "
            + json.dumps(current_market, sort_keys=True, default=str)
        )

        self.assertEqual(result["snapshot_count"], 3)
        self.assertEqual(current_market["snapshot_count"], 3)
        self.assertFalse(current_market["provider_fact_time_verified"])
        self.assertFalse(current_market["current_market_freshness_verified"])
        self.assertFalse(result["provider_timestamp_units_verified"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["update_source_semantics_verified"])
        self.assertFalse(result["same_fact_temporal_alignment_verified"])
        self.assertFalse(result["price_native_semantics_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
