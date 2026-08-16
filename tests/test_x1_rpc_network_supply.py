import unittest

from liquidity_scout.providers.x1.rpc import X1RPCProvider
from liquidity_scout.providers.x1.rpc_supply import (
    RPC_NETWORK_SUPPLY_SOURCE,
    X1_NATIVE_BASE_UNITS_PER_XNT,
    X1_NATIVE_UNIT_SOURCE,
    X1RPCSupplyError,
    X1RPCSupplyProvider,
    base_units_to_xnt_text,
    get_network_supply_rpc,
    parse_network_supply_result,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class X1RPCNetworkSupplyTests(unittest.TestCase):
    def test_official_x1_sdk_native_scale_is_recorded(self):
        self.assertEqual(X1_NATIVE_BASE_UNITS_PER_XNT, 1_000_000_000)
        self.assertIn("x1-labs/x1-sdk", X1_NATIVE_UNIT_SOURCE)
        self.assertIn("LAMPORTS_PER_SOL=1_000_000_000", X1_NATIVE_UNIT_SOURCE)

    def test_exact_base_unit_conversion_uses_integer_arithmetic(self):
        cases = {
            0: "0",
            1: "0.000000001",
            10: "0.00000001",
            1_000_000_000: "1",
            4_100_000_000: "4.1",
            1_067_261_047_026_136_701: "1067261047.026136701",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(base_units_to_xnt_text(raw), expected)

    def test_parse_preserves_raw_units_and_adds_exact_xnt_values(self):
        parsed = parse_network_supply_result({
            "context": {"slot": 123},
            "value": {
                "total": 1067000000000000000,
                "circulating": 13800000000000000,
                "nonCirculating": 1053200000000000000,
            },
        })

        self.assertEqual(parsed["chain"], "x1")
        self.assertEqual(parsed["asset"], "XNT")
        self.assertEqual(parsed["total_raw"], "1067000000000000000")
        self.assertEqual(parsed["circulating_raw"], "13800000000000000")
        self.assertEqual(parsed["non_circulating_raw"], "1053200000000000000")
        self.assertEqual(parsed["total_xnt"], "1067000000")
        self.assertEqual(parsed["circulating_xnt"], "13800000")
        self.assertEqual(parsed["non_circulating_xnt"], "1053200000")
        self.assertEqual(parsed["context_slot"], "123")
        self.assertEqual(parsed["commitment"], "finalized")
        self.assertEqual(parsed["representation"], "rpc_base_units")
        self.assertEqual(parsed["base_units_per_xnt"], 1_000_000_000)
        self.assertTrue(parsed["units_verified_by_x1_sdk"])
        self.assertFalse(parsed["api_x1_xyz_rounding_verified"])
        self.assertEqual(parsed["source"], RPC_NETWORK_SUPPLY_SOURCE)

    def test_parse_accepts_digit_strings_and_canonicalizes_leading_zeroes(self):
        parsed = parse_network_supply_result({
            "value": {
                "total": "00100",
                "circulating": "00025",
                "nonCirculating": "00075",
            }
        })

        self.assertEqual(parsed["total_raw"], "100")
        self.assertEqual(parsed["circulating_raw"], "25")
        self.assertEqual(parsed["non_circulating_raw"], "75")
        self.assertEqual(parsed["total_xnt"], "0.0000001")
        self.assertEqual(parsed["circulating_xnt"], "0.000000025")
        self.assertEqual(parsed["non_circulating_xnt"], "0.000000075")
        self.assertIsNone(parsed["context_slot"])

    def test_parse_fails_closed_on_missing_or_invalid_required_values(self):
        invalid_results = [
            None,
            {},
            {"value": []},
            {"value": {"total": 1, "circulating": 1}},
            {"value": {"total": -1, "circulating": 1, "nonCirculating": 0}},
            {"value": {"total": True, "circulating": 1, "nonCirculating": 0}},
            {"value": {"total": "1.5", "circulating": 1, "nonCirculating": 0}},
        ]

        for value in invalid_results:
            with self.subTest(value=value):
                with self.assertRaises(X1RPCSupplyError):
                    parse_network_supply_result(value)

    def test_get_network_supply_uses_finalized_excluding_account_list(self):
        calls = []

        def post(url, json, timeout):
            calls.append((url, json, timeout))
            return FakeResponse({
                "result": {
                    "context": {"slot": 999},
                    "value": {
                        "total": 1000,
                        "circulating": 250,
                        "nonCirculating": 750,
                    },
                }
            })

        result = get_network_supply_rpc(
            rpc_url="https://rpc.example",
            retries=1,
            timeout=8,
            post=post,
            sleep=lambda _seconds: None,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["method"], "getSupply")
        self.assertEqual(
            calls[0][1]["params"],
            [{"commitment": "finalized", "excludeNonCirculatingAccountsList": True}],
        )
        self.assertEqual(calls[0][2], 8)
        self.assertEqual(result["total_raw"], "1000")
        self.assertEqual(result["total_xnt"], "0.000001")
        self.assertEqual(result["context_slot"], "999")

    def test_facade_uses_existing_rpc_provider(self):
        calls = []

        def post(_url, json, timeout):
            calls.append((json, timeout))
            return FakeResponse({
                "result": {
                    "value": {
                        "total": 10,
                        "circulating": 4,
                        "nonCirculating": 6,
                    }
                }
            })

        rpc = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )
        result = X1RPCSupplyProvider(rpc).get_supply()

        self.assertEqual(calls[0][0]["method"], "getSupply")
        self.assertEqual(result["total_raw"], "10")
        self.assertEqual(result["circulating_raw"], "4")
        self.assertEqual(result["total_xnt"], "0.00000001")


if __name__ == "__main__":
    unittest.main()
