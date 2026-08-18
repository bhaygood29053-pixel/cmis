from decimal import Decimal
import unittest

from liquidity_scout.providers.x1.xdex_slippage_semantics import (
    classify_xdex_slippage_semantics,
)


class XdexSlippageSemanticTests(unittest.TestCase):
    def test_verifies_exact_percent_transform(self):
        result = classify_xdex_slippage_semantics(
            zero_slippage_output_raw=1_000_000,
            observed_output_raw=995_000,
            slippage_percent="0.5",
        )
        self.assertEqual(result.slippage_bps, Decimal("50.0"))
        self.assertEqual(result.expected_output_raw, 995_000)
        self.assertTrue(result.output_transform_verified)
        self.assertFalse(result.quote_to_onchain_minimum_out_binding_verified)
        self.assertFalse(result.cmis_promotable)

    def test_preserves_mismatch_as_unverified(self):
        result = classify_xdex_slippage_semantics(
            zero_slippage_output_raw=1_000_000,
            observed_output_raw=994_999,
            slippage_percent="0.5",
        )
        self.assertFalse(result.output_transform_verified)

    def test_verifies_price_impact_independence_only_on_exact_match(self):
        matched = classify_xdex_slippage_semantics(
            zero_slippage_output_raw=1000,
            observed_output_raw=999,
            slippage_percent="0.1",
            price_impact_without_slippage="0.1234",
            price_impact_with_slippage="0.1234",
        )
        self.assertTrue(matched.price_impact_independent_of_slippage_verified)

        changed = classify_xdex_slippage_semantics(
            zero_slippage_output_raw=1000,
            observed_output_raw=999,
            slippage_percent="0.1",
            price_impact_without_slippage="0.1234",
            price_impact_with_slippage="0.1235",
        )
        self.assertFalse(changed.price_impact_independent_of_slippage_verified)

    def test_default_requires_same_observed_output(self):
        result = classify_xdex_slippage_semantics(
            zero_slippage_output_raw=1000,
            observed_output_raw=995,
            slippage_percent="0.5",
            omitted_slippage_output_raw=995,
            explicit_default_output_raw=995,
        )
        self.assertTrue(result.default_slippage_verified)

    def test_rejects_invalid_slippage_and_raw_amounts(self):
        for value in (True, -1, 100, "nan", "inf"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    classify_xdex_slippage_semantics(
                        zero_slippage_output_raw=1000,
                        observed_output_raw=995,
                        slippage_percent=value,
                    )

        with self.assertRaises(ValueError):
            classify_xdex_slippage_semantics(
                zero_slippage_output_raw=True,
                observed_output_raw=995,
                slippage_percent="0.5",
            )

    def test_requires_paired_optional_observations(self):
        with self.assertRaises(ValueError):
            classify_xdex_slippage_semantics(
                zero_slippage_output_raw=1000,
                observed_output_raw=995,
                slippage_percent="0.5",
                price_impact_without_slippage="1",
            )
        with self.assertRaises(ValueError):
            classify_xdex_slippage_semantics(
                zero_slippage_output_raw=1000,
                observed_output_raw=995,
                slippage_percent="0.5",
                omitted_slippage_output_raw=995,
            )


if __name__ == "__main__":
    unittest.main()
