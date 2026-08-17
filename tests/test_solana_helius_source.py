import unittest

from liquidity_scout.providers.solana.helius import (
    HeliusDASProvider,
    HeliusNotConfigured,
    HeliusSourceError,
    PRICE_CACHE_MAX_AGE_SECONDS,
    TOKEN_BASE_UNITS,
)


MINT = "Mint111"


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
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return _Response(body)

    post.calls = calls
    return post


class HeliusDASProviderTests(unittest.TestCase):
    def test_api_key_is_required(self):
        with self.assertRaises(HeliusNotConfigured):
            HeliusDASProvider(api_key="")

    def test_get_asset_preserves_indexed_state_and_cached_price_without_freshness_claim(self):
        post = _post_with(
            {
                "jsonrpc": "2.0",
                "id": "1",
                "result": {
                    "last_indexed_slot": 365749093,
                    "id": MINT,
                    "content": {"metadata": {"name": "Example", "symbol": "EX"}},
                    "token_info": {
                        "supply": 42000000,
                        "decimals": 6,
                        "token_program": "TokenProgram111",
                        "mint_authority": None,
                        "freeze_authority": "Freeze111",
                        "price_info": {"price_per_token": 0.5, "currency": "USDC"},
                    },
                    "mint_extensions": {"transfer_fee_config": {}},
                },
            }
        )
        provider = HeliusDASProvider(api_key="secret", post=post)

        result = provider.get_asset(MINT)

        self.assertTrue(result["asset_available"])
        self.assertTrue(result["identity_verified"])
        self.assertEqual(result["last_indexed_slot"], 365749093)
        self.assertEqual(result["indexed_supply_candidate"], 42000000)
        self.assertEqual(result["supply_unit"], TOKEN_BASE_UNITS)
        self.assertTrue(result["supply_semantics_verified"])
        self.assertEqual(result["decimals"], 6)
        self.assertEqual(result["token_program"], "TokenProgram111")
        self.assertIsNone(result["mint_authority"])
        self.assertEqual(result["freeze_authority"], "Freeze111")
        self.assertEqual(result["mint_extension_names"], ["transfer_fee_config"])
        self.assertEqual(result["cached_price_source_value"], "0.5")
        self.assertEqual(result["cached_price_currency"], "USDC")
        self.assertEqual(result["price_cache_max_age_seconds"], PRICE_CACHE_MAX_AGE_SECONDS)
        self.assertFalse(result["price_freshness_verified"])
        self.assertEqual(result["name"], "Example")
        self.assertEqual(result["symbol"], "EX")
        self.assertEqual(post.calls[0]["json"]["method"], "getAsset")
        self.assertEqual(post.calls[0]["json"]["params"]["id"], MINT)

    def test_get_asset_requires_exact_mint_identity(self):
        provider = HeliusDASProvider(
            api_key="secret",
            post=_post_with(
                {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "result": {
                        "last_indexed_slot": 1,
                        "id": "DifferentMint",
                        "token_info": {"supply": 1, "decimals": 0, "token_program": "P"},
                    },
                }
            ),
        )

        with self.assertRaisesRegex(HeliusSourceError, "different asset id"):
            provider.get_asset(MINT)

    def test_helius_not_found_error_becomes_explicit_unavailability(self):
        provider = HeliusDASProvider(
            api_key="secret",
            post=_post_with(
                {"jsonrpc": "2.0", "id": "1", "error": {"code": -32004, "message": "not found"}}
            ),
        )

        result = provider.get_asset(MINT)

        self.assertFalse(result["asset_available"])
        self.assertEqual(result["reason"], "helius_asset_not_found")

    def test_cached_price_does_not_become_fresh_even_when_index_slot_exists(self):
        provider = HeliusDASProvider(
            api_key="secret",
            post=_post_with(
                {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "result": {
                        "last_indexed_slot": 999999,
                        "id": MINT,
                        "token_info": {
                            "supply": 1,
                            "decimals": 0,
                            "token_program": "P",
                            "price_info": {"price_per_token": 123, "currency": "USD"},
                        },
                    },
                }
            ),
        )

        result = provider.get_asset(MINT)

        self.assertEqual(result["last_indexed_slot"], 999999)
        self.assertEqual(result["cached_price_source_value"], "123")
        self.assertFalse(result["price_freshness_verified"])

    def test_token_accounts_total_is_not_holder_count(self):
        post = _post_with(
            {
                "last_indexed_slot": 365750752,
                "total": 2,
                "limit": 100,
                "cursor": "next",
                "token_accounts": [
                    {"address": "AccountA", "mint": MINT, "owner": "OwnerA", "amount": 1000},
                    {"address": "AccountB", "mint": MINT, "owner": "OwnerA", "amount": 500},
                ],
            }
        )
        provider = HeliusDASProvider(api_key="secret", post=post)

        result = provider.get_token_accounts_for_mint(MINT)

        self.assertTrue(result["accounts_available"])
        self.assertEqual(result["last_indexed_slot"], 365750752)
        self.assertEqual(result["token_account_count_candidate"], 2)
        self.assertEqual(result["counted_entity"], "token_accounts")
        self.assertFalse(result["holder_count_semantics_verified"])
        self.assertEqual(result["accounts"][0]["owner"], "OwnerA")
        self.assertEqual(result["accounts"][1]["owner"], "OwnerA")
        self.assertEqual(result["cursor"], "next")
        self.assertEqual(post.calls[0]["json"]["params"], {"mint": MINT, "limit": 100})

    def test_token_account_mint_mismatch_fails_closed(self):
        provider = HeliusDASProvider(
            api_key="secret",
            post=_post_with(
                {
                    "last_indexed_slot": 1,
                    "total": 1,
                    "token_accounts": [
                        {"address": "A", "mint": "OtherMint", "owner": "O", "amount": 1}
                    ],
                }
            ),
        )

        with self.assertRaisesRegex(HeliusSourceError, "mint mismatch"):
            provider.get_token_accounts_for_mint(MINT)

    def test_token_account_total_rejects_float(self):
        provider = HeliusDASProvider(
            api_key="secret",
            post=_post_with({"last_indexed_slot": 1, "total": 1.5, "token_accounts": []}),
        )

        with self.assertRaisesRegex(HeliusSourceError, "token account total"):
            provider.get_token_accounts_for_mint(MINT)

    def test_provider_errors_and_transport_errors_do_not_echo_api_key(self):
        provider = HeliusDASProvider(
            api_key="super-secret",
            post=_post_with(
                {"jsonrpc": "2.0", "id": "1", "error": {"code": -32001, "message": "super-secret invalid"}}
            ),
        )
        with self.assertRaises(HeliusSourceError) as caught:
            provider.get_asset(MINT)
        self.assertNotIn("super-secret", str(caught.exception))
        self.assertIn("-32001", str(caught.exception))

        def failing_post(*args, **kwargs):
            raise RuntimeError("super-secret transport")

        provider = HeliusDASProvider(api_key="super-secret", post=failing_post)
        with self.assertRaises(HeliusSourceError) as caught:
            provider.get_asset(MINT)
        self.assertNotIn("super-secret", str(caught.exception))
        self.assertIn("RuntimeError", str(caught.exception))

    def test_token_2022_extension_names_are_preserved_without_interpretation(self):
        provider = HeliusDASProvider(
            api_key="secret",
            post=_post_with(
                {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "result": {
                        "last_indexed_slot": 1,
                        "id": MINT,
                        "token_info": {
                            "supply": 1,
                            "decimals": 0,
                            "token_program": "Token2022Program",
                        },
                        "mint_extensions": {
                            "transfer_fee_config": {},
                            "metadata_pointer": {},
                        },
                    },
                }
            ),
        )

        result = provider.get_asset(MINT)

        self.assertEqual(
            result["mint_extension_names"],
            ["metadata_pointer", "transfer_fee_config"],
        )
        self.assertEqual(result["token_program"], "Token2022Program")


if __name__ == "__main__":
    unittest.main()
