import unittest

from liquidity_scout.cmis.evidence_quality_gateway import EvidenceQualityMixin
from liquidity_scout.cmis.evidence_receipt import build_evidence_receipt
from liquidity_scout.cmis.proof_score import build_proof_score
from liquidity_scout.services.cmis_contract import build_service_envelope


class _StaticGateway:
    def __init__(self, response):
        self.response = response

    def dispatch(self, _request):
        return self.response


class _QualityGateway(EvidenceQualityMixin, _StaticGateway):
    pass


class CMISEvidenceReceiptTests(unittest.TestCase):
    def _verified_envelope(self):
        return build_service_envelope(
            "verification_evidence",
            "x1",
            "ok",
            asset={
                "canonical_id": "x1:test",
                "symbol": "TEST",
                "mint": "mint-test",
            },
            data={
                "fact": {
                    "fact_type": "pool_reserve",
                    "subject_id": "pool:test:asset",
                    "normalized_value": "10",
                    "unit": "token_ui_units",
                },
                "verification": {
                    "status": "AGREEMENT",
                    "code": "VALUES_AGREE",
                    "agreement": True,
                },
                "data_quality": {
                    "identity_verified": True,
                    "semantics_verified": True,
                    "freshness_verified": True,
                    "independent_source_count": 2,
                    "independent_agreement_verified": True,
                },
                "observations": {
                    "primary": {
                        "source": "provider-a",
                        "source_role": "provider_report",
                        "observed_at": "2026-08-18T09:00:00Z",
                        "block_slot": 100,
                        "identity_verified": True,
                        "semantics_verified": True,
                        "freshness_verified": True,
                    },
                    "verifier": {
                        "source": "x1_rpc",
                        "source_role": "independent_chain_verifier",
                        "observed_at": "2026-08-18T09:00:01Z",
                        "block_slot": 101,
                        "identity_verified": True,
                        "semantics_verified": True,
                        "freshness_verified": True,
                    },
                },
                "verification_scope": "exact_pool_leg",
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
                    "observed_at": "2026-08-18T09:00:00Z",
                },
                {
                    "source": "x1_rpc",
                    "role": "independent_verifier",
                    "observed_at": "2026-08-18T09:00:01Z",
                    "block_slot": 101,
                },
            ],
            observed_at="2026-08-18T09:00:01Z",
        )

    def test_receipt_is_deterministic_and_content_addressed(self):
        envelope = self._verified_envelope()
        first = build_evidence_receipt(envelope)
        second = build_evidence_receipt(envelope)
        self.assertEqual(first, second)
        self.assertTrue(first["receipt_id"].startswith("er_"))
        self.assertEqual(first["schema_version"], 1)
        self.assertEqual(first["chain"], "x1")
        self.assertEqual(first["service"], "verification_evidence")

    def test_receipt_preserves_reported_vs_verifier_observations(self):
        receipt = build_evidence_receipt(self._verified_envelope())
        classes = {item["evidence_class"] for item in receipt["sources"]}
        self.assertIn("reported_observation", classes)
        self.assertIn("verifier_observation", classes)
        self.assertTrue(receipt["verification"]["source_independence_verified"])
        self.assertTrue(receipt["verification"]["independently_verified"])
        self.assertFalse(receipt["verification"]["provider_assertion_promoted"])
        self.assertEqual(receipt["verification"]["status"], "AGREEMENT")

    def test_independence_flag_cannot_rescue_single_source_structure(self):
        envelope = self._verified_envelope()
        envelope["data"]["observations"]["verifier"]["source"] = "provider-a"
        envelope["sources"][1]["source"] = "provider-a"

        receipt = build_evidence_receipt(envelope)

        self.assertTrue(receipt["verification"]["source_independence_verified"])
        self.assertFalse(receipt["verification"]["independently_verified"])
        self.assertIn("verification.source_structure", receipt["unresolved_fields"])

    def test_agreement_without_independence_proof_remains_unknown(self):
        envelope = self._verified_envelope()
        del envelope["data"]["source_independence_verified"]

        receipt = build_evidence_receipt(envelope)

        self.assertEqual(receipt["verification"]["status"], "AGREEMENT")
        self.assertIsNone(receipt["verification"]["source_independence_verified"])
        self.assertIsNone(receipt["verification"]["independently_verified"])
        self.assertIn(
            "verification.source_independence",
            receipt["unresolved_fields"],
        )

    def test_explicit_failed_independence_is_not_treated_as_missing(self):
        envelope = self._verified_envelope()
        envelope["data"]["source_independence_verified"] = False

        receipt = build_evidence_receipt(envelope)

        self.assertFalse(receipt["verification"]["source_independence_verified"])
        self.assertFalse(receipt["verification"]["independently_verified"])
        self.assertIn(
            "data.source_independence_verified",
            receipt["unresolved_fields"],
        )

    def test_missing_evidence_stays_unknown_not_false(self):
        envelope = build_service_envelope(
            "market_report",
            "x1",
            "partial",
            asset={"symbol": "TEST"},
            data={"price_usd": "1"},
            sources=[{"source": "provider-only", "role": "market_provider"}],
        )
        receipt = build_evidence_receipt(envelope)
        score = build_proof_score(receipt)

        self.assertEqual(receipt["verification"]["status"], "UNVERIFIED")
        self.assertIsNone(receipt["verification"]["source_independence_verified"])
        self.assertIsNone(receipt["verification"]["independently_verified"])
        self.assertIsNone(receipt["freshness"]["verified"])
        self.assertIn("verification.status", receipt["unresolved_fields"])
        self.assertIn("verification.source_independence", receipt["unresolved_fields"])
        self.assertIsNone(score["categories"]["identity"]["score"])
        self.assertIsNone(score["categories"]["semantics"]["score"])
        self.assertIsNone(score["categories"]["freshness"]["score"])
        self.assertEqual(score["proof_strength"], "WEAK")

    def test_explicit_failed_gate_is_not_treated_as_missing(self):
        envelope = build_service_envelope(
            "market_report",
            "x1",
            "partial",
            data={"semantics_verified": False},
            confidence={"identity_verified": True, "freshness_verified": False},
            sources=[
                {
                    "source": "provider-only",
                    "role": "market_provider",
                    "observed_at": "2026-08-18T09:00:00Z",
                }
            ],
        )
        score = build_proof_score(build_evidence_receipt(envelope))
        self.assertEqual(score["categories"]["identity"]["score"], 100)
        self.assertEqual(score["categories"]["semantics"]["score"], 0)
        self.assertEqual(score["categories"]["freshness"]["score"], 0)


