import unittest

from liquidity_scout.services import (
    ERROR,
    OK,
    PARTIAL,
    UNAVAILABLE,
    WARN,
    build_historical_compare_response,
    build_risk_check,
)


MINT = "ReferenceMint"


class FakeHistory:
    def __init__(self, *, old=None, metric="price", period="24h", recognized=True):
        self.old = old
        self.metric = metric
        self.period = period
        self.recognized = recognized
        self.recorded = []

    def parse_historical_comparison(self, _question):
        if not self.recognized:
            return None
        return {
            "metric": self.metric,
            "period": self.period,
            "period_seconds": 86400 if self.period == "24h" else None,
            "direction": None,
            "threshold": None,
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


def market_report(*, price=120.0, observed_at=2000):
    return {
        "symbol": "REF",
        "mint": MINT,
        "price_usd": price,
        "liquidity_usd": 250000.0,
        "volume_24h_usd": 125000.0,
        "transactions_24h": 500,
        "holders": 1000,
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
            "catalog_last_refresh_unix": observed_at,
        },
    }


def structured_snapshot(*, price=120.0, observed_at=2000):
    report = market_report(price=price, observed_at=observed_at)
    return {
        "symbol": "REF",
        "token_address": MINT,
        "_market_report": report,
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


class CMISHistoricalContractTests(unittest.TestCase):
    def test_verified_comparison_is_ok_and_preserves_structured_data(self):
        response = build_historical_compare_response(
            "How has REF price changed in 24h?",
            structured_snapshot(),
            history_backend=FakeHistory(old={"timestamp": 1000, "value": 100.0}),
        )

        self.assertEqual(response["service"], "historical_compare")
        self.assertEqual(response["chain"], "x1")
        self.assertEqual(response["status"], OK)
        self.assertEqual(response["asset"], {"symbol": "REF", "mint": MINT})
        self.assertEqual(response["data"]["metric"], "price")
        self.assertEqual(response["data"]["current_value"], 120.0)
        self.assertEqual(response["data"]["historical_value"], 100.0)
        self.assertEqual(response["data"]["change_pct"], 20.0)
        self.assertTrue(response["data"]["current_verified"])
        self.assertTrue(response["data"]["historical_verified"])
        self.assertTrue(response["confidence"]["complete"])
        self.assertEqual(response["confidence"]["verified_checks"], 3)
        self.assertEqual(response["observed_at"], 2000)
        self.assertEqual(response["errors"], [])

    def test_sources_preserve_current_and_historical_observation_times(self):
        response = build_historical_compare_response(
            "How has REF price changed in 24h?",
            structured_snapshot(observed_at=2000),
            history_backend=FakeHistory(old={"timestamp": 1000, "value": 100.0}),
        )

        self.assertIn(
            {
                "source": "X1.Ninja/XDEX",
                "role": "historical_compare.current",
                "observed_at": 2000,
            },
            response["sources"],
        )
        self.assertIn(
            {
                "source": "historical_db",
                "role": "historical_compare.baseline",
                "observed_at": 1000,
            },
            response["sources"],
        )

    def test_missing_historical_baseline_is_unavailable_not_zero(self):
        response = build_historical_compare_response(
            "How has REF price changed in 24h?",
            structured_snapshot(),
            history_backend=FakeHistory(old=None),
        )

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertIsNone(response["data"]["historical_value"])
        self.assertFalse(response["data"]["historical_verified"])
        self.assertIsNone(response["data"]["change_pct"])
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("historical_value_unavailable", codes)
        self.assertIn("historical_metric_verified", codes)
        self.assertIn("change_verified", codes)

    def test_zero_historical_baseline_is_partial_and_change_unverified(self):
        response = build_historical_compare_response(
            "How has REF price changed in 24h?",
            structured_snapshot(),
            history_backend=FakeHistory(old={"timestamp": 1000, "value": 0.0}),
        )

        self.assertEqual(response["status"], PARTIAL)
        self.assertEqual(response["data"]["historical_value"], 0.0)
        self.assertTrue(response["data"]["historical_verified"])
        self.assertIsNone(response["data"]["change_pct"])
        self.assertFalse(response["confidence"]["checks"]["change_verified"])
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("historical_baseline_zero", codes)

    def test_legacy_snapshot_remains_partial_not_silently_verified(self):
        legacy = {
            "symbol": "REF",
            "token_address": MINT,
            "price_usd_value": 120.0,
            "liquidity": 250000.0,
            "vol24": 125000.0,
            "holders": 1000,
            "pool_count": 2,
        }
        response = build_historical_compare_response(
            "How has REF price changed in 24h?",
            legacy,
            history_backend=FakeHistory(old={"timestamp": 1000, "value": 100.0}),
        )

        self.assertEqual(response["status"], PARTIAL)
        self.assertFalse(response["data"]["current_verified"])
        self.assertTrue(response["data"]["historical_verified"])
        self.assertFalse(response["confidence"]["checks"]["change_verified"])
        self.assertEqual(response["data"]["reason"], "current_metric_legacy_unverified")

    def test_unrecognized_request_is_explicit_error(self):
        response = build_historical_compare_response(
            "Tell me something unrelated",
            structured_snapshot(),
            history_backend=FakeHistory(recognized=False),
        )

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "historical_request_unrecognized")

    def test_invalid_snapshot_is_explicit_error(self):
        response = build_historical_compare_response(
            "How has REF price changed in 24h?",
            "not a snapshot",
            history_backend=FakeHistory(),
        )

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "invalid_market_snapshot")

    def test_wrapper_data_flows_directly_into_risk_check(self):
        market = market_report(price=120.0)
        response = build_historical_compare_response(
            "How has REF price changed in 24h?",
            {"symbol": "REF", "token_address": MINT, "_market_report": market},
            history_backend=FakeHistory(old={"timestamp": 1000, "value": 100.0}),
        )

        risk = build_risk_check(
            market,
            tokenomics_report(),
            historical_report=response["data"],
            policy={"historical_price_warn_abs_change_pct": 15.0},
        )

        self.assertEqual(response["status"], OK)
        self.assertEqual(risk["recommendation"], WARN)
        self.assertIn("historical_price_move_exceeds_warn_threshold", risk["flags"])
        self.assertEqual(risk["components"]["history"]["evidence"]["change_pct"], 20.0)

    def test_chain_and_explicit_observed_at_are_preserved(self):
        response = build_historical_compare_response(
            "How has REF price changed in 24h?",
            structured_snapshot(observed_at=2000),
            history_backend=FakeHistory(old={"timestamp": 1000, "value": 100.0}),
            chain="Solana",
            observed_at="2026-08-15T10:48:00Z",
        )

        self.assertEqual(response["chain"], "solana")
        self.assertEqual(response["observed_at"], "2026-08-15T10:48:00Z")
        self.assertEqual(response["status"], OK)


if __name__ == "__main__":
    unittest.main()
