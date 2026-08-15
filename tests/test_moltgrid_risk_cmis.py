import unittest
from types import SimpleNamespace
from unittest.mock import patch

from liquidity_scout.integrations import moltgrid
from liquidity_scout.integrations.moltgrid_asset_cmis import (
    build_cmis_asset_request,
    cmis_asset_service,
    format_cmis_asset_answer,
)
from liquidity_scout.integrations.moltgrid_risk_cmis import (
    build_cmis_risk_request,
    wants_cmis_risk,
)
from liquidity_scout.services import build_risk_check
from liquidity_scout.services.cmis_native_tokenomics import (
    build_native_tokenomics_response,
)
from liquidity_scout.services.cmis_risk import build_risk_check_response


class FakeGateway:
    def __init__(self):
        self.requests = []

    def dispatch(self, request):
        self.requests.append(request)
        return {
            "service": "risk_check",
            "chain": "x1",
            "status": "partial",
            "asset": {
                "symbol": "XNT",
                "mint": "WrappedMarketRepresentation",
            },
            "data": {},
            "risk": {
                "chain": "x1",
                "asset": {
                    "symbol": "XNT",
                    "mint": "WrappedMarketRepresentation",
                },
                "recommendation": "WARN",
                "components": {
                    "liquidity": {
                        "status": "PASS",
                        "available": True,
                        "flags": [],
                        "reasons": [],
                        "evidence": {},
                    },
                    "activity": {
                        "status": "PASS",
                        "available": True,
                        "flags": [],
                        "reasons": [],
                        "evidence": {},
                    },
                    "tokenomics": {
                        "status": "WARN",
                        "available": True,
                        "flags": ["token_activity_unavailable"],
                        "reasons": [
                            "Verified bounded mint/burn activity was not supplied."
                        ],
                        "evidence": {},
                    },
                    "history": {
                        "status": "WARN",
                        "available": False,
                        "flags": ["historical_price_unavailable"],
                        "reasons": [
                            "Verified historical price comparison was not supplied to the risk core."
                        ],
                        "evidence": {},
                    },
                },
                "confidence": {
                    "level": "medium",
                    "verified_checks": 6,
                    "total_checks": 8,
                    "verification_ratio": 0.75,
                },
                "flags": [
                    "token_activity_unavailable",
                    "historical_price_unavailable",
                ],
                "reasons": [
                    "Verified bounded mint/burn activity was not supplied.",
                    "Verified historical price comparison was not supplied to the risk core.",
                ],
                "score": None,
                "score_verified": False,
                "score_reason": "risk_score_not_calibrated",
                "assessment_scope": {
                    "included": [
                        "liquidity",
                        "activity_24h",
                        "tokenomics_authorities",
                        "bounded_token_activity",
                        "historical_price_movement",
                        "source_completeness",
                    ],
                    "not_yet_included": [
                        "holder_distribution",
                        "statistical_volatility",
                        "trade_impact",
                    ],
                },
            },
            "confidence": {
                "level": "medium",
                "verified_checks": 6,
                "total_checks": 8,
            },
            "sources": [
                {
                    "source": "X1.Ninja/XDEX",
                    "role": "market_report",
                    "observed_at": 123.0,
                },
                {
                    "source": "api.x1.xyz /v1/supply/total",
                    "role": "tokenomics.network_total_supply",
                },
                {
                    "source": "api.x1.xyz /v1/supply/circulating",
                    "role": "tokenomics.network_circulating_supply",
                },
                {"source": "risk_engine", "role": "risk_check"},
            ],
            "observed_at": 123.0,
            "warnings": [
                {
                    "code": "token_activity_unavailable",
                    "message": "Verified bounded mint/burn activity was not supplied.",
                },
                {
                    "code": "historical_price_unavailable",
                    "message": "Verified historical price comparison was not supplied to the risk core.",
                },
            ],
            "errors": [],
        }


