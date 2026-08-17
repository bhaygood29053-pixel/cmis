import unittest
from unittest.mock import patch

from liquidity_scout.cmis.gateway import CMISGateway
from liquidity_scout.cmis.pre_trade_policy_gateway import PreTradePolicyMixin
from liquidity_scout.services import PASS, build_pre_trade_check, build_pre_trade_check_response, build_service_envelope
from liquidity_scout.services.pre_trade_freshness import assess_risk_freshness


MINT = "MINT_AGI"


class PolicyGateway(PreTradePolicyMixin, CMISGateway):
    pass


def raw_risk():
    return {
        "chain": "x1",
        "asset": {"symbol": "AGI", "mint": MINT},
        "recommendation": PASS,
        "components": {
            "liquidity": {
                "status": PASS,
                "flags": [],
                "reasons": [],
                "evidence": {"liquidity_usd": 100000.0},
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


def trade():
    return {
        "side": "buy",
        "asset": {"symbol": "AGI", "mint": MINT},
        "notional_usd": 1000,
    }


def risk_envelope(*, observed_at=1000):
    return build_service_envelope(
        "risk_check",
        "x1",
        "ok",
        asset={"symbol": "AGI", "mint": MINT},
        risk=raw_risk(),
        observed_at=observed_at,
    )


class PreTradeFreshnessTests(unittest.TestCase):
    def test_no_age_policy_does_not_invent_freshness_requirement(self):
        result = build_pre_trade_check(raw_risk(), trade())

        self.assertEqual(result["recommendation"], "PASS")
        freshness = result["components"]["freshness"]
        self.assertEqual(freshness["status"], "PASS")
        self.assertFalse(freshness["evidence"]["freshness_policy_active"])
        self.assertTrue(freshness["evidence"]["freshness_assessment_complete"])
        self.assertTrue(result["confidence"]["complete"])

    def test_explicit_age_policy_warns_and_blocks_from_verified_age(self):
        policy = {
            "warn_risk_age_seconds": 60,
            "block_risk_age_seconds": 90,
        }
        warn = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy=policy,
            risk_observed_at=1000,
            evaluated_at=1070,
        )
        block = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy=policy,
            risk_observed_at=1000,
            evaluated_at=1100,
        )

        self.assertEqual(warn["recommendation"], "WARN")
        self.assertIn("risk_evidence_stale_warn", warn["flags"])
        self.assertEqual(block["recommendation"], "BLOCK")
        self.assertIn("risk_evidence_stale_block", block["flags"])
        evidence = block["components"]["freshness"]["evidence"]
        self.assertEqual(evidence["risk_age_seconds"], 100.0)
        self.assertTrue(evidence["freshness_assessment_complete"])
        self.assertTrue(block["confidence"]["complete"])

    def test_missing_timestamp_under_active_policy_blocks_as_incomplete(self):
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={"block_risk_age_seconds": 90},
            risk_observed_at=None,
            evaluated_at=1100,
        )

        self.assertEqual(result["recommendation"], "BLOCK")
        self.assertIn("risk_timestamp_unverified_for_freshness", result["flags"])
        self.assertFalse(result["confidence"]["complete"])
        self.assertFalse(
            result["confidence"]["checks"]["risk_freshness_assessment_complete"]
        )

    def test_timestamp_after_evaluation_fails_closed(self):
        result = assess_risk_freshness(
            risk_observed_at=1200,
            evaluated_at=1100,
            policy={"block_risk_age_seconds": 90},
        )

        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("risk_timestamp_after_evaluation", result["flags"])
        self.assertFalse(result["evidence"]["freshness_assessment_complete"])

    def test_iso_z_timestamp_is_supported_deterministically(self):
        result = assess_risk_freshness(
            risk_observed_at="2026-08-17T19:00:00Z",
            evaluated_at="2026-08-17T19:01:30+00:00",
            policy={"block_risk_age_seconds": 90},
        )

        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["evidence"]["risk_age_seconds"], 90.0)

    def test_invalid_age_policy_order_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "block_risk_age_seconds"):
            assess_risk_freshness(
                risk_observed_at=1000,
                evaluated_at=1100,
                policy={
                    "warn_risk_age_seconds": 100,
                    "block_risk_age_seconds": 90,
                },
            )

    def test_verified_stale_risk_is_service_ok_with_block_finding(self):
        response = build_pre_trade_check_response(
            risk_envelope(observed_at=1000),
            trade(),
            policy={"block_risk_age_seconds": 90},
            evaluated_at=1100,
        )

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["risk"]["recommendation"], "BLOCK")
        self.assertIn("risk_evidence_stale_block", response["risk"]["flags"])
        self.assertEqual(response["data"]["risk_observed_at"], 1000)
        self.assertEqual(response["data"]["evaluated_at"], 1100)

    def test_missing_envelope_timestamp_is_partial_under_age_policy(self):
        response = build_pre_trade_check_response(
            risk_envelope(observed_at=None),
            trade(),
            policy={"block_risk_age_seconds": 90},
            evaluated_at=1100,
        )

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["risk"]["recommendation"], "BLOCK")
        self.assertIn("risk_timestamp_unverified_for_freshness", response["risk"]["flags"])

    def test_output_observed_at_override_cannot_replace_risk_evidence_timestamp(self):
        response = build_pre_trade_check_response(
            risk_envelope(observed_at=1000),
            trade(),
            policy={"block_risk_age_seconds": 90},
            evaluated_at=1100,
            observed_at=1099,
        )

        self.assertEqual(response["observed_at"], 1099)
        self.assertEqual(response["data"]["risk_observed_at"], 1000)
        self.assertEqual(
            response["risk"]["components"]["freshness"]["evidence"]["risk_age_seconds"],
            100.0,
        )
        self.assertEqual(response["risk"]["recommendation"], "BLOCK")

    def test_runtime_ignores_caller_evaluated_at_and_uses_internal_clock(self):
        gateway = PolicyGateway()
        gateway.pre_trade_now_fn = lambda: 1100
        risk = risk_envelope(observed_at=1000)

        with patch.object(gateway, "_risk_check", return_value=risk):
            response = gateway.dispatch({
                "service": "pre_trade_check",
                "chain": "x1",
                "asset": "AGI",
                "params": {
                    "trade": {"side": "buy", "notional_usd": 1000},
                    "pre_trade_policy": {"block_risk_age_seconds": 90},
                    "evaluated_at": 1001,
                },
            })

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["data"]["evaluated_at"], 1100.0)
        self.assertEqual(response["risk"]["recommendation"], "BLOCK")
        self.assertEqual(
            response["risk"]["components"]["freshness"]["evidence"]["risk_age_seconds"],
            100.0,
        )


if __name__ == "__main__":
    unittest.main()
