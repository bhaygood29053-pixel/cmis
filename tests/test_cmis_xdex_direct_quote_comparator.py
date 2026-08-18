import unittest

from liquidity_scout.cmis.xdex_direct_quote_comparator import (
    PREFERENCE_CLAIM,
    XDEXDirectQuoteComparatorError,
    compare_direct_xdex_quotes,
)


TOKEN_IN = "TOKEN_IN"
TOKEN_OUT = "TOKEN_OUT"
ROUTE_A = {
    "token_in_mint": TOKEN_IN,
    "token_out_mint": TOKEN_OUT,
    "pool": "POOL_A",
    "amm_config": "CONFIG_A",
}
ROUTE_B = {
    "token_in_mint": TOKEN_IN,
    "token_out_mint": TOKEN_OUT,
    "pool": "POOL_B",
    "amm_config": "CONFIG_B",
}


def candidate(route):
    return {
        **route,
        "active_reserve_in_raw": 10_000,
        "active_reserve_out_raw": 20_000,
        "pool_state_verified": True,
        "amm_config_verified": True,
        "vault_identity_verified": True,
        "active_reserves_verified": True,
    }


def discovery(*routes, status=None, verification_complete=True):
    routes = list(routes)
    if status is None:
        if not routes:
            status = "unavailable"
        elif len(routes) == 1:
            status = "verified_unique"
        else:
            status = "ambiguous"
    return {
        "service": "xdex_direct_route_discovery",
        "version": "1.2",
        "source": "X1 RPC exact-pair XDEX program discovery",
        "chain": "x1",
        "token_in_mint": TOKEN_IN,
        "token_out_mint": TOKEN_OUT,
        "status": status,
        "route": dict(routes[0]) if status == "verified_unique" and routes else None,
        "selection_claim": None,
        "program_id": "XDEX_PROGRAM",
        "program_family_pair_enumeration_complete": True,
        "candidate_verification_complete": verification_complete,
        "recognized_program_registry_globally_exhaustive": False,
        "all_x1_dex_pair_enumeration_complete": False,
        "enumerated_candidate_count": len(routes),
        "verified_candidate_count": len(routes),
        "candidates": [candidate(route) for route in routes],
        "rejected_candidates": [],
        "read_only": True,
        "best_route_claimed": False,
        "global_optimality_claimed": False,
        "multi_hop_evaluated": False,
        "execution_authorized": False,
    }


def snapshot(route, output, observed_at, *, output_decimals=6):
    return {
        "route": dict(route),
        "token_in_amount": "100",
        "output_decimals": output_decimals,
        "quote_output_amount": output,
        "quote_price_impact_percent": "1.25",
        "observed_at": observed_at,
    }


def accepting_resolver(route, amount, *, collector, **kwargs):
    record = collector(route, amount)
    if record["route"] != dict(route):
        raise AssertionError("snapshot route mismatch")
    if amount != "100":
        raise AssertionError("unexpected normalized amount")
    return {
        "schema_version": 2,
        "source": "cmis_xdex_route_resolver",
        "chain": "x1",
        "route": dict(route),
        "token_in_amount": amount,
        "observed_at": record["observed_at"],
        "capabilities": {
            "price_impact": {
                "status": "verified",
                "semantic": "route_price_impact_percent",
                "value": 1.25,
                "unit": "percent",
                "proof_basis": [
                    "verified_direct_cp_route",
                    "verified_pool_reserves",
                    "verified_price_impact_semantics",
                ],
            }
        },
    }


