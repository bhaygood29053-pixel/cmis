import unittest

from liquidity_scout.services import BLOCK, PASS, build_pre_trade_check, build_pre_trade_check_response


ASSET_MINT = "AGI_MINT"
XNT_MINT = "So11111111111111111111111111111111111111112"
POOL = "AGI_XNT_POOL"
AMM_CONFIG = "AGI_XNT_CONFIG"
ROUTE = {
    "token_in_mint": XNT_MINT,
    "token_out_mint": ASSET_MINT,
    "pool": POOL,
    "amm_config": AMM_CONFIG,
}


def raw_risk():
    return {
        "chain": "x1",
        "asset": {"symbol": "AGI", "mint": ASSET_MINT},
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


def trade(*, include_route=True, route=None):
    value = {
        "side": "buy",
        "asset": {"symbol": "AGI", "mint": ASSET_MINT},
        "notional_usd": 1000,
    }
    if include_route:
        value["route"] = dict(ROUTE if route is None else route)
    return value


def route_evidence(*, observed_at=990, route=None, capabilities=None, source="cmis_xdex_route_resolver"):
    if capabilities is None:
        capabilities = {
            "price_impact": {
                "status": "verified",
                "semantic": "route_price_impact_percent",
                "value": 1.25,
                "unit": "percent",
                "proof_basis": [
                    "verified_direct_cp_route",
                    "verified_pool_reserves",
                    "verified_price_impact_semantics",
                ],
            },
            "fees": {
                "status": "verified",
                "semantic": "route_execution_fee_estimate",
                "value": {
                    "amm_trade_fee_rate_percent": 0.28,
                    "bounded_historical_execution_model_fee_percent": 0.28,
                },
                "unit": "structured",
                "proof_basis": [
                    "verified_amm_config_trade_fee_rate",
                    "bounded_historical_execution_corroboration",
                ],
            },
        }
    return {
        "schema_version": 1,
        "source": source,
        "chain": "x1",
        "route": dict(ROUTE if route is None else route),
        "observed_at": observed_at,
        "capabilities": capabilities,
    }


class CMISPreTradeRouteEvidenceTests(unittest.TestCase):
    def test_generic_pretrade_remains_fail_closed_without_route_evidence(self):
        result = build_pre_trade_check(raw_risk(), trade(include_route=False))

        self.assertEqual(result["recommendation"], PASS)
        self.assertFalse(result["route_evidence"]["supplied"])
        for name in ("slippage", "price_impact", "fees"):
            self.assertEqual(result["execution_capabilities"][name]["status"], "unavailable")
            self.assertIsNone(result["execution_capabilities"][name]["value"])
        self.assertFalse(result["execution_authorized"])

    def test_exact_fresh_route_can_satisfy_required_price_impact_and_fee_capabilities(self):
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["price_impact", "fees"]},
            evaluated_at=1000,
            route_evidence=route_evidence(),
            route_evidence_max_age_seconds=60,
        )

        self.assertEqual(result["recommendation"], PASS)
        self.assertEqual(result["execution_capabilities"]["price_impact"]["status"], "ok")
        self.assertEqual(result["execution_capabilities"]["price_impact"]["value"], 1.25)
        self.assertEqual(result["execution_capabilities"]["fees"]["status"], "ok")
        fees = result["execution_capabilities"]["fees"]["value"]
        self.assertEqual(fees["amm_trade_fee_rate_percent"], 0.28)
        self.assertEqual(fees["bounded_historical_execution_model_fee_percent"], 0.28)
        self.assertNotIn("quote_effective_curve_deduction_percent", fees)
        audit = result["route_evidence"]
        self.assertTrue(audit["scope_match"])
        self.assertTrue(audit["fresh"])
        self.assertEqual(set(audit["usable_capabilities"]), {"price_impact", "fees"})
        self.assertNotIn("price_impact", result["assessment_scope"]["not_yet_included"])
        self.assertNotIn("fees", result["assessment_scope"]["not_yet_included"])
        self.assertIn("verified_route_price_impact", result["assessment_scope"]["included"])
        self.assertFalse(result["execution_authorized"])

    def test_public_projection_exposes_only_core_accepted_route_values(self):
        response = build_pre_trade_check_response(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["price_impact"]},
            evaluated_at=1000,
            route_evidence=route_evidence(),
            route_evidence_max_age_seconds=60,
        )

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["risk"]["recommendation"], PASS)
        route_analysis = response["data"]["route_analysis"]
        self.assertEqual(route_analysis["status"], "partial")
        self.assertEqual(route_analysis["route_scope"], ROUTE)
        self.assertEqual(route_analysis["estimated_price_impact_percent"], 1.25)
        self.assertEqual(
            route_analysis["estimated_fees"]["amm_trade_fee_rate_percent"],
            0.28,
        )
        self.assertNotIn(
            "quote_effective_curve_deduction_percent",
            route_analysis["estimated_fees"],
        )
        self.assertIsNone(route_analysis["estimated_slippage_percent"])
        self.assertIn(
            {"source": "cmis_xdex_route_resolver", "role": "route_evidence"},
            response["sources"],
        )
        self.assertFalse(response["data"]["execution_authorized"])

    def test_quote_slippage_tolerance_is_not_accepted_as_expected_execution_slippage(self):
        evidence = route_evidence(
            capabilities={
                "slippage": {
                    "status": "verified",
                    "semantic": "quote_slippage_tolerance_percent",
                    "value": 0.5,
                    "unit": "percent",
                    "proof_basis": ["verified_xdex_quote_slippage_parameter"],
                }
            }
        )
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["slippage"]},
            evaluated_at=1000,
            route_evidence=evidence,
            route_evidence_max_age_seconds=60,
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(result["execution_capabilities"]["slippage"]["status"], "unavailable")
        self.assertIsNone(result["execution_capabilities"]["slippage"]["value"])
        self.assertEqual(
            result["execution_capabilities"]["slippage"]["reason_code"],
            "route_evidence_semantic_not_accepted",
        )
        self.assertEqual(
            result["route_evidence"]["rejected_capabilities"]["slippage"]["reason_code"],
            "route_evidence_semantic_not_accepted",
        )
        self.assertFalse(result["execution_authorized"])

    def test_arbitrary_proof_labels_cannot_promote_price_impact(self):
        evidence = route_evidence(
            capabilities={
                "price_impact": {
                    "status": "verified",
                    "semantic": "route_price_impact_percent",
                    "value": 1.25,
                    "unit": "percent",
                    "proof_basis": ["caller_says_verified"],
                }
            }
        )
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["price_impact"]},
            evaluated_at=1000,
            route_evidence=evidence,
            route_evidence_max_age_seconds=60,
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(
            result["execution_capabilities"]["price_impact"]["reason_code"],
            "route_evidence_proof_basis_not_accepted",
        )
        self.assertIsNone(result["execution_capabilities"]["price_impact"]["value"])

    def test_fee_mapping_cannot_smuggle_quote_layer_deduction(self):
        evidence = route_evidence(
            capabilities={
                "fees": {
                    "status": "verified",
                    "semantic": "route_execution_fee_estimate",
                    "value": {
                        "amm_trade_fee_rate_percent": 0.28,
                        "bounded_historical_execution_model_fee_percent": 0.28,
                        "quote_effective_curve_deduction_percent": 0.30,
                    },
                    "unit": "structured",
                    "proof_basis": [
                        "verified_amm_config_trade_fee_rate",
                        "bounded_historical_execution_corroboration",
                    ],
                }
            }
        )
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["fees"]},
            evaluated_at=1000,
            route_evidence=evidence,
            route_evidence_max_age_seconds=60,
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(
            result["execution_capabilities"]["fees"]["reason_code"],
            "route_evidence_value_invalid",
        )
        self.assertIsNone(result["execution_capabilities"]["fees"]["value"])

    def test_wrong_unit_cannot_promote_price_impact(self):
        evidence = route_evidence(
            capabilities={
                "price_impact": {
                    "status": "verified",
                    "semantic": "route_price_impact_percent",
                    "value": 1.25,
                    "unit": "basis_points",
                    "proof_basis": [
                        "verified_direct_cp_route",
                        "verified_pool_reserves",
                        "verified_price_impact_semantics",
                    ],
                }
            }
        )
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["price_impact"]},
            evaluated_at=1000,
            route_evidence=evidence,
            route_evidence_max_age_seconds=60,
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(
            result["execution_capabilities"]["price_impact"]["reason_code"],
            "route_evidence_unit_not_accepted",
        )

    def test_route_scope_mismatch_fails_closed(self):
        wrong_route = dict(ROUTE)
        wrong_route["pool"] = "DIFFERENT_POOL"
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["price_impact"]},
            evaluated_at=1000,
            route_evidence=route_evidence(route=wrong_route),
            route_evidence_max_age_seconds=60,
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertFalse(result["route_evidence"]["scope_match"])
        self.assertEqual(
            result["execution_capabilities"]["price_impact"]["reason_code"],
            "route_evidence_scope_mismatch",
        )
        self.assertIsNone(result["execution_capabilities"]["price_impact"]["value"])

    def test_route_evidence_requires_explicit_trade_route(self):
        result = build_pre_trade_check(
            raw_risk(),
            trade(include_route=False),
            policy={"required_capabilities": ["price_impact"]},
            evaluated_at=1000,
            route_evidence=route_evidence(),
            route_evidence_max_age_seconds=60,
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(
            result["execution_capabilities"]["price_impact"]["reason_code"],
            "explicit_trade_route_unavailable",
        )

    def test_stale_route_evidence_fails_closed(self):
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["price_impact"]},
            evaluated_at=1000,
            route_evidence=route_evidence(observed_at=900),
            route_evidence_max_age_seconds=60,
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(result["route_evidence"]["age_seconds"], 100.0)
        self.assertFalse(result["route_evidence"]["fresh"])
        self.assertEqual(
            result["execution_capabilities"]["price_impact"]["reason_code"],
            "route_evidence_stale",
        )

    def test_naive_timestamp_cannot_complete_freshness(self):
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["price_impact"]},
            evaluated_at="2026-08-18T21:00:30Z",
            route_evidence=route_evidence(observed_at="2026-08-18T21:00:00"),
            route_evidence_max_age_seconds=60,
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(
            result["execution_capabilities"]["price_impact"]["reason_code"],
            "route_evidence_timestamp_unverified",
        )
        self.assertFalse(result["route_evidence"]["freshness_complete"])

    def test_string_freshness_window_is_not_coerced(self):
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["price_impact"]},
            evaluated_at=1000,
            route_evidence=route_evidence(),
            route_evidence_max_age_seconds="60",
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(
            result["execution_capabilities"]["price_impact"]["reason_code"],
            "route_evidence_freshness_policy_unconfigured",
        )

    def test_route_evidence_without_explicit_freshness_window_cannot_promote(self):
        result = build_pre_trade_check(
            raw_risk(),
            trade(),
            policy={"required_capabilities": ["price_impact"]},
            evaluated_at=1000,
            route_evidence=route_evidence(),
        )

        self.assertEqual(result["recommendation"], BLOCK)
        self.assertEqual(
            result["execution_capabilities"]["price_impact"]["reason_code"],
            "route_evidence_freshness_policy_unconfigured",
        )

    def test_unaccepted_route_evidence_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "source is not accepted"):
            build_pre_trade_check(
                raw_risk(),
                trade(),
                policy={"required_capabilities": ["price_impact"]},
                evaluated_at=1000,
                route_evidence=route_evidence(source="caller_supplied_claim"),
                route_evidence_max_age_seconds=60,
            )

    def test_buy_route_must_end_at_proposed_asset_mint(self):
        invalid_route = dict(ROUTE)
        invalid_route["token_out_mint"] = "OTHER_ASSET"
        with self.assertRaisesRegex(
            ValueError,
            "token_out_mint must match",
        ):
            build_pre_trade_check(raw_risk(), trade(route=invalid_route))

    def test_service_wrapper_converts_malformed_route_evidence_to_validation_error(self):
        evidence = route_evidence()
        evidence["schema_version"] = 99
        response = build_pre_trade_check_response(
            raw_risk(),
            trade(),
            evaluated_at=1000,
            route_evidence=evidence,
            route_evidence_max_age_seconds=60,
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "pre_trade_check_validation_error")
        self.assertFalse(response["data"].get("execution_authorized", False))


if __name__ == "__main__":
    unittest.main()
