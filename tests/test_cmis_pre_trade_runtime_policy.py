import unittest
from unittest.mock import patch

from liquidity_scout.cmis.gateway import CMISGateway
from liquidity_scout.cmis.pre_trade_policy_gateway import PreTradePolicyMixin
from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.services import PASS, build_service_envelope


MINT = "MINT_AGI"


class PolicyGateway(PreTradePolicyMixin, CMISGateway):
    pass


def risk_envelope(*, liquidity=100000.0):
    return build_service_envelope(
        "risk_check",
        "x1",
        "ok",
        asset={"symbol": "AGI", "mint": MINT},
        risk={
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
        },
        observed_at=123.0,
    )


class CMISPreTradeRuntimePolicyTests(unittest.TestCase):
    def setUp(self):
        self.gateway = PolicyGateway()

    def test_runtime_uses_separate_risk_and_pretrade_policies(self):
        risk = risk_envelope()
        with patch.object(self.gateway, "_risk_check", return_value=risk) as risk_check:
            response = self.gateway.dispatch({
                "service": "pre_trade_check",
                "chain": "x1",
                "asset": "AGI",
                "params": {
                    "trade": {"side": "buy", "notional_usd": 10000},
                    "policy": {"minimum_liquidity_usd": 1000},
                    "historical_question": "Has price changed in the last 24 hours?",
                    "pre_trade_policy": {
                        "warn_notional_to_liquidity_ratio": 0.05,
                        "block_notional_to_liquidity_ratio": 0.10,
                    },
                },
            })

        risk_check.assert_called_once_with(
            "AGI",
            {
                "policy": {"minimum_liquidity_usd": 1000},
                "historical_question": "Has price changed in the last 24 hours?",
            },
        )
        self.assertEqual(response["service"], "pre_trade_check")
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["risk"]["recommendation"], "BLOCK")
        self.assertEqual(
            response["risk"]["components"]["trade_size_liquidity"]["evidence"]["notional_to_liquidity_ratio"],
            0.10,
        )
        self.assertIn("trade_size_exceeds_liquidity_block_ratio", response["risk"]["flags"])
        self.assertFalse(response["risk"]["execution_authorized"])

    def test_caller_liquidity_fields_are_not_used_as_pretrade_evidence(self):
        risk = risk_envelope(liquidity=100000.0)
        with patch.object(self.gateway, "_risk_check", return_value=risk):
            response = self.gateway.dispatch({
                "service": "pre_trade_check",
                "chain": "x1",
                "asset": "AGI",
                "params": {
                    "trade": {"side": "buy", "notional_usd": 10000},
                    "pre_trade_policy": {
                        "block_notional_to_liquidity_ratio": 0.10,
                    },
                    # These are deliberately ignored. Market evidence must come
                    # from the internally produced risk result.
                    "liquidity_usd": 1000000000,
                    "market_report": {"liquidity_usd": 1000000000},
                },
            })

        evidence = response["risk"]["components"]["trade_size_liquidity"]["evidence"]
        self.assertEqual(evidence["liquidity_usd"], 100000.0)
        self.assertEqual(evidence["notional_to_liquidity_ratio"], 0.10)
        self.assertEqual(response["risk"]["recommendation"], "BLOCK")

    def test_invalid_pretrade_policy_fails_before_risk_collection(self):
        with patch.object(self.gateway, "_risk_check") as risk_check:
            response = self.gateway.dispatch({
                "service": "pre_trade_check",
                "chain": "x1",
                "asset": "AGI",
                "params": {
                    "trade": {"side": "buy", "notional_usd": 1000},
                    "pre_trade_policy": "ten percent",
                },
            })

        risk_check.assert_not_called()
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "invalid_pre_trade_policy")

    def test_runtime_gateway_mro_uses_pretrade_policy_mixin(self):
        self.assertTrue(issubclass(RuntimeCMISGateway, PreTradePolicyMixin))
        self.assertIs(
            RuntimeCMISGateway._pre_trade_check,
            PreTradePolicyMixin._pre_trade_check,
        )


if __name__ == "__main__":
    unittest.main()
