import unittest

from liquidity_scout.services import (
    WARN,
    build_historical_comparison,
    build_risk_check,
)


MINT = "ReferenceMint"


class FakeHistory:
    def __init__(self, *, old=None, metric="price", threshold=None, direction="down"):
        self.old = old
        self.metric = metric
        self.threshold = threshold
        self.direction = direction
        self.recorded = []

    def parse_historical_comparison(self, _question):
        return {
            "metric": self.metric,
            "period": "7d",
            "period_seconds": 7 * 86400,
            "direction": self.direction,
            "threshold": self.threshold,
            "comparator": None,
        }

    def record_snapshot(self, **kwargs):
        self.recorded.append(kwargs)

    def historical_value(self, _mint, _metric, _period_seconds):
        return self.old

    def percent_change(self, old_value, new_value):
        if old_value == 0:
            return None
        return ((new_value - old_value) / old_value) * 100.0

    def threshold_result(self, change, direction, threshold):
        if direction == "down":
            return change <= -abs(threshold)
        if direction == "up":
            return change >= abs(threshold)
        return abs(change) >= abs(threshold)


def structured_snapshot(*, price=2.0):
    return {
        "symbol": "REF",
        "token_address": MINT,
        "_market_report": {
            "symbol": "REF",
            "mint": MINT,
            "price_usd": price,
            "liquidity_usd": 100000.0,
            "volume_24h_usd": 50000.0,
            "transactions_24h": 250,
            "holders": 100,
            "lp_count": 2,
            "completeness": {
                "price": True,
                "liquidity": True,
                "volume_24h": True,
                "transactions_24h": True,
                "holders": True,
            },
            "provenance": {
                "source": "X1.Ninja/XDEX",
                "catalog_last_refresh_unix": 200,
            },
        },
    }


def market_report():
    return {
        "symbol": "REF",
        "mint": MINT,
        "liquidity_usd": 100000.0,
        "volume_24h_usd": 50000.0,
        "transactions_24h": 250,
        "completeness": {
            "liquidity": True,
            "volume_24h": True,
            "transactions_24h": True,
            "holders": True,
            "price": True,
        },
    }


def tokenomics_report():
    return {
        "supply_verified": True,
        "mint_authority_verified": True,
        "mint_authority_state": "revoked",
        "freeze_authority_verified": True,
        "freeze_authority_state": "none",
        "rpc_decimals_consistent": True,
        "token_activity": {
            "available": True,
            "activity_verified": True,
            "coverage_verified": True,
            "coverage_scope": "bounded",
            "lifetime_coverage_verified": False,
        },
    }


class StructuredHistoricalComparisonTests(unittest.TestCase):
    def test_verified_structured_price_comparison_exposes_risk_ready_fields(self):
        history = FakeHistory(old={"timestamp": 100, "value": 1.0})

        result = build_historical_comparison(
            "How has REF price changed over 7d?",
            structured_snapshot(),
            history_backend=history,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["metric"], "price")
        self.assertEqual(result["period"], "7d")
        self.assertEqual(result["current_value"], 2.0)
        self.assertEqual(result["historical_value"], 1.0)
        self.assertTrue(result["current_verified"])
        self.assertTrue(result["historical_verified"])
        self.assertEqual(result["change_pct"], 100.0)
        self.assertEqual(result["absolute_change"], 1.0)
        self.assertEqual(result["current_observed_at"], 200)
        self.assertEqual(result["historical_observed_at"], 100)
        self.assertEqual(result["source"], "historical_db")
        self.assertEqual(result["asset"], {"symbol": "REF", "mint": MINT})

    def test_structured_comparison_flows_directly_into_risk_check(self):
        history = FakeHistory(old={"timestamp": 100, "value": 1.0})
        comparison = build_historical_comparison(
            "How has REF price changed over 7d?",
            structured_snapshot(),
            history_backend=history,
        )

        risk = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report=comparison,
            policy={"historical_price_warn_abs_change_pct": 50},
        )

        self.assertEqual(risk["recommendation"], WARN)
        self.assertEqual(risk["components"]["history"]["status"], WARN)
        self.assertIn(
            "historical_price_move_exceeds_warn_threshold",
            risk["flags"],
        )
        self.assertTrue(risk["confidence"]["checks"]["historical_price_verified"])

    def test_missing_historical_value_remains_explicitly_unavailable(self):
        history = FakeHistory(old=None)

        result = build_historical_comparison(
            "How has REF price changed over 7d?",
            structured_snapshot(),
            history_backend=history,
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertTrue(result["current_verified"])
        self.assertFalse(result["historical_verified"])
        self.assertIsNone(result["historical_value"])
        self.assertEqual(result["reason"], "historical_value_unavailable")

    def test_legacy_snapshot_stays_display_compatible_but_not_risk_verified(self):
        history = FakeHistory(old={"timestamp": 100, "value": 1.0})
        legacy = {
            "symbol": "REF",
            "token_address": MINT,
            "price_usd_value": 2.0,
            "liquidity": 100000.0,
            "vol24": 50000.0,
            "holders": 100,
            "pool_count": 1,
        }

        result = build_historical_comparison(
            "How has REF price changed over 7d?",
            legacy,
            history_backend=history,
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["current_verified"])
        self.assertTrue(result["historical_verified"])
        self.assertEqual(result["change_pct"], 100.0)
        self.assertEqual(result["reason"], "current_metric_legacy_unverified")

    def test_threshold_result_is_exposed_without_replacing_raw_comparison(self):
        history = FakeHistory(
            old={"timestamp": 100, "value": 2.0},
            threshold=25,
            direction="down",
        )

        result = build_historical_comparison(
            "Did REF price fall 25% over 7d?",
            structured_snapshot(price=1.0),
            history_backend=history,
        )

        self.assertEqual(result["change_pct"], -50.0)
        self.assertEqual(result["threshold"], 25)
        self.assertEqual(result["direction"], "down")
        self.assertTrue(result["threshold_met"])


if __name__ == "__main__":
    unittest.main()
