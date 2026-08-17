import copy
import unittest

from liquidity_scout.providers.x1.reserve_scope_measurements import (
    measure_x1_reserve_scope,
)


def bundle():
    return {
        "service": "x1_reserve_live_evidence",
        "version": "1.0",
        "chain": "x1",
        "pool_address": "pool111",
        "collection": {
            "started_at": 100.0,
            "ended_at": 106.0,
            "duration_seconds": 6.0,
            "sequence": [
                {"step": "provider_pool_detail", "completed_at": 101.0},
                {"step": "asset_rpc_balance", "completed_at": 102.0},
                {"step": "asset_rpc_identity", "completed_at": 103.0},
                {"step": "counter_rpc_balance", "completed_at": 104.0},
                {"step": "counter_rpc_identity", "completed_at": 105.0},
            ],
        },
        "provider": {
            "source": "X1.Ninja Developer API",
            "observed_at": 100.5,
            "last_synced_at": "1970-01-01T00:01:40Z",
            "last_updated": 1234567890,
        },
        "roles": {
            "asset": {
                "rpc_balance": {"slot": 10},
                "rpc_identity_observation": {"slot": 10},
                "rpc_identity_verification": {"identity_verified": True},
                "rpc_decimals_match": True,
            },
            "counter": {
                "rpc_balance": {"slot": 11},
                "rpc_identity_observation": {"slot": 12},
                "rpc_identity_verification": {"identity_verified": True},
                "rpc_decimals_match": True,
            },
        },
        "rpc_identity_verified": True,
        "rpc_decimals_match": True,
        "reserve_field_semantics_verified": False,
        "observation_scope_verified": False,
        "value_agreement_verified": False,
        "cmis_promotable": False,
    }


class X1ReserveScopeMeasurementsTests(unittest.TestCase):
    def test_measures_complete_scope_without_deciding_freshness(self):
        result = measure_x1_reserve_scope(bundle())

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["metrics"]["collection_duration_seconds"], 6.0)
        self.assertTrue(result["metrics"]["collection_sequence_monotonic"])
        self.assertTrue(result["metrics"]["provider_observed_within_collection"])
        self.assertEqual(
            result["metrics"][
                "provider_reported_last_synced_age_at_collection_end_seconds"
            ],
            6.0,
        )
        self.assertEqual(result["metrics"]["provider_last_updated_raw"], 1234567890)
        self.assertEqual(result["metrics"]["rpc_min_slot"], 10)
        self.assertEqual(result["metrics"]["rpc_max_slot"], 12)
        self.assertEqual(result["metrics"]["rpc_slot_span"], 2)
        self.assertEqual(
            result["metrics"]["roles"]["asset"]["balance_identity_slot_delta"],
            0,
        )
        self.assertEqual(
            result["metrics"]["roles"]["counter"]["balance_identity_slot_delta"],
            1,
        )
        self.assertTrue(result["evidence_flags"]["rpc_identity_verified"])
        self.assertTrue(result["evidence_flags"]["rpc_decimals_match"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["observation_scope_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["errors"], [])

    def test_unparseable_provider_sync_time_is_partial_not_freshness_inference(self):
        item = bundle()
        item["provider"]["last_synced_at"] = "not-a-time"

        result = measure_x1_reserve_scope(item)

        self.assertEqual(result["status"], "partial")
        self.assertIsNone(
            result["metrics"][
                "provider_reported_last_synced_age_at_collection_end_seconds"
            ]
        )
        self.assertIn("provider_last_synced_at_unparseable", result["warnings"])
        self.assertFalse(result["freshness_verified"])

    def test_missing_rpc_slot_is_partial_and_preserves_other_slot_metrics(self):
        item = bundle()
        del item["roles"]["counter"]["rpc_identity_observation"]["slot"]

        result = measure_x1_reserve_scope(item)

        self.assertEqual(result["status"], "partial")
        self.assertIn("counter_rpc_slot_unavailable", result["warnings"])
        self.assertEqual(result["metrics"]["rpc_min_slot"], 10)
        self.assertEqual(result["metrics"]["rpc_max_slot"], 11)
        self.assertIsNone(
            result["metrics"]["roles"]["counter"]["balance_identity_slot_delta"]
        )
        self.assertFalse(result["cmis_promotable"])

    def test_non_monotonic_collection_sequence_is_error(self):
        item = bundle()
        item["collection"]["sequence"][2]["completed_at"] = 101.5

        result = measure_x1_reserve_scope(item)

        self.assertEqual(result["status"], "error")
        self.assertIn(
            "collection_sequence_non_monotonic_or_invalid",
            result["errors"],
        )
        self.assertFalse(result["observation_scope_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_sequence_outside_collection_bounds_is_error(self):
        item = bundle()
        item["collection"]["sequence"][-1]["completed_at"] = 107.0

        result = measure_x1_reserve_scope(item)

        self.assertEqual(result["status"], "error")
        self.assertIn("collection_sequence_outside_bounds", result["errors"])

    def test_provider_observation_outside_collection_is_reported_without_policy(self):
        item = bundle()
        item["provider"]["observed_at"] = 99.0

        result = measure_x1_reserve_scope(item)

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["metrics"]["provider_observed_within_collection"])
        self.assertIn("provider_observed_at_outside_collection", result["warnings"])
        self.assertFalse(result["freshness_verified"])

    def test_wrong_bundle_identity_fails_closed(self):
        item = bundle()
        item["service"] = "other_service"
        item["chain"] = "solana"

        result = measure_x1_reserve_scope(item)

        self.assertEqual(result["status"], "error")
        self.assertIn("unexpected_bundle_service", result["errors"])
        self.assertIn("wrong_chain", result["errors"])
        self.assertFalse(result["cmis_promotable"])

    def test_input_must_be_mapping(self):
        with self.assertRaisesRegex(TypeError, "bundle must be a mapping"):
            measure_x1_reserve_scope([])


if __name__ == "__main__":
    unittest.main()
