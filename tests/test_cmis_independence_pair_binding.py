import unittest

from liquidity_scout.cmis.evidence_receipt import build_evidence_receipt
from liquidity_scout.cmis.proof_score import build_proof_score
from liquidity_scout.services.cmis_contract import build_service_envelope


class CMISIndependencePairBindingTests(unittest.TestCase):
    def _envelope(self, *, verifier_source):
        observed_at = "2026-08-19T10:00:00Z"
        return build_service_envelope(
            "verification_evidence",
            "x1",
            "ok",
            asset={"canonical_id": "x1:test", "mint": "mint-test"},
            data={
                "verification": {
                    "status": "AGREEMENT",
                    "code": "VALUES_AGREE",
                    "agreement": True,
                },
                "observations": {
                    "primary": {
                        "source": "provider-a",
                        "source_role": "provider_report",
                        "observed_at": observed_at,
                    },
                    "verifier": {
                        "source": verifier_source,
                        "source_role": "onchain_verifier",
                        "observed_at": observed_at,
                    },
                },
                "verification_scope": "exact_fact",
                "scope_verified": True,
                "source_independence_verified": True,
                "cmis_promotable": True,
            },
            confidence={
                "identity_verified": True,
                "semantics_verified": True,
                "freshness_verified": True,
            },
            sources=[
                {
                    "source": "provider-a",
                    "role": "primary_provider",
                    "observed_at": observed_at,
                },
                {
                    "source": "unrelated-third-source",
                    "role": "other_context",
                    "observed_at": observed_at,
                },
            ],
            observed_at=observed_at,
        )

    def test_unrelated_third_source_cannot_rescue_same_source_pair(self):
        receipt = build_evidence_receipt(
            self._envelope(verifier_source="provider-a")
        )
        score = build_proof_score(receipt)

        self.assertTrue(receipt["verification"]["source_independence_verified"])
        self.assertFalse(receipt["verification"]["independently_verified"])
        self.assertIn(
            "verification.source_structure",
            receipt["unresolved_fields"],
        )
        category = score["categories"]["source_independence"]
        self.assertEqual(category["state"], "UNVERIFIED")
        self.assertEqual(category["score"], 0)
        self.assertIn(
            "positive source independence requires distinct reported and verifier observation sources",
            category["reasons"],
        )

    def test_distinct_reported_and_verifier_sources_can_receive_credit(self):
        receipt = build_evidence_receipt(
            self._envelope(verifier_source="x1-rpc")
        )
        score = build_proof_score(receipt)

        self.assertTrue(receipt["verification"]["independently_verified"])
        category = score["categories"]["source_independence"]
        self.assertEqual(category["state"], "VERIFIED")
        self.assertEqual(category["score"], 100)


if __name__ == "__main__":
    unittest.main()
