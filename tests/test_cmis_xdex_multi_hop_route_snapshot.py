from copy import deepcopy
import unittest

from liquidity_scout.providers.x1.xdex_multi_hop import PARSED_SCHEMA
from liquidity_scout.providers.x1.xdex_multi_hop_onchain import VERIFICATION_SCHEMA
from liquidity_scout.services.cmis_xdex_multi_hop_route_snapshot import (
    CONTRACT_VERSION,
    XDEXMultiHopRouteSnapshotError,
    build_xdex_multi_hop_route_snapshot,
)


TOKEN_A = "So11111111111111111111111111111111111111112"
TOKEN_B = "33kzreZb3DnzBrcbdeiWhGtdc8aU1uxqb2mMTii2hNGq"
TOKEN_C = "GdgA3rcAzWsrtt8QkyNXNTrrvfRPeAYiJPyyxSku8pzk"
POOL_0 = "FqZJXKZ92mbLzyZ3u6Mfb9WxsDpCnvSvq433m9qXUCLs"
POOL_1 = "DYjBdDGvMQ4rkFSWP5ZzF3weJNSx3tc639QehAnUyCkp"
CONFIG = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"


def parsed_quote():
    return {
        "schema": PARSED_SCHEMA,
        "chain": "x1",
        "source": "XDEX multi-hop public quote API",
        "request": {
            "token_in": TOKEN_A,
            "token_out": TOKEN_C,
            "token_in_amount": "1",
            "venue": "all",
            "max_hops": "6",
            "network": "X1 Mainnet",
        },
        "input_mint": TOKEN_A,
        "output_mint": TOKEN_C,
        "input_amount_raw": 1_000_000_000,
        "output_amount_gross_raw": 10_526_643,
        "output_amount_raw": 10_474_009,
        "provider_fee_bps": 50,
        "provider_fee_amount_raw": 52_633,
        "provider_fee_floor_rounding_delta_raw": 1,
        "hop_count": 2,
        "path": [TOKEN_A, TOKEN_B, TOKEN_C],
        "hops": [
            {
                "index": 0,
                "pool": POOL_0,
                "venue": "xdex",
                "token_in_mint": TOKEN_A,
                "token_out_mint": TOKEN_B,
                "amount_in_raw": 1_000_000_000,
                "amount_out_raw": 10_668_504_732,
                "provider_reserve_in_raw": 1_416_758_715,
                "provider_reserve_out_raw": 25_825_641_771,
                "provider_trade_fee_rate_ppm": 2800,
                "provider_curve_output_raw": 10_668_504_732,
            },
            {
                "index": 1,
                "pool": POOL_1,
                "venue": "xdex",
                "token_in_mint": TOKEN_B,
                "token_out_mint": TOKEN_C,
                "amount_in_raw": 10_668_504_732,
                "amount_out_raw": 10_526_643,
                "provider_reserve_in_raw": 1_000_000_000_000,
                "provider_reserve_out_raw": 1_000_000_000,
                "provider_trade_fee_rate_ppm": 2800,
                "provider_curve_output_raw": 10_526_643,
            },
        ],
        "provider_venues": ["xdex"],
        "provider_schema_verified": True,
        "provider_route_identity_verified": True,
        "provider_hop_continuity_verified": True,
        "provider_hop_curve_arithmetic_verified": True,
        "provider_fee_transform_verified": True,
        "provider_fee_business_semantics_verified": False,
        "provider_cross_dex_route_quoted": False,
        "cross_dex_execution_observed": False,
        "route_optimality_verified": False,
        "provider_semantics_promoted": False,
        "prepare_called": False,
        "read_only": True,
        "execution_authorized": False,
    }


