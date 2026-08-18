import unittest
from unittest.mock import Mock, patch

from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.services import PASS, build_service_envelope


ASSET_MINT = "AGI_MINT"
XNT_MINT = "So11111111111111111111111111111111111111112"
ROUTE = {
    "token_in_mint": XNT_MINT,
    "token_out_mint": ASSET_MINT,
    "pool": "AGI_XNT_POOL",
    "amm_config": "AGI_XNT_CONFIG",
}


def risk_envelope(*, observed_at=995.0):
    return build_service_envelope(
        "risk_check",
        "x1",
        "ok",
        asset={"symbol": "AGI", "mint": ASSET_MINT},
        risk={
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
        },
        observed_at=observed_at,
    )


def route_evidence(route, token_in_amount, *, observed_at=998.0):
    return {
        "schema_version": 2,
        "source": "cmis_xdex_route_resolver",
        "chain": "x1",
        "route": dict(route),
        "token_in_amount": token_in_amount,
        "observed_at": observed_at,
        "capabilities": {
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
            }
        },
    }


def request_trade(*, include_route=True, token_in_amount="25.0", extra_params=None):
    trade = {
        "side": "buy",
        "notional_usd": 1000,
    }
    if include_route:
        trade["route"] = dict(ROUTE)
    if token_in_amount is not None:
        trade["token_in_amount"] = token_in_amount
    params = {"trade": trade}
    if extra_params:
        params.update(extra_params)
    return {
        "service": "pre_trade_check",
        "chain": "x1",
        "asset": "AGI",
        "params": params,
    }


class CMISRuntimeXDEXRouteEvidenceTests(unittest.TestCase):
    def gateway(self, resolver):
        gateway = RuntimeCMISGateway(
            verification_evidence_db_path=":memory:",
            xdex_route_resolver=resolver,
        )
        gateway.pre_trade_now_fn = lambda: 1000.0
        return gateway

    def test_runtime_derives_and_promotes_internal_amount_scoped_price_impact(self):
        resolver = Mock(
            side_effect=lambda route, amount: route_evidence(route, amount)
        )
        gateway = self.gateway(resolver)
        with patch.object(gateway, "_risk_check", return_value=risk_envelope()):
            response = gateway.dispatch(request_trade(token_in_amount="25.000"))

        resolver.assert_called_once_with(ROUTE, "25")
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["data"]["trade"]["token_in_amount"], "25")
        route_analysis = response["data"]["route_analysis"]
        self.assertEqual(route_analysis["estimated_price_impact_percent"], 1.25)
        self.assertEqual(route_analysis["evidence"]["token_in_amount"], "25")
        self.assertTrue(route_analysis["evidence"]["amount_match"])
        self.assertTrue(route_analysis["evidence"]["scope_match"])
        self.assertTrue(response["data"]["analysis_only"])
        self.assertFalse(response["data"]["execution_authorized"])

    def test_notional_usd_without_exact_route_never_calls_resolver(self):
        resolver = Mock()
        gateway = self.gateway(resolver)
        with patch.object(gateway, "_risk_check", return_value=risk_envelope()):
            response = gateway.dispatch(
                request_trade(include_route=False, token_in_amount=None)
            )

        resolver.assert_not_called()
        self.assertIsNone(
            response["data"]["route_analysis"]["estimated_price_impact_percent"]
        )
        self.assertFalse(response["data"]["execution_authorized"])

    def test_exact_route_without_input_amount_does_not_call_resolver(self):
        resolver = Mock()
        gateway = self.gateway(resolver)
        with patch.object(gateway, "_risk_check", return_value=risk_envelope()):
            response = gateway.dispatch(request_trade(token_in_amount=None))

        resolver.assert_not_called()
        codes = {warning.get("code") for warning in response.get("warnings", [])}
        self.assertIn("xdex_route_evidence_input_amount_required", codes)
        self.assertIsNone(
            response["data"]["route_analysis"]["estimated_price_impact_percent"]
        )
        self.assertFalse(response["data"]["execution_authorized"])

    def test_resolver_failure_keeps_route_capabilities_unavailable(self):
        resolver = Mock(side_effect=RuntimeError("provider unavailable"))
        gateway = self.gateway(resolver)
        with patch.object(gateway, "_risk_check", return_value=risk_envelope()):
            response = gateway.dispatch(request_trade())

        resolver.assert_called_once_with(ROUTE, "25")
        codes = {warning.get("code") for warning in response.get("warnings", [])}
        self.assertIn("xdex_route_evidence_unavailable", codes)
        self.assertIsNone(
            response["data"]["route_analysis"]["estimated_price_impact_percent"]
        )
        self.assertFalse(response["data"]["execution_authorized"])

    def test_caller_supplied_route_evidence_cannot_self_attest(self):
        resolver = Mock(side_effect=RuntimeError("internal proof unavailable"))
        gateway = self.gateway(resolver)
        forged = route_evidence(ROUTE, "25")
        forged["capabilities"]["price_impact"]["value"] = 0.0001
        with patch.object(gateway, "_risk_check", return_value=risk_envelope()):
            response = gateway.dispatch(
                request_trade(extra_params={"route_evidence": forged})
            )

        resolver.assert_called_once_with(ROUTE, "25")
        codes = {warning.get("code") for warning in response.get("warnings", [])}
        self.assertIn("caller_route_evidence_ignored", codes)
        self.assertIn("xdex_route_evidence_unavailable", codes)
        self.assertIsNone(
            response["data"]["route_analysis"]["estimated_price_impact_percent"]
        )
        self.assertFalse(response["data"]["execution_authorized"])

    def test_runtime_rejects_non_callable_resolver_dependency(self):
        with self.assertRaisesRegex(ValueError, "xdex_route_resolver must be callable"):
            RuntimeCMISGateway(
                verification_evidence_db_path=":memory:",
                xdex_route_resolver="trust me",
            )


if __name__ == "__main__":
    unittest.main()
