import unittest

from liquidity_scout.providers.x1.ninja_price_fact_time import (
    classify_ninja_price_fact_time_series,
)


class NinjaPriceFactTimeSeriesTests(unittest.TestCase):
    def test_detects_price_change_without_claiming_source_semantics(self):
        snapshots = []
        for i, price in enumerate(("1.0", "1.1", "1.2")):
            snapshots.append(
                {
                    "provider_timestamp_candidates": {
                        "global_lastUpdated_raw": i,
                    },
                    "pools": [
                        {
                            "pool_address": "POOL",
                            "status": "ok",
                            "provider": {
                                "priceNative": price,
                                "pooledBase": "100",
                                "pooledQuote": "50",
                                "lastSyncedAt_raw": "same",
                            },
                            "price_vs_rpc_ratio": {
                                "relative_error": "1e-3",
                            },
                        }
                    ],
                }
            )

        result = classify_ninja_price_fact_time_series(snapshots)

        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["global_lastUpdated_changed"])
        self.assertTrue(result["separate_price_update_behavior_observed"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["update_source_semantics_verified"])
        self.assertFalse(result["same_fact_temporal_alignment_verified"])
        self.assertFalse(result["price_native_semantics_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_requires_three_snapshots(self):
        with self.assertRaises(ValueError):
            classify_ninja_price_fact_time_series([{}, {}])


if __name__ == "__main__":
    unittest.main()
