import unittest

from snapshot_xdex_metrics import build_snapshot_rows


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
        "address": mint,
    }


def pool(address, base, quote, liquidity, volume24h=0, price_usd=0, holders=0):
    return {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "liquidity": liquidity,
        "volume24h": volume24h,
        "priceUsd": price_usd,
        "holders": holders,
    }


class SnapshotMetricsTests(unittest.TestCase):
    def setUp(self):
        self.xnt = token("XNT", "MINT_XNT", "Wrapped XNT")
        self.agi = token("AGI", "MINT_AGI", "Artificial General Intelligence")
        self.usdc = token("USDC", "MINT_USDC", "USD Coin")

    def test_snapshot_rows_reuse_core_multi_lp_aggregation(self):
        duplicate = pool(
            "P1",
            self.agi,
            self.xnt,
            liquidity=1000,
            volume24h=300,
            price_usd=1.0,
            holders=100,
        )
        pools = [
            duplicate,
            dict(duplicate),
            pool(
                "P2",
                self.agi,
                self.usdc,
                liquidity=5000,
                volume24h=700,
                price_usd=1.2,
                holders=125,
            ),
        ]

        rows = {row["mint"]: row for row in build_snapshot_rows(pools)}
        agi = rows["MINT_AGI"]

        self.assertEqual(agi["pool_count"], 2)
        self.assertEqual(agi["liquidity"], 6000)
        self.assertEqual(agi["volume24"], 1000)
        self.assertEqual(agi["holders"], 125)
        self.assertEqual(agi["price"], 1.2)

    def test_xnt_reference_price_overrides_pool_price(self):
        pools = [
            pool(
                "P1",
                self.xnt,
                self.usdc,
                liquidity=5000,
                volume24h=700,
                price_usd=0.50,
            )
        ]

        rows = {row["mint"]: row for row in build_snapshot_rows(
            pools,
            xnt_price_usd="0.55",
        )}

        self.assertEqual(rows["MINT_XNT"]["price"], 0.55)

    def test_invalid_xnt_reference_preserves_deepest_pool_price(self):
        pools = [
            pool(
                "P1",
                self.xnt,
                self.usdc,
                liquidity=5000,
                volume24h=700,
                price_usd=0.50,
            )
        ]

        rows = {row["mint"]: row for row in build_snapshot_rows(
            pools,
            xnt_price_usd="not-a-number",
        )}

        self.assertEqual(rows["MINT_XNT"]["price"], 0.50)


if __name__ == "__main__":
    unittest.main()
