import json
import os
import time
import unittest

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_live_update_event import (
    collect_recent_exact_pool_activity,
    select_first_meaningful_transition,
)
from liquidity_scout.providers.x1.ninja_price_fact_time import (
    collect_ninja_price_fact_time_snapshot,
)
from liquidity_scout.providers.x1.ninja_price_native_semantics import (
    verify_ninja_price_native_semantics,
)
from liquidity_scout.providers.x1.xdex import fetch_pool_list


RUN_LIVE = os.getenv("RUN_X1_NINJA_LIVE_UPDATE_EVENT") == "1"
MAX_SNAPSHOTS = int(os.getenv("X1_NINJA_UPDATE_MAX_SNAPSHOTS", "36"))
POLL_SECONDS = int(os.getenv("X1_NINJA_UPDATE_POLL_SECONDS", "10"))


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIVE_UPDATE_EVENT=1 to run read-only evidence",
)
class NinjaLiveUpdateEventEvidenceTests(unittest.TestCase):
    def test_capture_meaningful_provider_update_or_fail_closed(self):
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

        mismatch_pools = [
            "42L71tiJR69Y8jDx9jGCivoxMkyS22LVAANeRS7smH5R",
            "VmZfZnHzFTKSf19ZvAxa4duzChve3JYHVCPq1FvezhN",
        ]
        activity = [
            collect_recent_exact_pool_activity(address, limit=5)
            for address in mismatch_pools
        ]
        print(
            "[X1 mismatch-pool recent signatures] "
            + json.dumps(activity, sort_keys=True, default=str)
        )

        snapshots = []
        result = None
        for index in range(MAX_SNAPSHOTS):
            snapshots.append(
                collect_ninja_price_fact_time_snapshot(
                    pool_addresses=addresses,
                )
            )
            if len(snapshots) >= 2:
                result = select_first_meaningful_transition(
                    snapshots,
                    pool_addresses=addresses,
                )
                if result["status"] == "observed":
                    break
            if index < MAX_SNAPSHOTS - 1:
                time.sleep(POLL_SECONDS)

        if result is None:
            result = select_first_meaningful_transition(
                snapshots,
                pool_addresses=addresses,
            )

        public = {
            "snapshot_count": len(snapshots),
            "poll_seconds": POLL_SECONDS,
            "result": result,
        }
        print(
            "[X1.Ninja live update-event evidence] "
            + json.dumps(public, sort_keys=True, default=str)
        )

        # The workflow is evidence-producing even if the bounded observation
        # window catches no market-fact change. In that case the gate remains
        # explicitly unavailable and #347 must stay open.
        self.assertIn(result["status"], {"observed", "unavailable"})
        if result["status"] == "observed":
            self.assertTrue(result["event"]["market_fact_change_observed"])
            self.assertIn(
                result["event"]["event_type"],
                {"price_only", "reserve_only", "joint_price_and_reserve"},
            )
        else:
            self.assertIsNone(result["event"])

        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["update_source_semantics_verified"])
        self.assertFalse(result["event_ordering_verified"])
        self.assertFalse(result["same_fact_temporal_alignment_verified"])
        self.assertFalse(result["price_native_semantics_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
