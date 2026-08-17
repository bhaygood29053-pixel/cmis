import unittest

from liquidity_scout.cmis.solana_market_gateway import _pair_observations


class CMISSolanaMarketPairSubjectTests(unittest.TestCase):
    def test_quote_side_pair_never_exposes_generic_requested_asset_price(self):
        requested_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        base_mint = "So11111111111111111111111111111111111111112"
        observations = _pair_observations(
            {
                "pairs": [
                    {
                        "pair_address": "pair-1",
                        "dex_id": "testdex",
                        "requested_mint_role": "quote",
                        "price_subject_address": base_mint,
                        "price_is_for_requested_mint": False,
                        "price_usd": "9.5",
                        "liquidity_usd": "1000",
                        "volume": {"h24": "50"},
                        "transactions": {"h24": {"buys": 2, "sells": 3}},
                        "price_change": {"h24": "1.2"},
                        "pair_created_at_ms": 1,
                    }
                ],
                "mint": requested_mint,
            }
        )

        self.assertEqual(len(observations), 1)
        observation = observations[0]
        self.assertEqual(observation["requested_mint_role"], "quote")
        self.assertEqual(observation["price_subject_address"], base_mint)
        self.assertFalse(observation["price_is_for_requested_mint"])
        self.assertEqual(observation["base_token_price_usd"], "9.5")
        self.assertNotIn("price_usd", observation)


if __name__ == "__main__":
    unittest.main()
