from datetime import datetime, timezone
import unittest

from liquidity_scout.cmis.concentration import build_top_account_concentration
from liquidity_scout.cmis.concentration_change import compare_top_account_concentration
from liquidity_scout.cmis.evidence_receipt import build_evidence_receipt
from liquidity_scout.cmis.intelligence_evidence import build_intelligence_evidence_bundle
from liquidity_scout.cmis.proof_score import build_proof_score
from liquidity_scout.services.cmis_verified_intelligence import (
    CONTRACT_VERSION,
    SERVICE,
    build_concentration_change_intelligence_response,
)


def evidence_bundle(*, freshness_verified=True, source_independence_verified=True):
    observed_at = "2026-08-18T12:00:00Z"
    data = {
        "scope": "asset_exact",
        "asset_identity_verified": True,
        "field_semantics_verified": True,
        "freshness_verified": freshness_verified,
        "cmis_promotable": True,
        "verification": {
            "status": "AGREEMENT",
            "code": "test_verification",
        },
        "observations": {
            "primary": {"source": "X1.Ninja", "observed_at": observed_at},
            "verifier": {"source": "X1 RPC", "observed_at": observed_at},
        },
    }
    if source_independence_verified is not None:
        data["source_independence_verified"] = source_independence_verified
    envelope = {
        "service": "market_report",
        "chain": "x1",
        "status": "ok",
        "asset": {
            "canonical_id": "mint-1",
            "mint": "mint-1",
            "symbol": "TEST",
        },
        "data": data,
        "risk": None,
        "confidence": {},
        "sources": [{"source": "X1.Ninja", "observed_at": observed_at}],
        "observed_at": observed_at,
        "warnings": [],
        "errors": [],
    }
    receipt = build_evidence_receipt(envelope)
    return {
        "evidence_receipt": receipt,
        "proof_score": build_proof_score(receipt),
    }


def concentration(*, first_amount):
    return build_top_account_concentration(
        chain="x1",
        asset_id="mint-1",
        source="X1.Ninja",
        supply_raw=1000,
        supply_decimals=0,
        requested_account_limit=2,
        accounts=[
            {"address": "acct-a", "amount": first_amount, "decimals": 0},
            {"address": "acct-b", "amount": 150, "decimals": 0},
        ],
        supply_identity_verified=True,
        account_identity_verified=True,
    )


def canonical_bundle(*, freshness_verified=True, source_independence_verified=True):
    change = compare_top_account_concentration(
        before=concentration(first_amount=250),
        after=concentration(first_amount=300),
        before_observed_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
        after_observed_at=datetime(2026, 8, 18, 13, tzinfo=timezone.utc),
    )
    return build_intelligence_evidence_bundle(
        conclusion_type="top_account_concentration_change",
        conclusion=change,
        evidence_bundles=[
            evidence_bundle(
                freshness_verified=freshness_verified,
                source_independence_verified=source_independence_verified,
            )
        ],
    )


