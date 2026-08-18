import os
import unittest

from liquidity_scout.cmis.xdex_direct_quote_comparator import (
    PREFERENCE_CLAIM,
    compare_direct_xdex_quotes,
)
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import XENCAT_MINT, XNT_MINT


RUN_LIVE = os.getenv("RUN_XDEX_DIRECT_QUOTE_COMPARATOR_LIVE") == "1"
USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_DIRECT_QUOTE_COMPARATOR_LIVE=1 to run read-only direct quote comparison",
)
class XDEXDirectQuoteComparatorLiveTests(unittest.TestCase):
    def assert_comparison_contract(self, result):
        self.assertEqual(result["discovery_status"], "ambiguous")
        self.assertTrue(result["program_family_pair_enumeration_complete"])
        self.assertTrue(result["candidate_verification_complete"])
        self.assertTrue(result["comparison_complete"])
        self.assertGreaterEqual(len(result["quote_candidates"]), 2)
        self.assertFalse(result["failed_candidates"])
        self.assertIn(
            result["comparison_status"],
            {"quote_preferred_direct_candidate", "quote_output_tie"},
        )
        if result["comparison_status"] == "quote_preferred_direct_candidate":
            self.assertIsNotNone(result["preferred_route"])
            self.assertEqual(result["preference_claim"], PREFERENCE_CLAIM)
            candidate_routes = [item["route"] for item in result["quote_candidates"]]
            self.assertIn(result["preferred_route"], candidate_routes)
        else:
            self.assertIsNone(result["preferred_route"])
            self.assertIsNone(result["preference_claim"])
        self.assertTrue(result["same_provider_quote_comparison"])
        self.assertFalse(result["independent_quote_corroboration"])
        self.assertFalse(result["best_execution_route_claimed"])
        self.assertFalse(result["global_best_route_claimed"])
        self.assertFalse(result["route_quality_evaluated"])
        self.assertFalse(result["expected_execution_slippage_estimated"])
        self.assertFalse(result["fill_guarantee"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["execution_authorized"])

    def test_xencat_xnt_compares_every_verified_direct_candidate(self):
        result = compare_direct_xdex_quotes(XENCAT_MINT, XNT_MINT, "1000")
        self.assert_comparison_contract(result)
        print({
            "pair": "XENCAT/XNT",
            "token_in_amount": result["token_in_amount"],
            "comparison_status": result["comparison_status"],
            "preferred_route": result["preferred_route"],
            "preference_claim": result["preference_claim"],
            "observation_spread_seconds": result["observation_spread_seconds"],
            "quotes": [
                {
                    "pool": item["pool"],
                    "amm_config": item["amm_config"],
                    "quote_output_amount": item["quote_output_amount"],
                    "quote_output_raw": item["quote_output_raw"],
                    "price_impact_percent": item["quote_price_impact_percent"],
                }
                for item in result["quote_candidates"]
            ],
            "best_execution_route_claimed": result["best_execution_route_claimed"],
            "expected_execution_slippage_estimated": result["expected_execution_slippage_estimated"],
        })

    def test_xnt_usdcx_compares_every_verified_direct_candidate(self):
        result = compare_direct_xdex_quotes(XNT_MINT, USDC_X_MINT, "0.1")
        self.assert_comparison_contract(result)
        print({
            "pair": "XNT/USDC.X",
            "token_in_amount": result["token_in_amount"],
            "comparison_status": result["comparison_status"],
            "preferred_route": result["preferred_route"],
            "preference_claim": result["preference_claim"],
            "observation_spread_seconds": result["observation_spread_seconds"],
            "quotes": [
                {
                    "pool": item["pool"],
                    "amm_config": item["amm_config"],
                    "quote_output_amount": item["quote_output_amount"],
                    "quote_output_raw": item["quote_output_raw"],
                    "price_impact_percent": item["quote_price_impact_percent"],
                }
                for item in result["quote_candidates"]
            ],
            "best_execution_route_claimed": result["best_execution_route_claimed"],
            "expected_execution_slippage_estimated": result["expected_execution_slippage_estimated"],
        })


if __name__ == "__main__":
    unittest.main()
