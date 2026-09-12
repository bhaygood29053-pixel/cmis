import unittest

from liquidity_scout.providers.x1.xdex_multi_hop import (
    MULTI_HOP_QUOTE_URL,
    OBSERVATION_SCHEMA,
    XDEXMultiHopError,
    collect_multi_hop_quote_observation,
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


class XDEXMultiHopProviderTests(unittest.TestCase):
    def test_preserves_exact_raw_response_without_promoting_semantics(self):
        body = {
            "success": True,
            "data": {
                "path": [{"pool": "P1"}, {"pool": "P2"}],
                "fee_bps": 50,
                "gross_output": "1.23",
                "net_output": "1.22",
            },
        }
        session = FakeSession(body)
        result = collect_multi_hop_quote_observation(
            "MINT_A",
            "MINT_C",
            "1.25",
            session=session,
            timeout=9,
        )

        self.assertEqual(result["schema"], OBSERVATION_SCHEMA)
        self.assertEqual(result["raw_response"], body)
        self.assertFalse(result["provider_semantics_promoted"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["prepare_called"])
        self.assertFalse(result["execution_authorized"])

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
