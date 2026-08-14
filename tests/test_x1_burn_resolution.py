import unittest

from liquidity_scout.market import AmbiguousAssetError
from x1_burn_scan import resolve_token


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
        "address": mint,
    }


def pool(address, base, quote, liquidity):
    return {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "liquidity": liquidity,
        "volume24h": 0,
    }


class FakeCatalog:
    def __init__(self, pools):
        self.pools = pools


class BurnScannerResolutionTests(unittest.TestCase):
    def setUp(self):
        self.xnt = token(
            "XNT",
            "MintXNT1111111111111111111111111111111",
            "Wrapped XNT",
        )
        self.agi = token(
            "AGI",
            "MintAGI1111111111111111111111111111111",
            "Artificial General Intelligence",
        )

    def test_direct_mint_bypasses_catalog(self):
        mint = "11111111111111111111111111111111"

        symbol, resolved_mint = resolve_token(mint)

        self.assertEqual(symbol, "11111111...")
        self.assertEqual(resolved_mint, mint)

    def test_symbol_resolves_through_market_core(self):
        catalog = FakeCatalog([
            pool("P1", self.agi, self.xnt, 5000),
        ])

        symbol, mint = resolve_token("AGI", catalog=catalog)

        self.assertEqual(symbol, "AGI")
        self.assertEqual(mint, self.agi["mint"])

    def test_unknown_token_fails_closed(self):
        catalog = FakeCatalog([
            pool("P1", self.agi, self.xnt, 5000),
        ])

        with self.assertRaises(RuntimeError):
            resolve_token("TOTALLYUNKNOWNCOIN", catalog=catalog)

    def test_ambiguous_symbol_fails_closed(self):
        same_one = token(
            "SAME",
            "MintOne111111111111111111111111111111",
            "Same One",
        )
        same_two = token(
            "SAME",
            "MintTwo111111111111111111111111111111",
            "Same Two",
        )
        catalog = FakeCatalog([
            pool("P1", same_one, self.xnt, 5000),
            pool("P2", same_two, self.xnt, 9000),
        ])

        with self.assertRaises(AmbiguousAssetError):
            resolve_token("SAME", catalog=catalog)

    def test_empty_identifier_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_token("   ", catalog=FakeCatalog([]))


if __name__ == "__main__":
    unittest.main()
