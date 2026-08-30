import unittest

from liquidity_scout.providers.x1.ninja_live_update_event import (
    classify_ninja_price_reserve_transition,
    select_first_meaningful_transition,
)


def snapshot(*, price="1", base="100", quote="50", sync="s1", global_update="g1"):
    return {
        "observed_at_start": 1,
        "observed_at_end": 2,
        "rpc_slot_bracket": {
            "before": {"slot": 10, "block_time": 100},
            "after": {"slot": 11, "block_time": 101},
        },
        "provider_timestamp_candidates": {
            "global_lastUpdated_raw": global_update,
        },
        "pools": [
            {
                "pool_address": "POOL",
                "provider": {
                    "priceNative": price,
                    "pooledBase": base,
                    "pooledQuote": quote,
                    "lastSyncedAt_raw": sync,
                },
                "price_vs_rpc_ratio": {"relative_error": "0.01"},
            }
        ],
    }


class NinjaLiveUpdateEventTests(unittest.TestCase):
    def test_classifies_price_only_change(self):
        event = classify_ninja_price_reserve_transition(
            snapshot(),
            snapshot(price="1.1"),
            pool_address="POOL",
        )
        self.assertEqual(event["event_type"], "price_only")
        self.assertTrue(event["market_fact_change_observed"])
        self.assertTrue(event["timing_classification_authorized"])
        self.assertFalse(event["provider_fact_time_verified"])

    def test_classifies_reserve_only_change(self):
        event = classify_ninja_price_reserve_transition(
            snapshot(),
            snapshot(base="101", sync="s2"),
            pool_address="POOL",
        )
        self.assertEqual(event["event_type"], "reserve_only")
        self.assertTrue(event["changed_fields"]["lastSyncedAt_raw"])

    def test_classifies_joint_change(self):
        event = classify_ninja_price_reserve_transition(
            snapshot(),
            snapshot(price="1.1", quote="51"),
            pool_address="POOL",
        )
        self.assertEqual(event["event_type"], "joint_price_and_reserve")

    def test_timestamp_only_change_does_not_satisfy_market_fact_gate(self):
        event = classify_ninja_price_reserve_transition(
            snapshot(),
            snapshot(sync="s2", global_update="g2"),
            pool_address="POOL",
        )
        self.assertEqual(event["event_type"], "timestamp_only")
        self.assertTrue(event["update_event_observed"])
        self.assertFalse(event["market_fact_change_observed"])
        self.assertFalse(event["timing_classification_authorized"])

    def test_selects_first_meaningful_transition_and_attaches_activity(self):
        snaps = [
            snapshot(),
            snapshot(sync="s2"),
            snapshot(sync="s2", price="1.2"),
        ]

        def activity(address, *, limit):
            return [
                {
                    "signature": "sig",
                    "slot": 12,
                    "block_time": 102,
                    "err": None,
                    "confirmation_status": "confirmed",
                }
            ]

        result = select_first_meaningful_transition(
            snaps,
            pool_addresses=["POOL"],
            activity_fetcher=activity,
        )
        self.assertEqual(result["status"], "observed")
        self.assertEqual(result["transition_index"], 2)
        self.assertEqual(result["event"]["event_type"], "price_only")
        self.assertTrue(result["recent_exact_pool_activity"]["available"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_no_market_change_fails_closed(self):
        result = select_first_meaningful_transition(
            [snapshot(), snapshot(sync="s2"), snapshot(sync="s3")],
            pool_addresses=["POOL"],
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["event"])
        self.assertTrue(result["timestamp_only_events"])
        self.assertFalse(result["cmis_promotable"])


if __name__ == "__main__":
    unittest.main()
