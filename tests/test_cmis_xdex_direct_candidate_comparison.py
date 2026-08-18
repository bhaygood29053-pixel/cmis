import unittest

from liquidity_scout.cmis.xdex_direct_candidate_comparison import (
    compare_verified_direct_xdex_candidates,
)
from liquidity_scout.cmis.xdex_route_resolver import (
    SCHEMA_VERSION,
    SOURCE,
)


MINT_A = "mint-a"
MINT_B = "mint-b"


def _candidate(pool, config):
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


def _discovery():
    rows = [_candidate("pool-1", "config-1"), _candidate("pool-2", "config-2")]
    return {
        "chain": "x1",
        "token_in_mint": MINT_A,
        "token_out_mint": MINT_B,
        "status": "ambiguous",
        "program_family_pair_enumeration_complete": True,
        "candidate_verification_complete": True,
        "verified_candidate_count": len(rows),
        "candidates": rows,
        "rejected_candidates": [],
    }


def _resolver(route, amount, *, collector):
    collector(route, amount)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "chain": "x1",
        "route": dict(route),
        "token_in_amount": amount,
        "observed_at": "2026-08-18T23:00:00Z",
        "capabilities": {"price_impact": {"status": "verified"}},
    }


class XDEXDirectCandidateCompositionTests(unittest.TestCase):
    def test_all_candidates_pass_resolver_before_unique_maximum_is_preferred(self):
        calls = []

        def collector(route, amount):
            calls.append((route["pool"], amount))
            return {
                "quote_output_amount": "9.500000" if route["pool"] == "pool-1" else "9.700000",
                "output_decimals": 6,
                "quote_slippage_percent": 0,
            }

        result = compare_verified_direct_xdex_candidates(
            MINT_A,
            MINT_B,
            "10.0",
            discovery_provider=lambda _a, _b: _discovery(),
            collector=collector,
            resolver=_resolver,
        )

        self.assertEqual(result["status"], "preferred")
        self.assertEqual(result["preferred_candidate"]["pool"], "pool-2")
        self.assertEqual(calls, [("pool-1", "10"), ("pool-2", "10")])
        self.assertTrue(result["candidate_quotes_passed_hardened_route_resolver"])
        self.assertFalse(result["runtime_integrated"])
        self.assertFalse(result["global_optimality_claimed"])
        self.assertFalse(result["execution_authorized"])

    def test_one_resolver_failure_makes_the_whole_comparison_incomplete(self):
        def collector(route, amount):
            return {
                "quote_output_amount": "9.500000",
                "output_decimals": 6,
                "quote_slippage_percent": 0,
            }

        def resolver(route, amount, *, collector):
            if route["pool"] == "pool-2":
                raise RuntimeError("candidate route proof failed")
            return _resolver(route, amount, collector=collector)

        result = compare_verified_direct_xdex_candidates(
            MINT_A,
            MINT_B,
            10,
            discovery_provider=lambda _a, _b: _discovery(),
            collector=collector,
            resolver=resolver,
        )

        self.assertEqual(result["status"], "comparison_incomplete")
        self.assertIsNone(result["preferred_candidate"])
        self.assertFalse(result["comparison_complete"])
        self.assertFalse(result["candidate_quotes_passed_hardened_route_resolver"])
        self.assertEqual(result["quoted_candidate_count"], 1)

    def test_nonzero_slippage_snapshot_cannot_participate(self):
        def collector(route, amount):
            return {
                "quote_output_amount": "9.500000",
                "output_decimals": 6,
                "quote_slippage_percent": 0 if route["pool"] == "pool-1" else 0.5,
            }

        result = compare_verified_direct_xdex_candidates(
            MINT_A,
            MINT_B,
            "10",
            discovery_provider=lambda _a, _b: _discovery(),
            collector=collector,
            resolver=_resolver,
        )

        self.assertEqual(result["status"], "comparison_incomplete")
        self.assertIsNone(result["preferred_candidate"])
        self.assertEqual(len(result["quote_failures"]), 1)
        self.assertIn("zero-slippage", result["quote_failures"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
