import unittest
from types import SimpleNamespace
from unittest.mock import patch

from liquidity_scout.integrations import moltgrid
from liquidity_scout.integrations.moltgrid_asset_cmis import (
    build_cmis_asset_request,
    cmis_asset_service,
    format_cmis_asset_answer,
)


class FakeGateway:
    def __init__(self):
        self.requests = []

    def dispatch(self, request):
        self.requests.append(request)
        service = request["service"]
        if service == "asset_lookup":
            return {
                "service": "asset_lookup",
                "chain": "x1",
                "status": "ok",
                "asset": {
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "mint": "MINT_XNT",
                },
                "data": {
                    "resolved_term": "XNT",
                    "resolved_by": "symbol",
                    "lp_count": 314,
                },
                "risk": None,
                "confidence": {
                    "complete": True,
                    "verified_checks": 1,
                    "total_checks": 1,
                },
                "sources": [{
                    "source": "X1.Ninja/XDEX",
                    "role": "asset_lookup",
                    "observed_at": 123.0,
                }],
                "observed_at": 123.0,
                "warnings": [],
                "errors": [],
            }

        if service == "market_report":
            return {
                "service": "market_report",
                "chain": "x1",
                "status": "partial",
                "asset": {
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "mint": "MINT_XNT",
                },
                "data": {
                    "price_usd": 0.519,
                    "liquidity_usd": 140344,
                    "volume_24h_usd": 16272,
                    "transactions_24h": 42,
                    "holders": None,
                    "lp_count": 314,
                    "#LPs": 314,
                    "completeness": {
                        "price": True,
                        "liquidity": True,
                        "volume_24h": True,
                        "transactions_24h": True,
                        "holders": False,
                    },
                },
                "risk": None,
                "confidence": {
                    "complete": False,
                    "verified_checks": 4,
                    "total_checks": 5,
                },
                "sources": [{
                    "source": "X1.Ninja/XDEX",
                    "role": "market_report",
                    "observed_at": 456.0,
                }],
                "observed_at": 456.0,
                "warnings": [{
                    "code": "holders_unverified",
                    "message": "Holder count is not verified asset-wide.",
                }],
                "errors": [],
            }

        raise AssertionError(service)


class MoltGridAssetCMISTests(unittest.TestCase):
    def setUp(self):
        self.listener = SimpleNamespace(
            format_usd=lambda value: f"${float(value):,.3f}".rstrip("0").rstrip("."),
        )

    def test_identity_question_uses_asset_lookup(self):
        self.assertEqual(cmis_asset_service("What is XNT?"), "asset_lookup")
        self.assertEqual(cmis_asset_service("Find XNT"), "asset_lookup")
        self.assertEqual(
            build_cmis_asset_request("What is XNT?", "XNT"),
            {
                "service": "asset_lookup",
                "chain": "x1",
                "asset": "XNT",
                "params": {},
            },
        )

    def test_market_question_uses_market_report(self):
        for question in (
            "What is XNT doing?",
            "What is the price of XNT?",
            "Show XNT liquidity",
            "How many holders does XNT have?",
        ):
            with self.subTest(question=question):
                self.assertEqual(cmis_asset_service(question), "market_report")

    def test_asset_lookup_answer_preserves_identity_traceability_and_timestamp(self):
        gateway = FakeGateway()
        answer = format_cmis_asset_answer(
            self.listener,
            "What is XNT?",
            "XNT",
            gateway=gateway,
        )

        self.assertEqual(gateway.requests[0]["service"], "asset_lookup")
        self.assertIn("CMIS asset lookup — XNT", answer)
        self.assertIn("Service status: OK", answer)
        self.assertIn("Name: Wrapped XNT", answer)
        self.assertIn("Mint: MINT_XNT", answer)
        self.assertIn("#LPs: 314", answer)
        self.assertIn("Confidence checks: 1/1 verified", answer)
        self.assertIn("Observed at: 123.0", answer)
        self.assertIn("Source: X1.Ninja/XDEX (asset_lookup) @ 123.0", answer)

    def test_market_report_answer_uses_verified_asset_wide_metrics_and_uncertainty(self):
        gateway = FakeGateway()
        answer = format_cmis_asset_answer(
            self.listener,
            "What is XNT doing?",
            "XNT",
            gateway=gateway,
        )

        self.assertEqual(gateway.requests[0]["service"], "market_report")
        self.assertIn("CMIS market report — XNT", answer)
        self.assertIn("Service status: PARTIAL", answer)
        self.assertIn("Verified price: $0.519", answer)
        self.assertIn("Asset-wide liquidity: $140,344", answer)
        self.assertIn("24h volume: $16,272", answer)
        self.assertIn("24h transactions: 42", answer)
        self.assertIn("Holders: unavailable from verified data", answer)
        self.assertIn("#LPs: 314", answer)
        self.assertIn("Confidence checks: 4/5 verified", answer)
        self.assertIn("Observed at: 456.0", answer)
        self.assertIn("Source: X1.Ninja/XDEX (market_report) @ 456.0", answer)
        self.assertIn("holders_unverified", answer)

    def test_wiring_routes_ordinary_pool_answer_through_cmis(self):
        listener = SimpleNamespace(
            wants_asset_analysis=lambda _question: False,
            format_asset_analysis_answer=lambda *_args: "legacy-analysis",
            format_pool_answer=lambda *_args: "legacy-pool",
            history=SimpleNamespace(parse_historical_comparison=lambda _question: None),
            wants_asset_rank=lambda _question: False,
            wants_historical_liquidity=lambda _question: False,
        )

        moltgrid.wire_market_core(listener)

        with patch.object(
            moltgrid,
            "format_cmis_asset_answer",
            return_value="cmis-market",
        ) as formatter:
            answer = listener.format_pool_answer(
                "What is XNT doing?",
                "XNT",
                ["legacy-match-ignored"],
                object(),
            )

        self.assertEqual(answer, "cmis-market")
        formatter.assert_called_once()
        self.assertEqual(formatter.call_args.args[2], "XNT")

    def test_wiring_preserves_historical_and_rank_routes(self):
        calls = []

        def legacy_pool(question, *_args):
            calls.append(question)
            return "legacy-specialized-route"

        listener = SimpleNamespace(
            wants_asset_analysis=lambda _question: False,
            format_asset_analysis_answer=lambda *_args: "legacy-analysis",
            format_pool_answer=legacy_pool,
            history=SimpleNamespace(
                parse_historical_comparison=lambda question: (
                    {"period": "7d"} if "7d" in question else None
                )
            ),
            wants_asset_rank=lambda question: "rank" in question.lower(),
            wants_historical_liquidity=lambda _question: False,
        )

        moltgrid.wire_market_core(listener)

        with patch.object(moltgrid, "format_cmis_asset_answer") as formatter:
            historical = listener.format_pool_answer(
                "How did XNT price change over 7d?", "XNT", [], object()
            )
            ranked = listener.format_pool_answer(
                "Where does XNT rank by volume?", "XNT", [], object()
            )

        self.assertEqual(historical, "legacy-specialized-route")
        self.assertEqual(ranked, "legacy-specialized-route")
        self.assertEqual(len(calls), 2)
        formatter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
