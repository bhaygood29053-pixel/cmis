import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from liquidity_scout.cmis.capabilities import build_capability_manifest
from liquidity_scout.cmis.gateway import (
    CMISGateway,
    KNOWN_CHAINS,
    SUPPORTED_CHAINS,
    SUPPORTED_SERVICES as BASE_SUPPORTED_SERVICES,
)
from liquidity_scout.cmis.intelligence_evidence_ledger import IntelligenceEvidenceLedger
from liquidity_scout.cmis.runtime_gateway import (
    RuntimeCMISGateway,
    SUPPORTED_SERVICES as RUNTIME_SUPPORTED_SERVICES,
)
from liquidity_scout.services.cmis_verified_intelligence import SERVICE


EVIDENCE_ID = "ie_" + "a" * 64
ASSET_ID = "X1:CMIS"


class _ExplodingMarketProvider:
    def refresh_if_needed(self):
        raise AssertionError(
            "concentration_change_intelligence must not collect market data"
        )

    def market_catalog(self):
        raise AssertionError(
            "concentration_change_intelligence must not read the market catalog"
        )


def _request(*, chain="x1"):
    return {
        "service": SERVICE,
        "chain": chain,
        "params": {
            "intelligence_evidence_id": EVIDENCE_ID,
            "asset_id": ASSET_ID,
        },
    }


class ConcentrationChangeIntelligenceGatewayIntegrationTests(unittest.TestCase):
    def test_base_gateway_advertises_and_delegates_without_provider_collection(self):
        resolver = Mock(return_value=None)
        request = _request()
        sentinel = {"service": SERVICE, "chain": "x1", "status": "unavailable"}
        gateway = CMISGateway(
            x1_market_provider=_ExplodingMarketProvider(),
            intelligence_evidence_resolver=resolver,
        )

        with patch(
            "liquidity_scout.cmis.gateway.dispatch_verified_intelligence_request",
            return_value=sentinel,
        ) as dispatcher:
            self.assertEqual(gateway.dispatch(request), sentinel)

        dispatcher.assert_called_once_with(
            request,
            evidence_resolver=resolver,
            promotion_authorized=True,
        )
        self.assertIn(SERVICE, BASE_SUPPORTED_SERVICES)

    def test_runtime_uses_cmis_owned_ledger_resolver(self):
        ledger = Mock()
        ledger.get.return_value = None
        gateway = RuntimeCMISGateway(
            verification_evidence_db_path=":memory:",
            intelligence_evidence_ledger=ledger,
            x1_market_provider=_ExplodingMarketProvider(),
        )

        response = gateway.dispatch(_request())

        ledger.get.assert_called_once_with(EVIDENCE_ID)
        self.assertEqual(response["service"], SERVICE)
        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["warnings"][0]["code"],
            "intelligence_evidence_not_found",
        )
        self.assertEqual(RUNTIME_SUPPORTED_SERVICES.count(SERVICE), 1)

    def test_runtime_cmis_owned_ledger_overrides_competing_resolver_kwarg(self):
        ledger = Mock()
        ledger.get.return_value = None
        competing_resolver = Mock(return_value={"caller": "controlled"})
        gateway = RuntimeCMISGateway(
            verification_evidence_db_path=":memory:",
            intelligence_evidence_ledger=ledger,
            intelligence_evidence_resolver=competing_resolver,
            x1_market_provider=_ExplodingMarketProvider(),
        )

        response = gateway.dispatch(_request())

        ledger.get.assert_called_once_with(EVIDENCE_ID)
        competing_resolver.assert_not_called()
        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["warnings"][0]["code"],
            "intelligence_evidence_not_found",
        )

    def test_runtime_constructs_default_intelligence_ledger_from_configured_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            intelligence_path = os.path.join(tmpdir, "intelligence-evidence.db")
            gateway = RuntimeCMISGateway(
                verification_evidence_db_path=":memory:",
                intelligence_evidence_db_path=intelligence_path,
                x1_market_provider=_ExplodingMarketProvider(),
            )

            self.assertIsInstance(
                gateway.intelligence_evidence_ledger,
                IntelligenceEvidenceLedger,
            )
            self.assertEqual(
                gateway.intelligence_evidence_ledger.db_path,
                intelligence_path,
            )

    def test_unknown_chain_is_rejected_before_internal_resolver(self):
        resolver = Mock(return_value=None)
        response = CMISGateway(
            x1_market_provider=_ExplodingMarketProvider(),
            intelligence_evidence_resolver=resolver,
        ).dispatch(_request(chain="ethereum"))

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "unsupported_chain")
        resolver.assert_not_called()

    def test_solana_remains_service_specific_unavailable_and_never_resolves_evidence(self):
        resolver = Mock(return_value=None)
        response = CMISGateway(
            x1_market_provider=_ExplodingMarketProvider(),
            intelligence_evidence_resolver=resolver,
        ).dispatch(_request(chain="solana"))

        self.assertEqual(response["service"], SERVICE)
        self.assertEqual(response["chain"], "solana")
        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["warnings"][0]["code"],
            "concentration_change_intelligence_chain_not_promoted",
        )
        self.assertFalse(response["data"]["public_service_promoted"])
        self.assertFalse(response["data"]["scout_reliance_promoted"])
        self.assertFalse(response["data"]["execution_authorized"])
        resolver.assert_not_called()

    def test_manifest_promotes_only_x1_service_and_not_phase_11_foundation(self):
        manifest = build_capability_manifest(
            runtime_services=RUNTIME_SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )
        foundation = manifest["intelligence_foundation"]
        x1 = manifest["chains"]["x1"]["services"][SERVICE]
        solana = manifest["chains"]["solana"]["services"][SERVICE]

        self.assertFalse(foundation["public_service_promoted"])
        self.assertFalse(foundation["scout_reliance_promoted"])
        self.assertEqual(
            foundation["promotion_rule"],
            "new_accepted_public_service_contract_required",
        )

        self.assertEqual(x1["service"], SERVICE)
        self.assertEqual(
            x1["service_contract_version"],
            "concentration_change_intelligence/v1",
        )
        self.assertEqual(x1["state"], "bounded")
        self.assertTrue(x1["callable"])
        self.assertTrue(x1["read_only"])
        self.assertTrue(x1["public_service_promoted"])
        self.assertTrue(x1["scout_reliance_promoted"])
        self.assertEqual(
            x1["promotion_scope"],
            "cmis_owned_top_account_concentration_change_evidence_by_id",
        )
        self.assertEqual(
            x1["accepted_conclusion_types"],
            ["top_account_concentration_change"],
        )
        self.assertIsNone(x1["promotion_blocker"])
        self.assertIn(
            "caller_supplied_intelligence_evidence_not_accepted",
            x1["limitations"],
        )
        self.assertFalse(x1["execution_authorized"])

        self.assertEqual(solana["state"], "unavailable")
        self.assertFalse(solana["callable"])
        self.assertFalse(solana["public_service_promoted"])
        self.assertFalse(solana["scout_reliance_promoted"])
        self.assertFalse(solana["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
