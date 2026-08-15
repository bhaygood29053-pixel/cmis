import unittest
from types import SimpleNamespace
from unittest.mock import patch

from liquidity_scout.integrations import moltgrid


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
        "address": mint,
    }


def pool(address, base, quote, liquidity, volume24h=0):
    return {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "liquidity": liquidity,
        "volume24h": volume24h,
    }


def presentation_listener(**overrides):
    values = {
        "format_usd": lambda value: f"${value:,.0f}",
        "format_age": lambda _value: "7mo",
        "get_token_total_supply": lambda _mint: None,
        "get_token_mint_info": lambda _mint: None,
        "history": SimpleNamespace(parse_historical_comparison=lambda _question: None),
        "wants_volume_rank": lambda _question: False,
        "wants_historical_liquidity": lambda _question: False,
        "wants_asset_analysis": lambda _question: False,
        "format_asset_analysis_answer": lambda *_args: "legacy-analysis",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class MoltGridMarketBridgeTests(unittest.TestCase):
    def setUp(self):
        self.xnt = token("XNT", "MINT_XNT", "Wrapped XNT")
        self.agi = token("AGI", "MINT_AGI", "Artificial General Intelligence")
        self.usdc = token("USDC", "MINT_USDC", "USD Coin")

    def test_wire_market_core_replaces_market_globals_snapshot_context_and_presentation(self):
        original_main = object()
        original_snapshot = object()
        original_context = object()
        original_fields = object()
        original_field_line = object()
        original_full_snapshot = object()
        original_token_address = object()
        listener = presentation_listener(
            XDEXCatalog=object(),
            resolve_asset=object(),
            resolve_multiple_assets=object(),
            compact_asset_snapshot=original_snapshot,
            liquidity_depth_label=object(),
            volume_activity_label=object(),
            price_movement_label=object(),
            verified_snapshot_context=original_context,
            FIELD_ORDER=["legacy"],
            requested_asset_fields=original_fields,
            format_field_line=original_field_line,
            full_snapshot_lines=original_full_snapshot,
            wants_token_address=original_token_address,
            main=original_main,
        )

        result = moltgrid.wire_market_core(listener)

        self.assertIs(result, listener)
        self.assertIs(listener.XDEXCatalog, moltgrid.MoltGridXDEXCatalog)
        self.assertIs(listener.resolve_asset, moltgrid.resolve_asset)
        self.assertIs(
            listener.resolve_multiple_assets,
            moltgrid.resolve_multiple_assets,
        )
        self.assertTrue(callable(listener.compact_asset_snapshot))
        self.assertIsNot(listener.compact_asset_snapshot, original_snapshot)
        self.assertIs(listener.liquidity_depth_label, moltgrid.liquidity_depth_label)
        self.assertIs(listener.volume_activity_label, moltgrid.volume_activity_label)
        self.assertIs(listener.price_movement_label, moltgrid.price_movement_label)
        self.assertTrue(callable(listener.verified_snapshot_context))
        self.assertIsNot(listener.verified_snapshot_context, original_context)
        self.assertEqual(listener.FIELD_ORDER, list(moltgrid.CORE_FIELD_ORDER))
        self.assertTrue(callable(listener.requested_asset_fields))
        self.assertIsNot(listener.requested_asset_fields, original_fields)
        self.assertTrue(callable(listener.format_field_line))
        self.assertIsNot(listener.format_field_line, original_field_line)
        self.assertTrue(callable(listener.full_snapshot_lines))
        self.assertIsNot(listener.full_snapshot_lines, original_full_snapshot)
        self.assertIs(listener.wants_token_address, moltgrid.core_wants_token_address)
        self.assertIs(listener.main, original_main)

    def test_single_asset_resolution_uses_core_pool_ordering(self):
        pools = [
            pool("P1", self.agi, self.xnt, 1000, 500),
            pool("P2", self.agi, self.usdc, 5000, 100),
        ]

        term, matches = moltgrid.resolve_asset("What is AGI doing?", pools)

        self.assertEqual(term.upper(), "AGI")
        self.assertEqual(matches[0][0]["address"], "P2")
        self.assertEqual(len(matches), 2)

    def test_snapshot_adapter_uses_asset_wide_metrics_and_legacy_shape(self):
        primary = pool("P2", self.agi, self.usdc, 5000, 100)
        primary.update(
            {
                "txns24h": 10,
                "holders": 1000,
                "priceUsd": 0.25,
                "priceChange1h": 1.5,
                "priceChange24h": 4.0,
                "marketCap": 12345,
                "fdv": 23456,
                "safetyGrade": "A",
                "safetyScore": 90,
                "createdAt": "2026-01-01T00:00:00Z",
            }
        )
        secondary = pool("P1", self.agi, self.xnt, 1000, 500)
        secondary.update(
            {
                "txns24h": 20,
                "holders": 1000,
                "priceUsd": 0.20,
                "createdAt": "2026-01-01T00:00:00Z",
            }
        )
        matches = [
            (primary, "base", self.agi, 90),
            (secondary, "base", self.agi, 90),
        ]
        listener = presentation_listener(
            format_usd=lambda value: f"${value:.2f}",
        )
        catalog = SimpleNamespace(xnt_price_usd=None, last_refresh=123.0)

        snap = moltgrid.compact_asset_snapshot(
            listener,
            "AGI",
            matches,
            catalog,
        )

        self.assertEqual(snap["title"], "AGI (Artificial General Intelligence)")
        self.assertEqual(snap["price"], "$0.25")
        self.assertEqual(snap["price_usd_value"], 0.25)
        self.assertEqual(snap["liquidity"], 6000)
        self.assertEqual(snap["primary_liquidity"], 5000)
        self.assertEqual(snap["vol24"], 600)
        self.assertEqual(snap["txns24"], 30)
        self.assertEqual(snap["holders"], 1000)
        self.assertEqual(snap["pool_count"], 2)
        self.assertEqual(snap["pool"], "AGI/USDC")
        self.assertEqual(snap["pool_address"], "P2")
        self.assertEqual(snap["safety"], "A (90/100)")
        self.assertEqual(snap["age"], "7mo")
        self.assertEqual(snap["_market_report"]["liquidity_usd"], 6000)
        self.assertTrue(snap["_market_report"]["completeness"]["liquidity"])

    def test_verified_context_does_not_classify_compatibility_zero_as_fact(self):
        primary = pool("P2", self.agi, self.usdc, None, 100)
        primary.update(
            {
                "txns24h": 10,
                "holders": 1000,
                "priceUsd": 0.25,
                "createdAt": "2026-01-01T00:00:00Z",
            }
        )
        matches = [(primary, "base", self.agi, 90)]
        listener = presentation_listener()
        catalog = SimpleNamespace(xnt_price_usd=None, last_refresh=123.0)

        snap = moltgrid.compact_asset_snapshot(
            listener,
            "AGI",
            matches,
            catalog,
        )
        context = moltgrid.verified_snapshot_context(
            listener,
            snap,
            ["liquidity"],
        )

        self.assertEqual(snap["liquidity"], 0)
        self.assertIn("Liquidity: Not available from verified data", context)
        self.assertNotIn("Liquidity: $0", context)
        self.assertNotIn("Liquidity classification:", context)

    def test_verified_context_marks_partial_sum_without_classifying_it(self):
        primary = pool("P2", self.agi, self.usdc, 5000, 100)
        secondary = pool("P1", self.agi, self.xnt, None, 500)
        matches = [
            (primary, "base", self.agi, 90),
            (secondary, "base", self.agi, 90),
        ]
        listener = presentation_listener()
        catalog = SimpleNamespace(xnt_price_usd=None, last_refresh=123.0)

        snap = moltgrid.compact_asset_snapshot(
            listener,
            "AGI",
            matches,
            catalog,
        )
        context = moltgrid.verified_snapshot_context(
            listener,
            snap,
            ["liquidity"],
        )

        self.assertEqual(snap["liquidity"], 5000)
        self.assertIn(
            "Liquidity: at least $5,000 — incomplete XDEX pool data",
            context,
        )
        self.assertNotIn("Liquidity classification:", context)

    def test_legacy_context_fallback_preserves_existing_snapshot_behavior(self):
        listener = presentation_listener()
        legacy_snap = {
            "title": "AGI",
            "liquidity": 3522,
        }

        context = moltgrid.verified_snapshot_context(
            listener,
            legacy_snap,
            ["liquidity"],
        )

        self.assertIn("Liquidity: $3,522", context)
        self.assertIn("Liquidity classification: very thin", context)

    def test_requested_fields_adapter_uses_listener_route_predicates(self):
        listener = presentation_listener(
            history=SimpleNamespace(
                parse_historical_comparison=lambda question: (
                    {"period": "30d"} if "30 days" in question else None
                )
            ),
            wants_volume_rank=lambda question: "rank" in question.lower(),
            wants_historical_liquidity=lambda question: "dropped" in question.lower(),
        )

        self.assertEqual(
            moltgrid.requested_asset_fields(
                listener,
                "Has AGI liquidity dropped?",
            ),
            [],
        )
        self.assertEqual(
            moltgrid.requested_asset_fields(
                listener,
                "Rank AGI by volume",
            ),
            [],
        )
        self.assertEqual(
            moltgrid.requested_asset_fields(
                listener,
                "Has AGI changed over 30 days?",
            ),
            [],
        )
        self.assertEqual(
            moltgrid.requested_asset_fields(
                listener,
                "What is AGI price and liquidity?",
            ),
            ["price", "liquidity"],
        )

    def test_field_format_adapter_keeps_rpc_transport_in_listener(self):
        calls = []
        listener = presentation_listener(
            format_usd=lambda value: f"${value:,.2f}",
            get_token_total_supply=lambda mint: (
                calls.append(("supply", mint)) or "1000"
            ),
            get_token_mint_info=lambda mint: (
                calls.append(("mint", mint)) or {"mint_authority": None}
            ),
        )
        snap = {
            "symbol": "AGI",
            "token_address": "MINT_AGI",
            "price_usd_value": 0.25,
        }

        fdv = moltgrid.format_field_line(listener, "fdv", snap)
        max_supply = moltgrid.format_field_line(listener, "max_supply", snap)

        self.assertIn("Current Supply Valuation: $250.00", fdv)
        self.assertIn("Mint authority revoked", max_supply)
        self.assertIn(("supply", "MINT_AGI"), calls)
        self.assertIn(("mint", "MINT_AGI"), calls)

    def test_ambiguous_symbol_fails_closed_for_listener(self):
        same_one = token("SAME", "MINT_ONE", "Same One")
        same_two = token("SAME", "MINT_TWO", "Same Two")
        pools = [
            pool("P1", same_one, self.xnt, 1000),
            pool("P2", same_two, self.usdc, 5000),
        ]

        term, matches = moltgrid.resolve_asset("What is SAME doing?", pools)

        self.assertIsNone(term)
        self.assertEqual(matches, [])

    def test_multi_asset_ambiguity_fails_closed_for_listener(self):
        same_one = token("SAME", "MINT_ONE", "Same One")
        same_two = token("SAME", "MINT_TWO", "Same Two")
        pools = [
            pool("P1", same_one, self.xnt, 1000),
            pool("P2", same_two, self.usdc, 5000),
        ]

        resolved = moltgrid.resolve_multiple_assets(
            "Compare SAME vs XNT",
            pools,
        )

        self.assertEqual(resolved, [])

    def test_main_runs_wired_legacy_listener(self):
        calls = []
        listener = SimpleNamespace(main=lambda: calls.append("main"))

        with patch.object(moltgrid, "load_listener", return_value=listener):
            moltgrid.main()

        self.assertEqual(calls, ["main"])


if __name__ == "__main__":
    unittest.main()
