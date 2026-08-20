import copy
import unittest
from unittest.mock import patch

from liquidity_scout.services.cmis_verified_intelligence import (
    CONTRACT_VERSION,
    build_verified_intelligence_response,
)


class CMISVerifiedIntelligenceTests(unittest.TestCase):
    @staticmethod
    def _bundle(*, chain="x1"):
        return {
            "intelligence_evidence_id": "ie_" + "a" * 64,
            "schema_version": 1,
            "conclusion_type": "top_account_concentration",
            "conclusion_fingerprint": "ic_" + "b" * 64,
            "conclusion": {
                "chain": chain,
                "source": "x1_rpc",
                "asset_id": "Mint111",
            },
            "evidence_bundles": [
                {
                    "evidence_receipt": {
                        "receipt_id": "er_" + "c" * 64,
                        "chain": chain,
                        "sources": [
                            {
                                "source": "x1_rpc",
                                "evidence_class": "verifier_observation",
                                "observed_at": "2026-08-20T00:00:00Z",
                            }
                        ],
                    },
                    "proof_score": {
                        "proof_strength": "STRONG",
                        "proof_percent": 100,
                        "method": "cmis_proof_score/v1",
                    },
                }
            ],
            "binding": {
                "chain_verified": True,
                "source_coverage_verified": True,
                "asset_coverage_verified": True,
                "independent_verification_present": False,
                "conclusion_sources": ["x1_rpc"],
                "conclusion_assets": ["Mint111"],
            },
            "source_classes": {
                "source_records": [],
                "reported_observations": [],
                "verifier_observations": [],
            },
            "proof_strength_separate_from_risk": True,
            "risk_reinterpreted": False,
            "behavioral_interpretation_added": False,
            "provider_assertion_promoted": False,
            "scout_reliance_promoted": False,
            "public_service_promoted": False,
            "execution_authorized": False,
        }

    def test_exact_revalidated_bundle_is_exposed_without_mutating_foundation(self):
        bundle = self._bundle()
        with patch(
            "liquidity_scout.services.cmis_verified_intelligence.build_intelligence_evidence_bundle",
            return_value=copy.deepcopy(bundle),
        ):
            result = build_verified_intelligence_response(bundle)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["service"], "verified_intelligence")
        self.assertIsNone(result["risk"])
        self.assertEqual(result["data"]["contract_version"], CONTRACT_VERSION)
        self.assertTrue(result["data"]["public_service_promoted"])
        self.assertTrue(result["data"]["scout_reliance_promoted"])
        self.assertFalse(result["data"]["execution_authorized"])
        nested = result["data"]["intelligence_evidence"]
        self.assertFalse(nested["public_service_promoted"])
        self.assertFalse(nested["scout_reliance_promoted"])
        self.assertFalse(nested["execution_authorized"])
        self.assertFalse(result["data"]["behavioral_interpretation_added"])
        self.assertFalse(result["data"]["provider_assertion_promoted"])

    def test_tampered_bundle_cannot_be_promoted(self):
        canonical = self._bundle()
        supplied = copy.deepcopy(canonical)
        supplied["binding"]["independent_verification_present"] = True
        with patch(
            "liquidity_scout.services.cmis_verified_intelligence.build_intelligence_evidence_bundle",
            return_value=canonical,
        ):
            result = build_verified_intelligence_response(supplied)

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["errors"][0]["code"],
            "intelligence_evidence_exact_match_required",
        )
        self.assertFalse(result["data"]["execution_authorized"])

    def test_validator_failure_is_fail_closed(self):
        bundle = self._bundle()
        with patch(
            "liquidity_scout.services.cmis_verified_intelligence.build_intelligence_evidence_bundle",
            side_effect=ValueError("receipt mismatch"),
        ):
            result = build_verified_intelligence_response(bundle)

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["errors"][0]["code"],
            "intelligence_evidence_validation_failed",
        )

    def test_unsupported_conclusion_type_is_rejected_before_validation(self):
        bundle = self._bundle()
        bundle["conclusion_type"] = "whale_classification"
        result = build_verified_intelligence_response(bundle)
        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["errors"][0]["code"],
            "unsupported_intelligence_conclusion",
        )

    def test_requested_chain_must_match_evidence_chain(self):
        bundle = self._bundle(chain="solana")
        canonical = copy.deepcopy(bundle)
        with patch(
            "liquidity_scout.services.cmis_verified_intelligence.build_intelligence_evidence_bundle",
            return_value=canonical,
        ):
            result = build_verified_intelligence_response(bundle, chain="x1")
        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["errors"][0]["code"],
            "intelligence_evidence_chain_mismatch",
        )

    def test_solana_is_not_silently_promoted(self):
        result = build_verified_intelligence_response(self._bundle(chain="solana"), chain="solana")
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["data"]["public_service_promoted"])
        self.assertFalse(result["data"]["scout_reliance_promoted"])
        self.assertFalse(result["data"]["execution_authorized"])

    def test_source_and_proof_traceability_are_preserved(self):
        bundle = self._bundle()
        with patch(
            "liquidity_scout.services.cmis_verified_intelligence.build_intelligence_evidence_bundle",
            return_value=copy.deepcopy(bundle),
        ):
            result = build_verified_intelligence_response(bundle)

        self.assertEqual(result["sources"][0]["source"], "x1_rpc")
        proof = result["data"]["proof_records"][0]
        self.assertEqual(proof["receipt_id"], "er_" + "c" * 64)
        self.assertEqual(proof["proof_strength"], "STRONG")
        self.assertTrue(result["data"]["proof_strength_separate_from_risk"])


if __name__ == "__main__":
    unittest.main()
