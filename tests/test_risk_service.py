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


class RiskCheckCoreTests(unittest.TestCase):
    def test_verified_low_risk_facts_pass_without_inventing_score(self):
        result = build_risk_check(market_report(), tokenomics_report())

        self.assertEqual(result["recommendation"], PASS)
        self.assertEqual(result["chain"], "x1")
        self.assertEqual(result["asset"], {"symbol": "REF", "mint": MINT})
        self.assertEqual(result["flags"], [])
        self.assertEqual(result["confidence"]["level"], "high")
        self.assertEqual(result["confidence"]["verified_checks"], 7)
        self.assertIsNone(result["score"])
        self.assertFalse(result["score_verified"])
        self.assertEqual(result["score_reason"], "risk_score_not_calibrated")
        self.assertIn(
            "historical_volatility",
            result["assessment_scope"]["not_yet_included"],
        )

    def test_active_mint_authority_warns_but_does_not_block(self):
        tokenomics = tokenomics_report(
            mint_authority_state="active",
        )

        result = build_risk_check(market_report(), tokenomics)

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

        result = build_risk_check(market_report(), tokenomics)

        self.assertEqual(result["recommendation"], WARN)
        self.assertIn("freeze_authority_active", result["flags"])

    def test_verified_zero_asset_wide_liquidity_blocks(self):
        market = market_report(liquidity_usd=0)

        result = build_risk_check(market, tokenomics_report())

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(result["components"]["liquidity"]["status"], BLOCK)
        self.assertIn("zero_verified_liquidity", result["flags"])

    def test_incomplete_liquidity_is_not_compared_as_verified_total(self):
        market = market_report(liquidity_usd=500.0)
        market["completeness"] = dict(market["completeness"], liquidity=False)

        result = build_risk_check(
            market,
            tokenomics_report(),
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
        result = build_risk_check(market_report())

        self.assertEqual(result["recommendation"], WARN)
        self.assertEqual(result["components"]["tokenomics"]["status"], WARN)
        self.assertFalse(result["components"]["tokenomics"]["available"])
        self.assertIn("tokenomics_unavailable", result["flags"])
        self.assertEqual(result["confidence"]["level"], "low")
        self.assertEqual(result["confidence"]["verified_checks"], 3)

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

        result = build_risk_check(market_report(), tokenomics)
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
            chain="Solana",
        )

        self.assertEqual(result["chain"], "solana")
        self.assertEqual(result["recommendation"], PASS)

    def test_invalid_policy_fails_closed(self):
        with self.assertRaises(ValueError):
            build_risk_check(
                market_report(),
                tokenomics_report(),
                policy={"minimum_liquidity_usd": -1},
            )

        with self.assertRaises(ValueError):
            build_risk_check(
                market_report(),
                tokenomics_report(),
                policy={"made_up_threshold": 1},
            )

        with self.assertRaises(ValueError):
            build_risk_check(
                market_report(),
                tokenomics_report(),
                policy={"block_on_zero_liquidity": "yes"},
            )


if __name__ == "__main__":
    unittest.main()
