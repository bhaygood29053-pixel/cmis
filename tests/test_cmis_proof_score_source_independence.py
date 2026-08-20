import unittest

from liquidity_scout.cmis.evidence_receipt import build_evidence_receipt
from liquidity_scout.cmis.proof_score import build_proof_score
from liquidity_scout.services.cmis_contract import build_service_envelope


_MISSING = object()


class CMISProofScoreSourceIndependenceTests(unittest.TestCase):
    def _envelope(self, *, source_independence_verified=_MISSING, same_source=False):
        verifier_source = "provider-a" if same_source else "x1_rpc"
        data = {
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
            "observations": {
                "primary": {
                    "source": "provider-a",
                    "source_role": "provider_report",
                    "observed_at": "2026-08-18T09:00:00Z",
                    "identity_verified": True,
                    "semantics_verified": True,
                    "freshness_verified": True,
                },
                "verifier": {
                    "source": verifier_source,
                    "source_role": "onchain_verifier",
                    "observed_at": "2026-08-18T09:00:01Z",
                    "identity_verified": True,
                    "semantics_verified": True,
                    "freshness_verified": True,
                },
            },
            "verification_scope": "exact_pool_leg",
            "scope_verified": True,
            "cmis_promotable": True,
        }
        if source_independence_verified is not _MISSING:
            data["source_independence_verified"] = source_independence_verified

        return build_service_envelope(
            "verification_evidence",
            "x1",
            "ok",
            asset={"canonical_id": "x1:test", "symbol": "TEST", "mint": "mint-test"},
            data=data,
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
                    "source": verifier_source,
                    "role": "verifier",
                    "observed_at": "2026-08-18T09:00:01Z",
                },
            ],
            observed_at="2026-08-18T09:00:01Z",
        )

    def _score(self, **kwargs):
        return build_proof_score(build_evidence_receipt(self._envelope(**kwargs)))

    def test_distinct_source_labels_and_verifier_role_do_not_prove_independence(self):
        category = self._score()["categories"]["source_independence"]

        self.assertEqual(category["state"], "UNKNOWN")
        self.assertIsNone(category["score"])
        self.assertIn(
            "distinct source labels and verifier roles do not prove source independence",
            category["reasons"],
        )

    def test_explicit_verified_independence_receives_proof_credit(self):
        category = self._score(source_independence_verified=True)["categories"][
            "source_independence"
        ]

        self.assertEqual(category["state"], "VERIFIED")
        self.assertEqual(category["score"], 100)
        self.assertEqual(
            category["evidence_paths"], ["data.source_independence_verified"]
        )

    def test_explicit_failed_independence_gate_receives_zero_credit(self):
        category = self._score(source_independence_verified=False)["categories"][
            "source_independence"
        ]

        self.assertEqual(category["state"], "UNVERIFIED")
        self.assertEqual(category["score"], 0)

    def test_explicit_flag_cannot_rescue_single_source_evidence(self):
        category = self._score(
            source_independence_verified=True,
            same_source=True,
        )["categories"]["source_independence"]

        self.assertEqual(category["state"], "UNVERIFIED")
        self.assertEqual(category["score"], 0)
        self.assertIn(
            "single-source evidence cannot establish source independence",
            category["reasons"],
        )

    def test_missing_independence_proof_stays_unknown_not_false(self):
        score = self._score()

        self.assertIn("source_independence", score["unknown_categories"])
        self.assertIsNone(score["categories"]["source_independence"]["score"])
        self.assertTrue(score["risk_separate"])
        self.assertFalse(score["risk_considered"])

    def test_risk_result_cannot_change_source_independence_proof(self):
        base = self._envelope(source_independence_verified=True)
        risky = dict(base)
        risky["risk"] = {"result": "BLOCK", "level": "HIGH"}
        safe = dict(base)
        safe["risk"] = {"result": "PASS", "level": "LOW"}

        risky_score = build_proof_score(build_evidence_receipt(risky))
        safe_score = build_proof_score(build_evidence_receipt(safe))

        self.assertEqual(risky_score, safe_score)
        self.assertEqual(
            risky_score["categories"]["source_independence"]["state"],
            "VERIFIED",
        )


if __name__ == "__main__":
    unittest.main()
