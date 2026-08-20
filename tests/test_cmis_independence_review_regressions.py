import hashlib
import json
import unittest

from liquidity_scout.cmis.concentration import build_top_account_concentration
from liquidity_scout.cmis.evidence_receipt import build_evidence_receipt
from liquidity_scout.cmis.intelligence_evidence import build_intelligence_evidence_bundle
from liquidity_scout.cmis.proof_score import build_proof_score
from liquidity_scout.services.cmis_contract import build_service_envelope


def _content_id(prefix, value):
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return prefix + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _conclusion():
    return build_top_account_concentration(
        chain="x1",
        asset_id="mint-1",
        source="provider-a",
        supply_raw=1000,
        supply_decimals=0,
        requested_account_limit=1,
        accounts=[{"address": "acct-a", "amount": 250, "decimals": 0}],
        supply_identity_verified=True,
        account_identity_verified=True,
    )


def _receipt():
    observed_at = "2026-08-19T10:00:00Z"
    envelope = build_service_envelope(
        "verification_evidence",
        "x1",
        "ok",
        asset={"canonical_id": "mint-1", "mint": "mint-1", "symbol": "TEST"},
        data={
            "scope": "asset_exact",
            "asset_identity_verified": True,
            "field_semantics_verified": True,
            "freshness_verified": True,
            "source_independence_verified": True,
            "cmis_promotable": True,
            "verification": {"status": "AGREEMENT", "code": "VALUES_AGREE"},
            "observations": {
                "primary": {"source": "provider-a", "observed_at": observed_at},
                "verifier": {"source": "x1_rpc", "observed_at": observed_at},
            },
        },
        confidence={},
        sources=[
            {"source": "provider-a", "observed_at": observed_at},
            {"source": "x1_rpc", "observed_at": observed_at},
        ],
        observed_at=observed_at,
    )
    return build_evidence_receipt(envelope)


class CMISIndependenceReviewRegressionTests(unittest.TestCase):
    def test_intelligence_bundle_rejects_omitted_independently_verified_field(self):
        receipt = _receipt()
        malformed = dict(receipt)
        malformed["verification"] = dict(receipt["verification"])
        malformed["verification"].pop("independently_verified")
        malformed["receipt_id"] = _content_id(
            "er_",
            {key: value for key, value in malformed.items() if key != "receipt_id"},
        )

        with self.assertRaisesRegex(
            ValueError,
            "receipt independently_verified field is required",
        ):
            build_intelligence_evidence_bundle(
                conclusion_type="top_account_concentration",
                conclusion=_conclusion(),
                evidence_bundles=[
                    {
                        "evidence_receipt": malformed,
                        "proof_score": build_proof_score(receipt),
                    }
                ],
            )

    def test_explicit_failed_independence_without_sources_remains_unverified_zero(self):
        envelope = build_service_envelope(
            "verification_evidence",
            "x1",
            "partial",
            data={
                "source_independence_verified": False,
                "verification": {
                    "status": "INSUFFICIENT_EVIDENCE",
                    "code": "NO_SOURCE_IDENTITY",
                },
            },
            confidence={},
            sources=[],
        )
        receipt = build_evidence_receipt(envelope)
        category = build_proof_score(receipt)["categories"]["source_independence"]

        self.assertEqual(category["state"], "UNVERIFIED")
        self.assertEqual(category["score"], 0)
        self.assertIn(
            "one or more source independence gates are explicitly unverified",
            category["reasons"],
        )


if __name__ == "__main__":
    unittest.main()
