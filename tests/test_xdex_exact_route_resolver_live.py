import os
import unittest

from liquidity_scout.cmis.xdex_route_resolver import resolve_xdex_route_evidence
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import (
    AMM_CONFIG,
    POOL,
    XENCAT_MINT,
    XNT_MINT,
)
from liquidity_scout.services.pre_trade_route_evidence import evaluate_route_evidence


RUN_LIVE = os.getenv("RUN_XDEX_EXACT_ROUTE_LIVE") == "1"
ROUTE = {
    "token_in_mint": XENCAT_MINT,
    "token_out_mint": XNT_MINT,
    "pool": POOL,
    "amm_config": AMM_CONFIG,
}


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_EXACT_ROUTE_LIVE=1 to run the read-only exact-route resolver probe",
)
class XDEXExactRouteResolverLiveTests(unittest.TestCase):
    def test_pinned_xencat_xnt_route_resolves_verified_price_impact_read_only(self):
        evidence = resolve_xdex_route_evidence(ROUTE, "1000")

        self.assertEqual(evidence["source"], "cmis_xdex_route_resolver")
        self.assertEqual(evidence["route"], ROUTE)
        self.assertIn("price_impact", evidence["capabilities"])
        # Bounded historical fee evidence must now be supplied explicitly to
        # the resolver and reclassified through the accepted #198 contract.
        # A live route read alone cannot manufacture that historical proof.
        self.assertNotIn("fees", evidence["capabilities"])
        self.assertNotIn("slippage", evidence["capabilities"])

        evaluated = evaluate_route_evidence(
            evidence,
            target_chain="x1",
            trade_route=ROUTE,
            evaluated_at=evidence["observed_at"],
            max_age_seconds=30,
        )
        self.assertEqual(
            set(evaluated["audit"]["usable_capabilities"]),
            {"price_impact"},
        )
        self.assertEqual(evaluated["overrides"]["price_impact"]["status"], "ok")
        self.assertFalse(evaluated["audit"]["rejected_capabilities"])

        print(
            {
                "route": evidence["route"],
                "observed_at": evidence["observed_at"],
                "price_impact_percent": evidence["capabilities"]["price_impact"]["value"],
                "bounded_historical_fee_promoted_without_explicit_evidence": False,
                "expected_execution_slippage_promoted": False,
                "execution_authorized": False,
            }
        )


if __name__ == "__main__":
    unittest.main()
