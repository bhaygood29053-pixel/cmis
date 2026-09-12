from copy import deepcopy
import unittest

from liquidity_scout.providers.x1.xdex_multi_hop import (
    MULTI_HOP_QUOTE_URL,
    OBSERVATION_SCHEMA,
    PARSED_SCHEMA,
    XDEXMultiHopError,
    collect_multi_hop_quote_observation,
    parse_multi_hop_quote_observation,
)


class FakeResponse:
    def __init__(self, body, *, text=""):
        self.body = body
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append({"url": url, "params": dict(params), "timeout": timeout})
        return FakeResponse(self.body)


def live_shape_observation():
    token_in = "So11111111111111111111111111111111111111112"
    middle = "33kzreZb3DnzBrcbdeiWhGtdc8aU1uxqb2mMTii2hNGq"
    token_out = "GdgA3rcAzWsrtt8QkyNXNTrrvfRPeAYiJPyyxSku8pzk"
    return {
        "schema": OBSERVATION_SCHEMA,
        "chain": "x1",
        "source": "XDEX multi-hop public quote API",
        "endpoint": MULTI_HOP_QUOTE_URL,
        "request": {
            "token_in": token_in,
            "token_out": token_out,
            "token_in_amount": "1",
            "venue": "all",
            "max_hops": "6",
            "network": "X1 Mainnet",
        },
        "raw_response": {
            "success": True,
            "data": {
                "input_mint": token_in,
                "output_mint": token_out,
                "input_amount": "1",
                "input_amount_raw": "1000000000",
                "output_amount_gross": "0.010526643",
                "output_amount_gross_raw": "10526643",
                "output_amount": "0.010474009",
                "output_amount_raw": "10474009",
                "fee_bps": 50,
                "fee_amount": "0.000052633",
                "fee_amount_raw": "52633",
                "hop_count": 2,
                "min_hops": 1,
                "max_hops": 6,
                "network": "X1 Mainnet",
                "venue": "all",
                "rate": 0.010474009,
                "rate_gross": 0.010526643,
                "path": [token_in, middle, token_out],
                "tokens": {
                    token_in: {"mint": token_in, "decimals": 9, "symbol": "WXNT", "name": "Wrapped XNT"},
                    middle: {"mint": middle, "decimals": 9, "symbol": "Bolt", "name": "Bolt"},
                    token_out: {"mint": token_out, "decimals": 9, "symbol": "Unknown", "name": "Unknown"},
                },
                "hops": [
                    {
                        "pool": "FqZJXKZ92mbLzyZ3u6Mfb9WxsDpCnvSvq433m9qXUCLs",
                        "venue": "xdex",
                        "token_in": token_in,
                        "token_out": middle,
                        "amount_in": "1",
                        "amount_in_raw": "1000000000",
                        "amount_out": "10.668504732",
                        "amount_out_raw": "10668504732",
                        "reserve_in": "1.416758715",
                        "reserve_in_raw": "1416758715",
                        "reserve_out": "25.825641771",
                        "reserve_out_raw": "25825641771",
                        "reserve_in_after": "2.416758715",
                        "reserve_in_after_raw": "2416758715",
                        "reserve_out_after": "15.157137039",
                        "reserve_out_after_raw": "15157137039",
                        "trade_fee_rate": "2800",
                    },
                    {
                        "pool": "DYjBdDGvMQ4rkFSWP5ZzF3weJNSx3tc639QehAnUyCkp",
                        "venue": "xdex",
                        "token_in": middle,
                        "token_out": token_out,
                        "amount_in": "10.668504732",
                        "amount_in_raw": "10668504732",
                        "amount_out": "0.010526643",
                        "amount_out_raw": "10526643",
                        "reserve_in": "1000",
                        "reserve_in_raw": "1000000000000",
                        "reserve_out": "1",
                        "reserve_out_raw": "1000000000",
                        "reserve_in_after": "1010.668504732",
                        "reserve_in_after_raw": "1010668504732",
                        "reserve_out_after": "0.989473357",
                        "reserve_out_after_raw": "989473357",
                        "trade_fee_rate": "2800",
                    },
                ],
            },
        },
        "provider_semantics_promoted": False,
        "prepare_called": False,
        "read_only": True,
        "execution_authorized": False,
    }


