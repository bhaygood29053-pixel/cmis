import copy
import unittest

from liquidity_scout.cmis.evidence import build_evidence_observation
from liquidity_scout.cmis.evidence_receipt import build_evidence_receipt
from liquidity_scout.cmis.proof_score import build_proof_score
from liquidity_scout.providers.x1.reserve_verification import verify_x1_pool_reserve
from liquidity_scout.services.cmis_verification_evidence import (
    build_verification_evidence_response,
)


SUBJECT = "x1:pool111:mint111:vault111"


def observation(source, *, slot):
    return build_evidence_observation(
        chain="x1",
        fact_type="pool_reserve",
        subject_id=SUBJECT,
        source=source,
        source_role="market_provider" if source == "X1.Ninja" else "onchain_verifier",
        observed_at=1000.0,
        block_slot=slot,
        raw_identifier="pool.pooledBase" if source == "X1.Ninja" else "vault111",
        raw_value="42",
        normalized_value="42",
        unit="TOKEN_UNITS",
        calculation_version="independence-runtime-test-1",
        identity_verified=True,
        semantics_verified=True,
        freshness_verified=True,
        warnings=[],
    )


def verified_result(*, source_independence_verified):
    return verify_x1_pool_reserve(
        observation("X1.Ninja", slot=100),
        observation("X1 RPC", slot=101),
        source_independence_verified=source_independence_verified,
    )


class CMISVerificationEvidenceIndependenceRuntimeTests(unittest.TestCase):
    def test_unknown_independence_stays_unknown_through_receipt_and_proof_score(self):
        response = build_verification_evidence_response(
            verified_result(source_independence_verified=None),
            observed_at=1001.0,
        )

        self.assertEqual(response["status"], "partial")
        self.assertTrue(response["confidence"]["same_fact_agreement_verified"])
        self.assertIsNone(response["confidence"]["source_independence_verified"])
        self.assertFalse(response["confidence"]["independent_agreement_verified"])

        receipt = build_evidence_receipt(response)
        score = build_proof_score(receipt)

        self.assertEqual(receipt["verification"]["status"], "AGREEMENT")
        self.assertIsNone(receipt["verification"]["source_independence_verified"])
        self.assertIsNone(receipt["verification"]["independently_verified"])
        self.assertEqual(score["categories"]["agreement"]["state"], "VERIFIED")
        self.assertEqual(score["categories"]["agreement"]["score"], 100)
        self.assertEqual(score["categories"]["source_independence"]["state"], "UNKNOWN")
        self.assertIsNone(score["categories"]["source_independence"]["score"])

    def test_explicit_failed_independence_stays_zero_credit(self):
        response = build_verification_evidence_response(
            verified_result(source_independence_verified=False),
            observed_at=1001.0,
        )
        self.assertEqual(response["status"], "partial")

        receipt = build_evidence_receipt(response)
        score = build_proof_score(receipt)

        self.assertFalse(receipt["verification"]["source_independence_verified"])
        self.assertFalse(receipt["verification"]["independently_verified"])
        self.assertEqual(score["categories"]["source_independence"]["state"], "UNVERIFIED")
        self.assertEqual(score["categories"]["source_independence"]["score"], 0)

    def test_service_rejects_false_derived_independent_agreement_when_prerequisites_true(self):
        forged = copy.deepcopy(
            verified_result(source_independence_verified=True)
        )
        forged["cmis_promotable"] = False
        forged["data_quality"]["independent_agreement_verified"] = False

        response = build_verification_evidence_response(forged)

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "data_quality_independence_inconsistent",
        )


if __name__ == "__main__":
    unittest.main()
