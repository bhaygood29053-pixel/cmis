import unittest

from liquidity_scout.providers.solana.jupiter import (
    JupiterNotConfigured,
    JupiterSourceError,
    JupiterSourceProvider,
)


MINT = "Mint111"
TEST_KEY = "test-key"


class _Response:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def _get_with(body):
    calls = []

    def get(url, *, params, headers, timeout):
        calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return _Response(body)

    get.calls = calls
    return get


def _provider(body):
    get = _get_with(body)
    return JupiterSourceProvider(api_key=TEST_KEY, get=get), get


class JupiterSourceProviderTests(unittest.TestCase):
    def test_api_key_is_required_by_current_jupiter_contract(self):
        with self.assertRaises(JupiterNotConfigured):
            JupiterSourceProvider(api_key="")

    def test_price_v3_preserves_price_and_block_without_claiming_freshness(self):
        provider, get = _provider(
            {
                MINT: {
                    "createdAt": "2025-01-02T03:04:05Z",
                    "liquidity": 123456.78,
                    "usdPrice": 0.125,
                    "blockId": 987654,
                    "decimals": 6,
                    "priceChange24h": -1.25,
                }
            }
        )

        result = provider.get_price(MINT)

        self.assertTrue(result["price_available"])
        self.assertEqual(result["chain"], "solana")
        self.assertEqual(result["source"], "jupiter_price_v3")
        self.assertEqual(result["mint"], MINT)
        self.assertEqual(result["usd_price"], "0.125")
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(result["block_id"], 987654)
        self.assertEqual(result["decimals"], 6)
        self.assertEqual(result["token_created_at"], "2025-01-02T03:04:05Z")
        self.assertEqual(result["liquidity_usd_source_value"], "123456.78")
        self.assertEqual(result["price_change_24h_percent_source_value"], "-1.25")
        self.assertIsNone(result["observed_at"])
        self.assertFalse(result["freshness_verified"])
        self.assertEqual(get.calls[0]["params"], {"ids": MINT})
        self.assertEqual(get.calls[0]["headers"]["x-api-key"], TEST_KEY)

    def test_missing_price_key_is_unavailable_not_zero(self):
        provider, _ = _provider({})

        result = provider.get_price(MINT)

        self.assertFalse(result["price_available"])
        self.assertEqual(result["reason"], "jupiter_price_unavailable")
        self.assertNotIn("usd_price", result)
        self.assertFalse(result["freshness_verified"])

    def test_invalid_zero_or_negative_price_fails_closed(self):
        for value in (0, -1):
            provider, _ = _provider(
                {
                    MINT: {
                        "usdPrice": value,
                        "blockId": 1,
                        "decimals": 6,
                    }
                }
            )
            with self.subTest(value=value):
                with self.assertRaises(JupiterSourceError):
                    provider.get_price(MINT)

    def test_price_requires_integer_block_and_u8_decimals(self):
        provider, _ = _provider(
            {
                MINT: {
                    "usdPrice": 1,
                    "blockId": 1.5,
                    "decimals": 6,
                }
            }
        )
        with self.assertRaisesRegex(JupiterSourceError, "blockId"):
            provider.get_price(MINT)

        provider, _ = _provider(
            {
                MINT: {
                    "usdPrice": 1,
                    "blockId": 1,
                    "decimals": 256,
                }
            }
        )
        with self.assertRaisesRegex(JupiterSourceError, "u8"):
            provider.get_price(MINT)

    def test_configured_api_key_is_sent_but_never_returned(self):
        get = _get_with({})
        provider = JupiterSourceProvider(api_key="secret-key", get=get)

        result = provider.get_price(MINT)

        self.assertEqual(get.calls[0]["headers"]["x-api-key"], "secret-key")
        self.assertNotIn("secret-key", str(result))

    def test_transport_error_does_not_echo_api_key_or_url(self):
        secret_key = "secret-key"
        secret_url = "https://api.example.invalid/private"

        def failing_get(*args, **kwargs):
            raise RuntimeError(f"failed {secret_url} with {secret_key}")

        provider = JupiterSourceProvider(
            base_url=secret_url,
            api_key=secret_key,
            get=failing_get,
        )

        with self.assertRaises(JupiterSourceError) as caught:
            provider.get_price(MINT)

        message = str(caught.exception)
        self.assertIn("RuntimeError", message)
        self.assertNotIn(secret_key, message)
        self.assertNotIn(secret_url, message)

    def test_exact_mint_token_record_preserves_provider_opinions(self):
        provider, get = _provider(
            [
                {
                    "id": MINT,
                    "name": "Example",
                    "symbol": "EX",
                    "decimals": 6,
                    "isVerified": True,
                    "organicScore": 98.08,
                    "organicScoreLabel": "high",
                    "usdPrice": 0.5,
                    "mcap": 5000000,
                    "holderCount": 12345,
                    "liquidity": 900000,
                    "tags": ["verified", "community", "verified"],
                }
            ]
        )

        result = provider.get_token_by_mint(MINT)

        self.assertTrue(result["token_available"])
        self.assertTrue(result["identity_verified"])
        self.assertEqual(result["mint"], MINT)
        self.assertEqual(result["name"], "Example")
        self.assertEqual(result["symbol"], "EX")
        self.assertEqual(result["decimals"], 6)
        self.assertTrue(result["provider_is_verified"])
        self.assertEqual(result["provider_organic_score"], "98.08")
        self.assertEqual(result["provider_organic_score_label"], "high")
        self.assertEqual(result["indexed_holder_count_candidate"], 12345)
        self.assertFalse(result["holder_count_semantics_verified"])
        self.assertEqual(result["usd_price_source_value"], "0.5")
        self.assertEqual(result["liquidity_usd_source_value"], "900000")
        self.assertEqual(result["market_cap_usd_source_value"], "5000000")
        self.assertEqual(result["tags"], ["verified", "community"])
        self.assertTrue(result["provider_opinion_only"])
        self.assertEqual(get.calls[0]["params"], {"query": MINT})
        self.assertEqual(get.calls[0]["headers"]["x-api-key"], TEST_KEY)

    def test_token_search_ignores_symbol_match_and_requires_exact_mint(self):
        provider, _ = _provider(
            [
                {
                    "id": "DifferentMint",
                    "name": "Looks similar",
                    "symbol": "MINT111",
                    "decimals": 6,
                }
            ]
        )

        result = provider.get_token_by_mint(MINT)

        self.assertFalse(result["token_available"])
        self.assertFalse(result["identity_verified"])
        self.assertEqual(result["reason"], "jupiter_token_not_found")

    def test_duplicate_exact_mint_records_fail_closed(self):
        record = {"id": MINT, "decimals": 6}
        provider, _ = _provider([record, dict(record)])

        with self.assertRaisesRegex(JupiterSourceError, "duplicate exact mint"):
            provider.get_token_by_mint(MINT)

    def test_provider_verified_field_must_be_boolean(self):
        provider, _ = _provider([{"id": MINT, "decimals": 6, "isVerified": "yes"}])

        with self.assertRaisesRegex(JupiterSourceError, "isVerified"):
            provider.get_token_by_mint(MINT)

    def test_holder_count_must_be_nonnegative_integer(self):
        provider, _ = _provider([{"id": MINT, "decimals": 6, "holderCount": 1.5}])

        with self.assertRaisesRegex(JupiterSourceError, "holderCount"):
            provider.get_token_by_mint(MINT)


if __name__ == "__main__":
    unittest.main()
