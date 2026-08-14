import inspect
import unittest
from unittest.mock import call, patch

import moltgrid_signal_v12_ollama as legacy


class LegacyMarketComparisonDelegationTests(unittest.TestCase):
    def test_legacy_comparison_delegates_to_reusable_service(self):
        resolved = [
            ("AGI", ["agi-match"]),
            ("XNT", ["xnt-match"]),
        ]
        snapshots = [
            {"title": "AGI", "symbol": "AGI"},
            {"title": "XNT", "symbol": "XNT"},
        ]
        catalog = object()

        with patch.object(
            legacy,
            "compact_asset_snapshot",
            side_effect=snapshots,
        ) as snapshot_builder, patch.object(
            legacy,
            "requested_asset_fields",
            return_value=["price"],
        ), patch.object(
            legacy,
            "wants_token_address",
            return_value=True,
        ), patch.object(
            legacy,
            "core_format_market_comparison",
            return_value="comparison",
        ) as formatter:
            result = legacy.format_multi_asset_answer(
                "Compare AGI vs XNT and show token address",
                resolved,
                catalog,
            )

        self.assertEqual(result, "comparison")
        self.assertEqual(
            snapshot_builder.call_args_list,
            [
                call("AGI", ["agi-match"], catalog),
                call("XNT", ["xnt-match"], catalog),
            ],
        )
        args, kwargs = formatter.call_args
        self.assertEqual(args[0], "Compare AGI vs XNT and show token address")
        self.assertEqual(args[1], snapshots)
        self.assertEqual(kwargs["fields"], ["price"])
        self.assertIs(kwargs["format_usd"], legacy.format_usd)
        self.assertIs(kwargs["format_field_line"], legacy.format_field_line)
        self.assertTrue(kwargs["include_token_addresses"])

    def test_legacy_function_contains_only_adapter_policy(self):
        source = inspect.getsource(legacy.format_multi_asset_answer)

        self.assertIn("core_format_market_comparison(", source)
        self.assertIn("compact_asset_snapshot(term, matches, catalog)", source)
        self.assertIn("requested_asset_fields(question)", source)

        for duplicated_policy in (
            "Analyst comparison:",
            "more available liquidity",
            "more 24h volume",
            "Largest absolute 24h price move",
            "Best 24h return",
            "reduce slippage and price-impact pressure",
        ):
            self.assertNotIn(duplicated_policy, source)


if __name__ == "__main__":
    unittest.main()
