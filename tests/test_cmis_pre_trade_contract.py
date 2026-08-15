import unittest

from liquidity_scout.services import (
    BLOCK,
    ERROR,
    OK,
    PARTIAL,
    PASS,
    UNAVAILABLE,
    WARN,
    build_pre_trade_check_response,
    build_risk_check_response,
    build_service_envelope,
)


MINT = "ReferenceMint"


def raw_risk(*, recommendation=PASS, chain="x1", mint=MINT, verified=8, total=8):
    return {
        "chain": chain,
        "asset": {"symbol": "REF", "mint": mint},
        "recommendation": recommendation,
        "confidence": {
            "level": "high" if verified == total else "medium",
            "verified_checks": verified,
            "total_checks": total,
            "verification_ratio": verified / total if total else 0.0,
            "checks": {},
        },
        "flags": [],
        "reasons": [],
    }


def trade(*, side="buy", mint=MINT, symbol="REF", chain=None, notional_usd=1000):
    value = {
        "side": side,
        "asset": {"symbol": symbol, "mint": mint},
        "notional_usd": notional_usd,
    }
    if chain is not None:
        value["chain"] = chain
    return value


def market_report(*, liquidity=100000.0):
    return {
        "symbol": "REF",
        "mint": MINT,
        "liquidity_usd": liquidity,
        "volume_24h_usd": 50000.0,
        "transactions_24h": 250,
        "completeness": {
            "liquidity": True,
            "volume_24h": True,
            "transactions_24h": True,
            "holders": False,
            "price": True,
        },
        "provenance": {
            "source": "X1.Ninja/XDEX",
            "catalog_last_refresh_unix": 2000,
        },
    }


def tokenomics_report():
    return {
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
            "token_activity": "X1 RPC parsed token instructions",
        },
    }


def historical_report():
    return {
        "metric": "price",
        "period": "24h",
        "current_value": 105.0,
        "historical_value": 100.0,
        "current_verified": True,
        "historical_verified": True,
        "current_observed_at": 2000,
        "historical_observed_at": 1000,
        "source": "historical_db",
    }


