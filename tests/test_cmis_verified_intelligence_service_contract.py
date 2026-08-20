import unittest
from unittest.mock import Mock

from liquidity_scout.cmis.verified_intelligence_service import (
    build_verified_intelligence_capability,
    dispatch_verified_intelligence_request,
)
from liquidity_scout.services.cmis_verified_intelligence import SERVICE


EVIDENCE_ID = "ie_" + "a" * 64


class CMISVerifiedIntelligenceServiceContractTests(unittest.TestCase):
    def test_x1_contract_exists_but_is_not_promoted_by_default(self):
        capability = build_verified_intelligence_capability(chain="x1")
        self.assertEqual(capability["state"], "bounded")
        self.assertFalse(capability["callable"])
        self.assertFalse(capability["public_service_promoted"])
        self.assertFalse(capability["scout_reliance_promoted"])
        self.assertEqual(
            capability["accepted_conclusion_types"],
            ["top_account_concentration_change"],
        )
        self.assertEqual(
            capability["promotion_blocker"],
            "canonical_runtime_and_capability_manifest_integration_required",
        )
        self.assertFalse(capability["execution_authorized"])

    def test_explicit_internal_promotion_flag_makes_only_x1_contract_callable(self):
        capability = build_verified_intelligence_capability(
            chain="x1", promotion_authorized=True
        )
        self.assertTrue(capability["callable"])
        self.assertTrue(capability["public_service_promoted"])
        self.assertTrue(capability["scout_reliance_promoted"])
        self.assertIsNone(capability["promotion_blocker"])
        self.assertIn(
            "caller_supplied_intelligence_evidence_not_accepted",
            capability["limitations"],
        )

        solana = build_verified_intelligence_capability(
            chain="solana", promotion_authorized=True
        )
        self.assertEqual(solana["state"], "unavailable")
        self.assertFalse(solana["callable"])
        self.assertFalse(solana["public_service_promoted"])
        self.assertFalse(solana["scout_reliance_promoted"])

    def test_dispatch_rejects_caller_supplied_proof_objects(self):
        resolver = Mock()
        result = dispatch_verified_intelligence_request(
            {
                "service": SERVICE,
                "chain": "x1",
                "params": {
                    "intelligence_evidence_id": EVIDENCE_ID,
                    "asset_id": "mint-1",
                    "intelligence_evidence": {"trust": "me"},
                },
            },
            evidence_resolver=resolver,
            promotion_authorized=True,
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["errors"][0]["code"],
            "caller_intelligence_evidence_not_accepted",
        )
        resolver.assert_not_called()

    def test_dispatch_requires_exact_internal_evidence_id_and_asset_identity(self):
        missing_id = dispatch_verified_intelligence_request(
            {"service": SERVICE, "chain": "x1", "params": {"asset_id": "mint-1"}},
            promotion_authorized=True,
        )
        self.assertEqual(missing_id["status"], "error")
        self.assertEqual(missing_id["errors"][0]["code"], "intelligence_evidence_id_required")

        missing_asset = dispatch_verified_intelligence_request(
            {
                "service": SERVICE,
                "chain": "x1",
                "params": {"intelligence_evidence_id": EVIDENCE_ID},
            },
            promotion_authorized=True,
        )
        self.assertEqual(missing_asset["status"], "error")
        self.assertEqual(missing_asset["errors"][0]["code"], "asset_id_required")

    def test_unpromoted_dispatch_fails_before_trusted_resolver_is_used(self):
        resolver = Mock()
        result = dispatch_verified_intelligence_request(
            {
                "service": SERVICE,
                "chain": "x1",
                "params": {
                    "intelligence_evidence_id": EVIDENCE_ID,
                    "asset_id": "mint-1",
                },
            },
            evidence_resolver=resolver,
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(
            result["warnings"][0]["code"],
            "concentration_change_intelligence_not_promoted",
        )
        resolver.assert_not_called()
        self.assertFalse(result["data"]["scout_reliance_promoted"])

    def test_promoted_dispatch_uses_internal_resolver_not_request_body(self):
        resolver = Mock(return_value=None)
        result = dispatch_verified_intelligence_request(
            {
                "service": SERVICE,
                "chain": "x1",
                "params": {
                    "intelligence_evidence_id": EVIDENCE_ID,
                    "asset_id": "mint-1",
                },
            },
            evidence_resolver=resolver,
            promotion_authorized=True,
        )
        resolver.assert_called_once_with(EVIDENCE_ID)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["warnings"][0]["code"], "intelligence_evidence_not_found")

    def test_wrong_service_and_unknown_params_fail_closed(self):
        wrong = dispatch_verified_intelligence_request(
            {"service": "verified_intelligence", "chain": "x1", "params": {}},
            promotion_authorized=True,
        )
        self.assertEqual(wrong["status"], "error")
        self.assertEqual(wrong["errors"][0]["code"], "unsupported_service")

        unknown = dispatch_verified_intelligence_request(
            {
                "service": SERVICE,
                "chain": "x1",
                "params": {
                    "intelligence_evidence_id": EVIDENCE_ID,
                    "asset_id": "mint-1",
                    "wallet": "not-accepted",
                },
            },
            promotion_authorized=True,
        )
        self.assertEqual(unknown["status"], "error")
        self.assertEqual(unknown["errors"][0]["code"], "unknown_params")


if __name__ == "__main__":
    unittest.main()
