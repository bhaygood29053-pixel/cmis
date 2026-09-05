import unittest

from liquidity_scout.providers.x1.current_usdcx_usd_equivalence import (
    PYTH_USDC_USD_UNIT,
    SOLANA_USDC_MINT,
    X1_USDC_X_MINT,
    evaluate_current_usdcx_usd_equivalence,
)


def route():
    return {
        "warp_qualified": True,
        "exact_route_identity_verified": True,
        "route_status_verified": True,
        "backing_model_verified": True,
        "source_chain": "solana",
        "source_mint": SOLANA_USDC_MINT,
        "destination_chain": "x1",
        "destination_mint": X1_USDC_X_MINT,
    }


def source_price(price="1.0002", *, unit=PYTH_USDC_USD_UNIT):
    return {
        "chain": "solana",
        "source": "pyth_core_solana_push",
        "mint": SOLANA_USDC_MINT,
        "mapping_verified": True,
        "price_integrity_verified": True,
        "fact_time_verified": True,
        "unit": unit,
        "price_usd": price,
    }


def fresh():
    return {
        "classification": "FRESH",
        "classification_verified": True,
        "pyth_freshness_verified": True,
        "pyth_current_price_eligible": True,
    }


def parity():
    return {
        "source_mint": SOLANA_USDC_MINT,
        "destination_mint": X1_USDC_X_MINT,
        "proof_scope": "current",
        "reserve_or_redemption_semantics_verified": True,
        "destination_representation_value_equivalence_verified": True,
    }


class CurrentUsdcxUsdEquivalenceTests(unittest.TestCase):
    def test_route_and_fresh_source_price_do_not_prove_destination_parity(self):
        result = evaluate_current_usdcx_usd_equivalence(
            warp_route_evidence=route(),
            source_usdc_usd_evidence=source_price(),
            source_usdc_freshness=fresh(),
        )
        self.assertTrue(result["route_identity_verified"])
        self.assertTrue(result["source_usdc_usd_price_unit_verified"])
        self.assertTrue(result["source_usdc_usd_price_fresh"])
        self.assertFalse(result["destination_representation_value_equivalence_verified"])
        self.assertFalse(result["current_usdcx_usd_equivalence_verified"])
        self.assertIn("destination_representation_value_equivalence", result["missing_gates"])

    def test_full_current_parity_contract_can_verify_equivalence(self):
        result = evaluate_current_usdcx_usd_equivalence(
            warp_route_evidence=route(),
            source_usdc_usd_evidence=source_price("0.9998"),
            source_usdc_freshness=fresh(),
            destination_parity_evidence=parity(),
        )
        self.assertTrue(result["current_usdcx_usd_equivalence_verified"])
        self.assertFalse(result["historical_usdcx_usd_equivalence_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_provider_native_pyth_unit_is_required(self):
        wrong_unit = source_price(unit="USD")
        result = evaluate_current_usdcx_usd_equivalence(
            warp_route_evidence=route(),
            source_usdc_usd_evidence=wrong_unit,
            source_usdc_freshness=fresh(),
            destination_parity_evidence=parity(),
        )
        self.assertFalse(result["source_usdc_usd_price_unit_verified"])
        self.assertFalse(result["current_usdcx_usd_equivalence_verified"])
        self.assertIn("verified_solana_usdc_usd_price", result["missing_gates"])

    def test_stale_source_price_fails_closed(self):
        stale = fresh()
        stale["classification"] = "STALE"
        stale["pyth_current_price_eligible"] = False
        result = evaluate_current_usdcx_usd_equivalence(
            warp_route_evidence=route(),
            source_usdc_usd_evidence=source_price(),
            source_usdc_freshness=stale,
            destination_parity_evidence=parity(),
        )
        self.assertFalse(result["current_usdcx_usd_equivalence_verified"])
        self.assertIn("fresh_solana_usdc_usd_price", result["missing_gates"])

    def test_wrong_destination_mint_fails_closed(self):
        wrong = route()
        wrong["destination_mint"] = "WrongMint111"
        result = evaluate_current_usdcx_usd_equivalence(
            warp_route_evidence=wrong,
            source_usdc_usd_evidence=source_price(),
            source_usdc_freshness=fresh(),
            destination_parity_evidence=parity(),
        )
        self.assertFalse(result["route_identity_verified"])
        self.assertFalse(result["current_usdcx_usd_equivalence_verified"])

    def test_source_usdc_outside_tolerance_fails_closed(self):
        result = evaluate_current_usdcx_usd_equivalence(
            warp_route_evidence=route(),
            source_usdc_usd_evidence=source_price("0.97"),
            source_usdc_freshness=fresh(),
            destination_parity_evidence=parity(),
        )
        self.assertFalse(result["source_usdc_within_usd_tolerance"])
        self.assertFalse(result["current_usdcx_usd_equivalence_verified"])


if __name__ == "__main__":
    unittest.main()
