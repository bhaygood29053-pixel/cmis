import unittest

from liquidity_scout.services import (
    BLOCK,
    ERROR,
    OK,
    PARTIAL,
    UNAVAILABLE,
    build_risk_check_response,
    build_service_envelope,
)


MINT = "ReferenceMint"


def market_report(**overrides):
    report = {
        "symbol": "REF",
        "mint": MINT,
        "liquidity_usd": 250000.0,
        "volume_24h_usd": 125000.0,
        "transactions_24h": 500,
        "completeness": {
            "liquidity": True,
            "volume_24h": True,
            "transactions_24h": True,
            "holders": False,
            "price": True,
        },
        "provenance": {
            "source": "X1.Ninja/XDEX",
            "catalog_last_refresh_unix": 1234567890,
        },
    }
    report.update(overrides)
    return report


def tokenomics_report(**overrides):
    report = {
        "supply_verified": True,
        "mint_authority_verified": True,
        "mint_authority_state": "revoked",
        "freeze_authority_verified": True,
        "freeze_authority_state": "none",
        "rpc_decimals_consistent": True,
        "token_activity": {
            "available": True,
            "activity_verified": True,
            "coverage_verified": True,
            "coverage_scope": "bounded",
            "lifetime_coverage_verified": False,
        },
        "sources": {
            "current_supply": "X1 RPC getTokenSupply",
            "mint_account": "X1 RPC getAccountInfo(jsonParsed)",
            "token_activity": "X1 RPC parsed token instructions",
        },
    }
    report.update(overrides)
    return report


def historical_report(**overrides):
    report = {
        "metric": "price",
        "period": "24h",
        "current_value": 104.0,
        "historical_value": 100.0,
        "current_verified": True,
        "historical_verified": True,
        "current_observed_at": 2000,
        "historical_observed_at": 1000,
        "source": "historical_db",
    }
    report.update(overrides)
    return report


class CMISRiskContractTests(unittest.TestCase):
    def test_shared_envelope_has_stable_chain_aware_shape(self):
        response = build_service_envelope(
            "risk_check",
            "X1",
            OK,
            asset={"symbol": "REF"},
        )

        self.assertEqual(
            list(response),
            [
                "service",
                "chain",
                "status",
                "asset",
                "data",
                "risk",
                "confidence",
                "sources",
                "observed_at",
                "warnings",
                "errors",
            ],
        )
        self.assertEqual(response["service"], "risk_check")
        self.assertEqual(response["chain"], "x1")
        self.assertEqual(response["status"], OK)
        self.assertEqual(response["data"], {})
        self.assertIsNone(response["risk"])
        self.assertEqual(response["warnings"], [])
        self.assertEqual(response["errors"], [])

    def test_fully_verified_pass_is_ok_and_preserves_risk_result(self):
        response = build_risk_check_response(
            market_report(),
            tokenomics_report(),
            historical_report(),
        )

        self.assertEqual(response["service"], "risk_check")
        self.assertEqual(response["chain"], "x1")
        self.assertEqual(response["status"], OK)
        self.assertEqual(response["asset"], {"symbol": "REF", "mint": MINT})
        self.assertEqual(response["confidence"]["verified_checks"], 8)
        self.assertEqual(response["risk"]["recommendation"], "PASS")
        self.assertEqual(response["risk"]["confidence"], response["confidence"])
        self.assertEqual(response["errors"], [])

    def test_fully_verified_block_is_still_successful_service_response(self):
        response = build_risk_check_response(
            market_report(liquidity_usd=0.0),
            tokenomics_report(),
            historical_report(),
        )

        self.assertEqual(response["status"], OK)
        self.assertEqual(response["risk"]["recommendation"], BLOCK)
        self.assertIn("zero_verified_liquidity", response["risk"]["flags"])
        self.assertTrue(
            any(
                warning.get("code") == "zero_verified_liquidity"
                for warning in response["warnings"]
            )
        )

    def test_incomplete_verification_returns_partial_not_error(self):
        response = build_risk_check_response(market_report())

        self.assertEqual(response["status"], PARTIAL)
        self.assertIsNotNone(response["risk"])
        self.assertEqual(response["errors"], [])
        self.assertLess(
            response["confidence"]["verified_checks"],
            response["confidence"]["total_checks"],
        )
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("tokenomics_unavailable", codes)
        self.assertIn("historical_price_unavailable", codes)

    def test_missing_required_market_report_is_unavailable(self):
        response = build_risk_check_response(None)

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertIsNone(response["risk"])
        self.assertEqual(response["confidence"], {})
        self.assertEqual(response["warnings"][0]["code"], "market_report_unavailable")
        self.assertEqual(response["errors"], [])

    def test_malformed_market_report_is_error(self):
        response = build_risk_check_response("not a mapping")

        self.assertEqual(response["status"], ERROR)
        self.assertIsNone(response["risk"])
        self.assertEqual(response["errors"][0]["code"], "invalid_market_report")

    def test_invalid_risk_policy_becomes_explicit_error_response(self):
        response = build_risk_check_response(
            market_report(),
            tokenomics_report(),
            historical_report(),
            policy={"minimum_liquidity_usd": -1},
        )

        self.assertEqual(response["status"], ERROR)
        self.assertIsNone(response["risk"])
        self.assertEqual(
            response["errors"][0]["code"],
            "risk_check_validation_error",
        )

    def test_sources_preserve_traceability_and_known_timestamps(self):
        response = build_risk_check_response(
            market_report(),
            tokenomics_report(),
            historical_report(),
        )

        self.assertIsNone(response["observed_at"])
        self.assertIn(
            {
                "source": "X1.Ninja/XDEX",
                "role": "market_report",
                "observed_at": 1234567890,
            },
            response["sources"],
        )
        self.assertIn(
            {
                "source": "historical_db",
                "role": "historical_compare",
                "observed_at": 2000,
            },
            response["sources"],
        )
        self.assertIn(
            {"source": "risk_engine", "role": "risk_check"},
            response["sources"],
        )
        self.assertIn(
            {
                "source": "X1 RPC getTokenSupply",
                "role": "tokenomics.current_supply",
            },
            response["sources"],
        )

    def test_explicit_overall_observed_at_is_preserved_not_recomputed(self):
        response = build_risk_check_response(
            market_report(),
            tokenomics_report(),
            historical_report(),
            observed_at="2026-08-15T10:00:00Z",
        )

        self.assertEqual(response["observed_at"], "2026-08-15T10:00:00Z")

    def test_chain_is_explicit_for_future_provider_reuse(self):
        response = build_risk_check_response(
            market_report(),
            tokenomics_report(),
            historical_report(),
            chain="Solana",
        )

        self.assertEqual(response["chain"], "solana")
        self.assertEqual(response["risk"]["chain"], "solana")
        self.assertEqual(response["status"], OK)


if __name__ == "__main__":
    unittest.main()
