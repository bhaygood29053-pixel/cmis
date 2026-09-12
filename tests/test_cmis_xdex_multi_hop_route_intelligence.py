import unittest

from liquidity_scout.providers.x1.xdex_multi_hop import OBSERVATION_SCHEMA
from liquidity_scout.services.cmis_xdex_multi_hop_route_intelligence import (
    CONTRACT_VERSION,
    XDEXMultiHopRouteIntelligenceError,
    build_xdex_multi_hop_route_intelligence,
)


def observation():
    return {
        "schema": OBSERVATION_SCHEMA,
        "chain": "x1",
        "source": "XDEX multi-hop public quote API",
        "endpoint": "https://api.xdex.xyz/api/xdex/swap/multi-hop/quote",
        "request": {
            "token_in": "A",
            "token_out": "C",
            "token_in_amount": "1",
            "venue": "all",
            "max_hops": "6",
            "network": "X1 Mainnet",
        },
        "raw_response": {"success": True, "data": {"uninterpreted": True}},
        "provider_semantics_promoted": False,
        "prepare_called": False,
        "read_only": True,
        "execution_authorized": False,
    }


def hop(index, token_in, token_out, pool, *, venue="xdex", verified=True):
    return {
        "index": index,
        "token_in_mint": token_in,
        "token_out_mint": token_out,
        "pool": pool,
        "venue": venue,
        "pool_identity_verified": verified,
        "pool_state_verified": verified,
        "fee_math_verified": verified,
        "reserve_math_verified": verified,
        "price_impact_verified": False,
        "minimum_received_bounded": False,
        "venue_identity_verified": verified,
        "execution_authorized": False,
    }


class XDEXMultiHopRouteIntelligenceTests(unittest.TestCase):
    def test_without_independent_hops_remains_evidence_required(self):
        result = build_xdex_multi_hop_route_intelligence(observation())
        self.assertEqual(result["contract_version"], CONTRACT_VERSION)
        self.assertEqual(result["status"], "evidence_required")
        self.assertIsNone(result["hop_count"])
        self.assertEqual(result["evidence_quality"], "EVIDENCE_REQUIRED")
        self.assertFalse(result["verification"]["route_structure_verified"])
        self.assertFalse(result["verification"]["route_optimality_verified"])
        self.assertFalse(result["provider_route_is_independent_verification"])
        self.assertFalse(result["execution_authorized"])

    def test_verified_hop_identity_and_state_can_promote_only_bounded_structure(self):
        result = build_xdex_multi_hop_route_intelligence(
            observation(),
            hop_evidence=[hop(0, "A", "B", "P1"), hop(1, "B", "C", "P2")],
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["hop_count"], 2)
        self.assertEqual(result["evidence_quality"], "VERIFIED_ROUTE_STRUCTURE")
        self.assertTrue(result["verification"]["route_structure_verified"])
        self.assertTrue(result["verification"]["pool_identity_verified"])
        self.assertTrue(result["verification"]["pool_state_verified"])
        self.assertTrue(result["verification"]["fee_math_verified"])
        self.assertTrue(result["verification"]["reserve_math_verified"])
        self.assertFalse(result["verification"]["price_impact_verified"])
        self.assertFalse(result["verification"]["route_optimality_verified"])
        self.assertFalse(result["cross_dex_execution_observed"])
        self.assertFalse(result["global_route_optimality_claimed"])

    def test_multiple_verified_venue_labels_do_not_become_cross_dex_execution(self):
        result = build_xdex_multi_hop_route_intelligence(
            observation(),
            hop_evidence=[
                hop(0, "A", "B", "P1", venue="xdex"),
                hop(1, "B", "C", "P2", venue="degen"),
            ],
        )
        self.assertEqual(result["verified_venues"], ["degen", "xdex"])
        self.assertFalse(result["verification"]["cross_dex_observed"])
        self.assertFalse(result["cross_dex_execution_observed"])
        self.assertFalse(result["cross_dex_execution_verified"])

    def test_non_contiguous_hops_fail_closed(self):
        with self.assertRaisesRegex(XDEXMultiHopRouteIntelligenceError, "not mint-contiguous"):
            build_xdex_multi_hop_route_intelligence(
                observation(),
                hop_evidence=[hop(0, "A", "B", "P1"), hop(1, "D", "C", "P2")],
            )

    def test_request_endpoints_must_match_verified_hops(self):
        with self.assertRaisesRegex(XDEXMultiHopRouteIntelligenceError, "endpoints"):
            build_xdex_multi_hop_route_intelligence(
                observation(),
                hop_evidence=[hop(0, "X", "B", "P1"), hop(1, "B", "C", "P2")],
            )

    def test_prepare_or_execution_authority_fails_closed(self):
        bad = observation()
        bad["prepare_called"] = True
        with self.assertRaisesRegex(XDEXMultiHopRouteIntelligenceError, "prepare"):
            build_xdex_multi_hop_route_intelligence(bad)

        bad = observation()
        bad["execution_authorized"] = True
        with self.assertRaisesRegex(XDEXMultiHopRouteIntelligenceError, "execution_authorized"):
            build_xdex_multi_hop_route_intelligence(bad)


if __name__ == "__main__":
    unittest.main()
