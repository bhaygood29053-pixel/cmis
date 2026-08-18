import unittest

from liquidity_scout.providers.x1.xdex_direct_candidate_quote_comparison import (
    SELECTION_CLAIM,
    XDEXDirectCandidateQuoteComparisonError,
    compare_direct_candidate_quotes,
)


MINT_A = "mint-a"
MINT_B = "mint-b"


def candidate(pool, config):
    return {
        "pool": pool,
        "amm_config": config,
        "token_in_mint": MINT_A,
        "token_out_mint": MINT_B,
        "pool_state_verified": True,
        "amm_config_verified": True,
        "vault_identity_verified": True,
        "active_reserves_verified": True,
    }


def discovery(*rows, rejected=None, complete=True):
    return {
        "chain": "x1",
        "token_in_mint": MINT_A,
        "token_out_mint": MINT_B,
        "program_family_pair_enumeration_complete": True,
        "candidate_verification_complete": complete,
        "verified_candidate_count": len(rows),
        "candidates": list(rows),
        "rejected_candidates": [] if rejected is None else rejected,
    }


def quote_for(outputs, *, decimals=6):
    def provider(route, token_in, token_out, amount):
        return {
            "token_in_mint": token_in,
            "token_out_mint": token_out,
            "pool": route["pool"],
            "amm_config": route["amm_config"],
            "route_identity_verified": True,
            "zero_slippage_output_verified": True,
            "zero_slippage_output": outputs[route["pool"]],
            "output_decimals": decimals,
        }
    return provider


class DirectCandidateQuoteComparisonTests(unittest.TestCase):
    def test_unique_maximum_is_narrowly_preferred(self):
        result = compare_direct_candidate_quotes(
            MINT_A,
            MINT_B,
            "10",
            discovery=discovery(candidate("pool-1", "config-1"), candidate("pool-2", "config-2")),
            quote_provider=quote_for({"pool-1": "9.5", "pool-2": "9.7"}),
        )
        self.assertEqual(result["status"], "preferred")
        self.assertEqual(result["selection_claim"], SELECTION_CLAIM)
        self.assertEqual(result["preferred_candidate"]["pool"], "pool-2")
        self.assertTrue(result["comparison_complete"])
        self.assertFalse(result["global_optimality_claimed"])
        self.assertFalse(result["execution_quality_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_equal_maximum_is_tie_with_no_selection(self):
        result = compare_direct_candidate_quotes(
            MINT_A,
            MINT_B,
            10,
            discovery=discovery(candidate("pool-1", "config-1"), candidate("pool-2", "config-2")),
            quote_provider=quote_for({"pool-1": "9.5", "pool-2": "9.500000"}),
        )
        self.assertEqual(result["status"], "tie")
        self.assertIsNone(result["preferred_candidate"])
        self.assertIsNone(result["selection_claim"])

    def test_one_failed_quote_makes_comparison_incomplete(self):
        def provider(route, token_in, token_out, amount):
            if route["pool"] == "pool-2":
                raise RuntimeError("provider timeout")
            return quote_for({"pool-1": "9.5"})(route, token_in, token_out, amount)

        result = compare_direct_candidate_quotes(
            MINT_A,
            MINT_B,
            10,
            discovery=discovery(candidate("pool-1", "config-1"), candidate("pool-2", "config-2")),
            quote_provider=provider,
        )
        self.assertEqual(result["status"], "comparison_incomplete")
        self.assertFalse(result["comparison_complete"])
        self.assertIsNone(result["preferred_candidate"])
        self.assertEqual(len(result["quote_failures"]), 1)

    def test_incomplete_candidate_verification_is_rejected_before_quotes(self):
        with self.assertRaisesRegex(XDEXDirectCandidateQuoteComparisonError, "verification is incomplete"):
            compare_direct_candidate_quotes(
                MINT_A,
                MINT_B,
                10,
                discovery=discovery(candidate("pool-1", "config-1"), complete=False),
                quote_provider=quote_for({"pool-1": "9.5"}),
            )

    def test_rejected_candidate_blocks_comparison(self):
        with self.assertRaisesRegex(XDEXDirectCandidateQuoteComparisonError, "rejected candidates"):
            compare_direct_candidate_quotes(
                MINT_A,
                MINT_B,
                10,
                discovery=discovery(candidate("pool-1", "config-1"), rejected=[{"pool": "pool-2"}]),
                quote_provider=quote_for({"pool-1": "9.5"}),
            )

    def test_shared_config_fails_closed_because_quote_cannot_distinguish_pool(self):
        with self.assertRaisesRegex(XDEXDirectCandidateQuoteComparisonError, "AMM configs must be unique"):
            compare_direct_candidate_quotes(
                MINT_A,
                MINT_B,
                10,
                discovery=discovery(candidate("pool-1", "config-1"), candidate("pool-2", "config-1")),
                quote_provider=quote_for({"pool-1": "9.5", "pool-2": "9.6"}),
            )

    def test_unverified_quote_semantics_make_comparison_incomplete(self):
        def provider(route, token_in, token_out, amount):
            return {
                "token_in_mint": token_in,
                "token_out_mint": token_out,
                "pool": route["pool"],
                "amm_config": route["amm_config"],
                "route_identity_verified": True,
                "zero_slippage_output_verified": False,
                "zero_slippage_output": "9.5",
                "output_decimals": 6,
            }
        result = compare_direct_candidate_quotes(
            MINT_A, MINT_B, 10,
            discovery=discovery(candidate("pool-1", "config-1")),
            quote_provider=provider,
        )
        self.assertEqual(result["status"], "comparison_incomplete")
        self.assertIsNone(result["preferred_candidate"])

    def test_fraction_beyond_output_decimals_is_incomplete(self):
        result = compare_direct_candidate_quotes(
            MINT_A, MINT_B, 10,
            discovery=discovery(candidate("pool-1", "config-1")),
            quote_provider=quote_for({"pool-1": "9.5000001"}, decimals=6),
        )
        self.assertEqual(result["status"], "comparison_incomplete")
        self.assertIsNone(result["preferred_candidate"])

    def test_boolean_amount_is_rejected(self):
        with self.assertRaises(XDEXDirectCandidateQuoteComparisonError):
            compare_direct_candidate_quotes(
                MINT_A, MINT_B, True,
                discovery=discovery(candidate("pool-1", "config-1")),
                quote_provider=quote_for({"pool-1": "9.5"}),
            )


if __name__ == "__main__":
    unittest.main()
