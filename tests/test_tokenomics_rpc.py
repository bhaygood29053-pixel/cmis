import unittest

from liquidity_scout.tokenomics import (
    X1RPCError,
    get_mint_info,
    get_token_supply,
    parse_mint_account_result,
    parse_token_supply_result,
    rpc_request,
)


class FakeResponse:
    def __init__(self, payload, status_code=200, raise_error=None):
        self.payload = payload
        self.status_code = status_code
        self.raise_error = raise_error

    def raise_for_status(self):
        if self.raise_error is not None:
            raise self.raise_error

    def json(self):
        return self.payload


class TokenomicsRPCTests(unittest.TestCase):
    def test_rpc_request_retries_temporary_http_failure(self):
        responses = iter([
            FakeResponse({}, status_code=429),
            FakeResponse({"result": {"ok": True}}),
        ])
        sleeps = []
        calls = []

        def post(url, json, timeout):
            calls.append((url, json, timeout))
            return next(responses)

        result = rpc_request(
            "getTokenSupply",
            ["MintA"],
            rpc_url="https://rpc.example",
            retries=2,
            post=post,
            sleep=sleeps.append,
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [0.75])
        self.assertEqual(calls[0][1]["method"], "getTokenSupply")
        self.assertEqual(calls[0][1]["params"], ["MintA"])

    def test_rpc_request_raises_after_final_failure(self):
        def post(_url, json, timeout):
            return FakeResponse({"error": {"code": -1, "message": "boom"}})

        with self.assertRaises(X1RPCError) as ctx:
            rpc_request(
                "getAccountInfo",
                ["MintA"],
                rpc_url="https://rpc.example",
                retries=2,
                post=post,
                sleep=lambda _seconds: None,
            )

        self.assertIn("failed after 2 attempts", str(ctx.exception))

    def test_token_supply_preserves_integer_precision(self):
        result = {
            "value": {
                "amount": "123456789012345678901234567890",
                "decimals": 9,
                "uiAmountString": "123456789012345678901.23456789",
            }
        }

        parsed = parse_token_supply_result(result)

        self.assertEqual(
            parsed["raw_supply"],
            "123456789012345678901234567890",
        )
        self.assertEqual(parsed["decimals"], 9)
        self.assertEqual(
            parsed["total_supply"],
            "123456789012345678901.234567890",
        )
        self.assertTrue(parsed["supply_verified"])

    def test_token_supply_missing_decimals_is_unverified_not_zero_decimals(self):
        parsed = parse_token_supply_result({
            "value": {
                "amount": "5000000",
                "uiAmountString": "5",
            }
        })

        self.assertEqual(parsed["raw_supply"], "5000000")
        self.assertIsNone(parsed["decimals"])
        self.assertIsNone(parsed["total_supply"])
        self.assertFalse(parsed["supply_verified"])

    def test_verified_null_authorities_are_distinct_from_missing_fields(self):
        parsed = parse_mint_account_result({
            "value": {
                "data": {
                    "parsed": {
                        "info": {
                            "supply": "2500000",
                            "decimals": 6,
                            "mintAuthority": None,
                            "freezeAuthority": None,
                        }
                    }
                }
            }
        })

        self.assertIsNone(parsed["mint_authority"])
        self.assertTrue(parsed["mint_authority_verified"])
        self.assertIsNone(parsed["freeze_authority"])
        self.assertTrue(parsed["freeze_authority_verified"])
        self.assertEqual(parsed["total_supply"], "2.5")
        self.assertTrue(parsed["supply_verified"])

    def test_missing_authority_fields_remain_unverified(self):
        parsed = parse_mint_account_result({
            "value": {
                "data": {
                    "parsed": {
                        "info": {
                            "supply": "2500000",
                            "decimals": 6,
                        }
                    }
                }
            }
        })

        self.assertIsNone(parsed["mint_authority"])
        self.assertFalse(parsed["mint_authority_verified"])
        self.assertIsNone(parsed["freeze_authority"])
        self.assertFalse(parsed["freeze_authority_verified"])

    def test_malformed_supply_does_not_become_zero(self):
        parsed = parse_mint_account_result({
            "value": {
                "data": {
                    "parsed": {
                        "info": {
                            "supply": "not-a-number",
                            "decimals": 6,
                            "mintAuthority": "AuthorityA",
                            "freezeAuthority": None,
                        }
                    }
                }
            }
        })

        self.assertEqual(parsed["raw_supply"], "not-a-number")
        self.assertIsNone(parsed["total_supply"])
        self.assertFalse(parsed["supply_verified"])

    def test_get_token_supply_uses_get_token_supply_rpc(self):
        calls = []

        def post(_url, json, timeout):
            calls.append(json)
            return FakeResponse({
                "result": {
                    "value": {
                        "amount": "42000000",
                        "decimals": 6,
                        "uiAmountString": "42",
                    }
                }
            })

        parsed = get_token_supply(
            "MintA",
            rpc_url="https://rpc.example",
            post=post,
        )

        self.assertEqual(calls[0]["method"], "getTokenSupply")
        self.assertEqual(calls[0]["params"], ["MintA"])
        self.assertEqual(parsed["total_supply"], "42")

    def test_get_mint_info_requests_json_parsed_account(self):
        calls = []

        def post(_url, json, timeout):
            calls.append(json)
            return FakeResponse({
                "result": {
                    "value": {
                        "data": {
                            "parsed": {
                                "info": {
                                    "supply": "42000000",
                                    "decimals": 6,
                                    "mintAuthority": "AuthorityA",
                                    "freezeAuthority": None,
                                }
                            }
                        }
                    }
                }
            })

        parsed = get_mint_info(
            "MintA",
            rpc_url="https://rpc.example",
            post=post,
        )

        self.assertEqual(calls[0]["method"], "getAccountInfo")
        self.assertEqual(
            calls[0]["params"],
            ["MintA", {"encoding": "jsonParsed"}],
        )
        self.assertEqual(parsed["mint_authority"], "AuthorityA")
        self.assertTrue(parsed["mint_authority_verified"])
        self.assertIsNone(parsed["freeze_authority"])
        self.assertTrue(parsed["freeze_authority_verified"])

    def test_empty_mint_is_rejected(self):
        with self.assertRaises(ValueError):
            get_token_supply("   ")

        with self.assertRaises(ValueError):
            get_mint_info("")


if __name__ == "__main__":
    unittest.main()