class CMISProofScoreTests(unittest.TestCase):
    def test_proof_score_is_separate_from_risk(self):
        base = CMISEvidenceReceiptTests()._verified_envelope()
        risky = dict(base)
        risky["risk"] = {"result": "BLOCK", "level": "HIGH"}
        safe = dict(base)
        safe["risk"] = {"result": "PASS", "level": "LOW"}

        risky_score = build_proof_score(build_evidence_receipt(risky))
        safe_score = build_proof_score(build_evidence_receipt(safe))
        self.assertEqual(risky_score, safe_score)
        self.assertFalse(risky_score["risk_considered"])
        self.assertTrue(risky_score["risk_separate"])

    def test_conflict_prevents_strong_proof(self):
        envelope = CMISEvidenceReceiptTests()._verified_envelope()
        envelope["status"] = "partial"
        envelope["data"]["verification"] = {
            "status": "CONFLICT",
            "code": "VALUES_DISAGREE",
            "agreement": False,
        }
        envelope["data"]["cmis_promotable"] = False
        receipt = build_evidence_receipt(envelope)
        score = build_proof_score(receipt)
        self.assertEqual(score["categories"]["agreement"]["state"], "CONFLICT")
        self.assertEqual(score["proof_strength"], "WEAK")
        self.assertTrue(receipt["disagreements"])

    def test_runtime_mixin_adds_metadata_without_rewriting_core_envelope(self):
        envelope = CMISEvidenceReceiptTests()._verified_envelope()
        gateway = _QualityGateway(envelope)
        result = gateway.dispatch({"service": "ignored"})
        self.assertEqual(result["risk"], envelope["risk"])
        self.assertEqual(result["data"], envelope["data"])
        self.assertIn("evidence_receipt", result)
        self.assertIn("proof_score", result)
        self.assertNotIn("evidence_receipt", envelope)
        self.assertNotIn("proof_score", envelope)


if __name__ == "__main__":
    unittest.main()
