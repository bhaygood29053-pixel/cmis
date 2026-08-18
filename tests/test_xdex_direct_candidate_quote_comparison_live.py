import os
import unittest

from liquidity_scout.cmis.xdex_route_resolver import resolve_xdex_route_evidence
from liquidity_scout.providers.x1.xdex_direct_candidate_quote_comparison import (
    SELECTION_CLAIM,
    compare_direct_candidate_quotes,
)
from liquidity_scout.providers.x1.xdex_direct_route_discovery import discover_direct_route
from liquidity_scout.providers.x1.xdex_exact_route import collect_exact_route_snapshot
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import XENCAT_MINT, XNT_MINT


RUN_LIVE = os.getenv("RUN_XDEX_DIRECT_CANDIDATE_QUOTE_LIVE") == "1"
USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"


def _live_quote_provider(candidate, token_in, token_out, amount):
    route = {
        "token_in_mint": token_in,
        "token_out_mint": token_out,
        "pool": candidate["pool"],
        "amm_config": candidate["amm_config"],
    }
    snapshot = collect_exact_route_snapshot(route, amount)
    print({
        "candidate_snapshot": {
            "pool": candidate["pool"],
            "amm_config": candidate["amm_config"],
            "raw_input_amount": snapshot.get("raw_input_amount"),
            "active_reserve_in_raw": snapshot.get("active_reserve_in_raw"),
            "trade_fee_rate_ppm": snapshot.get("trade_fee_rate_ppm"),
            "creator_fee_rate_ppm": snapshot.get("creator_fee_rate_ppm"),
            "reconstructed_price_impact_percent": snapshot.get("reconstructed_price_impact_percent"),
            "quote_price_impact_percent": snapshot.get("quote_price_impact_percent"),
            "quote_output_amount": snapshot.get("quote_output_amount"),
        }
    })

    # Re-run the accepted CMIS exact-route validation over this exact snapshot.
    # The comparator is allowed to use the quote output only after the route
    # identity, current pool/config/vault state, active reserves, zero-slippage
    # quote identity, and independent price-impact reconstruction all pass.
    resolved = resolve_xdex_route_evidence(
        route,
        amount,
        collector=lambda requested_route, requested_amount: snapshot,
    )
    if resolved.get("route") != route:
        raise AssertionError("accepted route resolver did not preserve the exact candidate route")
    price_impact = (resolved.get("capabilities") or {}).get("price_impact") or {}
    if price_impact.get("status") != "verified":
        raise AssertionError("accepted route resolver did not verify route price-impact evidence")
    if snapshot.get("quote_slippage_percent") != 0:
        raise AssertionError("candidate quote is not the accepted zero-slippage observation")

    return {
        "token_in_mint": token_in,
        "token_out_mint": token_out,
        "pool": candidate["pool"],
        "amm_config": candidate["amm_config"],
        "route_identity_verified": True,
        "zero_slippage_output_verified": True,
        "zero_slippage_output": snapshot.get("quote_output_amount"),
        "output_decimals": snapshot.get("output_decimals"),
    }


def _compare_live_pair(token_in, token_out, amount):
    discovery = discover_direct_route(token_in, token_out)
    if discovery.get("status") != "ambiguous":
        raise AssertionError(
            "live comparison evidence currently requires multiple fully verified direct candidates"
        )
    if discovery.get("candidate_verification_complete") is not True:
        raise AssertionError("direct-candidate verification is incomplete")
    if discovery.get("program_family_pair_enumeration_complete") is not True:
        raise AssertionError("direct-pair program-family enumeration is incomplete")

    return compare_direct_candidate_quotes(
        token_in,
        token_out,
        amount,
        discovery=discovery,
        quote_provider=_live_quote_provider,
    )


def _print_live_comparison_diagnostics(pair, result):
    print({
        "pair": pair,
        "status": result.get("status"),
        "comparison_complete": result.get("comparison_complete"),
        "candidate_count": result.get("candidate_count"),
        "quoted_candidate_count": result.get("quoted_candidate_count"),
        "quote_failures": result.get("quote_failures"),
        "quotes": result.get("quotes"),
    })


def _assert_live_comparison_boundary(testcase, result):
    testcase.assertTrue(result["comparison_complete"])
    testcase.assertGreaterEqual(result["candidate_count"], 2)
    testcase.assertEqual(result["quoted_candidate_count"], result["candidate_count"])
    testcase.assertEqual(result["quote_failures"], [])
    testcase.assertIn(result["status"], {"preferred", "tie"})
    testcase.assertFalse(result["same_provider_quotes_independently_corroborated"])
    testcase.assertTrue(result["accepted_xdex_program_family_only"])
    testcase.assertFalse(result["all_x1_dex_routes_compared"])
    testcase.assertFalse(result["multi_hop_evaluated"])
    testcase.assertFalse(result["execution_quality_verified"])
    testcase.assertFalse(result["expected_fill_verified"])
    testcase.assertFalse(result["expected_slippage_verified"])
    testcase.assertFalse(result["global_optimality_claimed"])
    testcase.assertFalse(result["execution_authorized"])
    testcase.assertTrue(result["read_only"])

    if result["status"] == "preferred":
        testcase.assertEqual(result["selection_claim"], SELECTION_CLAIM)
        testcase.assertIsNotNone(result["preferred_candidate"])
    else:
        testcase.assertIsNone(result["selection_claim"])
        testcase.assertIsNone(result["preferred_candidate"])


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_DIRECT_CANDIDATE_QUOTE_LIVE=1 to compare verified direct XDEX candidates read-only",
)
class XDEXDirectCandidateQuoteComparisonLiveTests(unittest.TestCase):
    def test_xencat_xnt_all_verified_direct_candidates_are_compared(self):
        result = _compare_live_pair(XENCAT_MINT, XNT_MINT, "1000")
        _print_live_comparison_diagnostics("XENCAT/XNT", result)
        _assert_live_comparison_boundary(self, result)
        print({
            "pair": "XENCAT/XNT",
            "status": result["status"],
            "candidate_count": result["candidate_count"],
            "quotes": result["quotes"],
            "selection_claim": result["selection_claim"],
            "preferred_candidate": result["preferred_candidate"],
        })

    def test_xnt_usdcx_all_verified_direct_candidates_are_compared(self):
        result = _compare_live_pair(XNT_MINT, USDC_X_MINT, "1")
        _print_live_comparison_diagnostics("XNT/USDC.X", result)
        _assert_live_comparison_boundary(self, result)
        print({
            "pair": "XNT/USDC.X",
            "status": result["status"],
            "candidate_count": result["candidate_count"],
            "quotes": result["quotes"],
            "selection_claim": result["selection_claim"],
            "preferred_candidate": result["preferred_candidate"],
        })


if __name__ == "__main__":
    unittest.main()
