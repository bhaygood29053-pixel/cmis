import unittest

from liquidity_scout.providers.x1 import (
    DEFAULT_X1_RPC_URL,
    RPC_SOURCE,
    X1RPCError,
    X1RPCProvider,
    get_mint_info as provider_get_mint_info,
    get_token_supply as provider_get_token_supply,
    parse_mint_account_result as provider_parse_mint_account_result,
    parse_token_supply_result as provider_parse_token_supply_result,
    rpc_request as provider_rpc_request,
)
from liquidity_scout.tokenomics import (
    get_mint_info as legacy_get_mint_info,
    get_token_supply as legacy_get_token_supply,
    parse_mint_account_result as legacy_parse_mint_account_result,
    parse_token_supply_result as legacy_parse_token_supply_result,
    rpc_request as legacy_rpc_request,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class X1RPCProviderTests(unittest.TestCase):
    def test_provider_identifies_chain_and_source(self):
        provider = X1RPCProvider(post=lambda *_args, **_kwargs: None)

        self.assertEqual(provider.chain, "x1")
        self.assertEqual(provider.rpc_source, "X1 RPC")
        self.assertEqual(RPC_SOURCE, "X1 RPC")
        self.assertEqual(provider.rpc_url, DEFAULT_X1_RPC_URL)

    def test_legacy_tokenomics_imports_are_provider_compatibility_exports(self):
        self.assertIs(legacy_rpc_request, provider_rpc_request)
        self.assertIs(legacy_get_token_supply, provider_get_token_supply)
        self.assertIs(legacy_get_mint_info, provider_get_mint_info)
        self.assertIs(
            legacy_parse_token_supply_result,
            provider_parse_token_supply_result,
        )
        self.assertIs(
            legacy_parse_mint_account_result,
            provider_parse_mint_account_result,
        )

    def test_provider_request_delegates_with_configured_transport(self):
        calls = []

        def post(url, json, timeout):
            calls.append((url, json, timeout))
            return FakeResponse({"result": {"ok": True}})

        provider = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            timeout=9,
            post=post,
            sleep=lambda _seconds: None,
        )

        result = provider.request("getSlot", [])

        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls[0][0], "https://rpc.example")
        self.assertEqual(calls[0][1]["method"], "getSlot")
        self.assertEqual(calls[0][1]["params"], [])
        self.assertEqual(calls[0][2], 9)

    def test_provider_get_token_supply_preserves_verified_result(self):
        calls = []

        def post(_url, json, timeout):
            calls.append((json, timeout))
            return FakeResponse({
                "result": {
                    "value": {
                        "amount": "42000000",
                        "decimals": 6,
                        "uiAmountString": "42",
                    }
                }
            })

        provider = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        result = provider.get_token_supply("MintA")

        self.assertEqual(calls[0][0]["method"], "getTokenSupply")
        self.assertEqual(calls[0][0]["params"], ["MintA"])
        self.assertEqual(result["raw_supply"], "42000000")
        self.assertEqual(result["decimals"], 6)
        self.assertEqual(result["total_supply"], "42")
        self.assertTrue(result["supply_verified"])
        self.assertEqual(result["source"], "X1 RPC getTokenSupply")

    def test_provider_get_mint_info_preserves_authority_verification(self):
        def post(_url, json, timeout):
            return FakeResponse({
                "result": {
                    "value": {
                        "data": {
                            "parsed": {
                                "info": {
                                    "supply": "2500000",
                                    "decimals": 6,
                                    "mintAuthority": None,
                                    "freezeAuthority": "FreezeAuthorityA",
                                }
                            }
                        }
                    }
                }
            })

        provider = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        result = provider.get_mint_info("MintA")

        self.assertIsNone(result["mint_authority"])
        self.assertTrue(result["mint_authority_verified"])
        self.assertEqual(result["freeze_authority"], "FreezeAuthorityA")
        self.assertTrue(result["freeze_authority_verified"])
        self.assertEqual(result["total_supply"], "2.5")
        self.assertTrue(result["supply_verified"])
        self.assertEqual(result["source"], "X1 RPC getAccountInfo(jsonParsed)")

    def test_provider_preserves_unverified_missing_decimals(self):
        parsed = provider_parse_token_supply_result({
            "value": {
                "amount": "5000000",
                "uiAmountString": "5",
            }
        })

        self.assertEqual(parsed["raw_supply"], "5000000")
        self.assertIsNone(parsed["decimals"])
        self.assertIsNone(parsed["total_supply"])
        self.assertFalse(parsed["supply_verified"])

    def test_provider_rejects_empty_rpc_url_and_invalid_retries(self):
        with self.assertRaises(ValueError):
            X1RPCProvider(rpc_url="   ")

        with self.assertRaises(ValueError):
            X1RPCProvider(retries=0)

    def test_provider_propagates_final_rpc_failure(self):
        def post(_url, json, timeout):
            return FakeResponse({"error": {"code": -1, "message": "boom"}})

        provider = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        with self.assertRaises(X1RPCError):
            provider.get_token_supply("MintA")


if __name__ == "__main__":
    unittest.main()
