import unittest

from liquidity_scout.providers.x1 import (
    DEFAULT_X1_RPC_URL,
    RPC_SOURCE,
    X1RPCError,
    X1RPCProvider,
    get_first_available_block as provider_get_first_available_block,
    get_mint_info as provider_get_mint_info,
    get_signatures_for_address as provider_get_signatures_for_address,
    get_token_account_info as provider_get_token_account_info,
    get_token_supply as provider_get_token_supply,
    parse_mint_account_result as provider_parse_mint_account_result,
    parse_token_account_result as provider_parse_token_account_result,
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

    def test_token_account_parser_separates_program_owner_and_authority(self):
        parsed = provider_parse_token_account_result(
            {
                "value": {
                    "owner": "TokenProgram111",
                    "data": {
                        "parsed": {
                            "type": "account",
                            "info": {
                                "mint": "MintA",
                                "owner": "VaultAuthorityA",
                                "tokenAmount": {
                                    "amount": "1250000",
                                    "decimals": 6,
                                    "uiAmountString": "1.25",
                                },
                            },
                        }
                    },
                }
            },
            account="TokenAccountA",
        )

        self.assertTrue(parsed["account_exists"])
        self.assertTrue(parsed["identity_verified"])
        self.assertEqual(parsed["account"], "TokenAccountA")
        self.assertEqual(parsed["program_owner"], "TokenProgram111")
        self.assertEqual(parsed["token_authority"], "VaultAuthorityA")
        self.assertEqual(parsed["mint"], "MintA")
        self.assertEqual(parsed["raw_amount"], "1250000")
        self.assertEqual(parsed["decimals"], 6)

    def test_token_account_parser_preserves_missing_account(self):
        parsed = provider_parse_token_account_result(
            {"value": None},
            account="MissingAccount",
        )

        self.assertFalse(parsed["account_exists"])
        self.assertFalse(parsed["identity_verified"])
        self.assertEqual(parsed["account"], "MissingAccount")
        self.assertIsNone(parsed["mint"])
        self.assertIsNone(parsed["token_authority"])

    def test_provider_get_token_account_info_uses_json_parsed_rpc(self):
        calls = []

        def post(_url, json, timeout):
            calls.append((json, timeout))
            return FakeResponse({
                "result": {
                    "value": {
                        "owner": "TokenProgram111",
                        "data": {
                            "parsed": {
                                "type": "account",
                                "info": {
                                    "mint": "MintA",
                                    "owner": "VaultAuthorityA",
                                    "tokenAmount": {
                                        "amount": "9",
                                        "decimals": 0,
                                        "uiAmountString": "9",
                                    },
                                },
                            }
                        },
                    }
                }
            })

        provider = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        result = provider.get_token_account_info("TokenAccountA")

        self.assertEqual(calls[0][0]["method"], "getAccountInfo")
        self.assertEqual(
            calls[0][0]["params"],
            ["TokenAccountA", {"encoding": "jsonParsed"}],
        )
        self.assertTrue(result["identity_verified"])
        self.assertEqual(result["mint"], "MintA")
        self.assertEqual(result["token_authority"], "VaultAuthorityA")

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

        with self.assertRaises(ValueError):
            provider_get_token_account_info("   ")


    def test_provider_get_first_available_block_preserves_boundary_without_claiming_archive(self):
        calls = []

        def post(_url, json, timeout):
            calls.append((json, timeout))
            return FakeResponse({"result": 123})

        provider = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        result = provider.get_first_available_block()

        self.assertEqual(calls[0][0]["method"], "getFirstAvailableBlock")
        self.assertEqual(calls[0][0]["params"], [])
        self.assertEqual(result["first_available_block"], 123)
        self.assertTrue(result["history_boundary_verified"])
        self.assertFalse(result["archival_completeness_verified"])

    def test_provider_get_signatures_for_address_supports_before_cursor(self):
        calls = []

        def post(_url, json, timeout):
            calls.append((json, timeout))
            return FakeResponse({
                "result": [
                    {
                        "signature": "SigA",
                        "slot": 99,
                        "err": None,
                        "blockTime": 1700000000,
                        "confirmationStatus": "finalized",
                    }
                ]
            })

        provider = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        result = provider.get_signatures_for_address(
            "AddressA",
            before="OlderSig",
            limit=25,
        )

        self.assertEqual(calls[0][0]["method"], "getSignaturesForAddress")
        self.assertEqual(
            calls[0][0]["params"],
            ["AddressA", {"limit": 25, "before": "OlderSig"}],
        )
        self.assertEqual(result[0]["address"], "AddressA")
        self.assertEqual(result[0]["signature"], "SigA")
        self.assertEqual(result[0]["slot"], 99)
        self.assertEqual(result[0]["block_time"], 1700000000)

    def test_provider_get_block_time_preserves_unavailable_timestamp(self):
        def post(_url, json, timeout):
            return FakeResponse({"result": None})

        provider = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        result = provider.get_block_time(100)

        self.assertEqual(result["slot"], 100)
        self.assertIsNone(result["block_time"])
        self.assertFalse(result["block_time_verified"])

    def test_provider_get_block_parses_historical_identity_fields(self):
        calls = []

        def post(_url, json, timeout):
            calls.append((json, timeout))
            return FakeResponse({
                "result": {
                    "blockhash": "BlockHashA",
                    "previousBlockhash": "BlockHashPrev",
                    "parentSlot": 99,
                    "blockHeight": 88,
                    "blockTime": 1700000000,
                }
            })

        provider = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        result = provider.get_block(100)

        self.assertEqual(calls[0][0]["method"], "getBlock")
        self.assertEqual(calls[0][0]["params"][0], 100)
        self.assertTrue(result["block_available"])
        self.assertTrue(result["identity_verified"])
        self.assertEqual(result["parent_slot"], 99)
        self.assertEqual(result["block_height"], 88)
        self.assertEqual(result["block_time"], 1700000000)

    def test_provider_get_parsed_transactions_uses_canonical_get_transaction(self):
        calls = []

        def post(_url, json, timeout):
            calls.append((json, timeout))
            signature = json["params"][0]
            return FakeResponse({
                "result": {
                    "slot": 100,
                    "transaction": {"signatures": [signature]},
                    "meta": {"err": None},
                }
            })

        provider = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        result = provider.get_parsed_transactions(["SigA", "SigB"])

        self.assertEqual([call[0]["method"] for call in calls], ["getTransaction", "getTransaction"])
        self.assertEqual(
            calls[0][0]["params"][1]["encoding"],
            "jsonParsed",
        )
        self.assertEqual([item["signature"] for item in result], ["SigA", "SigB"])
        self.assertTrue(all(item["transaction_available"] for item in result))

    def test_historical_rpc_primitives_fail_closed_on_malformed_results(self):
        def malformed_first(_url, json, timeout):
            return FakeResponse({"result": "not-a-slot"})

        provider = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            post=malformed_first,
            sleep=lambda _seconds: None,
        )
        with self.assertRaises(X1RPCError):
            provider.get_first_available_block()

        def malformed_history(_url, json, timeout):
            return FakeResponse({
                "result": [{"signature": "SigA", "slot": "bad", "err": None}]
            })

        provider = X1RPCProvider(
            rpc_url="https://rpc.example",
            retries=1,
            post=malformed_history,
            sleep=lambda _seconds: None,
        )
        with self.assertRaises(X1RPCError):
            provider.get_signatures_for_address("AddressA")

        with self.assertRaises(ValueError):
            provider_get_signatures_for_address("AddressA", limit=0)
        with self.assertRaises(ValueError):
            provider_get_first_available_block(
                rpc_url=" ",
                retries=1,
                post=malformed_first,
            )

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
