import unittest

from xdex_rankings import format_top, rank_assets
from liquidity_scout.market.aggregation import aggregate_assets
from liquidity_scout.market.client import fetch_all_pools
from liquidity_scout.market.resolver import (
    AmbiguousAssetError,
    resolve_asset,
    resolve_multiple_assets,
)


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
        "address": mint,
    }


def pool(address, base, quote, liquidity, volume24h=0, price_usd=0):
    return {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "liquidity": liquidity,
        "volume24h": volume24h,
        "priceUsd": price_usd,
    }


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get(self, url, params, headers, timeout):
        self.calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return FakeResponse(self.pages.pop(0))


class MarketCoreTests(unittest.TestCase):
    def setUp(self):
        self.xnt = token("XNT", "MINT_XNT", "Wrapped XNT")
        self.agi = token("AGI", "MINT_AGI", "Artificial General Intelligence")
        self.usdc = token("USDC", "MINT_USDC", "USD Coin")

    def test_resolve_exact_symbol_prefers_deepest_pool(self):
        pools = [
            pool("P1", self.agi, self.xnt, 1000, 300),
            pool("P2", self.agi, self.usdc, 5000, 100),
        ]

        term, matches = resolve_asset("What is AGI doing?", pools)

        self.assertEqual(term.upper(), "AGI")
        self.assertEqual(matches[0][0]["address"], "P2")
        self.assertEqual(len(matches), 2)

    def test_unknown_asset_does_not_fall_back(self):
        pools = [pool("P1", self.agi, self.xnt, 1000, 300)]

        term, matches = resolve_asset("What is TOTALLYUNKNOWNCOIN doing?", pools)

        self.assertIsNone(term)
        self.assertEqual(matches, [])

    def test_multi_asset_resolution_keeps_distinct_mints(self):
        pools = [pool("P1", self.agi, self.xnt, 1000, 300)]

        resolved = resolve_multiple_assets("Compare AGI vs XNT", pools)

        self.assertEqual({term.upper() for term, _ in resolved}, {"AGI", "XNT"})

    def test_shared_symbol_is_rejected_as_ambiguous(self):
        same_one = token("SAME", "MintOne123", "Same One")
        same_two = token("SAME", "MintTwo456", "Same Two")
        pools = [
            pool("P1", same_one, self.xnt, 5000, 100),
            pool("P2", same_two, self.usdc, 10000, 200),
        ]

        with self.assertRaises(AmbiguousAssetError) as ctx:
            resolve_asset("What is SAME doing?", pools)

        self.assertEqual(ctx.exception.term.upper(), "SAME")
        self.assertEqual(set(ctx.exception.asset_keys), {"MintOne123", "MintTwo456"})

    def test_exact_mint_disambiguates_shared_symbol(self):
        same_one = token("SAME", "MintOne123", "Same One")
        same_two = token("SAME", "MintTwo456", "Same Two")
        pools = [
            pool("P1", same_one, self.xnt, 5000, 100),
            pool("P2", same_two, self.usdc, 10000, 200),
        ]

        term, matches = resolve_asset("MintOne123", pools)

        self.assertEqual(term, "MintOne123")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][2]["mint"], "MintOne123")

    def test_multi_asset_resolution_rejects_ambiguous_ticker(self):
        same_one = token("SAME", "MintOne123", "Same One")
        same_two = token("SAME", "MintTwo456", "Same Two")
        pools = [
            pool("P1", same_one, self.xnt, 5000, 100),
            pool("P2", same_two, self.usdc, 10000, 200),
        ]

        with self.assertRaises(AmbiguousAssetError):
            resolve_multiple_assets("Compare SAME vs XNT", pools)

    def test_aggregation_sums_unique_pools_and_selects_deepest_price(self):
        pools = [
            pool("P1", self.agi, self.xnt, 1000, 300, 1.0),
            pool("P2", self.agi, self.usdc, 5000, 700, 1.2),
        ]

        assets = {asset["mint"]: asset for asset in aggregate_assets(pools)}
        agi = assets["MINT_AGI"]

        self.assertEqual(agi["pool_count"], 2)
        self.assertEqual(agi["liquidity"], 6000)
        self.assertEqual(agi["volume24"], 1000)
        self.assertEqual(agi["price"], 1.2)
        self.assertEqual(agi["primary_pool_id"], "P2")

    def test_duplicate_pool_is_not_double_counted(self):
        p1 = pool("P1", self.agi, self.xnt, 1000, 300, 1.0)

        assets = {asset["mint"]: asset for asset in aggregate_assets([p1, dict(p1)])}
        agi = assets["MINT_AGI"]

        self.assertEqual(agi["pool_count"], 1)
        self.assertEqual(agi["liquidity"], 1000)
        self.assertEqual(agi["volume24"], 300)

    def test_same_symbol_different_mints_are_not_merged(self):
        fake_one = token("SAME", "MINT_ONE")
        fake_two = token("SAME", "MINT_TWO")
        pools = [
            pool("P1", fake_one, self.xnt, 1000, 100),
            pool("P2", fake_two, self.usdc, 2000, 200),
        ]

        same_assets = [
            asset for asset in aggregate_assets(pools)
            if asset["symbol"] == "SAME"
        ]

        self.assertEqual(len(same_assets), 2)
        self.assertEqual({a["mint"] for a in same_assets}, {"MINT_ONE", "MINT_TWO"})

    def test_rankings_use_core_aggregation_and_public_lp_count(self):
        duplicate = pool("P1", self.agi, self.xnt, 1000, 300, 1.0)
        pools = [
            duplicate,
            dict(duplicate),
            pool("P2", self.agi, self.usdc, 5000, 700, 1.2),
        ]

        ranked, _meta = rank_assets(pools, metric="liquidity", limit=10)
        agi = next(asset for asset in ranked if asset["mint"] == "MINT_AGI")

        self.assertEqual(agi["pool_count"], 2)
        self.assertEqual(agi["liquidity"], 6000)
        self.assertEqual(agi["volume24"], 1000)

        rendered = format_top(pools, metric="liquidity", limit=10)
        self.assertIn("#LPs", rendered)

    def test_catalog_client_preserves_pagination_and_xnt_reference(self):
        session = FakeSession(
            [
                {
                    "pools": [{"address": "P1"}],
                    "total": 2,
                    "xntPriceUsd": "0.55",
                },
                {
                    "pools": [{"address": "P2"}],
                    "total": 2,
                    "xntPriceUsd": "0.56",
                },
            ]
        )

        pools, xnt_price = fetch_all_pools(
            "test-key",
            session=session,
            page_size=1,
            sleep_seconds=0,
        )

        self.assertEqual([p["address"] for p in pools], ["P1", "P2"])
        self.assertEqual(xnt_price, "0.55")
        self.assertEqual(session.calls[0]["params"], {"limit": 1, "offset": 0})
        self.assertEqual(session.calls[1]["params"], {"limit": 1, "offset": 1})
        self.assertEqual(
            session.calls[0]["headers"],
            {"Authorization": "Bearer test-key"},
        )


if __name__ == "__main__":
    unittest.main()
