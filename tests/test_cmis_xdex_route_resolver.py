import unittest

from liquidity_scout.cmis.xdex_route_resolver import (
    XDEXRouteResolverError,
    resolve_xdex_route_evidence,
)
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import (
    AMM_CONFIG,
    POOL,
    X1_PROGRAM,
    XENCAT_MINT,
    XNT_MINT,
)
from liquidity_scout.services.pre_trade_route_evidence import evaluate_route_evidence


ROUTE = {
    "token_in_mint": XENCAT_MINT,
    "token_out_mint": XNT_MINT,
    "pool": POOL,
    "amm_config": AMM_CONFIG,
}


def execution_fee_observation(**overrides):
    observation = {
        "chain": "x1",
        "program": X1_PROGRAM,
        "pool": POOL,
        "amm_config": AMM_CONFIG,
        "asset_a_mint": XENCAT_MINT,
        "asset_b_mint": XNT_MINT,
        "configured_fee_ppm": 2800,
        "supported_candidate_ppm": 2800,
        "rejected_candidate_ppm": 3000,
        "swap_count": 23,
        "seed_swap_count": 2,
        "holdout_swap_count": 21,
        "first_slot": 66617613,
        "last_slot": 72301970,
        "gross_vault_balances_observed": True,
        "state_contiguous": True,
        "both_directions_observed": True,
        "opposite_direction_seed_verified": True,
        "holdout_validation_performed": True,
        "fee_accounting_model_corroborated": True,
        "initial_fee_counters_inferred": True,
        "initial_fee_counters_observed": False,
        "supported_max_abs_error_raw": 406,
        "supported_sum_abs_error_raw": 1115,
        "rejected_max_abs_error_raw": 1557603301,
        "rejected_sum_abs_error_raw": 2513561183,
        "quote_baseline_ppm": 3000,
        "quote_baseline_verified": True,
    }
    observation.update(overrides)
    return observation


def snapshot_for(route=None, **overrides):
    route = dict(route or ROUTE)
    snapshot = {
        "schema": "xdex_exact_route_snapshot.v1",
        "source": "XDEX exact-route read-only collector",
        "chain": "x1",
        "program": X1_PROGRAM,
        "route": route,
        "observed_at": "2026-08-18T21:58:00Z",
        "token_in_amount": "1000",
        "raw_input_amount": 1_000_000_000,
        "input_decimals": 6,
        "output_decimals": 9,
        "active_reserve_in_raw": 50_000_000_000,
        "active_reserve_out_raw": 10_000_000_000,
        "trade_fee_rate_ppm": 2800,
        "protocol_fee_rate_ppm_of_trade_fee": 250000,
        "fund_fee_rate_ppm_of_trade_fee": 50000,
        "creator_fee_rate_ppm": 0,
        "reconstructed_price_impact_percent": "1.955401473022048269316746802",
        "quote_price_impact_percent": "1.9554010",
        "quote_output_amount": "999999999999999999999999",
        "quote_rate": "999999",
        "quote_slippage_percent": 0,
        "quote_identity_verified": True,
        "pool_state_verified": True,
        "vault_identity_verified": True,
        "active_reserves_verified": True,
        "amm_config_verified": True,
        "read_only": True,
        "execution_authorized": False,
    }
    snapshot.update(overrides)
    return snapshot


