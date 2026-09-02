import unittest

from liquidity_scout.providers.x1.instant_scan_freshness_policy import (
    accepted_instant_scan_freshness_policy,
)
from liquidity_scout.providers.x1.current_market_freshness import (
    evaluate_current_market_freshness,
)


def market(*, price=0.4, observed_at=1000):
    return {
        "data": {
            "price_usd": price,
            "liquidity_usd": 100000.0,
            "volume_24h_usd": 12000.0,
            "transactions_24h": 5000,
            "completeness": {
                "price": True,
                "liquidity": True,
                "volume_24h": True,
                "transactions_24h": True,
            },
            "provenance": {
                "source": "X1.Ninja/XDEX",
                "catalog_last_refresh_unix": observed_at,
            },
        }
    }


def backfill(*, price=0.4, observed_at=990):
    return {
        "status": "partial",
        "provider_history_imported": True,
        "last_imported_observed_at": observed_at,
        "last_imported_price_usd": price,
    }


class InstantX1ScanFreshnessTests(unittest.TestCase):
    def test_policy_is_explicit_and_has_no_hidden_defaults(self):
        policy = accepted_instant_scan_freshness_policy()
        self.assertEqual(
            policy["policy_id"],
            "cmis.x1.instant_x1_scan.current_market_freshness.v1",
        )
        self.assertEqual(policy["max_collection_age_seconds"], 60)
        self.assertEqual(policy["max_price_fact_age_seconds"], 60)
        self.assertEqual(policy["max_future_skew_seconds"], 5)
        self.assertEqual(policy["price_relative_tolerance"], 0.005)
        self.assertTrue(policy["policy_complete"])
        self.assertFalse(policy["has_hidden_defaults"])

    def test_fresh_timestamped_matching_price_is_partial_market_freshness(self):
        result = evaluate_current_market_freshness(
            market(price=0.4, observed_at=1000),
            backfill(price=0.4005, observed_at=990),
            evaluated_at=1010,
            policy=accepted_instant_scan_freshness_policy(),
        )

        self.assertEqual(result["contract_version"], "x1_current_market_freshness/v1")
        self.assertTrue(result["collection_freshness_verified"])
        self.assertTrue(result["provider_price_fact_time_verified"])
        self.assertTrue(result["fields"]["price_usd"]["value_link_verified"])
        self.assertTrue(result["fields"]["price_usd"]["freshness_verified"])
        self.assertFalse(result["fields"]["liquidity_usd"]["freshness_verified"])
        self.assertFalse(result["fields"]["volume_24h_usd"]["freshness_verified"])
        self.assertFalse(result["fields"]["transactions_24h"]["freshness_verified"])
        self.assertEqual(result["freshness_state"], "PARTIAL")
        self.assertEqual(result["verified_field_count"], 1)
        self.assertFalse(result["current_market_freshness_verified"])

    def test_stale_provider_price_fact_fails_closed(self):
        result = evaluate_current_market_freshness(
            market(price=0.4, observed_at=1000),
            backfill(price=0.4, observed_at=900),
            evaluated_at=1010,
            policy=accepted_instant_scan_freshness_policy(),
        )

        self.assertTrue(result["collection_freshness_verified"])
        self.assertFalse(result["provider_price_fact_time_verified"])
        self.assertFalse(result["fields"]["price_usd"]["freshness_verified"])
        self.assertEqual(result["freshness_state"], "NOT_VERIFIED")

    def test_collection_recency_alone_never_proves_price_freshness(self):
        result = evaluate_current_market_freshness(
            market(price=0.4, observed_at=1000),
            {
                "status": "unavailable",
                "provider_history_imported": False,
                "last_imported_observed_at": None,
                "last_imported_price_usd": None,
            },
            evaluated_at=1010,
            policy=accepted_instant_scan_freshness_policy(),
        )

        self.assertTrue(result["collection_freshness_verified"])
        self.assertFalse(result["provider_price_fact_time_verified"])
        self.assertFalse(result["fields"]["price_usd"]["freshness_verified"])
        self.assertFalse(result["fields"]["price_usd"]["value_link_verified"])
        self.assertEqual(result["freshness_state"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
