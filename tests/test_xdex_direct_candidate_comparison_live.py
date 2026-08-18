import os
import unittest

from liquidity_scout.cmis.xdex_direct_candidate_comparison import (
    compare_verified_direct_xdex_candidates,
)
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import (
    XENCAT_MINT,
    XNT_MINT,
)


USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"


@unittest.skipUnless(
    os.getenv("RUN_XDEX_DIRECT_CANDIDATE_COMPARISON_LIVE") == "1",
    "set RUN_XDEX_DIRECT_CANDIDATE_COMPARISON_LIVE=1 for read-only live evidence",
)
class XDEXDirectCandidateComparisonLiveTests(unittest.TestCase):
    def _assert_live_pair(self, token_in, token_out, amount):
        result = compare_verified_direct_xdex_candidates(token_in, token_out, amount)

        self.assertEqual(result["service"], "cmis_xdex_verified_direct_candidate_comparison")
        self.assertTrue(result["read_only"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["global_optimality_claimed"])
        self.assertFalse(result["multi_hop_evaluated"])
        self.assertFalse(result["execution_quality_verified"])
        self.assertFalse(result["expected_fill_verified"])
        self.assertFalse(result["expected_slippage_verified"])

        self.assertEqual(result["discovery_status"], "ambiguous")
        self.assertGreaterEqual(result["candidate_count"], 2)
        self.assertTrue(result["comparison_complete"])
        self.assertEqual(result["quoted_candidate_count"], result["candidate_count"])
        self.assertTrue(result["candidate_quotes_passed_hardened_route_resolver"])
        self.assertIn(result["status"], {"preferred", "tie"})

        if result["status"] == "preferred":
            self.assertIsNotNone(result["preferred_candidate"])
            self.assertEqual(
                result["selection_claim"],
                "highest_zero_slippage_quote_output_among_verified_direct_xdex_candidates",
            )
        else:
            self.assertIsNone(result["preferred_candidate"])
            self.assertIsNone(result["selection_claim"])

        print("live direct candidate comparison:", result)

    def test_xencat_to_xnt_current_multi_pool_comparison(self):
        self._assert_live_pair(XENCAT_MINT, XNT_MINT, "1000")

    def test_xnt_to_usdc_x_current_multi_pool_comparison(self):
        self._assert_live_pair(XNT_MINT, USDC_X_MINT, "1")


if __name__ == "__main__":
    unittest.main()