def verified_hop(index, pool, token_in, token_out, reserve_in, reserve_out, output, trade_fee, pool_slot, config_slot):
    return {
        "index": index,
        "pool": pool,
        "venue": "xdex",
        "token_in_mint": token_in,
        "token_out_mint": token_out,
        "amm_config": CONFIG,
        "pool_context_slot": pool_slot,
        "config_context_slot": config_slot,
        "active_reserve_in_raw": reserve_in,
        "active_reserve_out_raw": reserve_out,
        "trade_fee_rate_ppm": 2800,
        "protocol_fee_rate_ppm_of_trade_fee": 120000,
        "fund_fee_rate_ppm_of_trade_fee": 40000,
        "creator_fee_rate_ppm": 0,
        "creator_fee_on": 0,
        "enable_creator_fee": False,
        "reconstructed_output_raw": output,
        "reconstructed_trade_fee_raw": trade_fee,
        "reconstructed_creator_fee_raw": 0,
        "pool_identity_verified": True,
        "pool_state_verified": True,
        "venue_identity_verified": True,
        "reserve_math_verified": True,
        "fee_math_verified": True,
        "price_impact_verified": False,
        "minimum_received_bounded": False,
        "execution_authorized": False,
    }


def onchain_verification():
    return {
        "schema": VERIFICATION_SCHEMA,
        "chain": "x1",
        "source": "X1 RPC independent XDEX multi-hop verifier",
        "verification_slot_before": 80_000_000,
        "verification_slot_after": 80_000_006,
        "verification_slot_min": 80_000_000,
        "verification_slot_max": 80_000_006,
        "verification_slot_span": 6,
        "max_slot_span": 8,
        "hop_count": 2,
        "hops": [
            verified_hop(
                0,
                POOL_0,
                TOKEN_A,
                TOKEN_B,
                1_416_758_715,
                25_825_641_771,
                10_668_504_732,
                2_800_000,
                80_000_002,
                80_000_003,
            ),
            verified_hop(
                1,
                POOL_1,
                TOKEN_B,
                TOKEN_C,
                1_000_000_000_000,
                1_000_000_000,
                10_526_643,
                29_871_814,
                80_000_004,
                80_000_005,
            ),
        ],
        "route_structure_verified": True,
        "pool_identity_verified": True,
        "pool_state_verified": True,
        "fee_math_verified": True,
        "reserve_math_verified": True,
        "current_state_alignment_verified": True,
        "provider_fact_time_verified": False,
        "route_optimality_verified": False,
        "cross_dex_execution_observed": False,
        "cross_dex_execution_verified": False,
        "read_only": True,
        "execution_authorized": False,
    }


