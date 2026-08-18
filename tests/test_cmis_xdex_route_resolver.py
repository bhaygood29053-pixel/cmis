import unittest

from liquidity_scout.cmis.xdex_route_resolver import (
    XDEXRouteResolverError,
    resolve_xdex_route_evidence,
)
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import (
    AMM_CONFIG,
    POOL,
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


def snapshot_for(route=None, **overrides):
    route = dict(route or ROUTE)
    snapshot = {
        "schema": "xdex_exact_route_snapshot.v1",
        "source": "XDEX exact-route read-only collector",
        "chain": "x1",
        "program": "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN",
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
        "reconstructed_price_impact_percent": "1.955321",
        "quote_price_impact_percent": "1.9553205",
        "quote_output_amount": "0.123",
        "quote_rate": "0.000123",
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
    def test_exact_bounded_route_emits_amount_scoped_price_impact_and_fee_evidence(self):
        evidence = resolve_xdex_route_evidence(
            ROUTE,
            "1000.000",
            collector=lambda route, amount: snapshot_for(route),
        )

        self.assertEqual(evidence["schema_version"], 2)
        self.assertEqual(evidence["source"], "cmis_xdex_route_resolver")
        self.assertEqual(evidence["route"], ROUTE)
        self.assertEqual(evidence["token_in_amount"], "1000")
        self.assertEqual(set(evidence["capabilities"]), {"price_impact", "fees"})
        self.assertEqual(
            evidence["capabilities"]["price_impact"]["semantic"],
            "route_price_impact_percent",
        )
        self.assertAlmostEqual(
            evidence["capabilities"]["fees"]["value"]["amm_trade_fee_rate_percent"],
            0.28,
        )
        self.assertNotIn("slippage", evidence["capabilities"])

    def test_evidence_is_accepted_only_for_same_trade_amount(self):
        evidence = resolve_xdex_route_evidence(
            ROUTE,
            "1000",
            collector=lambda route, amount: snapshot_for(route),
        )
        result = evaluate_route_evidence(
            evidence,
            target_chain="x1",
            trade_route=ROUTE,
            trade_token_in_amount="1000.0",
            evaluated_at="2026-08-18T21:58:05Z",
            max_age_seconds=30,
        )

        self.assertTrue(result["audit"]["route_match"])
        self.assertTrue(result["audit"]["amount_match"])
        self.assertEqual(
            set(result["audit"]["usable_capabilities"]),
            {"price_impact", "fees"},
        )
        self.assertEqual(result["overrides"]["price_impact"]["status"], "ok")
        self.assertEqual(result["overrides"]["fees"]["status"], "ok")
        self.assertFalse(result["audit"]["rejected_capabilities"])

    def test_evidence_is_rejected_for_different_trade_amount(self):
        evidence = resolve_xdex_route_evidence(
            ROUTE,
            "1000",
            collector=lambda route, amount: snapshot_for(route),
        )
        result = evaluate_route_evidence(
            evidence,
            target_chain="x1",
            trade_route=ROUTE,
            trade_token_in_amount="1",
            evaluated_at="2026-08-18T21:58:05Z",
            max_age_seconds=30,
        )

        self.assertFalse(result["audit"]["amount_match"])
        self.assertEqual(
            result["audit"]["global_rejection_reason"],
            "route_evidence_input_amount_mismatch",
        )
        self.assertFalse(result["overrides"])

    def test_other_verified_route_does_not_inherit_bounded_fee_evidence(self):
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
                trade_fee_rate_ppm=3000,
            ),
        )

        self.assertEqual(evidence["token_in_amount"], "1")
        self.assertEqual(set(evidence["capabilities"]), {"price_impact"})
        self.assertNotIn("fees", evidence["capabilities"])

    def test_collector_amount_mismatch_fails_closed(self):
        with self.assertRaisesRegex(XDEXRouteResolverError, "requested exact input amount"):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(
                    route,
                    token_in_amount="1",
                ),
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

    def test_snapshot_route_mismatch_fails_closed(self):
        wrong = dict(ROUTE)
        wrong["pool"] = "WRONG_POOL"
        with self.assertRaisesRegex(XDEXRouteResolverError, "does not match the requested exact route"):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: snapshot_for(wrong),
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
