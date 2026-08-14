import unittest

from liquidity_scout.services.market_rankings import (
    find_asset_rank,
    format_top,
    rank_assets,
)


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
    }


def pool(
    address,
    base,
    quote,
    *,
    liquidity,
    volume24h,
    volume1h=0,
    txns1h=0,
    change24=0,
):
    return {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "liquidity": liquidity,
        "volume24h": volume24h,
        "volume1h": volume1h,
        "txns1h": txns1h,
        "priceChange24h": change24,
    }


class MarketRankingsServiceTests(unittest.TestCase):
    def test_volume_ranking_aggregates_all_distinct_lps_per_asset(self):
        agi = token("AGI", "AGI_MINT", "Artificial General Intelligence")
        xnt = token("XNT", "XNT_MINT")
        usdx = token("USDX", "USDX_MINT")
        pools = [
            pool("p1", agi, xnt, liquidity=100, volume24h=20),
            pool("p2", agi, usdx, liquidity=200, volume24h=30),
        ]

        ranked, _ = rank_assets(pools, metric="volume")
        agi_row = next(asset for asset in ranked if asset["mint"] == "AGI_MINT")

        self.assertEqual(agi_row["rank"], 1)
        self.assertEqual(agi_row["volume24"], 50)
        self.assertEqual(agi_row["liquidity"], 300)
        self.assertEqual(agi_row["pool_count"], 2)

    def test_public_ranking_table_uses_lps_column(self):
        agi = token("AGI", "AGI_MINT")
        xnt = token("XNT", "XNT_MINT")
        text = format_top(
            [pool("p1", agi, xnt, liquidity=100, volume24h=20)],
            metric="volume",
            limit=10,
        )

        self.assertIn("#LPs", text)
        self.assertIn("X1.NINJA / XDEX TOP", text)
        self.assertIn("AGI", text)

    def test_trending_prefers_transactions_when_any_1h_txns_exist(self):
        agi = token("AGI", "AGI_MINT")
        xnt = token("XNT", "XNT_MINT")
        dog = token("DOG", "DOG_MINT")
        usdx = token("USDX", "USDX_MINT")
        pools = [
            pool(
                "p1",
                agi,
                xnt,
                liquidity=100,
                volume24h=20,
                volume1h=10,
                txns1h=5,
            ),
            pool(
                "p2",
                dog,
                usdx,
                liquidity=200,
                volume24h=30,
                volume1h=999,
                txns1h=0,
            ),
        ]

        ranked, meta = rank_assets(pools, metric="trending")

        self.assertEqual(meta["trending_basis"], "1h transactions")
        self.assertTrue(ranked)
        self.assertTrue(all(asset["txns1h"] > 0 for asset in ranked))
        self.assertNotIn("DOG_MINT", {asset["mint"] for asset in ranked})

    def test_find_asset_rank_accepts_name_and_reports_universe_size(self):
        agi = token("AGI", "AGI_MINT", "Artificial General Intelligence")
        xnt = token("XNT", "XNT_MINT")
        pools = [pool("p1", agi, xnt, liquidity=100, volume24h=20)]

        found, total, _ = find_asset_rank(
            pools,
            "Artificial General Intelligence",
            metric="volume",
        )

        self.assertIsNotNone(found)
        self.assertEqual(found["mint"], "AGI_MINT")
        self.assertEqual(total, 2)


if __name__ == "__main__":
    unittest.main()
