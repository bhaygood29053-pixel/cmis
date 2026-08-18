import os
import time
import unittest
from unittest.mock import patch

from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import (
    AMM_CONFIG,
    POOL,
    XENCAT_MINT,
    XNT_MINT,
)
from liquidity_scout.services import PASS, build_service_envelope


RUN_LIVE = os.getenv("RUN_XDEX_RUNTIME_ROUTE_EVIDENCE_LIVE") == "1"
ROUTE = {
    "token_in_mint": XENCAT_MINT,
    "token_out_mint": XNT_MINT,
    "pool": POOL,
    "amm_config": AMM_CONFIG,
}


def risk_envelope(observed_at):
    return build_service_envelope(
        "risk_check",
        "x1",
        "ok",
        asset={"symbol": "XENCAT", "mint": XENCAT_MINT},
        risk={
            "chain": "x1",
            "asset": {"symbol": "XENCAT", "mint": XENCAT_MINT},
            "recommendation": PASS,
            "components": {
                "liquidity": {
                    "status": PASS,
                    "flags": [],
                    "reasons": [],
                    "evidence": {"liquidity_usd": 1_000_000.0},
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


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_RUNTIME_ROUTE_EVIDENCE_LIVE=1 to run the read-only runtime route probe",
)
class CMISRuntimeXDEXRouteEvidenceLiveTests(unittest.TestCase):
    def test_runtime_derives_real_amount_scoped_xdex_price_impact_evidence(self):
        gateway = RuntimeCMISGateway(verification_evidence_db_path=":memory:")
        observed_at = time.time()
        with patch.object(
            gateway,
            "_risk_check",
            return_value=risk_envelope(observed_at),
        ):
            response = gateway.dispatch({
                "service": "pre_trade_check",
                "chain": "x1",
                "asset": "XENCAT",
                "params": {
                    "trade": {
                        "side": "sell",
                        "asset": {"symbol": "XENCAT", "mint": XENCAT_MINT},
                        "notional_usd": 100.0,
                        "token_in_amount": "1000",
                        "route": dict(ROUTE),
                    }
                },
            })

        self.assertIn(response["status"], {"ok", "partial"})
        route_analysis = response["data"]["route_analysis"]
        self.assertEqual(route_analysis["route_scope"], ROUTE)
        self.assertIsNotNone(route_analysis["estimated_price_impact_percent"])
        # Runtime currently has no separate accepted historical-fee observation
        # dependency. A live exact-route read must therefore not recreate or
        # self-attest the 23-swap bounded historical fee proof.
        self.assertIsNone(route_analysis["estimated_fees"])
        self.assertIsNone(route_analysis["estimated_slippage_percent"])
        evidence = route_analysis["evidence"]
        self.assertEqual(evidence["source"], "cmis_xdex_route_resolver")
        self.assertEqual(evidence["token_in_amount"], "1000")
        self.assertTrue(evidence["route_match"])
        self.assertTrue(evidence["amount_match"])
        self.assertTrue(evidence["scope_match"])
        self.assertTrue(evidence["fresh"])
        self.assertFalse(response["data"]["execution_authorized"])

        print({
            "runtime_route_scope": route_analysis["route_scope"],
            "token_in_amount": evidence["token_in_amount"],
            "price_impact_percent": route_analysis["estimated_price_impact_percent"],
            "bounded_historical_fees_promoted_without_explicit_evidence": False,
            "expected_execution_slippage": route_analysis["estimated_slippage_percent"],
            "execution_authorized": response["data"]["execution_authorized"],
        })


if __name__ == "__main__":
    unittest.main()
