import unittest

from liquidity_scout.services.pre_trade_size import (
    POLICY_SCHEMA_VERSION,
    assess_trade_size,
    normalize_trade_size_policy,
)


class PreTradeSizeTests(unittest.TestCase):
    def test_ratio_is_calculated_without_inventing_thresholds(self):
        result = assess_trade_size(500, 3380, liquidity_verified=True)
        self.assertTrue(result["available"])
        self.assertEqual(result["status"], "UNCLASSIFIED")
        self.assertEqual(result["notional_to_liquidity_ratio"], str(__import__("decimal").Decimal("500") / __import__("decimal").Decimal("3380")))
        self.assertIn("trade_size_policy_thresholds_unset", result["flags"])

    def test_explicit_versioned_policy_classifies_pass_warn_block(self):
        policy = {
            "schema_version": POLICY_SCHEMA_VERSION,
            "warn_ratio": "0.05",
            "block_ratio": "0.10",
        }
        self.assertEqual(assess_trade_size(40, 1000, liquidity_verified=True, policy=policy)["status"], "PASS")
        self.assertEqual(assess_trade_size(50, 1000, liquidity_verified=True, policy=policy)["status"], "WARN")
        self.assertEqual(assess_trade_size(100, 1000, liquidity_verified=True, policy=policy)["status"], "BLOCK")

    def test_unverified_liquidity_fails_closed(self):
        result = assess_trade_size(500, 3380, liquidity_verified=False)
        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIsNone(result["notional_to_liquidity_ratio"])

    def test_zero_verified_liquidity_blocks_without_division(self):
        result = assess_trade_size(10, 0, liquidity_verified=True)
        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "BLOCK")
        self.assertIsNone(result["notional_to_liquidity_ratio"])

    def test_invalid_notional_rejected(self):
        for value in (None, 0, -1, True, "nan", "inf"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    assess_trade_size(value, 1000, liquidity_verified=True)

    def test_policy_is_explicit_and_ordered(self):
        with self.assertRaises(ValueError):
            normalize_trade_size_policy({"schema_version": POLICY_SCHEMA_VERSION, "warn_ratio": "0.2", "block_ratio": "0.1"})
        with self.assertRaises(ValueError):
            normalize_trade_size_policy({"schema_version": "future.v2", "warn_ratio": "0.1"})
        with self.assertRaises(ValueError):
            normalize_trade_size_policy({"schema_version": POLICY_SCHEMA_VERSION, "mystery": 1})


if __name__ == "__main__":
    unittest.main()
