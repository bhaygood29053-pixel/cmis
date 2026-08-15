import types
import unittest
from unittest.mock import patch

from liquidity_scout.integrations import moltgrid
from liquidity_scout.integrations import moltgrid_historical_cmis


QUESTION = "Has AGI liquidity changed over 7d?"


class FakeHistory:
    def parse_historical_comparison(self, question):
        if "7d" not in str(question):
            return None
        return {
            "metric": "liquidity",
            "period": "7d",
            "period_seconds": 604800,
        }

    def format_number(self, metric, value):
        if metric in {"price", "liquidity", "volume"}:
            return f"${float(value):,.2f}"
        return f"{float(value):,.0f}"


class FakeGateway:
    def __init__(self, *, historical_available=True):
        self.requests = []
        self.historical_available = historical_available

    def dispatch(self, request):
        self.requests.append(request)
        data = {
            "status": "ok" if self.historical_available else "unavailable",
            "metric": "liquidity",
            "period": "7d",
            "period_seconds": 604800,
            "asset": {"symbol": "AGI", "mint": "MINT_AGI"},
            "current_value": 120000.0,
            "historical_value": 100000.0 if self.historical_available else None,
            "current_verified": True,
            "historical_verified": self.historical_available,
            "change_pct": 20.0 if self.historical_available else None,
            "absolute_change": 20000.0 if self.historical_available else None,
            "current_observed_at": 2000,
            "historical_observed_at": 1000 if self.historical_available else None,
            "source": "historical_db",
            "threshold": None,
            "direction": None,
            "threshold_met": None,
            "reason": None if self.historical_available else "historical_value_unavailable",
        }
        verified = 3 if self.historical_available else 1
        warnings = []
        sources = [
            {
                "source": "X1.Ninja/XDEX",
                "role": "historical_compare.current",
                "observed_at": 2000,
            }
        ]
        if self.historical_available:
            sources.append(
                {
                    "source": "historical_db",
                    "role": "historical_compare.baseline",
                    "observed_at": 1000,
                }
            )
        else:
            warnings = [
                {"code": "historical_value_unavailable"},
                {
                    "code": "historical_metric_verified",
                    "message": "Historical baseline value is not verified.",
                },
                {
                    "code": "change_verified",
                    "message": "Historical percentage change is not verified.",
                },
            ]

        return {
            "service": "historical_compare",
            "chain": "x1",
            "status": "ok" if self.historical_available else "unavailable",
            "asset": {"symbol": "AGI", "mint": "MINT_AGI"},
            "data": data,
            "risk": None,
            "confidence": {
                "complete": self.historical_available,
                "verified_checks": verified,
                "total_checks": 3,
                "checks": {
                    "current_metric_verified": True,
                    "historical_metric_verified": self.historical_available,
                    "change_verified": self.historical_available,
                },
            },
            "sources": sources,
            "observed_at": 2000,
            "warnings": warnings,
            "errors": [],
        }


class MoltGridHistoricalBridgeTests(unittest.TestCase):
    def _listener(self):
        return types.SimpleNamespace(
            history=FakeHistory(),
            format_usd=lambda value: f"${float(value):,.2f}",
            wants_volume_rank=lambda _question: False,
            wants_historical_liquidity=lambda _question: False,
            get_token_total_supply=lambda _mint: None,
            get_token_mint_info=lambda _mint: None,
            wants_asset_analysis=lambda _question: False,
            format_asset_analysis_answer=lambda *_args: "legacy-analysis",
        )

    def test_exact_historical_question_calls_public_cmis_service(self):
        listener = self._listener()
        gateway = FakeGateway()

        answer = moltgrid_historical_cmis.format_cmis_historical_answer(
            listener,
            QUESTION,
            "AGI",
            gateway=gateway,
        )

        self.assertEqual(len(gateway.requests), 1)
        self.assertEqual(
            gateway.requests[0],
            {
                "service": "historical_compare",
                "chain": "x1",
                "asset": "AGI",
                "params": {"question": QUESTION},
            },
        )
        self.assertIn("CMIS historical compare — AGI", answer)
        self.assertIn("Service status: OK", answer)
        self.assertIn("Current liquidity: $120,000.00", answer)
        self.assertIn("7d ago: $100,000.00", answer)
        self.assertIn("Change: +20.00%", answer)
        self.assertIn("Confidence checks: 3/3 verified", answer)
        self.assertIn("Source: X1.Ninja/XDEX (historical_compare.current) @ 2000", answer)
        self.assertIn("Source: historical_db (historical_compare.baseline) @ 1000", answer)

    def test_missing_history_is_unavailable_not_fabricated_zero(self):
        listener = self._listener()
        gateway = FakeGateway(historical_available=False)

        answer = moltgrid_historical_cmis.format_cmis_historical_answer(
            listener,
            QUESTION,
            "AGI",
            gateway=gateway,
        )

        self.assertIn("Service status: UNAVAILABLE", answer)
        self.assertIn("Current liquidity: $120,000.00", answer)
        self.assertIn("7d ago: unavailable from verified history", answer)
        self.assertIn("Change: unavailable from verified history", answer)
        self.assertIn("Confidence checks: 1/3 verified", answer)
        self.assertIn("historical_value_unavailable", answer)
        self.assertNotIn("7d ago: $0", answer)
        self.assertNotIn("Change: +0.00%", answer)

    def test_non_historical_question_does_not_call_gateway(self):
        listener = self._listener()
        gateway = FakeGateway()

        answer = moltgrid_historical_cmis.format_cmis_historical_answer(
            listener,
            "What is AGI price?",
            "AGI",
            gateway=gateway,
        )

        self.assertIsNone(answer)
        self.assertEqual(gateway.requests, [])

    def test_bridge_formatter_uses_shared_cmis_gateway_instance(self):
        listener = self._listener()
        gateway = FakeGateway()

        with patch.object(moltgrid, "_gateway_instance", return_value=gateway):
            result = moltgrid.format_historical_comparison_answer(
                listener,
                QUESTION,
                "AGI",
                ["legacy-match-is-not-used"],
                object(),
            )

        self.assertIn("CMIS historical compare — AGI", result)
        self.assertEqual(len(gateway.requests), 1)
        self.assertEqual(gateway.requests[0]["service"], "historical_compare")

    def test_wire_market_core_replaces_listener_historical_formatter(self):
        legacy_formatter = lambda *_args: "legacy"
        listener = self._listener()
        listener.format_historical_comparison_answer = legacy_formatter

        moltgrid.wire_market_core(listener)

        self.assertIsNot(listener.format_historical_comparison_answer, legacy_formatter)
        self.assertTrue(callable(listener.format_historical_comparison_answer))


if __name__ == "__main__":
    unittest.main()
