import unittest

from liquidity_scout.services.cmis_pre_trade import build_pre_trade_check_response
from liquidity_scout.services.pre_trade import build_pre_trade_check
from liquidity_scout.services.pre_trade_liquidity import (
    CMIS_X1_CONSERVATIVE_PRE_TRADE_POLICY,
    DEFAULT_PRE_TRADE_POLICY,
    VERSION,
    assess_trade_size_liquidity,
)


MINT = "AGI111111111111111111111111111111111111111"


def _risk(liquidity=3380.0, *, liquidity_verified=True):
    return {
        "chain": "x1",
        "asset": {"symbol": "AGI", "mint": MINT},
        "recommendation": "PASS",
        "components": {
            "liquidity": {
                "evidence": {"liquidity_usd": liquidity},
            }
        },
        "confidence": {
            "verified_checks": 1,
            "total_checks": 1,
            "checks": {"liquidity_verified": liquidity_verified},
        },
    }


def _trade(notional, side="buy"):
    return {
        "side": side,
        "chain": "x1",
        "asset": {"symbol": "AGI", "mint": MINT},
        "notional_usd": notional,
    }


def _assess(notional, *, side="buy", liquidity=3380.0, liquidity_verified=True):
    return assess_trade_size_liquidity(
        _risk(liquidity=liquidity, liquidity_verified=liquidity_verified),
        _trade(notional, side=side),
        policy=CMIS_X1_CONSERVATIVE_PRE_TRADE_POLICY,
    )


class Issue99TradeSizePolicyTests(unittest.TestCase):
    def test_generic_core_remains_uncalibrated_but_x1_profile_is_explicit(self):
        self.assertEqual(VERSION, "2.0")
        self.assertEqual(DEFAULT_PRE_TRADE_POLICY["policy_name"], "cmis_pre_trade_unconfigured")
        self.assertIsNone(DEFAULT_PRE_TRADE_POLICY["warn_notional_to_liquidity_ratio"])
        self.assertIsNone(DEFAULT_PRE_TRADE_POLICY["block_notional_to_liquidity_ratio"])

        policy = CMIS_X1_CONSERVATIVE_PRE_TRADE_POLICY
        self.assertEqual(policy["policy_name"], "cmis_x1_trade_size_conservative")
        self.assertEqual(policy["policy_version"], "1.0")
        self.assertEqual(policy["low_max_notional_to_liquidity_ratio"], 0.02)
        self.assertEqual(policy["moderate_max_notional_to_liquidity_ratio"], 0.05)
        self.assertEqual(policy["high_max_notional_to_liquidity_ratio"], 0.10)
        self.assertEqual(policy["warn_notional_to_liquidity_ratio"], 0.05)
        self.assertEqual(policy["block_notional_to_liquidity_ratio"], 0.10)

    def test_small_50_dollar_trade_is_low_at_verified_3380_liquidity(self):
        result = _assess(50)
        evidence = result["evidence"]
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(evidence["trade_size_classification"], "LOW")
        self.assertAlmostEqual(evidence["notional_to_liquidity_ratio"], 50 / 3380)
        self.assertEqual(evidence["evidence_status"], "verified")

    def test_medium_trade_is_moderate_then_high_as_ratio_crosses_policy(self):
        moderate = _assess(150)
        high = _assess(250)
        self.assertEqual(moderate["status"], "PASS")
        self.assertEqual(moderate["evidence"]["trade_size_classification"], "MODERATE")
        self.assertEqual(high["status"], "WARN")
        self.assertEqual(high["evidence"]["trade_size_classification"], "HIGH")

    def test_500_dollar_agi_example_is_very_high_and_blocked(self):
        result = _assess(500)
        evidence = result["evidence"]
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(evidence["trade_size_classification"], "VERY_HIGH")
        self.assertAlmostEqual(evidence["notional_to_liquidity_ratio"], 500 / 3380)
        self.assertGreater(evidence["notional_to_liquidity_ratio"], 0.14)

    def test_market_large_2000_trade_is_very_high(self):
        result = _assess(2000)
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["evidence"]["trade_size_classification"], "VERY_HIGH")

    def test_sell_side_uses_same_verified_market_size_policy(self):
        result = _assess(1000, side="sell")
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["evidence"]["trade_size_classification"], "VERY_HIGH")

    def test_missing_liquidity_fails_closed_without_fake_ratio(self):
        result = _assess(500, liquidity=None, liquidity_verified=False)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIsNone(result["evidence"]["notional_to_liquidity_ratio"])
        self.assertIsNone(result["evidence"]["trade_size_classification"])
        self.assertEqual(result["evidence"]["evidence_status"], "insufficient")

    def test_conflicting_or_unverified_liquidity_fails_closed(self):
        result = _assess(500, liquidity=3380.0, liquidity_verified=False)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIsNone(result["evidence"]["notional_to_liquidity_ratio"])
        self.assertIn("sized_trade_liquidity_unverified", result["flags"])

    def test_public_response_exposes_classification_policy_and_thresholds(self):
        response = build_pre_trade_check_response(
            _risk(),
            _trade(500),
            chain="x1",
            policy=CMIS_X1_CONSERVATIVE_PRE_TRADE_POLICY,
        )
        size = response["data"]["trade_size"]
        self.assertEqual(size["assessment"], "BLOCK")
        self.assertEqual(size["classification"], "VERY_HIGH")
        self.assertEqual(size["evidence_status"], "verified")
        self.assertAlmostEqual(size["notional_to_liquidity_ratio"], 500 / 3380)
        self.assertEqual(size["policy"]["contract_version"], "2.0")
        self.assertEqual(size["policy"]["name"], "cmis_x1_trade_size_conservative")
        self.assertEqual(size["policy"]["version"], "1.0")
        self.assertEqual(size["policy"]["warn_notional_to_liquidity_ratio"], 0.05)
        self.assertEqual(size["policy"]["block_notional_to_liquidity_ratio"], 0.10)

    def test_execution_estimates_remain_explicitly_unavailable_without_proof(self):
        result = build_pre_trade_check(
            _risk(),
            _trade(50),
            chain="x1",
            policy=CMIS_X1_CONSERVATIVE_PRE_TRADE_POLICY,
        )
        self.assertTrue(result["analysis_only"])
        self.assertFalse(result["execution_authorized"])
        for name in ("price_impact", "slippage", "fees", "route_quality"):
            capability = result["execution_capabilities"][name]
            self.assertEqual(capability["status"], "unavailable")
            self.assertIsNone(capability["value"])


if __name__ == "__main__":
    unittest.main()
