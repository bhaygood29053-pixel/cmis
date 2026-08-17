import unittest
from unittest.mock import patch

from liquidity_scout.cmis import CMISGateway, SUPPORTED_SERVICES
from liquidity_scout.cmis.gateway import SUPPORTED_SERVICES as BASE_SUPPORTED_SERVICES
from liquidity_scout.services.cmis_contract import build_service_envelope


class ExplodingMarketProvider:
    def __init__(self):
        self.refresh_calls = 0

    def refresh_if_needed(self):
        self.refresh_calls += 1
        raise AssertionError("verification_evidence must not collect market data")


class FakeLedger:
    pass


class CMISVerificationGatewayTests(unittest.TestCase):
    def setUp(self):
        self.market = ExplodingMarketProvider()
        self.ledger = FakeLedger()
        self.gateway = CMISGateway(
            x1_market_provider=self.market,
            verification_evidence_ledger=self.ledger,
        )

    def test_external_surface_adds_verification_evidence_as_eighth_service(self):
        self.assertEqual(len(BASE_SUPPORTED_SERVICES), 7)
        self.assertEqual(
            SUPPORTED_SERVICES,
            (*BASE_SUPPORTED_SERVICES, "verification_evidence"),
        )

    def test_exact_evidence_id_selector_calls_lookup_without_provider_collection(self):
        expected = build_service_envelope(
            "verification_evidence",
            "x1",
            "partial",
            data={"evidence_ref": {"evidence_id": "ve_abc"}},
        )
        with patch(
            "liquidity_scout.cmis.verification_gateway.lookup_verification_evidence",
            return_value=expected,
        ) as lookup:
            response = self.gateway.dispatch({
                "service": "verification_evidence",
                "chain": "x1",
                "params": {"evidence_id": "ve_abc"},
            })

        self.assertEqual(response, expected)
        lookup.assert_called_once_with(
            self.ledger,
            chain="x1",
            evidence_id="ve_abc",
            fact_type=None,
            subject_id=None,
        )
        self.assertEqual(self.market.refresh_calls, 0)

    def test_exact_fact_selector_calls_lookup_without_asset_resolution(self):
        expected = build_service_envelope(
            "verification_evidence",
            "x1",
            "partial",
        )
        with patch(
            "liquidity_scout.cmis.verification_gateway.lookup_verification_evidence",
            return_value=expected,
        ) as lookup:
            response = self.gateway.dispatch({
                "service": "verification_evidence",
                "chain": "x1",
                "params": {
                    "fact_type": "pool_reserve",
                    "subject_id": "x1:pool:vault",
                },
            })

        self.assertEqual(response, expected)
        lookup.assert_called_once_with(
            self.ledger,
            chain="x1",
            evidence_id=None,
            fact_type="pool_reserve",
            subject_id="x1:pool:vault",
        )
        self.assertEqual(self.market.refresh_calls, 0)

    def test_unconfigured_ledger_remains_explicitly_unavailable(self):
        gateway = CMISGateway(
            x1_market_provider=self.market,
            verification_evidence_ledger=None,
        )
        response = gateway.dispatch({
            "service": "verification_evidence",
            "chain": "x1",
            "params": {"evidence_id": "ve_missing"},
        })

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["warnings"][0]["code"],
            "verification_evidence_ledger_not_configured",
        )
        self.assertEqual(self.market.refresh_calls, 0)

    def test_asset_or_raw_top_level_payloads_fail_closed_before_lookup(self):
        cases = [
            {
                "service": "verification_evidence",
                "chain": "x1",
                "asset": "AGI",
                "params": {"evidence_id": "ve_abc"},
            },
            {
                "service": "verification_evidence",
                "chain": "x1",
                "params": {"evidence_id": "ve_abc"},
                "verifier_result": {"verification": {"status": "AGREEMENT"}},
            },
        ]
        with patch(
            "liquidity_scout.cmis.verification_gateway.lookup_verification_evidence"
        ) as lookup:
            for request in cases:
                with self.subTest(request=request):
                    response = self.gateway.dispatch(request)
                    self.assertEqual(response["status"], "error")
                    self.assertEqual(
                        response["errors"][0]["code"],
                        "verification_evidence_request_fields_not_allowed",
                    )

        lookup.assert_not_called()
        self.assertEqual(self.market.refresh_calls, 0)

    def test_extra_or_raw_params_fail_closed_before_lookup(self):
        cases = [
            {"evidence_id": "ve_abc", "asset": "AGI"},
            {"evidence_id": "ve_abc", "raw": {"secret": "payload"}},
            {"evidence_id": "ve_abc", "provider_response": {"value": 42}},
        ]
        with patch(
            "liquidity_scout.cmis.verification_gateway.lookup_verification_evidence"
        ) as lookup:
            for params in cases:
                with self.subTest(params=params):
                    response = self.gateway.dispatch({
                        "service": "verification_evidence",
                        "chain": "x1",
                        "params": params,
                    })
                    self.assertEqual(response["status"], "error")
                    self.assertEqual(
                        response["errors"][0]["code"],
                        "verification_evidence_params_not_allowed",
                    )

        lookup.assert_not_called()
        self.assertEqual(self.market.refresh_calls, 0)

    def test_selector_validation_stays_owned_by_exact_lookup(self):
        response = self.gateway.dispatch({
            "service": "verification_evidence",
            "chain": "x1",
            "params": {},
        })
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_selector_required",
        )

        response = self.gateway.dispatch({
            "service": "verification_evidence",
            "chain": "x1",
            "params": {
                "evidence_id": "ve_abc",
                "fact_type": "pool_reserve",
                "subject_id": "x1:pool:vault",
            },
        })
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_selector_conflict",
        )
        self.assertEqual(self.market.refresh_calls, 0)

    def test_chain_and_params_validation_happen_before_lookup(self):
        unknown = self.gateway.dispatch({
            "service": "verification_evidence",
            "chain": "ethereum",
            "params": {"evidence_id": "ve_abc"},
        })
        self.assertEqual(unknown["status"], "error")
        self.assertEqual(unknown["errors"][0]["code"], "unsupported_chain")

        solana = self.gateway.dispatch({
            "service": "verification_evidence",
            "chain": "solana",
            "params": {"evidence_id": "ve_abc"},
        })
        self.assertEqual(solana["status"], "unavailable")
        self.assertEqual(
            solana["warnings"][0]["code"],
            "chain_provider_not_implemented",
        )

        bad_params = self.gateway.dispatch({
            "service": "verification_evidence",
            "chain": "x1",
            "params": "ve_abc",
        })
        self.assertEqual(bad_params["status"], "error")
        self.assertEqual(bad_params["errors"][0]["code"], "invalid_params")
        self.assertEqual(self.market.refresh_calls, 0)


if __name__ == "__main__":
    unittest.main()
