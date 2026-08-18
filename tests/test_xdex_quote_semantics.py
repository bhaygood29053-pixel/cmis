import unittest

from liquidity_scout.providers.x1.xdex_quote_semantics import classify_xdex_quote_semantics


IN_MINT = "InputMint111"
OUT_MINT = "OutputMint222"
CONFIG = "Config333"


def quote(**overrides):
    value = {
        "inputMint": IN_MINT,
        "outputMint": OUT_MINT,
        "amm_config_address": CONFIG,
        "inputAmount": 100,
        "outputAmount": 97,
        "rate": "0.97",
        "priceImpactPct": "0.125",
    }
    value.update(overrides)
    return value


class XDEXQuoteSemanticTests(unittest.TestCase):
    def test_verified_fields_remain_narrow_and_non_promotable(self):
        result = classify_xdex_quote_semantics(
            quote(),
            requested_input_mint=IN_MINT,
            requested_output_mint=OUT_MINT,
            independently_verified_amm_config=CONFIG,
            independently_verified_trade_fee_bps=28,
            corroborated_price_impact_pct="0.125",
        )
        self.assertTrue(result.route_identity_verified)
        self.assertTrue(result.amm_config_identity_verified)
        self.assertTrue(result.trade_fee_config_verified)
        self.assertEqual(result.trade_fee_bps, 28)
        self.assertTrue(result.price_impact_semantics_verified)
        self.assertFalse(result.output_amount_semantics_verified)
        self.assertFalse(result.output_decomposition_verified)
        self.assertFalse(result.slippage_semantics_verified)
        self.assertFalse(result.fill_quality_verified)
        self.assertFalse(result.execution_quality_verified)
        self.assertFalse(result.cmis_promotable)

    def test_route_mismatch_fails_identity(self):
        result = classify_xdex_quote_semantics(
            quote(outputMint="OtherMint"),
            requested_input_mint=IN_MINT,
            requested_output_mint=OUT_MINT,
            independently_verified_amm_config=CONFIG,
        )
        self.assertFalse(result.route_identity_verified)
        self.assertFalse(result.amm_config_identity_verified)

    def test_config_mismatch_blocks_config_identity(self):
        result = classify_xdex_quote_semantics(
            quote(),
            requested_input_mint=IN_MINT,
            requested_output_mint=OUT_MINT,
            independently_verified_amm_config="OtherConfig",
        )
        self.assertTrue(result.route_identity_verified)
        self.assertFalse(result.amm_config_identity_verified)

    def test_fee_requires_verified_config_identity(self):
        with self.assertRaises(ValueError):
            classify_xdex_quote_semantics(
                quote(),
                requested_input_mint=IN_MINT,
                requested_output_mint=OUT_MINT,
                independently_verified_amm_config="OtherConfig",
                independently_verified_trade_fee_bps=28,
            )

    def test_invalid_fee_rejected(self):
        for fee in (True, -1, 10001, 2.8):
            with self.subTest(fee=fee), self.assertRaises(ValueError):
                classify_xdex_quote_semantics(
                    quote(),
                    requested_input_mint=IN_MINT,
                    requested_output_mint=OUT_MINT,
                    independently_verified_amm_config=CONFIG,
                    independently_verified_trade_fee_bps=fee,
                )

    def test_impact_mismatch_stays_unverified(self):
        result = classify_xdex_quote_semantics(
            quote(),
            requested_input_mint=IN_MINT,
            requested_output_mint=OUT_MINT,
            independently_verified_amm_config=CONFIG,
            corroborated_price_impact_pct="0.126",
        )
        self.assertFalse(result.price_impact_semantics_verified)

    def test_impact_requires_field_and_finite_values(self):
        missing = quote()
        missing.pop("priceImpactPct")
        with self.assertRaises(ValueError):
            classify_xdex_quote_semantics(
                missing,
                requested_input_mint=IN_MINT,
                requested_output_mint=OUT_MINT,
                independently_verified_amm_config=CONFIG,
                corroborated_price_impact_pct="0.1",
            )
        for value in (True, "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                classify_xdex_quote_semantics(
                    quote(priceImpactPct=value),
                    requested_input_mint=IN_MINT,
                    requested_output_mint=OUT_MINT,
                    independently_verified_amm_config=CONFIG,
                    corroborated_price_impact_pct="0.1",
                )

    def test_requested_mints_must_be_distinct_and_nonempty(self):
        for input_mint, output_mint in (("", OUT_MINT), (IN_MINT, ""), (IN_MINT, IN_MINT)):
            with self.subTest(input_mint=input_mint, output_mint=output_mint), self.assertRaises(ValueError):
                classify_xdex_quote_semantics(
                    quote(),
                    requested_input_mint=input_mint,
                    requested_output_mint=output_mint,
                )


if __name__ == "__main__":
    unittest.main()
