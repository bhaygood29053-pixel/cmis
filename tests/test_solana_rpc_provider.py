import unittest

from liquidity_scout.providers.registry import build_default_chain_provider_registry
from liquidity_scout.providers.solana.rpc import (
    SolanaRPCError,
    SolanaRPCNotFound,
    SolanaRPCProvider,
)


class _Response:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def _post_with(body):
    calls = []

    def post(url, *, json, headers, timeout):
        calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return _Response(body)

    post.calls = calls
    return post


class SolanaRPCProviderTests(unittest.TestCase):
    def test_token_supply_preserves_raw_amount_decimals_and_slot(self):
        post = _post_with(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "context": {"slot": 123},
                    "value": {
                        "amount": "42000000",
                        "decimals": 6,
                        "uiAmount": 42.0,
                        "uiAmountString": "42",
                    },
                },
            }
        )
        provider = SolanaRPCProvider(
            "https://rpc.example.invalid",
            post=post,
        )

        result = provider.get_token_supply("Mint111")

        self.assertEqual(result["chain"], "solana")
        self.assertEqual(result["source"], "solana_rpc")
        self.assertEqual(result["method"], "getTokenSupply")
        self.assertEqual(result["mint"], "Mint111")
        self.assertEqual(result["context_slot"], 123)
        self.assertEqual(result["amount_raw"], "42000000")
        self.assertEqual(result["decimals"], 6)
        self.assertEqual(result["ui_amount_string"], "42")
        self.assertTrue(result["supply_verified"])
        self.assertEqual(result["coverage"], "total_token_supply")
        self.assertEqual(post.calls[0]["json"]["method"], "getTokenSupply")
        self.assertEqual(post.calls[0]["json"]["params"][0], "Mint111")

    def test_parsed_mint_account_preserves_program_and_authorities(self):
        post = _post_with(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "context": {"slot": 456},
                    "value": {
                        "owner": "TokenProgram111",
                        "data": {
                            "program": "spl-token",
                            "parsed": {
                                "type": "mint",
                                "info": {
                                    "supply": "9000000",
                                    "decimals": 6,
                                    "mintAuthority": "Authority111",
                                    "freezeAuthority": None,
                                    "isInitialized": True,
                                },
                            },
                        },
                    },
                },
            }
        )
        provider = SolanaRPCProvider("https://rpc.example.invalid", post=post)

        result = provider.get_mint_account("Mint111")

        self.assertEqual(result["context_slot"], 456)
        self.assertEqual(result["owner_program_id"], "TokenProgram111")
        self.assertEqual(result["parsed_program"], "spl-token")
        self.assertTrue(result["program_identity_verified"])
        self.assertEqual(result["amount_raw"], "9000000")
        self.assertEqual(result["decimals"], 6)
        self.assertEqual(result["mint_authority"], "Authority111")
        self.assertIsNone(result["freeze_authority"])
        self.assertTrue(result["is_initialized"])
        self.assertEqual(result["extension_names"], [])
        self.assertTrue(result["mint_state_verified"])

    def test_token_2022_parsed_label_and_extension_names_are_preserved_not_reinterpreted(self):
        post = _post_with(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "context": {"slot": 789},
                    "value": {
                        "owner": "Token2022Program111",
                        "data": {
                            "program": "spl-token-2022",
                            "parsed": {
                                "type": "mint",
                                "info": {
                                    "supply": "1",
                                    "decimals": 0,
                                    "mintAuthority": None,
                                    "freezeAuthority": None,
                                    "isInitialized": True,
                                    "extensions": [
                                        {"extension": "transferFeeConfig", "state": {}},
                                        {"type": "metadataPointer", "state": {}},
                                    ],
                                },
                            },
                        },
                    },
                },
            }
        )
        provider = SolanaRPCProvider("https://rpc.example.invalid", post=post)

        result = provider.get_mint_account("Mint2022")

        self.assertEqual(result["parsed_program"], "spl-token-2022")
        self.assertEqual(
            result["extension_names"],
            ["transferFeeConfig", "metadataPointer"],
        )

    def test_missing_mint_account_fails_with_explicit_not_found(self):
        provider = SolanaRPCProvider(
            "https://rpc.example.invalid",
            post=_post_with(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"context": {"slot": 1}, "value": None},
                }
            ),
        )

        with self.assertRaises(SolanaRPCNotFound):
            provider.get_mint_account("MissingMint")

    def test_largest_accounts_are_explicitly_not_holder_count(self):
        post = _post_with(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "context": {"slot": 999},
                    "value": [
                        {
                            "address": "AccountA",
                            "amount": "1000",
                            "decimals": 6,
                            "uiAmount": 0.001,
                            "uiAmountString": "0.001",
                        },
                        {
                            "address": "AccountB",
                            "amount": "500",
                            "decimals": 6,
                            "uiAmount": 0.0005,
                            "uiAmountString": "0.0005",
                        },
                    ],
                },
            }
        )
        provider = SolanaRPCProvider("https://rpc.example.invalid", post=post)

        result = provider.get_token_largest_accounts("Mint111")

        self.assertEqual(result["account_count_observed"], 2)
        self.assertEqual(result["counted_entity"], "token_accounts")
        self.assertEqual(result["coverage"], "largest_token_accounts_only")
        self.assertFalse(result["total_holder_count_verified"])
        self.assertIn("does not establish total holder", result["warning"])

    def test_json_rpc_error_does_not_echo_provider_error_message_or_rpc_url(self):
        secret_url = "https://rpc.example.invalid/?api-key=super-secret"
        provider = SolanaRPCProvider(
            secret_url,
            post=_post_with(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {
                        "code": -32000,
                        "message": "super-secret provider detail",
                    },
                }
            ),
        )

        with self.assertRaises(SolanaRPCError) as caught:
            provider.get_token_supply("Mint111")

        message = str(caught.exception)
        self.assertIn("-32000", message)
        self.assertNotIn("super-secret", message)
        self.assertNotIn(secret_url, message)

    def test_transport_error_does_not_echo_keyed_rpc_url(self):
        secret_url = "https://rpc.example.invalid/?api-key=super-secret"

        def failing_post(*args, **kwargs):
            raise RuntimeError(f"failed to reach {secret_url}")

        provider = SolanaRPCProvider(secret_url, post=failing_post)

        with self.assertRaises(SolanaRPCError) as caught:
            provider.get_token_supply("Mint111")

        message = str(caught.exception)
        self.assertIn("RuntimeError", message)
        self.assertNotIn("super-secret", message)
        self.assertNotIn(secret_url, message)

    def test_registry_can_expose_only_rpc_component_without_enabling_market(self):
        rpc = SolanaRPCProvider(
            "https://rpc.example.invalid",
            post=_post_with(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"context": {"slot": 1}, "value": {}},
                }
            ),
        )
        registry = build_default_chain_provider_registry(
            x1_market_provider=object(),
            x1_supply_provider=object(),
            solana_rpc_provider=rpc,
        )

        rpc_result = registry.resolve(chain="solana", component="rpc")
        market_result = registry.resolve(chain="solana", component="market")

        self.assertEqual(rpc_result.status, "selected")
        self.assertIs(rpc_result.provider, rpc)
        self.assertEqual(market_result.status, "unavailable")
        self.assertIsNone(market_result.provider)


if __name__ == "__main__":
    unittest.main()
