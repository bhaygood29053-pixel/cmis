import unittest
from unittest.mock import patch

from liquidity_scout.cmis.verified_intelligence_service import (
    build_verified_intelligence_capability,
    dispatch_verified_intelligence_request,
)


class CMISVerifiedIntelligenceServiceContractTests(unittest.TestCase):
    def test_x1_capability_promotes_only_wrapper_service(self):
        capability = build_verified_intelligence_capability(chain="x1")
        self.assertEqual(capability["state"], "bounded")
        self.assertTrue(capability["callable"])
        self.assertTrue(capability["public_service_promoted"])
        self.assertTrue(capability["scout_reliance_promoted"])
        self.assertEqual(
            capability["promotion_scope"],
            "exact_revalidated_intelligence_evidence_bundle_only",
        )
        self.assertFalse(capability["execution_authorized"])
        self.assertIn("no_behavioral_or_ownership_labels", capability["limitations"])

    def test_other_chain_is_unavailable(self):
        capability = build_verified_intelligence_capability(chain="solana")
        self.assertEqual(capability["state"], "unavailable")
        self.assertFalse(capability["callable"])
        self.assertFalse(capability["public_service_promoted"])
        self.assertFalse(capability["scout_reliance_promoted"])
        self.assertFalse(capability["execution_authorized"])

    def test_dispatch_requires_exact_service_and_evidence_param(self):
        bad_service = dispatch_verified_intelligence_request(
            {"service": "market_report", "chain": "x1", "params": {}}
        )
        self.assertEqual(bad_service["status"], "error")
        self.assertEqual(bad_service["errors"][0]["code"], "unsupported_service")

        missing = dispatch_verified_intelligence_request(
            {"service": "verified_intelligence", "chain": "x1", "params": {}}
        )
        self.assertEqual(missing["status"], "error")
        self.assertEqual(missing["errors"][0]["code"], "intelligence_evidence_required")
        self.assertFalse(missing["data"]["execution_authorized"])

    def test_dispatch_delegates_only_supplied_evidence_and_chain(self):
        sentinel = {"service": "verified_intelligence", "status": "ok"}
        evidence = {"conclusion_type": "top_account_concentration"}
        with patch(
            "liquidity_scout.cmis.verified_intelligence_service.build_verified_intelligence_response",
            return_value=sentinel,
        ) as builder:
            result = dispatch_verified_intelligence_request(
                {
                    "service": "verified_intelligence",
                    "chain": "x1",
                    "params": {"intelligence_evidence": evidence},
                }
            )
        self.assertIs(result, sentinel)
        builder.assert_called_once_with(evidence, chain="x1")


if __name__ == "__main__":
    unittest.main()
