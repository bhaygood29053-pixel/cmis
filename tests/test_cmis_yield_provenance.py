import unittest
from decimal import Decimal

from liquidity_scout.services.cmis_yield_provenance import (
    CONTRACT_VERSION,
    build_yield_provenance,
)


class CMISYieldProvenanceTests(unittest.TestCase):
    def build(self, **overrides):
        values = {
            "chain": "robinhood",
            "pool_id": "0xpool",
            "window_start": 1000,
            "window_end": 87400,
            "value_unit": "USD",
            "average_liquidity_value": "100000",
            "liquidity_value_verified": True,
            "base_fee_value": "1000",
            "base_fee_value_verified": True,
            "base_fee_evidence_id": "base-fees",
            "incentive_value": "1000",
            "incentive_value_verified": True,
            "incentive_source": "creator rewards",
            "incentive_evidence_id": "booster",
            "reported_apy_percent": "771",
            "reported_apy_source": "lp-app",
        }
        values.update(overrides)
        return build_yield_provenance(**values)

    def test_separates_organic_and_subsidized_yield(self):
        result = self.build()

        self.assertEqual(result["contract_version"], CONTRACT_VERSION)
        self.assertEqual(
            Decimal(result["organic_fee_yield"]["window_return_ratio"]),
            Decimal("0.01"),
        )
        self.assertEqual(
            Decimal(
                result["subsidized_incentive_yield"]["window_return_ratio"]
            ),
            Decimal("0.01"),
        )
        self.assertEqual(
            Decimal(result["combined_yield"]["window_return_ratio"]),
            Decimal("0.02"),
        )
        self.assertEqual(
            result["reported_yield"]["reported_apy_percent"],
            "771",
        )
        self.assertFalse(
            result["reported_yield"]["treated_as_verified_calculation"]
        )
        self.assertFalse(
            result["boundaries"]["future_apy_guarantee_authorized"]
        )
        self.assertFalse(result["execution_authorized"])

    def test_missing_incentive_is_unavailable_not_zero(self):
        result = self.build(
            incentive_value=None,
            incentive_value_verified=False,
            incentive_source=None,
            incentive_evidence_id=None,
        )

        subsidy = result["subsidized_incentive_yield"]
        self.assertEqual(subsidy["state"], "unavailable")
        self.assertIsNone(subsidy["incentive_value"])
        self.assertEqual(
            result["combined_yield"]["state"],
            "unavailable_incentive",
        )
        self.assertIsNone(result["combined_yield"]["window_return_ratio"])
        self.assertFalse(
            result["boundaries"]["missing_incentive_is_zero_authorized"]
        )

    def test_numeric_incentive_requires_verified_evidence(self):
        with self.assertRaisesRegex(
            ValueError,
            "incentive_value_verified=true",
        ):
            self.build(incentive_value_verified=False)

    def test_verified_incentive_requires_value(self):
        with self.assertRaisesRegex(
            ValueError,
            "incentive_value is required",
        ):
            self.build(incentive_value=None)

    def test_liquidity_must_be_verified(self):
        with self.assertRaisesRegex(
            ValueError,
            "liquidity_value_verified must be true",
        ):
            self.build(liquidity_value_verified=False)

    def test_base_fee_must_be_verified(self):
        with self.assertRaisesRegex(
            ValueError,
            "base_fee_value_verified must be true",
        ):
            self.build(base_fee_value_verified=False)

    def test_window_must_be_positive(self):
        with self.assertRaisesRegex(
            ValueError,
            "window_end must be greater",
        ):
            self.build(window_end=1000)


if __name__ == "__main__":
    unittest.main()