class XDEXRouteResolverTests(unittest.TestCase):
    def test_exact_route_emits_only_price_impact_without_explicit_fee_evidence(self):
        evidence = resolve_xdex_route_evidence(
            ROUTE,
            "1000",
            collector=lambda route, amount: snapshot_for(route),
        )

        self.assertEqual(evidence["source"], "cmis_xdex_route_resolver")
        self.assertEqual(evidence["route"], ROUTE)
        self.assertEqual(set(evidence["capabilities"]), {"price_impact"})
        self.assertEqual(
            evidence["capabilities"]["price_impact"]["semantic"],
            "route_price_impact_percent",
        )
        self.assertNotIn("slippage", evidence["capabilities"])
        self.assertNotIn("fees", evidence["capabilities"])

    def test_bounded_fee_requires_explicit_accepted_historical_evidence(self):
        evidence = resolve_xdex_route_evidence(
            ROUTE,
            "1000",
            collector=lambda route, amount: snapshot_for(route),
            execution_fee_observation=execution_fee_observation(),
        )

        self.assertEqual(set(evidence["capabilities"]), {"price_impact", "fees"})
        self.assertAlmostEqual(
            evidence["capabilities"]["fees"]["value"]["amm_trade_fee_rate_percent"],
            0.28,
        )
        self.assertEqual(
            evidence["capabilities"]["fees"]["value"],
            {
                "amm_trade_fee_rate_percent": 0.28,
                "bounded_historical_execution_model_fee_percent": 0.28,
            },
        )

    def test_evidence_is_accepted_by_pre_trade_route_contract(self):
        evidence = resolve_xdex_route_evidence(
            ROUTE,
            "1000",
            collector=lambda route, amount: snapshot_for(route),
            execution_fee_observation=execution_fee_observation(),
        )
        result = evaluate_route_evidence(
            evidence,
            target_chain="x1",
            trade_route=ROUTE,
            evaluated_at="2026-08-18T21:58:05Z",
            max_age_seconds=30,
        )

        self.assertEqual(
            set(result["audit"]["usable_capabilities"]),
            {"price_impact", "fees"},
        )
        self.assertEqual(result["overrides"]["price_impact"]["status"], "ok")
        self.assertEqual(result["overrides"]["fees"]["status"], "ok")
        self.assertFalse(result["audit"]["rejected_capabilities"])

    def test_other_verified_route_does_not_get_fee_without_accepted_observation(self):
        other = {
            "token_in_mint": "AAA",
            "token_out_mint": "BBB",
            "pool": "OTHER_POOL",
            "amm_config": "OTHER_CONFIG",
        }
        evidence = resolve_xdex_route_evidence(
            other,
            "1",
            collector=lambda route, amount: snapshot_for(
                route,
                token_in_amount="1",
                raw_input_amount=1_000_000,
                active_reserve_in_raw=50_000_000,
                reconstructed_price_impact_percent="1.955401473022048269316746802",
                quote_price_impact_percent="1.9554010",
                trade_fee_rate_ppm=2800,
            ),
        )

        self.assertEqual(set(evidence["capabilities"]), {"price_impact"})

    def test_explicit_unaccepted_fee_evidence_fails_closed(self):
        observation = execution_fee_observation(state_contiguous=False)
        with self.assertRaisesRegex(XDEXRouteResolverError, "not strongly corroborated"):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(route),
                execution_fee_observation=observation,
            )

    def test_current_config_fee_must_match_historical_bounded_fee(self):
        with self.assertRaisesRegex(
            XDEXRouteResolverError,
            "does not match the current verified config fee",
        ):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(
                    route,
                    trade_fee_rate_ppm=3000,
                    reconstructed_price_impact_percent="1.955017549363701870478474085",
                    quote_price_impact_percent="1.9550175",
                ),
                execution_fee_observation=execution_fee_observation(),
            )

    def test_price_impact_disagreement_fails_closed(self):
        with self.assertRaisesRegex(
            XDEXRouteResolverError,
            "does not match independent verified-reserve reconstruction",
        ):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(
                    route,
                    quote_price_impact_percent="2.1",
                ),
            )

    def test_forged_reconstructed_price_impact_fails_closed(self):
        with self.assertRaisesRegex(
            XDEXRouteResolverError,
            "does not match deterministic reserve arithmetic",
        ):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(
                    route,
                    reconstructed_price_impact_percent="1.0",
                    quote_price_impact_percent="1.0",
                ),
            )

    def test_snapshot_route_mismatch_fails_closed(self):
        wrong = dict(ROUTE)
        wrong["pool"] = "WRONG_POOL"
        with self.assertRaisesRegex(XDEXRouteResolverError, "does not match the requested exact route"):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(wrong),
            )

    def test_snapshot_source_is_revalidated(self):
        with self.assertRaisesRegex(XDEXRouteResolverError, "source is not accepted"):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(
                    route,
                    source="caller_claim",
                ),
            )

    def test_snapshot_program_is_revalidated(self):
        with self.assertRaisesRegex(XDEXRouteResolverError, "accepted XDEX program"):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(
                    route,
                    program="other-program",
                ),
            )

    def test_noncanonical_observed_at_fails_closed(self):
        with self.assertRaisesRegex(XDEXRouteResolverError, "canonical UTC"):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(
                    route,
                    observed_at="2026-08-18T17:58:00-04:00",
                ),
            )

    def test_nonzero_quote_slippage_snapshot_fails_closed(self):
        with self.assertRaisesRegex(XDEXRouteResolverError, "zero-slippage quote"):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(
                    route,
                    quote_slippage_percent=0.5,
                ),
            )

    def test_token_amount_and_raw_amount_must_reconcile(self):
        with self.assertRaisesRegex(XDEXRouteResolverError, "are inconsistent"):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(
                    route,
                    raw_input_amount=999,
                ),
            )

    def test_unverified_vault_identity_fails_closed(self):
        with self.assertRaisesRegex(XDEXRouteResolverError, "vault_identity_verified"):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(
                    route,
                    vault_identity_verified=False,
                ),
            )

    def test_execution_authorization_is_rejected(self):
        with self.assertRaisesRegex(XDEXRouteResolverError, "must not authorize execution"):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(
                    route,
                    execution_authorized=True,
                ),
            )


if __name__ == "__main__":
    unittest.main()
