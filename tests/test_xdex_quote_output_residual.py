import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.xdex_quote_output_residual import (
    observe_xdex_quote_output_residual,
)


class XDEXQuoteOutputResidualTests(unittest.TestCase):
    def test_exact_match_does_not_promote_semantics(self):
        result = observe_xdex_quote_output_residual(
            observed_output_amount="100",
            independently_derived_reference_output_amount="100",
        )
        self.assertTrue(result.exact_match)
        self.assertFalse(result.residual_present)
        self.assertEqual(result.residual_amount, Decimal("0"))
        self.assertEqual(result.residual_ratio, Decimal("0"))
        self.assertFalse(result.residual_cause_verified)
        self.assertFalse(result.curve_semantics_verified)
        self.assertFalse(result.cmis_promotable)

    def test_negative_residual_is_preserved_without_explanation(self):
        result = observe_xdex_quote_output_residual(
            observed_output_amount="97",
            independently_derived_reference_output_amount="100",
        )
        self.assertEqual(result.residual_amount, Decimal("-3"))
        self.assertEqual(result.residual_ratio, Decimal("-0.03"))
        self.assertTrue(result.residual_present)
        self.assertFalse(result.transfer_fee_semantics_verified)
        self.assertFalse(result.rounding_semantics_verified)
        self.assertFalse(result.slippage_semantics_verified)
        self.assertFalse(result.fill_quality_verified)
        self.assertFalse(result.execution_quality_verified)

    def test_positive_residual_is_preserved(self):
        result = observe_xdex_quote_output_residual(
            observed_output_amount="101.5",
            independently_derived_reference_output_amount="100",
        )
        self.assertEqual(result.residual_amount, Decimal("1.5"))
        self.assertEqual(result.residual_ratio, Decimal("0.015"))

    def test_zero_reference_has_no_ratio(self):
        result = observe_xdex_quote_output_residual(
            observed_output_amount="1",
            independently_derived_reference_output_amount="0",
        )
        self.assertIsNone(result.residual_ratio)
        self.assertEqual(result.residual_amount, Decimal("1"))

    def test_invalid_amounts_fail_closed(self):
        for value in (True, -1, "NaN", "Infinity", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                observe_xdex_quote_output_residual(
                    observed_output_amount=value,
                    independently_derived_reference_output_amount="1",
                )
            with self.subTest(reference=value), self.assertRaises(ValueError):
                observe_xdex_quote_output_residual(
                    observed_output_amount="1",
                    independently_derived_reference_output_amount=value,
                )


if __name__ == "__main__":
    unittest.main()
