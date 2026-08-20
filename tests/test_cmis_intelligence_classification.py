from copy import deepcopy
from datetime import datetime, timezone
import unittest

from liquidity_scout.cmis.concentration import build_top_account_concentration
from liquidity_scout.cmis.concentration_change import compare_top_account_concentration
from liquidity_scout.cmis.evidence_receipt import build_evidence_receipt
from liquidity_scout.cmis.intelligence_classification import (
    CLASSIFICATION_KIND,
    CLASSIFICATION_TYPE,
    RULESET_ID,
    SCHEMA,
    build_concentration_direction_classification,
    validate_concentration_direction_classification,
)
from liquidity_scout.cmis.intelligence_evidence import build_intelligence_evidence_bundle
from liquidity_scout.cmis.proof_score import build_proof_score


def evidence_bundle():
    observed_at = "2026-08-18T12:00:00Z"
    envelope = {
        "service": "market_report",
        "chain": "x1",
        "status": "ok",
        "asset": {
            "canonical_id": "mint-1",
            "mint": "mint-1",
            "symbol": "TEST",
        },
        "data": {
            "scope": "asset_exact",
            "asset_identity_verified": True,
            "field_semantics_verified": True,
            "freshness_verified": True,
            "cmis_promotable": True,
            "source_independence_verified": True,
            "verification": {
                "status": "AGREEMENT",
                "code": "test_verification",
            },
            "observations": {
                "primary": {"source": "X1.Ninja", "observed_at": observed_at},
                "verifier": {"source": "X1 RPC", "observed_at": observed_at},
            },
        },
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


def canonical_bundle(*, before_amount=250, after_amount=300):
    change = compare_top_account_concentration(
        before=concentration(first_amount=before_amount),
        after=concentration(first_amount=after_amount),
        before_observed_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
        after_observed_at=datetime(2026, 8, 18, 13, tzinfo=timezone.utc),
    )
    return build_intelligence_evidence_bundle(
        conclusion_type="top_account_concentration_change",
        conclusion=change,
        evidence_bundles=[evidence_bundle()],
    )


def resolver_for(bundle):
    return lambda evidence_id: bundle


class CMISIntelligenceClassificationTests(unittest.TestCase):
    def test_increase_is_classified_descriptively_without_interpretation(self):
        bundle = canonical_bundle(before_amount=250, after_amount=300)
        result = build_concentration_direction_classification(
            bundle["intelligence_evidence_id"],
            evidence_resolver=resolver_for(bundle),
        )

        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["classification_type"], CLASSIFICATION_TYPE)
        self.assertEqual(result["classification_kind"], CLASSIFICATION_KIND)
        self.assertEqual(result["ruleset_id"], RULESET_ID)
        self.assertEqual(result["label"], "CONCENTRATION_INCREASED")
        self.assertEqual(result["fact"]["direction"], "INCREASE")
        self.assertEqual(result["fact"]["delta_bps"], "500")
        self.assertEqual(
            result["evidence"]["intelligence_evidence_id"],
            bundle["intelligence_evidence_id"],
        )
        self.assertIsNone(result["risk_interpretation"])
        self.assertFalse(result["behavioral_interpretation_added"])
        self.assertFalse(result["ownership_interpretation_added"])
        self.assertFalse(result["provider_assertion_promoted"])
        self.assertTrue(result["proof_strength_separate_from_risk"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_decrease_and_no_change_have_exact_deterministic_labels(self):
        cases = (
            (300, 250, "CONCENTRATION_DECREASED", "DECREASE", "-500"),
            (250, 250, "CONCENTRATION_UNCHANGED", "NO_CHANGE", "0"),
        )
        for before_amount, after_amount, label, direction, delta_bps in cases:
            with self.subTest(label=label):
                bundle = canonical_bundle(
                    before_amount=before_amount,
                    after_amount=after_amount,
                )
                result = build_concentration_direction_classification(
                    bundle["intelligence_evidence_id"],
                    evidence_resolver=resolver_for(bundle),
                )
                self.assertEqual(result["label"], label)
                self.assertEqual(result["fact"]["direction"], direction)
                self.assertEqual(result["fact"]["delta_bps"], delta_bps)

    def test_malformed_or_missing_evidence_identity_fails_closed(self):
        bundle = canonical_bundle()
        with self.assertRaisesRegex(ValueError, "canonical ie_ content id"):
            build_concentration_direction_classification(
                "not-an-evidence-id",
                evidence_resolver=resolver_for(bundle),
            )
        with self.assertRaisesRegex(ValueError, "resolver is required"):
            build_concentration_direction_classification(
                bundle["intelligence_evidence_id"],
                evidence_resolver=None,
            )
        with self.assertRaisesRegex(ValueError, "was not found"):
            build_concentration_direction_classification(
                bundle["intelligence_evidence_id"],
                evidence_resolver=lambda evidence_id: None,
            )

    def test_resolved_evidence_must_match_requested_content_id(self):
        requested = canonical_bundle(before_amount=250, after_amount=300)
        other = canonical_bundle(before_amount=250, after_amount=350)
        with self.assertRaisesRegex(ValueError, "does not match the requested id"):
            build_concentration_direction_classification(
                requested["intelligence_evidence_id"],
                evidence_resolver=resolver_for(other),
            )

    def test_tampered_or_unsupported_evidence_fails_before_classification(self):
        bundle = canonical_bundle()
        tampered = deepcopy(bundle)
        tampered["conclusion"]["direction"] = "DECREASE"
        with self.assertRaises(ValueError):
            build_concentration_direction_classification(
                bundle["intelligence_evidence_id"],
                evidence_resolver=resolver_for(tampered),
            )

        unsupported = deepcopy(bundle)
        unsupported["conclusion_type"] = "wallet_activity_summary"
        with self.assertRaisesRegex(ValueError, "only top_account_concentration_change"):
            build_concentration_direction_classification(
                bundle["intelligence_evidence_id"],
                evidence_resolver=resolver_for(unsupported),
            )

    def test_caller_cannot_replace_deterministic_label_with_behavioral_claim(self):
        bundle = canonical_bundle()
        result = build_concentration_direction_classification(
            bundle["intelligence_evidence_id"],
            evidence_resolver=resolver_for(bundle),
        )
        tampered = deepcopy(result)
        tampered["label"] = "WHALE_ACCUMULATION"

        with self.assertRaisesRegex(ValueError, "deterministic canonical classification"):
            validate_concentration_direction_classification(
                tampered,
                evidence_resolver=resolver_for(bundle),
            )

    def test_classification_validation_rebuilds_exact_evidence_and_record(self):
        bundle = canonical_bundle()
        result = build_concentration_direction_classification(
            bundle["intelligence_evidence_id"],
            evidence_resolver=resolver_for(bundle),
        )
        self.assertEqual(
            validate_concentration_direction_classification(
                result,
                evidence_resolver=resolver_for(bundle),
            ),
            result,
        )


if __name__ == "__main__":
    unittest.main()
