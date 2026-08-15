import unittest

from liquidity_scout.services import BLOCK, PASS, WARN, build_risk_check


MINT = "ReferenceMint"


def market_profile(**overrides):
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
    }
    report.update(overrides)
    return report


def tokenomics_profile(**overrides):
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
    }
    report.update(overrides)
    return report


def history_profile(**overrides):
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


class Phase4RiskEngineSignoffTests(unittest.TestCase):
    """Deterministic Phase 4 acceptance profiles; no live-network assertions."""

    def test_healthy_verified_profile_passes(self):
        result = build_risk_check(
            market_profile(),
            tokenomics_profile(),
            history_profile(),
        )

        self.assertEqual(result["recommendation"], PASS)
        self.assertEqual(result["flags"], [])
        self.assertEqual(result["confidence"]["level"], "high")
        self.assertEqual(result["confidence"]["verified_checks"], 8)
        self.assertIsNone(result["score"])
        self.assertFalse(result["score_verified"])

    def test_active_mint_and_freeze_authorities_warn(self):
        result = build_risk_check(
            market_profile(),
            tokenomics_profile(
                mint_authority_state="active",
                freeze_authority_state="active",
            ),
            history_profile(),
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertIn("mint_authority_active", result["flags"])
        self.assertIn("freeze_authority_active", result["flags"])
        self.assertEqual(result["components"]["tokenomics"]["status"], WARN)

    def test_low_verified_liquidity_and_activity_warn_under_explicit_policy(self):
        result = build_risk_check(
            market_profile(
                liquidity_usd=25000.0,
                volume_24h_usd=5000.0,
                transactions_24h=20,
            ),
            tokenomics_profile(),
            history_profile(),
            policy={
                "minimum_liquidity_usd": 50000.0,
                "minimum_volume_24h_usd": 10000.0,
                "minimum_transactions_24h": 50,
            },
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertIn("liquidity_below_policy_minimum", result["flags"])
        self.assertIn("volume_24h_below_policy_minimum", result["flags"])
        self.assertIn("transactions_24h_below_policy_minimum", result["flags"])

    def test_zero_verified_liquidity_blocks(self):
        result = build_risk_check(
            market_profile(liquidity_usd=0.0),
            tokenomics_profile(),
            history_profile(),
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertIn("zero_verified_liquidity", result["flags"])
        self.assertEqual(result["components"]["liquidity"]["status"], BLOCK)

    def test_extreme_verified_historical_move_blocks_under_explicit_policy(self):
        result = build_risk_check(
            market_profile(),
            tokenomics_profile(),
            history_profile(current_value=35.0, historical_value=100.0),
            policy={
                "historical_price_warn_abs_change_pct": 25.0,
                "historical_price_block_abs_change_pct": 50.0,
            },
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertIn(
            "historical_price_move_exceeds_block_threshold",
            result["flags"],
        )
        self.assertEqual(result["components"]["history"]["status"], BLOCK)
        self.assertEqual(
            result["components"]["history"]["evidence"]["change_pct"],
            -65.0,
        )

    def test_missing_or_unverified_sources_warn_conservatively(self):
        market = market_profile(liquidity_usd=1000.0)
        market["completeness"] = dict(
            market["completeness"],
            liquidity=False,
            volume_24h=False,
        )
        history = history_profile(historical_verified=False)

        result = build_risk_check(
            market,
            tokenomics_report=None,
            historical_report=history,
            policy={
                "minimum_liquidity_usd": 50000.0,
                "minimum_volume_24h_usd": 10000.0,
            },
        )

        self.assertEqual(result["recommendation"], WARN)
        self.assertIn("liquidity_unverified", result["flags"])
        self.assertIn("volume_24h_unverified", result["flags"])
        self.assertIn("tokenomics_unavailable", result["flags"])
        self.assertIn("historical_price_unverified", result["flags"])
        self.assertNotIn("liquidity_below_policy_minimum", result["flags"])
        self.assertNotIn("volume_24h_below_policy_minimum", result["flags"])

    def test_combined_risks_use_worst_severity_deterministically(self):
        result = build_risk_check(
            market_profile(
                liquidity_usd=0.0,
                volume_24h_usd=0.0,
                transactions_24h=0,
            ),
            tokenomics_profile(
                mint_authority_state="active",
                freeze_authority_state="active",
            ),
            history_profile(current_value=60.0, historical_value=100.0),
            policy={
                "historical_price_warn_abs_change_pct": 20.0,
                "historical_price_block_abs_change_pct": 50.0,
            },
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(result["components"]["liquidity"]["status"], BLOCK)
        self.assertEqual(result["components"]["activity"]["status"], WARN)
        self.assertEqual(result["components"]["tokenomics"]["status"], WARN)
        self.assertEqual(result["components"]["history"]["status"], WARN)
        self.assertIn("zero_verified_liquidity", result["flags"])
        self.assertIn("zero_verified_volume_24h", result["flags"])
        self.assertIn("mint_authority_active", result["flags"])
        self.assertIn(
            "historical_price_move_exceeds_warn_threshold",
            result["flags"],
        )


if __name__ == "__main__":
    unittest.main()