class CMISPreTradeContractTests(unittest.TestCase):
    def test_complete_pass_is_ok_but_never_authorizes_execution(self):
        response = build_pre_trade_check_response(raw_risk(), trade())

        self.assertEqual(response["service"], "pre_trade_check")
        self.assertEqual(response["chain"], "x1")
        self.assertEqual(response["status"], OK)
        self.assertEqual(response["asset"], {"symbol": "REF", "mint": MINT})
        self.assertEqual(response["risk"]["recommendation"], PASS)
        self.assertTrue(response["risk"]["analysis_only"])
        self.assertFalse(response["risk"]["execution_authorized"])
        self.assertTrue(response["data"]["analysis_only"])
        self.assertFalse(response["data"]["execution_authorized"])
        self.assertEqual(response["data"]["trade"]["notional_usd"], 1000.0)
        self.assertEqual(
            response["sources"],
            [{"source": "pre_trade_engine", "role": "pre_trade_check"}],
        )
        self.assertEqual(response["warnings"], [])
        self.assertEqual(response["errors"], [])

    def test_fully_verified_upstream_block_is_service_ok(self):
        response = build_pre_trade_check_response(
            raw_risk(recommendation=BLOCK),
            trade(),
        )

        self.assertEqual(response["status"], OK)
        self.assertEqual(response["risk"]["recommendation"], BLOCK)
        self.assertIn("risk_check_block", response["risk"]["flags"])
        self.assertFalse(response["risk"]["execution_authorized"])

    def test_verified_asset_mismatch_is_ok_service_with_block_finding(self):
        response = build_pre_trade_check_response(
            raw_risk(),
            trade(mint="DifferentMint"),
        )

        self.assertEqual(response["status"], OK)
        self.assertEqual(response["risk"]["recommendation"], BLOCK)
        self.assertIn("trade_asset_mismatch", response["risk"]["flags"])
        self.assertFalse(response["confidence"]["complete"])
        # A false match predicate is a verified blocking fact, not missing data.
        self.assertNotEqual(response["status"], PARTIAL)

    def test_incomplete_risk_evidence_is_partial_and_warns(self):
        response = build_pre_trade_check_response(
            raw_risk(recommendation=PASS, verified=7, total=8),
            trade(),
        )

        self.assertEqual(response["status"], PARTIAL)
        self.assertEqual(response["risk"]["recommendation"], WARN)
        self.assertIn("risk_evidence_incomplete", response["risk"]["flags"])
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("risk_evidence_incomplete", codes)

    def test_missing_verified_trade_mint_is_partial_block_not_guessed_from_symbol(self):
        response = build_pre_trade_check_response(
            raw_risk(),
            trade(mint=None),
        )

        self.assertEqual(response["status"], PARTIAL)
        self.assertEqual(response["risk"]["recommendation"], BLOCK)
        self.assertIn("trade_asset_mint_unverified", response["risk"]["flags"])

    def test_missing_risk_input_is_unavailable(self):
        response = build_pre_trade_check_response(None, trade())

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertEqual(response["risk"], None)
        self.assertEqual(response["warnings"][0]["code"], "risk_check_unavailable")
        self.assertFalse(response["data"].get("execution_authorized", False))

    def test_invalid_risk_input_is_error(self):
        response = build_pre_trade_check_response("not risk", trade())

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "invalid_risk_result")

    def test_invalid_trade_input_is_error(self):
        response = build_pre_trade_check_response(raw_risk(), "not trade")

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "invalid_trade_context")

    def test_core_validation_error_becomes_service_error(self):
        response = build_pre_trade_check_response(
            raw_risk(recommendation="MAYBE"),
            trade(),
        )

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "pre_trade_check_validation_error")

    def test_full_cmis_risk_envelope_flows_directly_and_preserves_sources(self):
        risk_response = build_risk_check_response(
            market_report(),
            tokenomics_report(),
            historical_report(),
            chain="x1",
            observed_at=2000,
        )
        response = build_pre_trade_check_response(
            risk_response,
            trade(side="sell", notional_usd=2500),
        )

        self.assertEqual(risk_response["status"], OK)
        self.assertEqual(response["status"], OK)
        self.assertEqual(response["risk"]["recommendation"], PASS)
        self.assertEqual(response["data"]["trade"]["side"], "sell")
        self.assertEqual(response["data"]["trade"]["notional_usd"], 2500.0)
        self.assertEqual(response["observed_at"], 2000)
        self.assertIn(
            {
                "source": "X1.Ninja/XDEX",
                "role": "market_report",
                "observed_at": 2000,
            },
            response["sources"],
        )
        self.assertIn(
            {"source": "risk_engine", "role": "risk_check"},
            response["sources"],
        )
        self.assertIn(
            {"source": "pre_trade_engine", "role": "pre_trade_check"},
            response["sources"],
        )
        self.assertFalse(response["risk"]["execution_authorized"])

    def test_upstream_unavailable_risk_envelope_propagates_unavailable(self):
        upstream = build_service_envelope(
            "risk_check",
            "x1",
            UNAVAILABLE,
            warnings=[{"code": "market_report_unavailable"}],
            sources=[{"source": "risk_engine", "role": "risk_check"}],
            observed_at=2000,
        )
        response = build_pre_trade_check_response(upstream, trade())

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertEqual(response["warnings"][0]["code"], "market_report_unavailable")
        self.assertEqual(response["observed_at"], 2000)
        self.assertIn(
            {"source": "risk_engine", "role": "risk_check"},
            response["sources"],
        )

    def test_upstream_error_risk_envelope_propagates_error(self):
        upstream = build_service_envelope(
            "risk_check",
            "x1",
            ERROR,
            errors=[{"code": "risk_check_validation_error"}],
        )
        response = build_pre_trade_check_response(upstream, trade())

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "risk_check_validation_error")

    def test_malformed_ok_risk_envelope_without_risk_is_error(self):
        upstream = build_service_envelope("risk_check", "x1", OK, risk=None)
        response = build_pre_trade_check_response(upstream, trade())

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "invalid_risk_check_envelope")

    def test_chain_is_explicit_for_future_provider_reuse(self):
        response = build_pre_trade_check_response(
            raw_risk(chain="solana"),
            trade(chain="Solana"),
            chain="Solana",
        )

        self.assertEqual(response["chain"], "solana")
        self.assertEqual(response["status"], OK)
        self.assertEqual(response["risk"]["recommendation"], PASS)

    def test_explicit_observed_at_overrides_upstream_observation_time(self):
        upstream = build_service_envelope(
            "risk_check",
            "x1",
            OK,
            risk=raw_risk(),
            observed_at=1000,
        )
        response = build_pre_trade_check_response(
            upstream,
            trade(),
            observed_at="2026-08-15T11:03:00Z",
        )

        self.assertEqual(response["observed_at"], "2026-08-15T11:03:00Z")
        self.assertEqual(response["status"], OK)


if __name__ == "__main__":
    unittest.main()
