import unittest

from liquidity_scout.services import (
    BLOCK,
    PASS,
    WARN,
    build_pre_trade_check,
    build_risk_check,
)


MINT = "ReferenceMint"


def risk_result(*, recommendation=PASS, chain="x1", mint=MINT, verified=8, total=8):
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


def trade(*, side="buy", mint=MINT, symbol="REF", chain=None, notional_usd=None):
    value = {
        "side": side,
        "asset": {"symbol": symbol, "mint": mint},
    }
    if chain is not None:
        value["chain"] = chain
    if notional_usd is not None:
        value["notional_usd"] = notional_usd
    return value


def market_report(**overrides):
    value = {
        "symbol": "REF",
        "mint": MINT,
        "liquidity_usd": 100000.0,
        "volume_24h_usd": 50000.0,
        "transactions_24h": 250,
        "completeness": {
            "liquidity": True,
            "volume_24h": True,
            "transactions_24h": True,
            "holders": False,
            "price": True,
        },
    }
    value.update(overrides)
    return value


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


class PreTradeCheckCoreTests(unittest.TestCase):
    def test_clean_verified_risk_and_matching_identity_pass_with_no_execution_authority(self):
        result = build_pre_trade_check(
            risk_result(),
            trade(notional_usd=1000),
        )

        self.assertEqual(result["recommendation"], PASS)
        self.assertEqual(result["chain"], "x1")
        self.assertEqual(result["asset"], {"symbol": "REF", "mint": MINT})
        self.assertEqual(result["trade"]["side"], "buy")
        self.assertEqual(result["trade"]["notional_usd"], 1000.0)
        self.assertEqual(result["flags"], [])
        self.assertTrue(result["confidence"]["complete"])
        self.assertTrue(result["analysis_only"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(
            result["authorization_reason"],
            "pre_trade_check_analysis_only",
        )
        self.assertIn("price_impact", result["assessment_scope"]["not_yet_included"])
        self.assertIn("slippage", result["assessment_scope"]["not_yet_included"])
        self.assertIn("execution_authorization", result["assessment_scope"]["not_yet_included"])

    def test_risk_warn_propagates_to_pre_trade_warn(self):
        result = build_pre_trade_check(
            risk_result(recommendation=WARN),
            trade(),
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertEqual(result["components"]["risk_gate"]["status"], WARN)
        self.assertIn("risk_check_warn", result["flags"])

    def test_risk_block_propagates_to_pre_trade_block(self):
        result = build_pre_trade_check(
            risk_result(recommendation=BLOCK),
            trade(),
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(result["components"]["risk_gate"]["status"], BLOCK)
        self.assertIn("risk_check_block", result["flags"])
        self.assertFalse(result["execution_authorized"])

    def test_incomplete_risk_evidence_warns_even_if_upstream_recommendation_is_pass(self):
        result = build_pre_trade_check(
            risk_result(recommendation=PASS, verified=7, total=8),
            trade(),
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertIn("risk_evidence_incomplete", result["flags"])
        self.assertFalse(result["confidence"]["checks"]["risk_evidence_complete"])

    def test_trade_mint_mismatch_blocks_clean_risk(self):
        result = build_pre_trade_check(
            risk_result(),
            trade(mint="DifferentMint"),
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(result["components"]["identity"]["status"], BLOCK)
        self.assertIn("trade_asset_mismatch", result["flags"])
        self.assertFalse(result["confidence"]["checks"]["asset_identity_matches"])

    def test_missing_trade_mint_blocks_instead_of_guessing_from_symbol(self):
        result = build_pre_trade_check(
            risk_result(),
            trade(mint=None),
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertIn("trade_asset_mint_unverified", result["flags"])
        self.assertNotIn("trade_asset_mismatch", result["flags"])

    def test_missing_risk_mint_blocks_instead_of_treating_symbol_as_identity(self):
        result = build_pre_trade_check(
            risk_result(mint=None),
            trade(),
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertIn("risk_asset_mint_unverified", result["flags"])
        self.assertIsNone(result["asset"]["mint"])

    def test_target_chain_mismatch_with_risk_result_blocks(self):
        result = build_pre_trade_check(
            risk_result(chain="solana"),
            trade(),
            chain="x1",
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertIn("risk_chain_mismatch", result["flags"])
        self.assertFalse(result["confidence"]["checks"]["chain_consistent"])

    def test_explicit_trade_chain_mismatch_blocks(self):
        result = build_pre_trade_check(
            risk_result(chain="x1"),
            trade(chain="solana"),
            chain="x1",
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertIn("trade_chain_mismatch", result["flags"])

    def test_chain_is_normalized_for_future_provider_reuse(self):
        result = build_pre_trade_check(
            risk_result(chain="solana"),
            trade(chain="Solana"),
            chain="Solana",
        )

        self.assertEqual(result["chain"], "solana")
        self.assertEqual(result["trade"]["chain"], "solana")
        self.assertEqual(result["recommendation"], PASS)

    def test_notional_is_context_only_and_does_not_invent_trade_size_policy(self):
        small = build_pre_trade_check(risk_result(), trade(notional_usd=1))
        large = build_pre_trade_check(risk_result(), trade(notional_usd=1000000000))

        self.assertEqual(small["recommendation"], PASS)
        self.assertEqual(large["recommendation"], PASS)
        self.assertIn("trade_size_thresholds", large["assessment_scope"]["not_yet_included"])

    def test_invalid_side_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "trade side"):
            build_pre_trade_check(risk_result(), trade(side="swap"))

    def test_invalid_notional_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "notional_usd"):
            build_pre_trade_check(risk_result(), trade(notional_usd=-1))

    def test_invalid_risk_recommendation_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "recommendation"):
            build_pre_trade_check(risk_result(recommendation="MAYBE"), trade())

    def test_actual_risk_check_output_flows_directly_into_pre_trade_core(self):
        risk = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(),
        )

        result = build_pre_trade_check(
            risk,
            trade(side="sell", notional_usd=2500),
        )

        self.assertEqual(risk["recommendation"], PASS)
        self.assertEqual(result["recommendation"], PASS)
        self.assertEqual(result["trade"]["side"], "sell")
        self.assertEqual(result["trade"]["asset"]["mint"], MINT)
        self.assertTrue(result["confidence"]["complete"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
