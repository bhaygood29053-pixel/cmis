import unittest
from types import SimpleNamespace

from liquidity_scout.integrations.moltgrid import (
    build_cmis_trade_analysis,
    format_cmis_pre_trade_answer,
    parse_cmis_trade_context,
    wants_cmis_pre_trade,
    wire_market_core,
)
from liquidity_scout.market.resolver import resolve_asset


QUESTION = "Would it be smart to buy $1000 of XNT?"


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
        "address": mint,
    }


def pool(address, base, quote):
    return {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "liquidity": 1000,
        "volume24h": 100,
    }


class FakeGateway:
    def __init__(self):
        self.requests = []

    def dispatch(self, request):
        self.requests.append(request)
        service = request["service"]

        if service == "market_report":
            return {
                "service": "market_report",
                "chain": "x1",
                "status": "ok",
                "asset": {"symbol": "XNT", "mint": "MINT_XNT"},
                "data": {
                    "price_usd": 0.5,
                    "liquidity_usd": 25000,
                    "volume_24h_usd": 5000,
                    "#LPs": 4,
                    "completeness": {
                        "price": True,
                        "liquidity": True,
                        "volume_24h": True,
                    },
                },
                "risk": None,
                "confidence": {},
                "sources": [],
                "observed_at": 123,
                "warnings": [],
                "errors": [],
            }

        if service == "risk_check":
            return {
                "service": "risk_check",
                "chain": "x1",
                "status": "partial",
                "asset": {"symbol": "XNT", "mint": "MINT_XNT"},
                "data": {},
                "risk": {
                    "recommendation": "WARN",
                    "confidence": {
                        "verified_checks": 5,
                        "total_checks": 8,
                    },
                    "reasons": [
                        "Verified historical price comparison was not supplied to the risk core."
                    ],
                },
                "confidence": {},
                "sources": [],
                "observed_at": 123,
                "warnings": [],
                "errors": [],
            }

        if service == "pre_trade_check":
            return {
                "service": "pre_trade_check",
                "chain": "x1",
                "status": "partial",
                "asset": {"symbol": "XNT", "mint": "MINT_XNT"},
                "data": {},
                "risk": {
                    "recommendation": "WARN",
                    "analysis_only": True,
                    "execution_authorized": False,
                    "assessment_scope": {
                        "not_yet_included": [
                            "trade_size_thresholds",
                            "slippage",
                            "price_impact",
                            "route_quality",
                            "transaction_simulation",
                            "fees",
                            "execution_authorization",
                        ]
                    },
                },
                "confidence": {},
                "sources": [],
                "observed_at": 123,
                "warnings": [],
                "errors": [],
            }

        raise AssertionError(f"unexpected service: {service}")


class MoltGridCMISBridgeTests(unittest.TestCase):
    def setUp(self):
        self.usdc = token("USDC", "MINT_USDC", "USD Coin")
        self.pools = [
            pool("P_WOULD", token("WOULD", "MINT_WOULD"), self.usdc),
            pool("P_SMART", token("SMART", "MINT_SMART"), self.usdc),
            pool("P_XNT", token("XNT", "MINT_XNT", "Wrapped XNT"), self.usdc),
        ]

    def test_exact_reported_question_resolves_xnt_not_would(self):
        term, matches = resolve_asset(QUESTION, self.pools)

        self.assertEqual(term, "XNT")
        self.assertTrue(matches)
        self.assertEqual(matches[0][2]["mint"], "MINT_XNT")

    def test_lowercase_trade_question_still_resolves_xnt(self):
        term, matches = resolve_asset(
            "would it be smart to buy $1000 of xnt?",
            self.pools,
        )

        self.assertEqual(term.lower(), "xnt")
        self.assertEqual(matches[0][2]["mint"], "MINT_XNT")

    def test_uppercase_prose_like_symbol_remains_explicitly_queryable(self):
        term, matches = resolve_asset("What is SMART?", self.pools)

        self.assertEqual(term, "SMART")
        self.assertEqual(matches[0][2]["mint"], "MINT_SMART")

    def test_trade_context_parses_side_and_explicit_usd_notional(self):
        trade = parse_cmis_trade_context(QUESTION)

        self.assertEqual(
            trade,
            {"side": "buy", "chain": "x1", "notional_usd": 1000.0},
        )
        self.assertTrue(wants_cmis_pre_trade(QUESTION))
        self.assertIsNone(parse_cmis_trade_context("Should I buy or sell XNT?"))
        self.assertEqual(
            parse_cmis_trade_context("Should I buy 1000 XNT?"),
            {"side": "buy", "chain": "x1"},
        )

    def test_trade_analysis_uses_public_cmis_gateway_services(self):
        gateway = FakeGateway()
        analysis = build_cmis_trade_analysis(QUESTION, "XNT", gateway=gateway)

        self.assertEqual(
            [request["service"] for request in gateway.requests],
            ["market_report", "risk_check", "pre_trade_check"],
        )
        self.assertTrue(all(request["chain"] == "x1" for request in gateway.requests))
        self.assertTrue(all(request["asset"] == "XNT" for request in gateway.requests))
        self.assertEqual(
            gateway.requests[-1]["params"]["trade"]["notional_usd"],
            1000.0,
        )
        self.assertEqual(analysis["pre_trade_check"]["risk"]["recommendation"], "WARN")

    def test_visible_answer_names_xnt_and_refuses_execution_authorization(self):
        gateway = FakeGateway()
        listener = SimpleNamespace(
            format_usd=lambda value: f"${float(value):,.2f}".rstrip("0").rstrip(".")
        )

        answer = format_cmis_pre_trade_answer(
            listener,
            QUESTION,
            "XNT",
            gateway=gateway,
        )

        self.assertIn("CMIS pre-trade analysis — XNT", answer)
        self.assertNotIn("CMIS pre-trade analysis — WOULD", answer)
        self.assertIn("Proposed trade: BUY $1,000", answer)
        self.assertIn("CMIS risk result: WARN", answer)
        self.assertIn("Pre-trade result: WARN", answer)
        self.assertIn("trade size thresholds", answer)
        self.assertIn("slippage", answer)
        self.assertIn("price impact", answer)
        self.assertIn("Analysis only. Execution authorized: NO.", answer)

    def test_canonical_wiring_forces_trade_question_into_cmis_analysis_route(self):
        listener = SimpleNamespace(
            wants_asset_analysis=lambda _question: False,
            format_asset_analysis_answer=lambda *_args: "legacy-analysis",
        )

        wire_market_core(listener)

        self.assertTrue(listener.wants_asset_analysis(QUESTION))
        self.assertFalse(listener.wants_asset_analysis("What is XNT price?"))

        # Wiring is idempotent and must not wrap its own wrapper recursively.
        wire_market_core(listener)
        self.assertTrue(listener.wants_asset_analysis(QUESTION))
        self.assertFalse(listener.wants_asset_analysis("What is XNT price?"))


if __name__ == "__main__":
    unittest.main()