class CMISVerifiedIntelligenceTests(unittest.TestCase):
    def test_cmis_owned_concentration_change_is_exposed_without_mutating_foundation(self):
        bundle = canonical_bundle()
        result = build_concentration_change_intelligence_response(
            bundle["intelligence_evidence_id"],
            asset_id="mint-1",
            evidence_resolver=lambda evidence_id: bundle,
            promotion_authorized=True,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["service"], SERVICE)
        self.assertIsNone(result["risk"])
        self.assertEqual(result["data"]["contract_version"], CONTRACT_VERSION)
        self.assertTrue(result["data"]["public_service_promoted"])
        self.assertTrue(result["data"]["scout_reliance_promoted"])
        self.assertFalse(result["data"]["execution_authorized"])
        self.assertEqual(
            result["data"]["accepted_conclusion_type"],
            "top_account_concentration_change",
        )
        self.assertEqual(result["data"]["facts"]["direction"], "INCREASE")
        self.assertEqual(result["asset"], {"canonical_id": "mint-1"})
        nested = result["data"]["evidence"]["intelligence_evidence"]
        self.assertFalse(nested["public_service_promoted"])
        self.assertFalse(nested["scout_reliance_promoted"])
        self.assertFalse(nested["execution_authorized"])
        self.assertTrue(result["data"]["evidence"]["freshness_verified"])
        self.assertEqual(result["data"]["evidence"]["unresolved_fields"], [])

    def test_explicit_threshold_policy_remains_separate_from_market_fact_and_risk(self):
        bundle = canonical_bundle()
        result = build_concentration_change_intelligence_response(
            bundle["intelligence_evidence_id"],
            asset_id="mint-1",
            evidence_resolver=lambda evidence_id: bundle,
            threshold_policy={
                "policy_id": "x1_concentration_watch",
                "policy_version": "1.0",
                "absolute_delta_threshold_bps": "100",
            },
            promotion_authorized=True,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["facts"]["delta_bps"], "500")
        policy = result["data"]["policy_assessment"]
        self.assertEqual(policy["status"], "EXCEEDS_THRESHOLD")
        self.assertEqual(policy["policy"]["policy_id"], "x1_concentration_watch")
        self.assertFalse(policy["risk_interpretation_verified"])
        self.assertFalse(policy["behavioral_interpretation_verified"])
        self.assertIsNone(result["data"]["risk_interpretation"])
        self.assertIsNone(result["risk"])

    def test_exact_asset_identity_is_required(self):
        bundle = canonical_bundle()
        result = build_concentration_change_intelligence_response(
            bundle["intelligence_evidence_id"],
            asset_id="other-mint",
            evidence_resolver=lambda evidence_id: bundle,
            promotion_authorized=True,
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errors"][0]["code"], "intelligence_evidence_asset_mismatch")

    def test_internal_resolver_is_required_and_missing_record_is_unavailable(self):
        bundle = canonical_bundle()
        missing_resolver = build_concentration_change_intelligence_response(
            bundle["intelligence_evidence_id"],
            asset_id="mint-1",
            evidence_resolver=None,
            promotion_authorized=True,
        )
        self.assertEqual(missing_resolver["status"], "unavailable")
        self.assertEqual(
            missing_resolver["warnings"][0]["code"],
            "internal_intelligence_evidence_resolver_unavailable",
        )

        missing_record = build_concentration_change_intelligence_response(
            bundle["intelligence_evidence_id"],
            asset_id="mint-1",
            evidence_resolver=lambda evidence_id: None,
            promotion_authorized=True,
        )
        self.assertEqual(missing_record["status"], "unavailable")
        self.assertEqual(missing_record["warnings"][0]["code"], "intelligence_evidence_not_found")

    def test_freshness_is_preserved_not_inferred_from_timestamp(self):
        bundle = canonical_bundle(freshness_verified=False)
        result = build_concentration_change_intelligence_response(
            bundle["intelligence_evidence_id"],
            asset_id="mint-1",
            evidence_resolver=lambda evidence_id: bundle,
            promotion_authorized=True,
        )
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["data"]["evidence"]["freshness_verified"])
        self.assertIn("data.freshness_verified", result["data"]["evidence"]["unresolved_fields"])
        warning_codes = {warning["code"] for warning in result["warnings"]}
        self.assertIn("intelligence_evidence_not_fresh", warning_codes)
        self.assertIn("intelligence_evidence_unresolved_fields", warning_codes)

    def test_unresolved_source_independence_keeps_service_partial_even_when_fresh(self):
        bundle = canonical_bundle(source_independence_verified=None)
        result = build_concentration_change_intelligence_response(
            bundle["intelligence_evidence_id"],
            asset_id="mint-1",
            evidence_resolver=lambda evidence_id: bundle,
            promotion_authorized=True,
        )
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["data"]["evidence"]["freshness_verified"])
        self.assertIn(
            "verification.source_independence",
            result["data"]["evidence"]["unresolved_fields"],
        )
        self.assertIn(
            "intelligence_evidence_unresolved_fields",
            {warning["code"] for warning in result["warnings"]},
        )

    def test_other_chain_remains_unavailable_before_any_resolver_call(self):
        bundle = canonical_bundle()
        calls = []

        def resolver(evidence_id):
            calls.append(evidence_id)
            return bundle

        result = build_concentration_change_intelligence_response(
            bundle["intelligence_evidence_id"],
            asset_id="mint-1",
            evidence_resolver=resolver,
            chain="solana",
            promotion_authorized=True,
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(calls, [])
        self.assertFalse(result["data"]["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
