import unittest

from liquidity_scout.providers.x1.ninja_liquidity_revaluation_series import (
    REFERENCE_SOURCE,
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
    evaluate_ninja_liquidity_revaluation_series,
)


def event(key, pool, *, aligned=True):
    return {
        "event_key": key,
        "pool_address": pool,
        "revaluation": {
            "price_only_liquidity_revaluation_verified": True,
            "provider_internal_liquidity_formula_supported": True,
            "liquidity_usd_semantics_verified": False,
            "liquidity_freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        },
        "reference_alignment": {
            "source": REFERENCE_SOURCE,
            "base_mint": WRAPPED_XNT_MINT,
            "quote_mint": USDC_X_MINT,
            "exact_pool_identity_verified": True,
            "rpc_reserves_verified": True,
            "reference_fact_time_verified": aligned,
            "same_fact_temporal_alignment_verified": aligned,
            "provider_reference_price_matches_rpc": aligned,
        },
    }


class NinjaLiquidityRevaluationSeriesTests(unittest.TestCase):
    def test_repeated_same_fact_evidence_can_verify_fact_time_without_usd(self):
        result = evaluate_ninja_liquidity_revaluation_series(
            [
                event("a", "pool-1"),
                event("b", "pool-2"),
                event("c", "pool-1"),
            ]
        )
        self.assertTrue(result["repeated_revaluation_pattern_supported"])
        self.assertTrue(result["liquidity_fact_time_verified"])
        self.assertFalse(result["current_usdcx_usd_equivalence_verified"])
        self.assertFalse(result["x1_ninja_liquidity_usd_semantics_verified"])
        self.assertFalse(result["liquidity_freshness_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_five_distinct_same_fact_pools_plus_usd_can_verify_semantics(self):
        rows = [event(str(i), f"pool-{i}") for i in range(5)]
        result = evaluate_ninja_liquidity_revaluation_series(
            rows,
            current_usdcx_usd_equivalence_verified=True,
        )
        self.assertTrue(result["liquidity_fact_time_verified"])
        self.assertEqual(result["same_fact_reference_pool_count"], 5)
        self.assertTrue(result["x1_ninja_liquidity_usd_semantics_verified"])
        self.assertFalse(result["liquidity_freshness_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_duplicate_event_key_blocks_repeated_support(self):
        result = evaluate_ninja_liquidity_revaluation_series(
            [
                event("dup", "pool-1"),
                event("dup", "pool-2"),
                event("c", "pool-3"),
            ],
            current_usdcx_usd_equivalence_verified=True,
        )
        self.assertFalse(result["unique_event_keys"])
        self.assertFalse(result["repeated_revaluation_pattern_supported"])
        self.assertFalse(result["liquidity_fact_time_verified"])
        self.assertFalse(result["x1_ninja_liquidity_usd_semantics_verified"])

    def test_missing_same_fact_alignment_blocks_fact_time(self):
        result = evaluate_ninja_liquidity_revaluation_series(
            [
                event("a", "pool-1"),
                event("b", "pool-2", aligned=False),
                event("c", "pool-1"),
            ]
        )
        self.assertTrue(result["repeated_revaluation_pattern_supported"])
        self.assertFalse(result["liquidity_fact_time_verified"])

    def test_fewer_than_five_pools_blocks_usd_semantics(self):
        result = evaluate_ninja_liquidity_revaluation_series(
            [
                event("a", "pool-1"),
                event("b", "pool-2"),
                event("c", "pool-3"),
            ],
            current_usdcx_usd_equivalence_verified=True,
        )
        self.assertTrue(result["liquidity_fact_time_verified"])
        self.assertFalse(result["x1_ninja_liquidity_usd_semantics_verified"])
        self.assertIn(
            "minimum_five_distinct_usd_semantic_pools",
            result["missing_gates"],
        )


if __name__ == "__main__":
    unittest.main()
