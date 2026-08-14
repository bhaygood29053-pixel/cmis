import unittest

from liquidity_scout.services.market_comparison import format_market_comparison


def usd(value):
    return f"${value:,.0f}" if abs(value) >= 1 else f"${value:.4f}".rstrip("0").rstrip(".")


def legacy_snap(symbol, *, liquidity, volume, change, price="$1", safety="A (90/100)"):
    return {
        "title": symbol,
        "symbol": symbol,
        "token_address": f"{symbol}_MINT",
        "price": price,
        "liquidity": liquidity,
        "vol24": volume,
        "change24": change,
        "safety": safety,
    }


def structured_snap(
    symbol,
    *,
    liquidity,
    liquidity_complete,
    volume,
    volume_complete,
    change,
):
    snap = legacy_snap(
        symbol,
        liquidity=0 if liquidity is None else liquidity,
        volume=0 if volume is None else volume,
        change=0 if change is None else change,
    )
    snap["_market_report"] = {
        "symbol": symbol,
        "name": symbol,
        "price_usd": 1.0,
        "liquidity_usd": liquidity,
        "volume_24h_usd": volume,
        "price_change_24h_pct": change,
        "completeness": {
            "liquidity": liquidity_complete,
            "volume_24h": volume_complete,
        },
    }
    return snap


class MarketComparisonServiceTests(unittest.TestCase):
    def test_legacy_two_asset_comparison_preserves_existing_ratios(self):
        agi = legacy_snap("AGI", liquidity=3522, volume=1399, change=-5.57)
        xnt = legacy_snap("XNT", liquidity=33289, volume=6651, change=0.38)

        answer = format_market_comparison(
            "Compare AGI vs XNT",
            [agi, xnt],
            format_usd=usd,
            format_field_line=lambda field, snap: f"{field}:{snap['symbol']}",
        )

        self.assertIn("• Liquidity: AGI", answer)
        self.assertIn("• Liquidity: XNT", answer)
        self.assertIn("XNT has 9.5× more available liquidity", answer)
        self.assertIn("XNT has 4.8× more 24h volume", answer)
        self.assertIn("Largest absolute 24h price move: AGI (-5.57%).", answer)
        self.assertIn("Best 24h return: XNT (+0.38%).", answer)
        self.assertIn("Execution: For similarly sized AMM trades", answer)

    def test_missing_structured_liquidity_is_not_compared_as_zero(self):
        agi = structured_snap(
            "AGI",
            liquidity=None,
            liquidity_complete=False,
            volume=1000,
            volume_complete=True,
            change=-1,
        )
        xnt = structured_snap(
            "XNT",
            liquidity=20000,
            liquidity_complete=True,
            volume=2000,
            volume_complete=True,
            change=1,
        )

        answer = format_market_comparison(
            "Compare AGI vs XNT",
            [agi, xnt],
            format_usd=usd,
            format_field_line=lambda field, snap: "unused",
        )

        self.assertIn("Liquidity: Not available from verified data", answer)
        self.assertNotIn("Liquidity: $0", answer)
        self.assertNotIn("more available liquidity", answer)
        self.assertNotIn("• Execution:", answer)

    def test_incomplete_volume_is_lower_bound_and_not_ranked(self):
        agi = structured_snap(
            "AGI",
            liquidity=5000,
            liquidity_complete=True,
            volume=100,
            volume_complete=False,
            change=-1,
        )
        xnt = structured_snap(
            "XNT",
            liquidity=10000,
            liquidity_complete=True,
            volume=200,
            volume_complete=True,
            change=1,
        )

        answer = format_market_comparison(
            "Compare AGI vs XNT",
            [agi, xnt],
            format_usd=usd,
            format_field_line=lambda field, snap: "unused",
        )

        self.assertIn("Volume 24h: at least $100 — incomplete XDEX pool data", answer)
        self.assertNotIn("more 24h volume", answer)

    def test_specific_fields_use_injected_field_formatter(self):
        snaps = [
            legacy_snap("AGI", liquidity=1, volume=2, change=3),
            legacy_snap("XNT", liquidity=4, volume=5, change=6),
        ]
        calls = []

        answer = format_market_comparison(
            "Compare prices",
            snaps,
            fields=["price", "liquidity"],
            format_usd=usd,
            format_field_line=lambda field, snap: (
                calls.append((field, snap["symbol"])) or f"{field}:{snap['symbol']}"
            ),
        )

        self.assertEqual(
            calls,
            [
                ("price", "AGI"),
                ("liquidity", "AGI"),
                ("price", "XNT"),
                ("liquidity", "XNT"),
            ],
        )
        self.assertIn("price:AGI", answer)
        self.assertNotIn("Analyst comparison:", answer)

    def test_token_addresses_remain_explicit_opt_in(self):
        snaps = [
            legacy_snap("AGI", liquidity=1, volume=2, change=3),
            legacy_snap("XNT", liquidity=4, volume=5, change=6),
        ]

        hidden = format_market_comparison(
            "Compare AGI vs XNT",
            snaps,
            format_usd=usd,
            format_field_line=lambda field, snap: "unused",
        )
        shown = format_market_comparison(
            "Compare AGI vs XNT and show token address",
            snaps,
            format_usd=usd,
            format_field_line=lambda field, snap: "unused",
            include_token_addresses=True,
        )

        self.assertNotIn("AGI_MINT", hidden)
        self.assertIn("Token Addresses:", shown)
        self.assertIn("AGI_MINT", shown)
        self.assertIn("XNT_MINT", shown)


if __name__ == "__main__":
    unittest.main()
