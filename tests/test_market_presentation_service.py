import unittest

from liquidity_scout.services import (
    FIELD_ORDER,
    format_field_line,
    full_snapshot_lines,
    requested_asset_fields,
    wants_token_address,
)


def usd(value):
    return f"${float(value):,.2f}"


def snapshot():
    return {
        "title": "AGI",
        "symbol": "AGI",
        "token_address": "MINT_AGI",
        "price": "$0.2500",
        "price_usd_value": 0.25,
        "age": "7mo",
        "holders": 1200,
        "txns24": 42,
        "vol24": 5432,
        "change1": 1.5,
        "change24": -4.25,
        "liquidity": 6000,
        "pool_count": 2,
        "market_cap": 12345,
        "fdv": 23456,
        "safety": "A (90/100)",
        "pool_address": "POOL_AGI",
    }


class MarketPresentationServiceTests(unittest.TestCase):
    def test_field_selection_preserves_aliases_and_stable_order(self):
        fields = requested_asset_fields(
            "What is AGI worth, age, holders, txns, volume, liquidity, mcap and safety?"
        )

        self.assertEqual(
            fields,
            [
                "price",
                "age",
                "holders",
                "txns24",
                "volume24",
                "liquidity",
                "market_cap",
                "safety",
            ],
        )

    def test_change_field_selection_preserves_timeframe_rules(self):
        self.assertEqual(
            requested_asset_fields("What is AGI 1h change?"),
            ["change1h"],
        )
        self.assertEqual(
            requested_asset_fields("What is AGI 24-hour performance?"),
            ["change24h"],
        )
        self.assertEqual(
            requested_asset_fields("What is AGI change?"),
            ["change1h", "change24h"],
        )

    def test_route_predicates_suppress_fields_without_owning_other_services(self):
        self.assertEqual(
            requested_asset_fields(
                "Has AGI liquidity changed?",
                historical_comparison=True,
            ),
            [],
        )
        self.assertEqual(
            requested_asset_fields(
                "Rank AGI by volume",
                volume_rank=True,
            ),
            [],
        )
        self.assertEqual(
            requested_asset_fields(
                "Has AGI liquidity dropped?",
                historical_liquidity=True,
            ),
            [],
        )

    def test_supply_and_pool_fields_keep_legacy_append_order(self):
        fields = requested_asset_fields(
            "AGI total supply circulating supply max supply pool address"
        )
        self.assertEqual(
            fields,
            [
                "total_supply",
                "circulating_supply",
                "max_supply",
                "pool_address",
            ],
        )

    def test_token_address_is_explicit_opt_in(self):
        self.assertTrue(wants_token_address("Show AGI token address"))
        self.assertTrue(wants_token_address("What is the mint address?"))
        self.assertFalse(wants_token_address("Tell me about AGI"))
        self.assertFalse(wants_token_address("Show the pool address"))

    def test_simple_public_field_formatting_matches_v012(self):
        snap = snapshot()
        self.assertEqual(
            format_field_line("price", snap, format_usd=usd),
            "• Price: $0.2500",
        )
        self.assertEqual(
            format_field_line("holders", snap, format_usd=usd),
            "• Holders: 1,200",
        )
        self.assertEqual(
            format_field_line("change24h", snap, format_usd=usd),
            "• Change 24h: -4.25%",
        )
        self.assertEqual(
            format_field_line("liquidity", snap, format_usd=usd),
            "• Liquidity: $6,000.00 • Pools: 2",
        )

    def test_unverified_market_cap_and_circulating_supply_wording_is_stable(self):
        snap = snapshot()
        self.assertEqual(
            format_field_line("market_cap", snap, format_usd=usd),
            "• Market Cap: Not verified — circulating supply unavailable from verified data",
        )
        self.assertEqual(
            format_field_line("circulating_supply", snap, format_usd=usd),
            "• Circulating Supply: Not available from verified data",
        )

    def test_total_and_max_supply_use_injected_rpc_facts(self):
        snap = snapshot()
        total = format_field_line(
            "total_supply",
            snap,
            format_usd=usd,
            get_total_supply=lambda mint: "1000.5" if mint == "MINT_AGI" else None,
        )
        revoked = format_field_line(
            "max_supply",
            snap,
            format_usd=usd,
            get_mint_info=lambda mint: {"mint_authority": None},
        )
        active = format_field_line(
            "max_supply",
            snap,
            format_usd=usd,
            get_mint_info=lambda mint: {"mint_authority": "AUTH"},
        )

        self.assertEqual(total, "• Total Supply: 1,001 AGI")
        self.assertEqual(
            revoked,
            "• Max Supply: Original maximum issuance not verified • Mint authority revoked",
        )
        self.assertEqual(active, "• Max Supply: Not fixed • Mint authority active")

    def test_fdv_and_current_supply_valuation_preserve_verification_boundary(self):
        snap = snapshot()
        supply = lambda mint: "1000" if mint == "MINT_AGI" else None

        fdv = format_field_line(
            "fdv",
            snap,
            format_usd=usd,
            get_total_supply=supply,
        )
        valuation = format_field_line(
            "total_supply_valuation",
            snap,
            format_usd=usd,
            get_total_supply=supply,
        )

        self.assertIn("Fully Diluted Valuation (FDV): Not verified", fdv)
        self.assertIn("Current Supply Valuation: $250.00", fdv)
        self.assertIn("it is not FDV unless current total supply equals maximum supply", fdv)
        self.assertTrue(valuation.startswith("• Current Supply Valuation: $250.00"))
        self.assertIn("Market Cap separately requires verified circulating supply", valuation)

    def test_full_snapshot_lines_uses_stable_default_field_order(self):
        snap = snapshot()
        lines = full_snapshot_lines(
            snap,
            format_usd=usd,
            get_total_supply=lambda _mint: "1000",
            get_mint_info=lambda _mint: {"mint_authority": None},
        )

        self.assertEqual(len(lines), len(FIELD_ORDER))
        self.assertTrue(lines[0].startswith("• Price:"))
        self.assertTrue(lines[7].startswith("• Liquidity:"))
        self.assertTrue(lines[8].startswith("• Market Cap:"))
        self.assertTrue(lines[-1].startswith("• Tokenomics Safety:"))


if __name__ == "__main__":
    unittest.main()
