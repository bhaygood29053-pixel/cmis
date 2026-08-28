import unittest

from liquidity_scout.providers.solana.dexscreener import (
    DexScreenerSolanaProvider,
    DexScreenerSourceError,
)


MINT = "Mint111"


class _Response:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def _get_with(body):
    calls = []

    def get(url, *, headers, timeout):
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        return _Response(body)

    get.calls = calls
    return get


def _pair(pair="PairA", *, chain="solana", token=MINT):
    return {
        "chainId": chain,
        "dexId": "raydium",
        "pairAddress": pair,
        "baseToken": {"address": token, "name": "Example", "symbol": "EX"},
        "quoteToken": {"address": "USDCMint", "name": "USD Coin", "symbol": "USDC"},
        "priceNative": "0.5",
        "priceUsd": "1.25",
        "txns": {"h24": {"buys": 100, "sells": 90}},
        "volume": {"h24": 500000.5},
        "priceChange": {"h24": -2.5},
        "liquidity": {"usd": 1000000, "base": 500000, "quote": 625000},
        "fdv": 10000000,
        "marketCap": 8000000,
        "pairCreatedAt": 1700000000000,
    }


class DexScreenerSolanaProviderTests(unittest.TestCase):
    def test_pair_observation_preserves_scope_without_aggregation(self):
        get = _get_with([_pair()])
        provider = DexScreenerSolanaProvider(get=get)

        result = provider.get_token_pairs(MINT)

        self.assertTrue(result["pairs_available"])
        self.assertEqual(result["chain"], "solana")
        self.assertEqual(result["mint"], MINT)
        self.assertEqual(result["pair_count_observed"], 1)
        self.assertEqual(result["scope"], "pair_scoped_dexscreener_observations")
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["solana_wide_coverage_verified"])
        self.assertFalse(result["aggregate_price_selected"])
        self.assertFalse(result["aggregate_liquidity_calculated"])
        self.assertFalse(result["aggregate_volume_calculated"])

        pair = result["pairs"][0]
        self.assertEqual(pair["pair_address"], "PairA")
        self.assertEqual(pair["dex_id"], "raydium")
        self.assertEqual(pair["requested_mint_role"], "base")
        self.assertEqual(pair["price_subject_address"], MINT)
        self.assertTrue(pair["price_is_for_requested_mint"])
        self.assertEqual(pair["price_usd"], "1.25")
        self.assertEqual(pair["liquidity_usd"], "1000000")
        self.assertEqual(pair["volume"], {"h24": "500000.5"})
        self.assertEqual(pair["transactions"], {"h24": {"buys": 100, "sells": 90}})
        self.assertEqual(pair["price_change"], {"h24": "-2.5"})
        self.assertEqual(pair["fdv"], "10000000")
        self.assertEqual(pair["market_cap"], "8000000")
        self.assertEqual(pair["pair_created_at_ms"], 1700000000000)
        self.assertTrue(get.calls[0]["url"].endswith(f"/token-pairs/v1/solana/{MINT}"))

    def test_collection_time_is_separate_from_pair_creation_time(self):
        ticks = iter([200.0, 201.5])
        provider = DexScreenerSolanaProvider(
            get=_get_with([_pair()]),
            clock=lambda: next(ticks),
        )

        result = provider.get_token_pairs(MINT)

        self.assertEqual(result["collection_started_at_unix"], 200.0)
        self.assertEqual(result["collection_completed_at_unix"], 201.5)
        self.assertTrue(result["collection_time_verified"])
        self.assertEqual(
            result["pairs"][0]["pair_created_at_ms"],
            1700000000000,
        )
        self.assertFalse(result["freshness_verified"])

    def test_quote_side_requested_mint_never_inherits_base_token_price(self):
        record = _pair(token="OtherBaseMint")
        record["quoteToken"] = {"address": MINT, "name": "Requested", "symbol": "REQ"}
        provider = DexScreenerSolanaProvider(get=_get_with([record]))

        result = provider.get_token_pairs(MINT)
        pair = result["pairs"][0]

        self.assertEqual(pair["requested_mint_role"], "quote")
        self.assertEqual(pair["price_subject_address"], "OtherBaseMint")
        self.assertFalse(pair["price_is_for_requested_mint"])
        # The source price is preserved for the base token, but downstream CMIS
        # cannot use it as the requested mint's price.
        self.assertEqual(pair["price_usd"], "1.25")

    def test_empty_pair_list_is_unavailable_not_zero_liquidity(self):
        provider = DexScreenerSolanaProvider(get=_get_with([]))

        result = provider.get_token_pairs(MINT)

        self.assertFalse(result["pairs_available"])
        self.assertEqual(result["pairs"], [])
        self.assertEqual(result["pair_count_observed"], 0)
        self.assertEqual(result["reason"], "dexscreener_pairs_unavailable")
        self.assertNotIn("liquidity", result)

    def test_pair_must_be_solana(self):
        provider = DexScreenerSolanaProvider(get=_get_with([_pair(chain="ethereum")]))

        with self.assertRaisesRegex(DexScreenerSourceError, "chainId mismatch"):
            provider.get_token_pairs(MINT)

    def test_pair_must_contain_requested_mint(self):
        record = _pair(token="OtherMint")
        provider = DexScreenerSolanaProvider(get=_get_with([record]))

        with self.assertRaisesRegex(DexScreenerSourceError, "does not contain requested mint"):
            provider.get_token_pairs(MINT)

    def test_duplicate_pair_addresses_fail_closed(self):
        provider = DexScreenerSolanaProvider(get=_get_with([_pair(), _pair()]))

        with self.assertRaisesRegex(DexScreenerSourceError, "duplicate pair address"):
            provider.get_token_pairs(MINT)

    def test_negative_price_change_is_allowed_but_negative_liquidity_is_rejected(self):
        record = _pair()
        record["priceChange"]["h24"] = -99
        provider = DexScreenerSolanaProvider(get=_get_with([record]))
        result = provider.get_token_pairs(MINT)
        self.assertEqual(result["pairs"][0]["price_change"]["h24"], "-99")

        record = _pair()
        record["liquidity"]["usd"] = -1
        provider = DexScreenerSolanaProvider(get=_get_with([record]))
        with self.assertRaisesRegex(DexScreenerSourceError, "liquidity.usd"):
            provider.get_token_pairs(MINT)

    def test_transaction_counts_must_be_nonnegative_integers(self):
        record = _pair()
        record["txns"]["h24"]["buys"] = 1.5
        provider = DexScreenerSolanaProvider(get=_get_with([record]))

        with self.assertRaisesRegex(DexScreenerSourceError, "buys"):
            provider.get_token_pairs(MINT)

    def test_non_array_response_fails_closed(self):
        provider = DexScreenerSolanaProvider(get=_get_with({"pairs": []}))

        with self.assertRaisesRegex(DexScreenerSourceError, "must be an array"):
            provider.get_token_pairs(MINT)

    def test_transport_error_does_not_echo_url_details(self):
        secret_url = "https://example.invalid/private"

        def failing_get(*args, **kwargs):
            raise RuntimeError(f"failed to reach {secret_url}")

        provider = DexScreenerSolanaProvider(base_url=secret_url, get=failing_get)

        with self.assertRaises(DexScreenerSourceError) as caught:
            provider.get_token_pairs(MINT)

        self.assertIn("RuntimeError", str(caught.exception))
        self.assertNotIn(secret_url, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
