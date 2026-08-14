import unittest

from liquidity_scout.market.aggregation import aggregate_assets
from liquidity_scout.services.market_rankings import (
    find_asset_rank,
    format_top,
    rank_assets,
)


def token(symbol, mint):
    return {"symbol": symbol, "name": symbol, "mint": mint}


def pool(address, base, quote, **metrics):
    row = {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
    }
    row.update(metrics)
    return row


class MarketRankingsUncertaintyTests(unittest.TestCase):
    def test_partial_sum_keeps_lower_bound_and_marks_incomplete(self):
        agi = token("AGI", "AGI_MINT")
        xnt = token("XNT", "XNT_MINT")
        usdx = token("USDX", "USDX_MINT")
        assets = aggregate_assets([
            pool("p1", agi, xnt, liquidity=100, volume24h=20),
            pool("p2", agi, usdx, liquidity=200),
        ])
        row = next(asset for asset in assets if asset["mint"] == "AGI_MINT")

        self.assertEqual(row["volume24"], 20)
        self.assertFalse(row["completeness"]["volume24"])
        self.assertEqual(row["liquidity"], 300)
        self.assertTrue(row["completeness"]["liquidity"])

    def test_completely_missing_metric_stays_none_not_zero(self):
        agi = token("AGI", "AGI_MINT")
        xnt = token("XNT", "XNT_MINT")
        row = next(
            asset
            for asset in aggregate_assets([
                pool("p1", agi, xnt, liquidity=100),
            ])
            if asset["mint"] == "AGI_MINT"
        )

        self.assertIsNone(row["volume24"])
        self.assertFalse(row["completeness"]["volume24"])

    def test_verified_zero_remains_distinct_from_missing(self):
        agi = token("AGI", "AGI_MINT")
        xnt = token("XNT", "XNT_MINT")
        row = next(
            asset
            for asset in aggregate_assets([
                pool("p1", agi, xnt, liquidity=100, volume24h=0),
            ])
            if asset["mint"] == "AGI_MINT"
        )

        self.assertEqual(row["volume24"], 0)
        self.assertTrue(row["completeness"]["volume24"])

    def test_holder_disagreement_is_unverified_not_maximum(self):
        agi = token("AGI", "AGI_MINT")
        xnt = token("XNT", "XNT_MINT")
        usdx = token("USDX", "USDX_MINT")
        row = next(
            asset
            for asset in aggregate_assets([
                pool("p1", agi, xnt, liquidity=100, volume24h=20, holders=1000),
                pool("p2", agi, usdx, liquidity=200, volume24h=30, holders=1200),
            ])
            if asset["mint"] == "AGI_MINT"
        )

        self.assertIsNone(row["holders"])
        self.assertEqual(row["holder_observations"], [1000, 1200])
        self.assertFalse(row["completeness"]["holders"])

    def test_incomplete_metric_is_excluded_from_exact_rank(self):
        uncertain = token("UNC", "UNC_MINT")
        exact = token("EXACT", "EXACT_MINT")
        q1 = token("Q1", "Q1_MINT")
        q2 = token("Q2", "Q2_MINT")
        q3 = token("Q3", "Q3_MINT")
        pools = [
            pool("u1", uncertain, q1, liquidity=100, volume24h=1000),
            pool("u2", uncertain, q2, liquidity=100),
            pool("e1", exact, q3, liquidity=100, volume24h=100),
        ]

        ranked, meta = rank_assets(pools, metric="volume")
        ranked_mints = {asset["mint"] for asset in ranked}

        self.assertNotIn("UNC_MINT", ranked_mints)
        self.assertIn("EXACT_MINT", ranked_mints)
        self.assertIn(
            "UNC_MINT",
            {asset["mint"] for asset in meta["unranked_incomplete"]},
        )

    def test_find_asset_rank_reports_incomplete_status(self):
        uncertain = token("UNC", "UNC_MINT")
        q1 = token("Q1", "Q1_MINT")
        q2 = token("Q2", "Q2_MINT")
        pools = [
            pool("u1", uncertain, q1, liquidity=100, volume24h=1000),
            pool("u2", uncertain, q2, liquidity=100),
        ]

        found, _total, meta = find_asset_rank(pools, "UNC", metric="volume")

        self.assertIsNone(found)
        self.assertEqual(meta["query_status"], "incomplete")
        self.assertEqual(meta["query_asset"]["mint"], "UNC_MINT")
        self.assertEqual(meta["query_asset"]["value"], 1000)

    def test_public_output_discloses_exclusions_and_partial_secondary_liquidity(self):
        agi = token("AGI", "AGI_MINT")
        xnt = token("XNT", "XNT_MINT")
        usdx = token("USDX", "USDX_MINT")
        text = format_top([
            pool("p1", agi, xnt, liquidity=100, volume24h=20),
            pool("p2", agi, usdx, volume24h=30),
        ], metric="volume", limit=10)

        self.assertIn("AGI", text)
        self.assertIn(">=$100.00", text)

        incomplete_text = format_top([
            pool("p3", agi, xnt, liquidity=100),
        ], metric="volume", limit=10)
        self.assertIn("excluded from the exact ranking", incomplete_text)


if __name__ == "__main__":
    unittest.main()
