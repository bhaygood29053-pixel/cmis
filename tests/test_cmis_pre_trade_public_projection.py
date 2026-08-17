import unittest

from liquidity_scout.services import PASS, build_pre_trade_check_response


MINT = "MINT_AGI"


def risk_result(*, liquidity=100000.0):
    return {
        "chain": "x1",
        "asset": {"symbol": "AGI", "mint": MINT},
        "recommendation": PASS,
        "components": {
            "liquidity": {
                "status": PASS,
                "flags": [],
                "reasons": [],
                "evidence": {"liquidity_usd": liquidity},
            },
        },
        "confidence": {
            "level": "high",
            "verified_checks": 8,
            "total_checks": 8,
            "verification_ratio": 1.0,
            "checks": {"liquidity_verified": True},
        },
        "flags": [],
        "reasons": [],
    }


def trade(*, notional_usd=2500):
    return {
        "side": "buy",
        "asset": {"symbol": "AGI", "mint": MINT},
        "notional_usd": notional_usd,
    }


class CMISPreTradePublicProjectionTests(unittest.TestCase):
    def test_projects_verified_liquidity_and_size_ratio_without_recalculation_surface(self):
        response = build_pre_trade_check_response(risk_result(), trade())

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["data"]["market"]["verified_liquidity_usd"], 100000.0)
        self.assertIsNone(response["data"]["market"]["verified_volume_24h_usd"])
        self.assertEqual(response["data"]["trade_size"]["assessment"], "PASS")
        self.assertEqual(
            response["data"]["trade_size"]["notional_to_liquidity_ratio"],
            0.025,
        )
        self.assertTrue(response["data"]["trade_size"]["assessment_complete"])

    def test_route_projection_preserves_unavailable_execution_estimates_as_null(self):
        response = build_pre_trade_check_response(risk_result(), trade())
        route = response["data"]["route_analysis"]

        self.assertEqual(route["status"], "unavailable")
        self.assertIsNone(route["route_scope"])
        self.assertIsNone(route["estimated_price_impact_percent"])
        self.assertIsNone(route["estimated_slippage_percent"])
        self.assertIsNone(route["estimated_fees"])
        self.assertIsNone(route["route_quality"])
        self.assertIsNone(route["bridge_dependency"])
        self.assertIsNone(route["transaction_simulation"])

    def test_projection_preserves_capability_reason_codes(self):
        response = build_pre_trade_check_response(risk_result(), trade())
        capabilities = response["data"]["execution_capabilities"]

        self.assertEqual(capabilities["slippage"]["status"], "unavailable")
        self.assertIsNone(capabilities["slippage"]["value"])
        self.assertEqual(
            capabilities["slippage"]["reason_code"],
            "verified_slippage_evidence_unavailable",
        )
        self.assertFalse(response["data"]["execution_authorized"])

    def test_explicit_policy_thresholds_are_projected_from_core_evidence(self):
        response = build_pre_trade_check_response(
            risk_result(),
            trade(notional_usd=10000),
            policy={
                "warn_notional_to_liquidity_ratio": 0.05,
                "block_notional_to_liquidity_ratio": 0.10,
            },
        )

        size = response["data"]["trade_size"]
        self.assertEqual(size["assessment"], "BLOCK")
        self.assertEqual(size["warn_threshold_notional_usd"], 5000.0)
        self.assertEqual(size["hard_block_notional_usd_threshold"], 10000.0)
        self.assertEqual(response["risk"]["recommendation"], "BLOCK")

    def test_unverified_liquidity_is_not_exposed_as_verified_market_fact(self):
        risk = risk_result()
        risk["confidence"]["checks"]["liquidity_verified"] = False
        response = build_pre_trade_check_response(risk, trade())

        self.assertEqual(response["status"], "partial")
        self.assertIsNone(response["data"]["market"]["verified_liquidity_usd"])
        self.assertFalse(response["data"]["trade_size"]["assessment_complete"])


if __name__ == "__main__":
    unittest.main()
