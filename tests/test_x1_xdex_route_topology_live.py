import json
import os
import unittest

from liquidity_scout.providers.x1.xdex_route_topology import (
    TOPOLOGY_MULTI_POOL_CYCLIC,
    aggregate_xdex_route_topologies,
    characterize_xdex_route_topology,
)


RUN_LIVE = os.getenv("RUN_X1_XDEX_ROUTE_TOPOLOGY_LIVE") == "1"
POOL = "GwwCyLS4VEeZXyPWPYRNiVSuVur6ntioxBmjDQHHHv9x"

# Development evidence set from the failed #363 live window.
# The remaining four rejected signatures are intentionally withheld as a
# separate holdout set and are not referenced here.
SIGNATURES = (
    "VyUNh8i2NkqxFsbb1xrMyaRhsXvCiHGkMsLGeAwqsVtvLARHpSnTqk4HU79HKh1m3s5SPku6GJzong2P9TSU2ba",
    "5oVCFKt88tZj3KuHywhrUYhCh5gx5faAwkyeU9YiBWhRpDoKvex3csULXS7JD6Lzrbw4SrXQy8fPRw662TMjpauk",
    "4mS2zp4kssxoe2AMJxALL6PdoKTdje8oQUXs7t7MeVTi3DtBwAuyfxKfGehHqiAx7V7ouARtpePSBmpe3KbxDgC6",
    "43mZe43SdcX4gU3PdawYC6DwBJ1s9y2YtXYevW9eFQK5Sr6HM32Tj8BLgTQqcbBg3WZvJTk3KtvntzaUA51bAoei",
    "318ADq83g41Sz5JhspVAy8oNnAwsTaW7AaVLKVBkYgA1uWZgTAnxpwNRMkBjMfxs349G8munw5hq3cthSwzMouas",
    "65vTuh7tU9F9H5JXpp78r5LSJ95xGTF4PJJXEgLHfZSCyrBa6Fb95aJ7uB18itcEFX1wJsaBVHSKCqC87awHNTK5",
    "4JLtnD7B65oDo1yVHDNruEFaypdYSoUJToKSRWXWLbnQHqKJtUZxpe2JATG93YX9itSxHE6gjUdxaAjrsf71iddg",
    "2BerwgGV1ujcMacobEyzSJfSR3RG2WDDqRgXMR8fFCs7nXrRQBNuSoRzgUZMhuJ1M5FnWYH1X6hJJG573qHSSWa3",
)


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_XDEX_ROUTE_TOPOLOGY_LIVE=1 to run read-only evidence",
)
class XdexRouteTopologyLiveTests(unittest.TestCase):
    def test_issue363_development_signatures_are_resolved_routes(self):
        rows = [
            characterize_xdex_route_topology(
                signature=signature,
                pool_address=POOL,
            )
            for signature in SIGNATURES
        ]
        aggregate = aggregate_xdex_route_topologies(rows)

        public = {
            "pool_address": POOL,
            "development_signatures": list(SIGNATURES),
            "aggregate": aggregate,
            "holdout_consumed": False,
        }
        print(
            "[X1 XDEX route-topology evidence] "
            + json.dumps(public, sort_keys=True, default=str)
        )

        self.assertEqual(aggregate["status"], "verified")
        self.assertEqual(aggregate["signature_count"], 8)
        self.assertEqual(
            aggregate["topology_counts"],
            {TOPOLOGY_MULTI_POOL_CYCLIC: 8},
        )
        self.assertTrue(aggregate["all_route_topologies_verified"])
        self.assertTrue(aggregate["all_target_pool_legs_verified"])
        self.assertTrue(
            aggregate["all_target_vault_attribution_verified"]
        )
        self.assertTrue(
            aggregate["all_routed_target_leg_evidence_complete"]
        )

        for row in rows:
            self.assertEqual(
                row["execution_topology"],
                TOPOLOGY_MULTI_POOL_CYCLIC,
            )
            self.assertTrue(row["route_connected"])
            self.assertTrue(row["route_cyclic"])
            self.assertEqual(row["target_pool_leg_count"], 1)
            self.assertTrue(row["target_pool_leg_verified"])
            self.assertTrue(
                row["target_vault_delta_attribution_verified"]
            )
            self.assertTrue(row["exact_vault_deltas_verified"])
            self.assertTrue(
                row["routed_target_leg_evidence_complete"]
            )
            self.assertEqual(row["order_origin"], "unknown")
            self.assertFalse(row["twap_execution_verified"])
            self.assertFalse(row["limit_order_execution_verified"])
            self.assertFalse(row["take_profit_execution_verified"])
            self.assertFalse(row["stop_loss_execution_verified"])
            self.assertFalse(row["classification_change_authorized"])
            self.assertTrue(
                row["existing_fail_closed_block_should_remain"]
            )
            self.assertFalse(row["provider_fact_time_verified"])
            self.assertFalse(row["freshness_verified"])
            self.assertFalse(row["cmis_promotable"])
            self.assertFalse(row["execution_authorized"])

        self.assertFalse(aggregate["classification_change_authorized"])
        self.assertFalse(aggregate["departure_pattern_verified"])
        self.assertFalse(aggregate["cmis_promotable"])
        self.assertFalse(aggregate["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
