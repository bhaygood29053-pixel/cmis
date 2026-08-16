import os
import time
import unittest
from collections.abc import Mapping

from liquidity_scout.providers.x1 import X1Provider, XDEXReadOnlyProvider


RUN_LIVE = os.getenv("RUN_XDEX_LIVE_TESTS") == "1"
_NATIVE_XNT_SYMBOLS = {"XNT", "WXNT"}


def _text(value):
    text = str(value or "").strip()
    return text or None


def _token_address(token):
    """Return the pool token's public address, preferring explicit address over mint."""
    if not isinstance(token, Mapping):
        return None
    return _text(token.get("address") or token.get("mint"))


def _is_native_xnt_side(token):
    if not isinstance(token, Mapping):
        return False
    symbol = (_text(token.get("symbol")) or "").upper()
    name = (_text(token.get("name")) or "").casefold()
    return symbol in _NATIVE_XNT_SYMBOLS or "wrapped xnt" in name


def select_non_native_live_pool_pair(pools):
    """Select one exact catalog pool without using XNT/WXNT as either side."""

    for pool in pools:
        if not isinstance(pool, Mapping):
            continue
        base = pool.get("baseToken")
        quote = pool.get("quoteToken")
        if not isinstance(base, Mapping) or not isinstance(quote, Mapping):
            continue
        if _is_native_xnt_side(base) or _is_native_xnt_side(quote):
            continue

        base_address = _token_address(base)
        quote_address = _token_address(quote)
        if not base_address or not quote_address or base_address == quote_address:
            continue

        return {
            "pool_address": _text(pool.get("address")),
            "base_address": base_address,
            "quote_address": quote_address,
            "base_symbol": _text(base.get("symbol")),
            "quote_symbol": _text(quote.get("symbol")),
        }
    return None


class XDEXLivePairSelectionTests(unittest.TestCase):
    def test_selects_exact_non_native_pool_pair(self):
        pools = [
            {
                "address": "P_XNT",
                "baseToken": {"symbol": "AGI", "mint": "AGI_MINT"},
                "quoteToken": {
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "mint": "XNT_ID",
                },
            },
            {
                "address": "P_USDC_AGI",
                "baseToken": {"symbol": "USDC", "mint": "USDC_MINT"},
                "quoteToken": {"symbol": "AGI", "mint": "AGI_MINT"},
            },
        ]

        pair = select_non_native_live_pool_pair(pools)

        self.assertEqual(
            pair,
            {
                "pool_address": "P_USDC_AGI",
                "base_address": "USDC_MINT",
                "quote_address": "AGI_MINT",
                "base_symbol": "USDC",
                "quote_symbol": "AGI",
            },
        )

    def test_prefers_explicit_public_address_over_mint_metadata(self):
        pools = [
            {
                "address": "P_ADDRESS_FIRST",
                "baseToken": {
                    "symbol": "AAA",
                    "address": "AAA_PUBLIC_ADDRESS",
                    "mint": "AAA_MINT_METADATA",
                },
                "quoteToken": {
                    "symbol": "BBB",
                    "address": "BBB_PUBLIC_ADDRESS",
                    "mint": "BBB_MINT_METADATA",
                },
            }
        ]

        pair = select_non_native_live_pool_pair(pools)

        self.assertEqual(pair["base_address"], "AAA_PUBLIC_ADDRESS")
        self.assertEqual(pair["quote_address"], "BBB_PUBLIC_ADDRESS")

    def test_returns_none_when_only_xnt_pairs_exist(self):
        pools = [
            {
                "address": "P_ONLY",
                "baseToken": {"symbol": "USDC", "mint": "USDC_MINT"},
                "quoteToken": {"symbol": "XNT", "mint": "XNT_ID"},
            }
        ]

        self.assertIsNone(select_non_native_live_pool_pair(pools))


@unittest.skipUnless(
    RUN_LIVE,
    "Set RUN_XDEX_LIVE_TESTS=1 to probe the live read-only XDEX contract.",
)
class XDEXLiveContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        market_provider = X1Provider()
        try:
            market_provider.refresh()
        except Exception as exc:
            raise unittest.SkipTest(
                f"Cannot load the live X1 pool catalog for XDEX contract probing: {exc}"
            ) from exc

        cls.live_pair = select_non_native_live_pool_pair(market_provider.pools)
        if cls.live_pair is None:
            raise unittest.SkipTest(
                "No current X1 catalog pool has two non-XNT token sides; "
                "native-XNT adapter behavior remains a separate verification task."
            )

        print(
            "[XDEX live probe] pool="
            f"{cls.live_pair['pool_address']} pair="
            f"{cls.live_pair['base_symbol'] or cls.live_pair['base_address']} -> "
            f"{cls.live_pair['quote_symbol'] or cls.live_pair['quote_address']}"
        )

    def setUp(self):
        self.provider = XDEXReadOnlyProvider(timeout=20)

    def test_live_token_price_returns_mapping(self):
        data = self.provider.token_price(self.live_pair["base_address"])

        self.assertIsInstance(data, dict)
        self.assertTrue(data)

    def test_live_history_exposes_candidate_timestamp_and_price_fields(self):
        time_to = int(time.time())
        time_from = time_to - (7 * 24 * 60 * 60)
        points = self.provider.price_history(
            self.live_pair["base_address"],
            self.live_pair["quote_address"],
            time_from=time_from,
            time_to=time_to,
        )

        self.assertIsInstance(points, list)
        self.assertTrue(
            points,
            "XDEX returned no history points; cannot verify history field semantics.",
        )
        for point in points[:10]:
            self.assertTrue(
                "timestamp" in point or "time" in point,
                f"history point lacks timestamp/time: {point}",
            )
            self.assertIn(
                "price",
                point,
                f"history point lacks price: {point}",
            )

    def test_live_quote_exposes_candidate_read_only_fields(self):
        data = self.provider.swap_quote(
            self.live_pair["base_address"],
            self.live_pair["quote_address"],
            1,
            is_exact_amount_in=True,
        )

        self.assertIn("outputAmount", data)
        self.assertIn("rate", data)
        if "priceImpactPct" in data:
            self.assertIsNotNone(data["priceImpactPct"])


if __name__ == "__main__":
    unittest.main()