class MoltGridCMISRiskTests(unittest.TestCase):
    def test_risk_intent_routes_to_risk_check(self):
        positives = (
            "Is XNT safe?",
            "Is XNT risky?",
            "What is XNT risk?",
            "Run a risk check on XNT",
            "Any red flags for XNT?",
            "Is XNT dangerous?",
            "What is XNT safety score?",
        )
        for question in positives:
            with self.subTest(question=question):
                self.assertTrue(wants_cmis_risk(question))
                self.assertEqual(cmis_asset_service(question), "risk_check")

        self.assertFalse(wants_cmis_risk("What is XNT liquidity?"))
        self.assertEqual(cmis_asset_service("What is XNT liquidity?"), "market_report")
        self.assertEqual(cmis_asset_service("What are XNT tokenomics?"), "tokenomics")

    def test_risk_request_uses_public_gateway_contract(self):
        expected = {
            "service": "risk_check",
            "chain": "x1",
            "asset": "XNT",
            "params": {},
        }
        self.assertEqual(build_cmis_risk_request("XNT"), expected)
        self.assertEqual(build_cmis_asset_request("Is XNT safe?", "XNT"), expected)

    def test_risk_formatter_preserves_outcome_scope_sources_and_uncertainty(self):
        gateway = FakeGateway()
        answer = format_cmis_asset_answer(
            SimpleNamespace(),
            "Is XNT safe?",
            "XNT",
            gateway=gateway,
        )

        self.assertEqual(gateway.requests, [build_cmis_risk_request("XNT")])
        self.assertIn("CMIS risk check — XNT", answer)
        self.assertIn("Service status: PARTIAL", answer)
        self.assertIn("Risk result: WARN", answer)
        self.assertIn("Risk evidence verified: 6/8 checks (medium confidence)", answer)
        self.assertIn("• Liquidity: PASS", answer)
        self.assertIn("• 24h activity: PASS", answer)
        self.assertIn("• Tokenomics: WARN", answer)
        self.assertIn("• History: WARN", answer)
        self.assertIn(
            "Verified native-network issuance/burn activity was not supplied.",
            answer,
        )
        self.assertIn("Risk score: unavailable", answer)
        self.assertIn("holder distribution", answer)
        self.assertIn("api.x1.xyz /v1/supply/total", answer)
        self.assertIn("risk_engine", answer)
        self.assertIn("Execution authorized: NO", answer)
        self.assertNotIn("Wrapped XNT", answer)

    def test_canonical_runtime_bypasses_legacy_ai_for_safe_question(self):
        gateway = FakeGateway()
        listener = SimpleNamespace(
            SETTINGS=SimpleNamespace(x1_rpc_url="https://rpc.example"),
            history=SimpleNamespace(parse_historical_comparison=lambda _q: None),
            wants_asset_rank=lambda _q: False,
            wants_historical_liquidity=lambda _q: False,
            wants_volume_rank=lambda _q: False,
            # Simulate the legacy listener, which classified safe/risky wording
            # as Route 3 AI analysis.
            wants_asset_analysis=lambda _q: True,
            format_asset_analysis_answer=lambda *_args: "legacy-ai-analysis",
            format_pool_answer=lambda *_args: "legacy-pool",
            format_usd=lambda value: f"${float(value):,.2f}",
            format_age=lambda value: str(value),
        )

        with patch.object(moltgrid, "_gateway_instance", return_value=gateway):
            moltgrid.wire_market_core(listener)
            self.assertFalse(listener.wants_asset_analysis("Is XNT safe?"))
            answer = listener.format_pool_answer(
                "Is XNT safe?",
                "XNT",
                ["match"],
                object(),
            )

        self.assertIn("CMIS risk check — XNT", answer)
        self.assertNotIn("legacy-ai-analysis", answer)
        self.assertEqual(gateway.requests, [build_cmis_risk_request("XNT")])


class NativeXNTDeterministicRiskTests(unittest.TestCase):
    @staticmethod
    def native_tokenomics():
        return build_native_tokenomics_response(
            symbol="XNT",
            name="XNT",
            chain="x1",
            total_supply_record={
                "supply": "1067069618",
                "supply_verified": True,
                "source": "api.x1.xyz /v1/supply/total",
            },
            circulating_supply_record={
                "supply": "13810243",
                "supply_verified": True,
                "source": "api.x1.xyz /v1/supply/circulating",
            },
        )

    @staticmethod
    def market_report():
        return {
            "symbol": "XNT",
            "mint": "WrappedMarketRepresentation",
            "liquidity_usd": 100000.0,
            "volume_24h_usd": 10000.0,
            "transactions_24h": 100,
            "completeness": {
                "liquidity": True,
                "volume_24h": True,
                "transactions_24h": True,
            },
            "provenance": {
                "source": "X1.Ninja/XDEX",
                "catalog_last_refresh_unix": 123.0,
            },
        }

    def test_native_not_applicable_authorities_do_not_become_false_risk_warnings(self):
        tokenomics = self.native_tokenomics()["data"]
        result = build_risk_check(self.market_report(), tokenomics)

        self.assertNotIn("mint_authority_unverified", result["flags"])
        self.assertNotIn("freeze_authority_unverified", result["flags"])
        self.assertNotIn("mint_authority_active", result["flags"])
        self.assertNotIn("freeze_authority_active", result["flags"])
        self.assertIn("token_activity_unavailable", result["flags"])
        self.assertIn("historical_price_unavailable", result["flags"])
        self.assertEqual(result["confidence"]["verified_checks"], 6)
        self.assertEqual(result["confidence"]["total_checks"], 8)

    def test_native_supply_sources_flow_into_risk_envelope(self):
        tokenomics = self.native_tokenomics()["data"]
        response = build_risk_check_response(
            self.market_report(),
            tokenomics,
            observed_at=123.0,
        )
        source_names = [source.get("source") for source in response["sources"]]

        self.assertIn("X1.Ninja/XDEX", source_names)
        self.assertIn("api.x1.xyz /v1/supply/total", source_names)
        self.assertIn("api.x1.xyz /v1/supply/circulating", source_names)
        self.assertIn("risk_engine", source_names)


if __name__ == "__main__":
    unittest.main()
