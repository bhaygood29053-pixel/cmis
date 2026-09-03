from __future__ import annotations

import unittest

from liquidity_scout.providers.x1.current_market_freshness import (
    evaluate_current_market_freshness,
)
from liquidity_scout.providers.x1.instant_scan_freshness_policy import (
    accepted_instant_scan_freshness_policy,
)


class CurrentMarketFreshness117Tests(unittest.TestCase):
    def test_price_can_be_fresh_without_promoting_other_market_fields(self):
        market = {
            "data": {
                "price_usd": 1.0,
                "completeness": {
                    "price": True,
                    "liquidity": True,
                    "volume_24h": True,
                    "transactions_24h": True,
                },
                "provenance": {"catalog_last_refresh_unix": 995.0},
            }
        }
        backfill = {
            "provider_history_imported": True,
            "last_imported_observed_at": 990.0,
            "last_imported_price_usd": 1.002,
        }

        result = evaluate_current_market_freshness(
            market,
            backfill,
            evaluated_at=1000.0,
            policy=accepted_instant_scan_freshness_policy(),
        )

        self.assertEqual(result["contract_version"], "x1_current_market_freshness/v1")
        self.assertEqual(result["freshness_state"], "PARTIAL")
        self.assertEqual(result["verified_field_count"], 1)
        self.assertTrue(result["fields"]["price_usd"]["freshness_verified"])
        self.assertFalse(result["fields"]["liquidity_usd"]["freshness_verified"])
        self.assertFalse(result["fields"]["volume_24h_usd"]["freshness_verified"])
        self.assertFalse(result["fields"]["transactions_24h"]["freshness_verified"])
        self.assertFalse(result["current_market_freshness_verified"])

    def test_collection_recency_does_not_substitute_for_provider_fact_time(self):
        market = {
            "data": {
                "price_usd": 1.0,
                "completeness": {"price": True},
                "provenance": {"catalog_last_refresh_unix": 999.0},
            }
        }
        backfill = {
            "provider_history_imported": True,
            "last_imported_observed_at": 800.0,
            "last_imported_price_usd": 1.0,
        }
        result = evaluate_current_market_freshness(
            market,
            backfill,
            evaluated_at=1000.0,
            policy=accepted_instant_scan_freshness_policy(),
        )

        self.assertTrue(result["collection_freshness_verified"])
        self.assertFalse(result["provider_price_fact_time_verified"])
        self.assertFalse(result["fields"]["price_usd"]["freshness_verified"])
        self.assertEqual(result["freshness_state"], "NOT_VERIFIED")

    def test_price_value_mismatch_fails_closed(self):
        market = {
            "data": {
                "price_usd": 1.0,
                "completeness": {"price": True},
                "provenance": {"catalog_last_refresh_unix": 999.0},
            }
        }
        backfill = {
            "provider_history_imported": True,
            "last_imported_observed_at": 999.0,
            "last_imported_price_usd": 1.02,
        }
        result = evaluate_current_market_freshness(
            market,
            backfill,
            evaluated_at=1000.0,
            policy=accepted_instant_scan_freshness_policy(),
        )

        price = result["fields"]["price_usd"]
        self.assertFalse(price["value_link_verified"])
        self.assertFalse(price["freshness_verified"])


if __name__ == "__main__":
    unittest.main()