class XDEXMultiHopRouteSnapshotTests(unittest.TestCase):
    def build(self, quote=None, verification=None):
        return build_xdex_multi_hop_route_snapshot(
            parsed_quote() if quote is None else quote,
            onchain_verification() if verification is None else verification,
        )

    def test_builds_provider_agnostic_verified_route_snapshot(self):
        result = self.build()
        self.assertEqual(result["contract_version"], CONTRACT_VERSION)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["hop_count"], 2)
        self.assertEqual(result["path"], [TOKEN_A, TOKEN_B, TOKEN_C])
        self.assertEqual(result["gross_output_raw"], 10_526_643)
        self.assertEqual(result["net_output_raw"], 10_474_009)
        self.assertEqual(result["observation_window"]["slot_span"], 6)
        self.assertTrue(result["observation_window"]["current_state_alignment_verified"])
        self.assertFalse(result["observation_window"]["provider_fact_time_verified"])
        self.assertTrue(result["route_output"]["aggregate_hop_output_verified"])
        self.assertEqual(result["provider_routing_fee_transform"]["fee_bps"], 50)
        self.assertTrue(result["provider_routing_fee_transform"]["arithmetic_transform_verified"])
        self.assertFalse(result["provider_routing_fee_transform"]["business_semantics_verified"])
        self.assertEqual(result["price_impact"]["status"], "EVIDENCE_REQUIRED")
        self.assertEqual(result["minimum_received"]["status"], "EVIDENCE_REQUIRED")
        self.assertEqual(result["network_fee"]["status"], "EVIDENCE_REQUIRED")
        self.assertFalse(result["route_optimality_verified"])
        self.assertFalse(result["provider_raw_json_exposed"])
        self.assertFalse(result["execution_authorized"])
        self.assertNotIn("raw_response", result)
        self.assertNotIn("provider_observation", result)

    def test_preserves_exact_hop_lineage_and_separate_fee_units(self):
        result = self.build()
        first = result["hops"][0]
        self.assertEqual(first["pool"], POOL_0)
        self.assertEqual(first["amm_config"], CONFIG)
        self.assertEqual(first["pool_context_slot"], 80_000_002)
        self.assertEqual(first["config_context_slot"], 80_000_003)
        self.assertEqual(first["trade_fee_rate_ppm"], 2800)
        self.assertEqual(result["pool_fee_evidence"][0]["input_mint"], TOKEN_A)
        self.assertEqual(result["pool_fee_evidence"][1]["input_mint"], TOKEN_B)

    def test_rejects_pool_identity_mutation(self):
        verification = onchain_verification()
        verification["hops"][0]["pool"] = "different-pool"
        with self.assertRaisesRegex(XDEXMultiHopRouteSnapshotError, "pool mismatch"):
            self.build(verification=verification)

    def test_rejects_route_mint_mutation(self):
        verification = onchain_verification()
        verification["hops"][1]["token_in_mint"] = TOKEN_A
        with self.assertRaisesRegex(XDEXMultiHopRouteSnapshotError, "token_in_mint mismatch"):
            self.build(verification=verification)

    def test_rejects_reserve_mutation(self):
        verification = onchain_verification()
        verification["hops"][0]["active_reserve_in_raw"] += 1
        with self.assertRaisesRegex(XDEXMultiHopRouteSnapshotError, "input reserve mismatch"):
            self.build(verification=verification)

    def test_rejects_fee_config_mutation(self):
        verification = onchain_verification()
        verification["hops"][1]["trade_fee_rate_ppm"] = 3000
        with self.assertRaisesRegex(XDEXMultiHopRouteSnapshotError, "trade-fee configuration mismatch"):
            self.build(verification=verification)

    def test_rejects_reconstructed_output_mutation(self):
        verification = onchain_verification()
        verification["hops"][1]["reconstructed_output_raw"] += 1
        with self.assertRaisesRegex(XDEXMultiHopRouteSnapshotError, "reconstructed output"):
            self.build(verification=verification)

    def test_rejects_stale_slot_span(self):
        verification = onchain_verification()
        verification["verification_slot_max"] = 80_000_009
        verification["verification_slot_after"] = 80_000_009
        verification["verification_slot_span"] = 9
        with self.assertRaisesRegex(XDEXMultiHopRouteSnapshotError, "slot-alignment bound"):
            self.build(verification=verification)

    def test_rejects_unverified_current_state_alignment(self):
        verification = onchain_verification()
        verification["current_state_alignment_verified"] = False
        with self.assertRaisesRegex(XDEXMultiHopRouteSnapshotError, "current_state_alignment_verified"):
            self.build(verification=verification)

    def test_rejects_execution_authority_widening(self):
        quote = parsed_quote()
        quote["execution_authorized"] = True
        with self.assertRaisesRegex(XDEXMultiHopRouteSnapshotError, "execution_authorized"):
            self.build(quote=quote)

    def test_rejects_provider_fee_business_semantics_promotion(self):
        quote = parsed_quote()
        quote["provider_fee_business_semantics_verified"] = True
        with self.assertRaisesRegex(XDEXMultiHopRouteSnapshotError, "provider_fee_business_semantics_verified"):
            self.build(quote=quote)

    def test_rejects_provider_raw_json_at_snapshot_boundary(self):
        quote = parsed_quote()
        quote["raw_response"] = {"success": True}
        with self.assertRaisesRegex(XDEXMultiHopRouteSnapshotError, "raw provider response"):
            self.build(quote=quote)

    def test_cross_dex_states_remain_separate_from_execution(self):
        quote = parsed_quote()
        quote["provider_cross_dex_route_quoted"] = True
        result = self.build(quote=quote)
        self.assertIsNone(result["cross_dex_configured"])
        self.assertTrue(result["cross_dex_route_available"])
        self.assertFalse(result["cross_dex_execution_observed"])
        self.assertFalse(result["cross_dex_execution_verified"])


if __name__ == "__main__":
    unittest.main()
