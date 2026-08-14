import unittest

from liquidity_scout.services.historical_compare import format_historical_comparison


class FakeHistory:
    def __init__(self, *, metric="liquidity", old=None, period="7d"):
        self.metric = metric
        self.old = old
        self.period = period
        self.recorded = []

    def parse_historical_comparison(self, _question):
        return {
            "metric": self.metric,
            "period": self.period,
            "period_seconds": 7 * 86400 if self.period == "7d" else 86400,
            "direction": "down",
            "threshold": None,
            "comparator": None,
        }

    def record_snapshot(self, **kwargs):
        self.recorded.append(kwargs)

    def historical_value(self, _mint, _metric, _period_seconds):
        return self.old

    def format_number(self, metric, value):
        if metric in ("liquidity", "volume"):
            return f"${value:,.2f}"
        return f"{value:,.0f}"

    def history_not_ready_message(self, symbol, metric, period, _mint):
        return f"Liquidity Scout reply: {symbol} • no {metric} history for {period}."

    def percent_change(self, old_value, new_value):
        if old_value == 0:
            return None
        return ((new_value - old_value) / old_value) * 100.0

    def threshold_result(self, change, direction, threshold):
        if direction == "down":
            return change <= -abs(threshold)
        if direction == "up":
            return change >= abs(threshold)
        return abs(change) >= abs(threshold)


def structured_snapshot(
    *,
    liquidity=100.0,
    liquidity_complete=True,
    volume=50.0,
    volume_complete=True,
    holders=10,
    holders_complete=True,
    price=2.0,
    price_complete=True,
):
    return {
        "symbol": "AGI",
        "token_address": "AGI_MINT",
        # Legacy compatibility values deliberately differ from report values.
        "price_usd_value": 0,
        "liquidity": 0,
        "vol24": 0,
        "holders": 999,
        "pool_count": 2,
        "_market_report": {
            "symbol": "AGI",
            "mint": "AGI_MINT",
            "price_usd": price,
            "liquidity_usd": liquidity,
            "volume_24h_usd": volume,
            "holders": holders,
            "lp_count": 2,
            "completeness": {
                "price": price_complete,
                "liquidity": liquidity_complete,
                "volume_24h": volume_complete,
                "holders": holders_complete,
            },
        },
    }


class HistoricalComparisonServiceTests(unittest.TestCase):
    def test_complete_structured_liquidity_uses_verified_report_not_legacy_zero(self):
        history = FakeHistory(old={"timestamp": 1, "value": 50.0})
        answer = format_historical_comparison(
            "Has AGI liquidity changed over 7d?",
            structured_snapshot(),
            history_backend=history,
        )

        self.assertIn("Current liquidity: $100.00", answer)
        self.assertIn("7d ago: $50.00", answer)
        self.assertIn("Change: +100.00%", answer)
        self.assertEqual(len(history.recorded), 1)
        self.assertEqual(history.recorded[0]["liquidity"], 100.0)
        self.assertEqual(history.recorded[0]["price"], 2.0)
        self.assertEqual(history.recorded[0]["volume24"], 50.0)
        self.assertEqual(history.recorded[0]["holders"], 10.0)
        self.assertEqual(history.recorded[0]["pool_count"], 2)

    def test_incomplete_liquidity_is_unavailable_and_not_persisted_as_zero(self):
        history = FakeHistory(old={"timestamp": 1, "value": 50.0})
        answer = format_historical_comparison(
            "Has AGI liquidity changed over 7d?",
            structured_snapshot(liquidity_complete=False),
            history_backend=history,
        )

        self.assertIn("Current liquidity data is not available from a verified source", answer)
        self.assertEqual(history.recorded, [])

    def test_holder_conflict_ignores_legacy_max_compatibility_value(self):
        history = FakeHistory(metric="holders", old={"timestamp": 1, "value": 8.0})
        answer = format_historical_comparison(
            "Have AGI holders changed over 7d?",
            structured_snapshot(holders=None, holders_complete=False),
            history_backend=history,
        )

        self.assertIn("Current holders data is not available from a verified source", answer)
        self.assertNotIn("999", answer)
        self.assertEqual(history.recorded, [])

    def test_verified_metric_records_other_incomplete_fields_as_null_not_zero(self):
        history = FakeHistory(old=None)
        answer = format_historical_comparison(
            "Has AGI liquidity changed over 7d?",
            structured_snapshot(
                volume=25.0,
                volume_complete=False,
                holders=None,
                holders_complete=False,
            ),
            history_backend=history,
        )

        self.assertIn("no liquidity history", answer)
        self.assertEqual(len(history.recorded), 1)
        row = history.recorded[0]
        self.assertEqual(row["liquidity"], 100.0)
        self.assertIsNone(row["volume24"])
        self.assertIsNone(row["holders"])

    def test_supply_uses_injected_verified_rpc_lookup(self):
        history = FakeHistory(metric="supply", old={"timestamp": 1, "value": 900.0})
        answer = format_historical_comparison(
            "Has AGI supply changed over 7d?",
            structured_snapshot(),
            history_backend=history,
            get_total_supply=lambda mint: "1000" if mint == "AGI_MINT" else None,
        )

        self.assertIn("Current supply: 1,000", answer)
        self.assertEqual(history.recorded[0]["total_supply"], 1000.0)

    def test_legacy_snapshot_shape_remains_supported(self):
        history = FakeHistory(old={"timestamp": 1, "value": 50.0})
        legacy = {
            "symbol": "AGI",
            "token_address": "AGI_MINT",
            "price_usd_value": 2.0,
            "liquidity": 100.0,
            "vol24": 25.0,
            "holders": 7,
            "pool_count": 1,
        }
        answer = format_historical_comparison(
            "Has AGI liquidity changed over 7d?",
            legacy,
            history_backend=history,
        )

        self.assertIn("Current liquidity: $100.00", answer)
        self.assertEqual(history.recorded[0]["holders"], 7.0)


if __name__ == "__main__":
    unittest.main()
