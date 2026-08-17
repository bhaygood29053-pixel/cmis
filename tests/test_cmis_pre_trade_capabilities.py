import unittest

from liquidity_scout.services import PASS, build_pre_trade_check, build_pre_trade_check_response
from liquidity_scout.services.pre_trade_capabilities import CAPABILITY_NAMES


MINT = "MINT_AGI"


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


class CMISPreTradeCapabilityTests(unittest.TestCase):
    def test_unsupported_execution_estimates_are_machine_readable_without_guessing(self):
        result = build_pre_trade_check(raw_risk(), trade())

        self.assertEqual(result["recommendation"], "PASS")
        self.assertEqual(set(result["execution_capabilities"]), set(CAPABILITY_NAMES))
        for name, record in result["execution_capabilities"].items():
            self.assertEqual(record["status"], "unavailable", name)
            self.assertIsNone(record["value"], name)
            self.assertTrue(record["reason_code"], name)
            self.assertTrue(record["required_evidence"], name)
        self.assertTrue(
            result["components"]["execution_capabilities"]["evidence"][
                "all_required_capabilities_available"
            ]
        )
        self.assertTrue(result["confidence"]["complete"])
        self.assertFalse(result["execution_authorized"])

    def test_requiring_unavailable_slippage_fails_closed_without_fabricating_percent(self):
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["slippage"]},
        )

        self.assertEqual(result["recommendation"], "BLOCK")
        self.assertIn("required_pretrade_capability_unavailable", result["flags"])
        self.assertEqual(
            result["components"]["execution_capabilities"]["evidence"][
                "unavailable_required_capabilities"
            ],
            ["slippage"],
        )
        self.assertIsNone(result["execution_capabilities"]["slippage"]["value"])
        self.assertFalse(
            result["confidence"]["checks"][
                "required_execution_capabilities_available"
            ]
        )
        self.assertFalse(result["execution_authorized"])

    def test_multiple_required_capabilities_are_deduplicated_and_all_reported(self):
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={
                "required_capabilities": [
                    "slippage",
                    "route_quality",
                    "slippage",
                ]
            },
        )

        self.assertEqual(
            result["policy"]["required_capabilities"],
            ["slippage", "route_quality"],
        )
        self.assertEqual(
            result["components"]["execution_capabilities"]["evidence"][
                "unavailable_required_capabilities"
            ],
            ["slippage", "route_quality"],
        )

    def test_unknown_required_capability_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "unsupported required pre-trade capability",
        ):
            build_pre_trade_check(
                raw_risk(),
                trade(),
                policy={"required_capabilities": ["magic_route_score"]},
            )

    def test_required_capability_gap_is_partial_service_block(self):
        response = build_pre_trade_check_response(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["transaction_simulation"]},
        )

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["risk"]["recommendation"], "BLOCK")
        self.assertIn(
            "required_pretrade_capability_unavailable",
            response["risk"]["flags"],
        )
        self.assertEqual(
            response["data"]["execution_capabilities"]["transaction_simulation"][
                "status"
            ],
            "unavailable",
        )
        self.assertIsNone(
            response["data"]["execution_capabilities"]["transaction_simulation"][
                "value"
            ]
        )
        self.assertFalse(response["data"]["execution_authorized"])

    def test_unknown_required_capability_becomes_service_error(self):
        response = build_pre_trade_check_response(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["magic_route_score"]},
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "pre_trade_check_validation_error",
        )


if __name__ == "__main__":
    unittest.main()
