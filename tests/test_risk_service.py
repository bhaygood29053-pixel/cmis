import unittest

from liquidity_scout.services import BLOCK, PASS, WARN, build_risk_check


MINT = "ReferenceMint"


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


def tokenomics_report(**overrides):
    value = {
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
    value.update(overrides)
    return value


def historical_report(**overrides):
    value = {
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
    value.update(overrides)
    return value


def freshness_report(*, unverified=()):
    fields = {
        "price_usd": {
            "freshness_verified": True,
            "reason": "timestamped_provider_price_matches_current_market_price",
        },
        "liquidity_usd": {
            "freshness_verified": True,
            "reason": "verified_test_fixture",
        },
        "volume_24h_usd": {
            "freshness_verified": True,
            "reason": "verified_test_fixture",
        },
        "transactions_24h": {
            "freshness_verified": True,
            "reason": "verified_test_fixture",
        },
    }
    for name in unverified:
        fields[name] = {
            "freshness_verified": False,
            "reason": f"{name}_freshness_not_verified",
        }
    verified = sum(
        1 for item in fields.values() if item["freshness_verified"] is True
    )
    return {
        "contract_version": "x1_current_market_freshness/v1",
        "freshness_state": "VERIFIED" if verified == 4 else ("PARTIAL" if verified else "NOT_VERIFIED"),
        "evaluated_at": 3000,
        "current_market_freshness_verified": verified == 4,
        "verified_field_count": verified,
        "total_field_count": 4,
        "fields": fields,
    }


class RiskCheckCoreTests(unittest.TestCase):
    def test_verified_current_market_freshness_is_included_without_changing_pass(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(),
            freshness_report(),
        )

        self.assertEqual(result["recommendation"], PASS)
        self.assertEqual(result["components"]["freshness"]["status"], PASS)
        self.assertEqual(result["confidence"]["verified_checks"], 12)
        self.assertEqual(result["confidence"]["total_checks"], 12)
        self.assertIn(
            "current_market_freshness",
            result["assessment_scope"]["included"],
        )

    def test_unverified_market_freshness_warns_fail_closed(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(),
            freshness_report(
                unverified=(
                    "liquidity_usd",
                    "volume_24h_usd",
                    "transactions_24h",
                )
            ),
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertEqual(result["components"]["freshness"]["status"], WARN)
        self.assertIn("liquidity_freshness_unverified", result["flags"])
        self.assertIn("volume_24h_freshness_unverified", result["flags"])
        self.assertIn("transactions_24h_freshness_unverified", result["flags"])
        self.assertNotIn("price_freshness_unverified", result["flags"])
        self.assertFalse(
            result["confidence"]["checks"]["liquidity_usd_freshness_verified"]
        )
        self.assertTrue(
            result["confidence"]["checks"]["price_usd_freshness_verified"]
        )

    def test_malformed_freshness_contract_fails_closed(self):
        invalid = freshness_report()
        invalid["contract_version"] = "made_up_freshness/v1"

        with self.assertRaisesRegex(
            ValueError,
            "x1_current_market_freshness/v1",
        ):
            build_risk_check(
                market_report(),
                tokenomics_report(),
                historical_report(),
                invalid,
            )

    def test_verified_low_risk_facts_pass_without_inventing_score(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(),
        )

        self.assertEqual(result["recommendation"], PASS)
        self.assertEqual(result["chain"], "x1")
        self.assertEqual(result["asset"], {"symbol": "REF", "mint": MINT})
        self.assertEqual(result["flags"], [])
        self.assertEqual(result["confidence"]["level"], "high")
        self.assertEqual(result["confidence"]["verified_checks"], 8)
        self.assertEqual(result["confidence"]["total_checks"], 8)
        self.assertIsNone(result["score"])
        self.assertFalse(result["score_verified"])
        self.assertEqual(result["score_reason"], "risk_score_not_calibrated")
        self.assertIn(
            "historical_price_movement",
            result["assessment_scope"]["included"],
        )
        self.assertIn(
            "statistical_volatility",
            result["assessment_scope"]["not_yet_included"],
        )

    def test_active_mint_authority_warns_but_does_not_block(self):
        tokenomics = tokenomics_report(
            mint_authority_state="active",
        )

        result = build_risk_check(
            market_report(),
            tokenomics,
            historical_report(),
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertEqual(result["components"]["tokenomics"]["status"], WARN)
        self.assertIn("mint_authority_active", result["flags"])
        self.assertIn(
            "future minting remains possible",
            " ".join(result["reasons"]),
        )

    def test_active_freeze_authority_warns(self):
        tokenomics = tokenomics_report(
            freeze_authority_state="active",
        )

        result = build_risk_check(
            market_report(),
            tokenomics,
            historical_report(),
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertIn("freeze_authority_active", result["flags"])

    def test_verified_zero_asset_wide_liquidity_blocks(self):
        market = market_report(liquidity_usd=0)

        result = build_risk_check(
            market,
            tokenomics_report(),
            historical_report(),
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(result["components"]["liquidity"]["status"], BLOCK)
        self.assertIn("zero_verified_liquidity", result["flags"])

    def test_incomplete_liquidity_is_not_compared_as_verified_total(self):
        market = market_report(liquidity_usd=500.0)
        market["completeness"] = dict(market["completeness"], liquidity=False)

        result = build_risk_check(
            market,
            tokenomics_report(),
            historical_report(),
            policy={"minimum_liquidity_usd": 1000},
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertIn("liquidity_unverified", result["flags"])
        self.assertNotIn("liquidity_below_policy_minimum", result["flags"])
        self.assertTrue(result["components"]["liquidity"]["available"])

    def test_explicit_policy_thresholds_warn_on_verified_values(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(),
            policy={
                "minimum_liquidity_usd": 200000,
                "minimum_volume_24h_usd": 100000,
                "minimum_transactions_24h": 500,
            },
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertIn("liquidity_below_policy_minimum", result["flags"])
        self.assertIn("volume_24h_below_policy_minimum", result["flags"])
        self.assertIn("transactions_24h_below_policy_minimum", result["flags"])

    def test_missing_tokenomics_warns_and_reduces_confidence(self):
        result = build_risk_check(
            market_report(),
            historical_report=historical_report(),
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertEqual(result["components"]["tokenomics"]["status"], WARN)
        self.assertFalse(result["components"]["tokenomics"]["available"])
        self.assertIn("tokenomics_unavailable", result["flags"])
        self.assertEqual(result["confidence"]["level"], "medium")
        self.assertEqual(result["confidence"]["verified_checks"], 4)

    def test_unverified_token_activity_warns_without_using_lifetime_claim(self):
        tokenomics = tokenomics_report(
            token_activity={
                "available": True,
                "activity_verified": False,
                "coverage_verified": False,
                "coverage_scope": "rpc_history_exhausted",
                "lifetime_coverage_verified": True,
            }
        )

        result = build_risk_check(
            market_report(),
            tokenomics,
            historical_report(),
        )
        evidence = result["components"]["tokenomics"]["evidence"]

        self.assertEqual(result["recommendation"], WARN)
        self.assertIn("token_activity_unverified", result["flags"])
        self.assertEqual(evidence["token_activity_coverage_scope"], "rpc_history_exhausted")
        # The risk core preserves the supplied fact as evidence but never uses
        # lifetime coverage to upgrade failed selected-window verification.
        self.assertTrue(evidence["lifetime_coverage_verified"])
        self.assertEqual(result["components"]["tokenomics"]["status"], WARN)

    def test_chain_is_explicit_and_normalized_for_future_cmis_use(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(),
            chain="Solana",
        )

        self.assertEqual(result["chain"], "solana")
        self.assertEqual(result["recommendation"], PASS)

    def test_missing_history_warns_and_reduces_confidence(self):
        result = build_risk_check(market_report(), tokenomics_report())

        self.assertEqual(result["recommendation"], WARN)
        self.assertIn("historical_price_unavailable", result["flags"])
        self.assertFalse(result["components"]["history"]["available"])
        self.assertEqual(result["confidence"]["level"], "medium")
        self.assertEqual(result["confidence"]["verified_checks"], 7)
        self.assertFalse(
            result["confidence"]["checks"]["historical_price_verified"]
        )

    def test_large_verified_move_does_not_warn_without_explicit_threshold(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(current_value=190.0, historical_value=100.0),
        )

        self.assertEqual(result["recommendation"], PASS)
        history = result["components"]["history"]
        self.assertEqual(history["status"], PASS)
        self.assertEqual(history["evidence"]["change_pct"], 90.0)
        self.assertEqual(history["evidence"]["absolute_change_pct"], 90.0)

    def test_explicit_historical_warning_threshold_warns(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(current_value=125.0, historical_value=100.0),
            policy={"historical_price_warn_abs_change_pct": 20},
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertEqual(result["components"]["history"]["status"], WARN)
        self.assertIn(
            "historical_price_move_exceeds_warn_threshold",
            result["flags"],
        )

    def test_explicit_historical_block_threshold_blocks(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(current_value=40.0, historical_value=100.0),
            policy={
                "historical_price_warn_abs_change_pct": 20,
                "historical_price_block_abs_change_pct": 50,
            },
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(result["components"]["history"]["status"], BLOCK)
        self.assertIn(
            "historical_price_move_exceeds_block_threshold",
            result["flags"],
        )
        self.assertEqual(
            result["components"]["history"]["evidence"]["change_pct"],
            -60.0,
        )

    def test_history_change_is_recomputed_not_trusted_from_caller(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(
                current_value=80.0,
                historical_value=100.0,
                change_pct=1.0,
            ),
            policy={"historical_price_warn_abs_change_pct": 15},
        )

        history = result["components"]["history"]
        self.assertEqual(history["evidence"]["change_pct"], -20.0)
        self.assertEqual(history["evidence"]["absolute_change_pct"], 20.0)
        self.assertEqual(history["status"], WARN)

    def test_unverified_history_warns_fail_closed(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(historical_verified=False),
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertIn("historical_price_unverified", result["flags"])
        self.assertFalse(
            result["confidence"]["checks"]["historical_price_verified"]
        )

    def test_zero_historical_price_cannot_produce_verified_change(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(historical_value=0),
        )

        self.assertEqual(result["components"]["history"]["status"], WARN)
        self.assertIn("historical_price_unverified", result["flags"])
        self.assertIsNone(
            result["components"]["history"]["evidence"]["change_pct"]
        )

    def test_unsupported_historical_metric_warns(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            historical_report(metric="liquidity"),
        )

        self.assertEqual(result["components"]["history"]["status"], WARN)
        self.assertIn("historical_metric_unsupported", result["flags"])

    def test_missing_history_warning_can_be_explicitly_disabled(self):
        result = build_risk_check(
            market_report(),
            tokenomics_report(),
            policy={"warn_on_missing_history": False},
        )

        self.assertEqual(result["recommendation"], PASS)
        self.assertEqual(result["components"]["history"]["status"], PASS)
        self.assertFalse(result["components"]["history"]["available"])
        self.assertEqual(result["confidence"]["level"], "medium")

    def test_invalid_policy_fails_closed(self):
        with self.assertRaises(ValueError):
            build_risk_check(
                market_report(),
                tokenomics_report(),
                historical_report(),
                policy={"minimum_liquidity_usd": -1},
            )

        with self.assertRaises(ValueError):
            build_risk_check(
                market_report(),
                tokenomics_report(),
                historical_report(),
                policy={"made_up_threshold": 1},
            )

        with self.assertRaises(ValueError):
            build_risk_check(
                market_report(),
                tokenomics_report(),
                historical_report(),
                policy={"block_on_zero_liquidity": "yes"},
            )

        with self.assertRaises(ValueError):
            build_risk_check(
                market_report(),
                tokenomics_report(),
                historical_report(),
                policy={
                    "historical_price_warn_abs_change_pct": 50,
                    "historical_price_block_abs_change_pct": 20,
                },
            )


if __name__ == "__main__":
    unittest.main()
