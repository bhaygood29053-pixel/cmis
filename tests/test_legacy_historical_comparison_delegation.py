import inspect
import unittest
from unittest.mock import patch

import moltgrid_signal_v12_ollama as legacy


class LegacyHistoricalComparisonDelegationTests(unittest.TestCase):
    def test_legacy_formatter_delegates_to_reusable_service(self):
        snapshot = {"symbol": "AGI", "token_address": "AGI_MINT"}

        with patch.object(
            legacy,
            "compact_asset_snapshot",
            return_value=snapshot,
        ) as snapshot_builder, patch(
            "liquidity_scout.services.format_historical_comparison",
            return_value="historical-answer",
        ) as formatter:
            result = legacy.format_historical_comparison_answer(
                "Has AGI liquidity changed over 7d?",
                "AGI",
                ["match"],
                object(),
            )

        self.assertEqual(result, "historical-answer")
        snapshot_builder.assert_called_once()
        args, kwargs = formatter.call_args
        self.assertEqual(args[0], "Has AGI liquidity changed over 7d?")
        self.assertIs(args[1], snapshot)
        self.assertIs(kwargs["history_backend"], legacy.history)
        self.assertIs(kwargs["get_total_supply"], legacy.get_token_total_supply)

    def test_legacy_formatter_contains_no_historical_calculation_policy(self):
        source = inspect.getsource(legacy.format_historical_comparison_answer)

        self.assertIn("format_historical_comparison", source)
        self.assertIn("compact_asset_snapshot", source)
        self.assertNotIn("historical_value", source)
        self.assertNotIn("percent_change", source)
        self.assertNotIn("threshold_result", source)
        self.assertNotIn("record_snapshot", source)
        self.assertNotIn("Current {metric}", source)


if __name__ == "__main__":
    unittest.main()
