import unittest
from types import SimpleNamespace
from unittest.mock import patch

from liquidity_scout.integrations import moltgrid


class MoltGridComparisonBridgeTests(unittest.TestCase):
    def test_bridge_builds_snapshots_and_calls_comparison_service(self):
        listener = SimpleNamespace(
            format_usd=lambda value: f"${value}",
            format_age=lambda value: "1d",
            get_token_total_supply=lambda mint: None,
            get_token_mint_info=lambda mint: None,
            history=SimpleNamespace(parse_historical_comparison=lambda question: None),
            wants_volume_rank=lambda question: False,
            wants_historical_liquidity=lambda question: False,
        )
        resolved = [
            ("AGI", [("pool-agi",)]),
            ("XNT", [("pool-xnt",)]),
        ]
        snapshots = [
            {"symbol": "AGI", "title": "AGI"},
            {"symbol": "XNT", "title": "XNT"},
        ]

        with patch.object(
            moltgrid,
            "compact_asset_snapshot",
            side_effect=snapshots,
        ) as snapshot_builder, patch.object(
            moltgrid,
            "requested_asset_fields",
            return_value=["price"],
        ), patch.object(
            moltgrid,
            "format_market_comparison",
            return_value="comparison",
        ) as formatter:
            result = moltgrid.format_multi_asset_answer(
                listener,
                "Compare AGI vs XNT",
                resolved,
                object(),
            )

        self.assertEqual(result, "comparison")
        self.assertEqual(snapshot_builder.call_count, 2)
        args, kwargs = formatter.call_args
        self.assertEqual(args[0], "Compare AGI vs XNT")
        self.assertEqual(args[1], snapshots)
        self.assertEqual(kwargs["fields"], ["price"])
        self.assertFalse(kwargs["include_token_addresses"])

    def test_wire_market_core_replaces_multi_asset_formatter(self):
        original = object()
        listener = SimpleNamespace(
            XDEXCatalog=object(),
            resolve_asset=object(),
            resolve_multiple_assets=object(),
            compact_asset_snapshot=object(),
            format_multi_asset_answer=original,
            liquidity_depth_label=object(),
            volume_activity_label=object(),
            price_movement_label=object(),
            verified_snapshot_context=object(),
            FIELD_ORDER=[],
            requested_asset_fields=object(),
            format_field_line=object(),
            full_snapshot_lines=object(),
            wants_token_address=object(),
            wants_asset_analysis=lambda _question: False,
            format_asset_analysis_answer=lambda *_args: "legacy-analysis",
        )

        moltgrid.wire_market_core(listener)

        self.assertTrue(callable(listener.format_multi_asset_answer))
        self.assertIsNot(listener.format_multi_asset_answer, original)

        with patch.object(
            moltgrid,
            "format_multi_asset_answer",
            return_value="wired",
        ) as formatter:
            result = listener.format_multi_asset_answer(
                "Compare AGI vs XNT",
                [("AGI", []), ("XNT", [])],
                object(),
            )

        self.assertEqual(result, "wired")
        formatter.assert_called_once()


if __name__ == "__main__":
    unittest.main()
