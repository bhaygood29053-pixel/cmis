import unittest

from liquidity_scout.providers.x1.ninja_price_fact_time import (
    classify_ninja_current_market_fact_time_series,
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

    def test_current_market_classifier_tracks_all_field_update_coupling_fail_closed(self):
        snapshots = []
        rows = (
            ("1.0", "100", "50", 10, "sync-a"),
            ("1.1", "100", "55", 11, "sync-b"),
            ("1.1", "105", "60", 12, "sync-b"),
        )
        for index, (price, liquidity, volume, txs, sync) in enumerate(rows):
            snapshots.append(
                {
                    "provider_timestamp_candidates": {
                        "global_lastUpdated_raw": index,
                    },
                    "pools": [
                        {
                            "pool_address": "POOL",
                            "status": "ok",
                            "provider": {
                                "priceNative": price,
                                "liquidity": liquidity,
                                "volume24h": volume,
                                "txns24h": txs,
                                "transactions24h": None,
                                "lastSyncedAt_raw": sync,
                            },
                        }
                    ],
                }
            )

        result = classify_ninja_current_market_fact_time_series(snapshots)

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["snapshot_count"], 3)
        self.assertTrue(result["global_lastUpdated_changed"])
        self.assertEqual(
            result["field_summary"]["priceNative"]["change_events"],
            1,
        )
        self.assertEqual(
            result["field_summary"]["liquidity"]["changes_without_row_sync_candidate_change"],
            1,
        )
        self.assertEqual(
            result["field_summary"]["volume24h"]["change_events"],
            2,
        )
        self.assertEqual(
            result["field_summary"]["transactions24h"]["change_events"],
            2,
        )
        for field in result["field_summary"].values():
            self.assertFalse(field["provider_fact_time_verified"])
            self.assertFalse(field["freshness_verified"])
        self.assertFalse(result["provider_timestamp_units_verified"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["update_source_semantics_verified"])
        self.assertFalse(result["current_market_freshness_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_requires_three_snapshots(self):
        with self.assertRaises(ValueError):
            classify_ninja_price_fact_time_series([{}, {}])


if __name__ == "__main__":
    unittest.main()