class XDEXDirectQuoteComparatorTests(unittest.TestCase):
    def test_unique_highest_zero_slippage_output_gets_narrow_preference(self):
        snapshots = {
            "POOL_A": snapshot(ROUTE_A, "10.000001", "2026-08-18T22:50:00Z"),
            "POOL_B": snapshot(ROUTE_B, "10.000002", "2026-08-18T22:50:01Z"),
        }
        result = compare_direct_xdex_quotes(
            TOKEN_IN,
            TOKEN_OUT,
            "100.000",
            discovery_provider=lambda a, b: discovery(ROUTE_A, ROUTE_B),
            snapshot_collector=lambda route, amount: snapshots[route["pool"]],
            route_resolver=accepting_resolver,
        )

        self.assertTrue(result["comparison_complete"])
        self.assertEqual(result["comparison_status"], "quote_preferred_direct_candidate")
        self.assertEqual(result["preferred_route"], ROUTE_B)
        self.assertEqual(result["preference_claim"], PREFERENCE_CLAIM)
        self.assertEqual(result["preferred_quote_output_raw"], 10_000_002)
        self.assertEqual(result["observation_spread_seconds"], 1.0)
        self.assertFalse(result["best_execution_route_claimed"])
        self.assertFalse(result["global_best_route_claimed"])
        self.assertFalse(result["expected_execution_slippage_estimated"])
        self.assertFalse(result["fill_guarantee"])
        self.assertFalse(result["execution_authorized"])

    def test_equal_maximum_outputs_tie_and_select_nothing(self):
        snapshots = {
            "POOL_A": snapshot(ROUTE_A, "10.5", "2026-08-18T22:50:00Z"),
            "POOL_B": snapshot(ROUTE_B, "10.500000", "2026-08-18T22:50:01Z"),
        }
        result = compare_direct_xdex_quotes(
            TOKEN_IN,
            TOKEN_OUT,
            100,
            discovery_provider=lambda a, b: discovery(ROUTE_A, ROUTE_B),
            snapshot_collector=lambda route, amount: snapshots[route["pool"]],
            route_resolver=accepting_resolver,
        )

        self.assertTrue(result["comparison_complete"])
        self.assertEqual(result["comparison_status"], "quote_output_tie")
        self.assertIsNone(result["preferred_route"])
        self.assertIsNone(result["preference_claim"])

    def test_one_candidate_snapshot_failure_makes_comparison_incomplete(self):
        def collect(route, amount):
            if route["pool"] == "POOL_B":
                raise RuntimeError("quote unavailable")
            return snapshot(route, "10", "2026-08-18T22:50:00Z")

        result = compare_direct_xdex_quotes(
            TOKEN_IN,
            TOKEN_OUT,
            "100",
            discovery_provider=lambda a, b: discovery(ROUTE_A, ROUTE_B),
            snapshot_collector=collect,
            route_resolver=accepting_resolver,
        )

        self.assertFalse(result["comparison_complete"])
        self.assertEqual(result["comparison_status"], "quote_comparison_incomplete")
        self.assertEqual(len(result["quote_candidates"]), 1)
        self.assertEqual(len(result["failed_candidates"]), 1)
        self.assertIsNone(result["preferred_route"])

    def test_candidate_resolver_rejection_makes_comparison_incomplete(self):
        def resolver(route, amount, *, collector, **kwargs):
            if route["pool"] == "POOL_B":
                raise RuntimeError("price-impact validation failed")
            return accepting_resolver(route, amount, collector=collector)

        snapshots = {
            "POOL_A": snapshot(ROUTE_A, "10", "2026-08-18T22:50:00Z"),
            "POOL_B": snapshot(ROUTE_B, "11", "2026-08-18T22:50:01Z"),
        }
        result = compare_direct_xdex_quotes(
            TOKEN_IN,
            TOKEN_OUT,
            "100",
            discovery_provider=lambda a, b: discovery(ROUTE_A, ROUTE_B),
            snapshot_collector=lambda route, amount: snapshots[route["pool"]],
            route_resolver=resolver,
        )

        self.assertEqual(result["comparison_status"], "quote_comparison_incomplete")
        self.assertFalse(result["comparison_complete"])
        self.assertIsNone(result["preferred_route"])

    def test_observation_spread_exceeded_selects_nothing(self):
        snapshots = {
            "POOL_A": snapshot(ROUTE_A, "10", "2026-08-18T22:50:00Z"),
            "POOL_B": snapshot(ROUTE_B, "11", "2026-08-18T22:50:20Z"),
        }
        result = compare_direct_xdex_quotes(
            TOKEN_IN,
            TOKEN_OUT,
            "100",
            discovery_provider=lambda a, b: discovery(ROUTE_A, ROUTE_B),
            snapshot_collector=lambda route, amount: snapshots[route["pool"]],
            route_resolver=accepting_resolver,
            max_observation_spread_seconds=15,
        )

        self.assertFalse(result["comparison_complete"])
        self.assertEqual(result["comparison_status"], "quote_observation_spread_exceeded")
        self.assertEqual(result["observation_spread_seconds"], 20.0)
        self.assertIsNone(result["preferred_route"])

    def test_shared_config_between_pools_fails_closed_before_quoting(self):
        route_b = dict(ROUTE_B)
        route_b["amm_config"] = ROUTE_A["amm_config"]
        calls = []
        with self.assertRaisesRegex(
            XDEXDirectQuoteComparatorError,
            "share one AMM config",
        ):
            compare_direct_xdex_quotes(
                TOKEN_IN,
                TOKEN_OUT,
                "100",
                discovery_provider=lambda a, b: discovery(ROUTE_A, route_b),
                snapshot_collector=lambda route, amount: calls.append(route),
                route_resolver=accepting_resolver,
            )
        self.assertEqual(calls, [])

    def test_discovery_verification_incomplete_never_quotes(self):
        incomplete = discovery(
            ROUTE_A,
            status="verification_incomplete",
            verification_complete=False,
        )
        incomplete["rejected_candidates"] = [{"pool": "POOL_B", "reason": "RPC failed"}]
        calls = []
        result = compare_direct_xdex_quotes(
            TOKEN_IN,
            TOKEN_OUT,
            "100",
            discovery_provider=lambda a, b: incomplete,
            snapshot_collector=lambda route, amount: calls.append(route),
            route_resolver=accepting_resolver,
        )

        self.assertEqual(calls, [])
        self.assertFalse(result["comparison_complete"])
        self.assertEqual(result["comparison_status"], "candidate_verification_incomplete")
        self.assertIsNone(result["preferred_route"])

    def test_no_direct_candidates_never_quotes(self):
        calls = []
        result = compare_direct_xdex_quotes(
            TOKEN_IN,
            TOKEN_OUT,
            "100",
            discovery_provider=lambda a, b: discovery(),
            snapshot_collector=lambda route, amount: calls.append(route),
            route_resolver=accepting_resolver,
        )

        self.assertEqual(calls, [])
        self.assertEqual(result["comparison_status"], "no_verified_direct_candidates")
        self.assertFalse(result["comparison_complete"])

    def test_quote_output_must_be_exactly_representable_in_raw_units(self):
        result = compare_direct_xdex_quotes(
            TOKEN_IN,
            TOKEN_OUT,
            "100",
            discovery_provider=lambda a, b: discovery(ROUTE_A),
            snapshot_collector=lambda route, amount: snapshot(
                route,
                "1.0000001",
                "2026-08-18T22:50:00Z",
                output_decimals=6,
            ),
            route_resolver=accepting_resolver,
        )

        self.assertEqual(result["comparison_status"], "quote_comparison_incomplete")
        self.assertFalse(result["comparison_complete"])
        self.assertEqual(len(result["failed_candidates"]), 1)
        self.assertIsNone(result["preferred_route"])

    def test_candidate_output_decimals_must_agree_for_same_output_mint(self):
        snapshots = {
            "POOL_A": snapshot(ROUTE_A, "10", "2026-08-18T22:50:00Z", output_decimals=6),
            "POOL_B": snapshot(ROUTE_B, "11", "2026-08-18T22:50:01Z", output_decimals=9),
        }
        result = compare_direct_xdex_quotes(
            TOKEN_IN,
            TOKEN_OUT,
            "100",
            discovery_provider=lambda a, b: discovery(ROUTE_A, ROUTE_B),
            snapshot_collector=lambda route, amount: snapshots[route["pool"]],
            route_resolver=accepting_resolver,
        )

        self.assertEqual(result["comparison_status"], "output_decimal_identity_inconsistent")
        self.assertFalse(result["comparison_complete"])
        self.assertIsNone(result["preferred_route"])


if __name__ == "__main__":
    unittest.main()