class XDEXMultiHopProviderTests(unittest.TestCase):
    def test_preserves_exact_raw_response_without_promoting_semantics(self):
        body = {"success": True, "data": {"path": [{"pool": "P1"}], "fee_bps": 50}}
        session = FakeSession(body)
        result = collect_multi_hop_quote_observation(
            "MINT_A", "MINT_C", "1.25", session=session, timeout=9
        )

        self.assertEqual(result["schema"], OBSERVATION_SCHEMA)
        self.assertEqual(result["raw_response"], body)
        self.assertFalse(result["provider_semantics_promoted"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["prepare_called"])
        self.assertFalse(result["execution_authorized"])
        self.assertNotIn("prepare", result["endpoint"])

        call = session.calls[0]
        self.assertEqual(call["url"], MULTI_HOP_QUOTE_URL)
        self.assertEqual(
            call["params"],
            {
                "token_in": "MINT_A",
                "token_out": "MINT_C",
                "token_in_amount": "1.25",
                "venue": "all",
                "max_hops": "6",
                "network": "X1 Mainnet",
            },
        )
        self.assertEqual(call["timeout"], 9)

    def test_parser_pins_live_shape_and_provider_arithmetic_without_promoting_semantics(self):
        parsed = parse_multi_hop_quote_observation(live_shape_observation())
        self.assertEqual(parsed["schema"], PARSED_SCHEMA)
        self.assertEqual(parsed["hop_count"], 2)
        self.assertEqual(parsed["provider_venues"], ["xdex"])
        self.assertEqual(parsed["provider_fee_bps"], 50)
        self.assertEqual(parsed["provider_fee_floor_rounding_delta_raw"], 1)
        self.assertTrue(parsed["provider_schema_verified"])
        self.assertTrue(parsed["provider_route_identity_verified"])
        self.assertTrue(parsed["provider_hop_continuity_verified"])
        self.assertTrue(parsed["provider_hop_curve_arithmetic_verified"])
        self.assertTrue(parsed["provider_fee_transform_verified"])
        self.assertFalse(parsed["provider_fee_business_semantics_verified"])
        self.assertFalse(parsed["provider_cross_dex_route_quoted"])
        self.assertFalse(parsed["cross_dex_execution_observed"])
        self.assertFalse(parsed["route_optimality_verified"])
        self.assertFalse(parsed["provider_semantics_promoted"])
        self.assertFalse(parsed["execution_authorized"])

    def test_parser_rejects_curve_tampering(self):
        source = live_shape_observation()
        source["raw_response"]["data"]["hops"][0]["trade_fee_rate"] = "3000"
        with self.assertRaisesRegex(XDEXMultiHopError, "constant-product arithmetic"):
            parse_multi_hop_quote_observation(source)

    def test_parser_rejects_fee_transform_tampering(self):
        source = live_shape_observation()
        source["raw_response"]["data"]["output_amount_raw"] = "10474010"
        with self.assertRaisesRegex(XDEXMultiHopError, "raw-token value"):
            parse_multi_hop_quote_observation(source)

    def test_mixed_venue_quote_is_not_execution_evidence(self):
        source = live_shape_observation()
        source["raw_response"]["data"]["hops"][1]["venue"] = "degen"
        parsed = parse_multi_hop_quote_observation(source)
        self.assertTrue(parsed["provider_cross_dex_route_quoted"])
        self.assertFalse(parsed["cross_dex_execution_observed"])

    def test_custom_venue_and_hop_limit_are_preserved(self):
        session = FakeSession({"success": True, "data": {}})
        result = collect_multi_hop_quote_observation(
            "A", "B", 2, venue="xdex", max_hops=3, session=session
        )
        self.assertEqual(result["request"]["venue"], "xdex")
        self.assertEqual(result["request"]["max_hops"], "3")

    def test_same_token_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must differ"):
            collect_multi_hop_quote_observation("A", "A", "1")

    def test_non_positive_amount_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "positive finite decimal"):
            collect_multi_hop_quote_observation("A", "B", "0")

    def test_hop_limit_is_bounded_to_router_ceiling(self):
        with self.assertRaisesRegex(ValueError, "1 through 6"):
            collect_multi_hop_quote_observation("A", "B", "1", max_hops=7)

    def test_non_mapping_response_fails_closed(self):
        session = FakeSession(["not", "an", "object"])
        with self.assertRaisesRegex(XDEXMultiHopError, "JSON object"):
            collect_multi_hop_quote_observation("A", "B", "1", session=session)


if __name__ == "__main__":
    unittest.main()
