import types
import unittest
from unittest.mock import patch

from liquidity_scout.integrations import moltgrid


class MoltGridHistoricalBridgeTests(unittest.TestCase):
    def test_bridge_builds_snapshot_and_calls_reusable_service(self):
        listener = types.SimpleNamespace(
            history=object(),
            get_token_total_supply=lambda mint: "1000",
        )
        catalog = object()
        snapshot = {"symbol": "AGI", "_market_report": {"symbol": "AGI"}}

        with patch.object(
            moltgrid,
            "compact_asset_snapshot",
            return_value=snapshot,
        ) as snapshot_builder, patch.object(
            moltgrid,
            "core_format_historical_comparison",
            return_value="history-answer",
        ) as formatter:
            result = moltgrid.format_historical_comparison_answer(
                listener,
                "Has AGI liquidity changed over 7d?",
                "AGI",
                ["match"],
                catalog,
            )

        self.assertEqual(result, "history-answer")
        snapshot_builder.assert_called_once_with(
            listener,
            "AGI",
            ["match"],
            catalog,
        )
        args, kwargs = formatter.call_args
        self.assertEqual(args[0], "Has AGI liquidity changed over 7d?")
        self.assertIs(args[1], snapshot)
        self.assertIs(kwargs["history_backend"], listener.history)
        self.assertIs(kwargs["get_total_supply"], listener.get_token_total_supply)

    def test_wire_market_core_replaces_listener_historical_formatter(self):
        legacy_formatter = lambda *_args: "legacy"
        listener = types.SimpleNamespace(
            history=types.SimpleNamespace(
                parse_historical_comparison=lambda _question: None,
            ),
            wants_volume_rank=lambda _question: False,
            wants_historical_liquidity=lambda _question: False,
            format_usd=lambda value: str(value),
            format_age=lambda value: str(value),
            get_token_total_supply=lambda _mint: None,
            get_token_mint_info=lambda _mint: None,
            format_historical_comparison_answer=legacy_formatter,
        )

        moltgrid.wire_market_core(listener)

        self.assertIsNot(listener.format_historical_comparison_answer, legacy_formatter)
        self.assertTrue(callable(listener.format_historical_comparison_answer))


if __name__ == "__main__":
    unittest.main()
