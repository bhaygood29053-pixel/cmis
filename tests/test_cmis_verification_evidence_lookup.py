import copy
import unittest

from liquidity_scout.cmis.evidence_ledger import (
    evidence_id_for,
    sanitize_verification_envelope,
)
from liquidity_scout.services.cmis_verification_evidence_lookup import (
    lookup_verification_evidence,
)


SUBJECT = "x1:pool111:mint111:vault111"


def stored_envelope(
    *,
    status="ok",
    promotable=True,
    freshness=True,
    source_independence_verified=True,
):
    quality = "HIGH" if promotable else "LOW"
    fact_value = "42" if promotable else None
    fact_unit = "TOKEN_UNITS" if promotable else None
    warning = [] if promotable else [
        {
            "code": "agreement_not_promotable",
            "message": "The observations agree, but the fact is not promotable.",
        }
    ]
    observation_common = {
        "chain": "x1",
        "fact_type": "pool_reserve",
        "subject_id": SUBJECT,
        "observed_at": 1000.0,
        "raw_value": "42",
        "normalized_value": "42",
        "unit": "TOKEN_UNITS",
        "calculation_version": "test-1",
        "identity_verified": True,
        "semantics_verified": True,
        "freshness_verified": freshness,
        "warnings": [],
    }
    data_quality = {
        "quality": quality,
        "independent_source_count": 2,
        "distinct_source_label_count": 2,
        "source_independence_verified": source_independence_verified,
        "identity_verified": True,
        "semantics_verified": True,
        "freshness_verified": freshness,
        "same_fact_agreement_verified": True,
        "independent_agreement_verified": source_independence_verified is True,
        "reasons": [] if freshness else ["FRESHNESS_UNVERIFIED"],
    }
    return {
        "service": "verification_evidence",
        "chain": "x1",
        "status": status,
        "asset": {"symbol": "REF", "mint": "mint111"},
        "data": {
            "fact": {
                "fact_type": "pool_reserve",
                "subject_id": SUBJECT,
                "normalized_value": fact_value,
                "unit": fact_unit,
            },
            "verification": {
                "status": "AGREEMENT",
                "code": "VALUES_AGREE",
                "agreement": True,
            },
            "data_quality": data_quality,
            "observations": {
                "primary": {
                    **observation_common,
                    "source": "X1.Ninja",
                    "source_role": "market_provider",
                    "block_slot": 100,
                    "raw_identifier": "pool.pooledBase",
                },
                "verifier": {
                    **observation_common,
                    "source": "X1 RPC",
                    "source_role": "onchain_verifier",
                    "block_slot": 101,
                    "raw_identifier": "vault111",
                },
            },
            "cmis_promotable": promotable,
        },
        "risk": None,
        "confidence": {**data_quality, "cmis_promotable": promotable},
        "sources": [
            {
                "source": "X1.Ninja",
                "role": "market_provider",
                "observed_at": 1000.0,
                "block_slot": 100,
                "calculation_version": "test-1",
            },
            {
                "source": "X1 RPC",
                "role": "onchain_verifier",
                "observed_at": 1000.0,
                "block_slot": 101,
                "calculation_version": "test-1",
            },
        ],
        "observed_at": 1001.0,
        "warnings": warning,
        "errors": [],
    }


class FakeLedger:
    def __init__(self, *, record=None, error=None):
        self.record = record
        self.error = error
        self.get_calls = []
        self.latest_calls = []

    def get(self, evidence_id):
        self.get_calls.append(evidence_id)
        if self.error:
            raise self.error
        return self.record

    def latest(self, *, chain, fact_type, subject_id):
        self.latest_calls.append((chain, fact_type, subject_id))
        if self.error:
            raise self.error
        return self.record


def record(envelope=None, *, evidence_id=None, recorded_at=2000.0):
    raw = copy.deepcopy(envelope or stored_envelope())
    safe = sanitize_verification_envelope(raw)
    return {
        "evidence_id": evidence_id or evidence_id_for(safe),
        "recorded_at": recorded_at,
        "envelope": raw,
    }


class CMISVerificationEvidenceLookupTests(unittest.TestCase):
    def test_lookup_by_content_addressed_evidence_id_preserves_stored_truth(self):
        stored = record()
        evidence_id = stored["evidence_id"]
        ledger = FakeLedger(record=stored)
        response = lookup_verification_evidence(
            ledger,
            chain="x1",
            evidence_id=evidence_id,
        )

        self.assertEqual(ledger.get_calls, [evidence_id])
        self.assertEqual(ledger.latest_calls, [])
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["data"]["verification"]["status"], "AGREEMENT")
        self.assertEqual(response["data"]["fact"]["normalized_value"], "42")
        self.assertTrue(response["data"]["cmis_promotable"])
        self.assertIs(response["data"]["data_quality"]["source_independence_verified"], True)
        self.assertEqual(
            response["data"]["evidence_ref"],
            {"evidence_id": evidence_id, "recorded_at": 2000.0},
        )

    def test_lookup_by_exact_fact_identity_uses_latest_only(self):
        stored = record()
        ledger = FakeLedger(record=stored)
        response = lookup_verification_evidence(
            ledger,
            chain="X1",
            fact_type="pool_reserve",
            subject_id=SUBJECT,
        )

        self.assertEqual(ledger.latest_calls, [("x1", "pool_reserve", SUBJECT)])
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["data"]["fact"]["subject_id"], SUBJECT)
        self.assertEqual(response["data"]["evidence_ref"]["evidence_id"], stored["evidence_id"])

    def test_lookup_preserves_partial_nonpromotable_agreement_without_promoted_fact(self):
        partial = stored_envelope(status="partial", promotable=False, freshness=False)
        stored = record(partial)
        response = lookup_verification_evidence(
            FakeLedger(record=stored),
            chain="x1",
            evidence_id=stored["evidence_id"],
        )

        self.assertEqual(response["status"], "partial")
        self.assertFalse(response["data"]["cmis_promotable"])
        self.assertIsNone(response["data"]["fact"]["normalized_value"])
        self.assertIsNone(response["data"]["fact"]["unit"])
        self.assertEqual(
            response["data"]["observations"]["primary"]["normalized_value"],
            "42",
        )

    def test_legacy_promotable_quality_without_explicit_independence_fails_closed(self):
        legacy = stored_envelope()
        for quality in (
            legacy["data"]["data_quality"],
            legacy["confidence"],
        ):
            quality.pop("distinct_source_label_count", None)
            quality.pop("source_independence_verified", None)
            quality.pop("same_fact_agreement_verified", None)

        response = lookup_verification_evidence(
            FakeLedger(
                record={
                    "evidence_id": "ve_legacy",
                    "recorded_at": 2000.0,
                    "envelope": legacy,
                }
            ),
            chain="x1",
            evidence_id="ve_legacy",
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_record_invalid",
        )

    def test_lookup_does_not_mutate_persisted_record(self):
        original = record()
        original_copy = copy.deepcopy(original)
        response = lookup_verification_evidence(
            FakeLedger(record=original),
            chain="x1",
            evidence_id=original["evidence_id"],
        )

        self.assertEqual(original, original_copy)
        self.assertIn("evidence_ref", response["data"])
        self.assertNotIn("evidence_ref", original["envelope"]["data"])

    def test_lookup_re_sanitizes_persisted_envelope_before_release(self):
        raw = stored_envelope()
        raw["sources"][0]["api_key"] = "must-not-return"
        raw["warnings"].append(
            {"code": "safe", "message": "safe", "secret": "must-not-return"}
        )
        stored = record(raw)

        response = lookup_verification_evidence(
            FakeLedger(record=stored),
            chain="x1",
            evidence_id=stored["evidence_id"],
        )

        self.assertNotIn("api_key", response["sources"][0])
        self.assertNotIn("secret", str(response))

    def test_unconfigured_or_missing_ledger_record_is_unavailable(self):
        response = lookup_verification_evidence(
            None,
            chain="x1",
            evidence_id="ve_missing",
        )
        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["warnings"][0]["code"],
            "verification_evidence_ledger_not_configured",
        )

        response = lookup_verification_evidence(
            FakeLedger(record=None),
            chain="x1",
            evidence_id="ve_missing",
        )
        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["warnings"][0]["code"],
            "verification_evidence_not_found",
        )

    def test_ledger_failure_is_sanitized_unavailable(self):
        response = lookup_verification_evidence(
            FakeLedger(error=RuntimeError("secret database detail")),
            chain="x1",
            evidence_id="ve_missing",
        )

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["warnings"][0]["code"],
            "verification_evidence_ledger_unavailable",
        )
        self.assertNotIn("secret database detail", str(response))

    def test_selector_modes_are_exact_and_mutually_exclusive(self):
        ledger = FakeLedger(record=record())
        response = lookup_verification_evidence(
            ledger,
            chain="x1",
            evidence_id="ve_any",
            fact_type="pool_reserve",
            subject_id=SUBJECT,
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_selector_conflict",
        )
        self.assertEqual(ledger.get_calls, [])
        self.assertEqual(ledger.latest_calls, [])

        response = lookup_verification_evidence(ledger, chain="x1")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_selector_required",
        )

        response = lookup_verification_evidence(
            ledger,
            chain="x1",
            fact_type="pool_reserve",
        )
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_fact_selector_incomplete",
        )

    def test_requested_evidence_id_or_chain_mismatch_fails_closed(self):
        stored = record()
        response = lookup_verification_evidence(
            FakeLedger(record=stored),
            chain="x1",
            evidence_id="ve_other",
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_id_mismatch",
        )

        wrong_chain = stored_envelope()
        wrong_chain["chain"] = "solana"
        for side in ("primary", "verifier"):
            wrong_chain["data"]["observations"][side]["chain"] = "solana"
        stored_wrong_chain = record(wrong_chain)
        response = lookup_verification_evidence(
            FakeLedger(record=stored_wrong_chain),
            chain="x1",
            evidence_id=stored_wrong_chain["evidence_id"],
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_record_chain_mismatch",
        )

    def test_invariant_breaking_tampering_is_rejected_before_hash_check(self):
        stored = record()
        original_id = stored["evidence_id"]
        stored["envelope"]["data"]["fact"]["normalized_value"] = "99"

        response = lookup_verification_evidence(
            FakeLedger(record=stored),
            chain="x1",
            evidence_id=original_id,
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_record_invalid",
        )

    def test_content_address_mismatch_detects_valid_content_tampering(self):
        stored = record()
        original_id = stored["evidence_id"]
        stored["envelope"]["asset"]["symbol"] = "ALT"

        response = lookup_verification_evidence(
            FakeLedger(record=stored),
            chain="x1",
            evidence_id=original_id,
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_content_id_mismatch",
        )

    def test_invalid_recorded_at_is_rejected(self):
        stored = record(recorded_at=float("nan"))
        response = lookup_verification_evidence(
            FakeLedger(record=stored),
            chain="x1",
            evidence_id=stored["evidence_id"],
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_record_timestamp_invalid",
        )

    def test_exact_fact_lookup_rechecks_returned_fact_identity(self):
        wrong = stored_envelope()
        wrong["data"]["fact"]["subject_id"] = "other"
        for side in ("primary", "verifier"):
            wrong["data"]["observations"][side]["subject_id"] = "other"
        stored_wrong = record(wrong)
        response = lookup_verification_evidence(
            FakeLedger(record=stored_wrong),
            chain="x1",
            fact_type="pool_reserve",
            subject_id=SUBJECT,
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_record_fact_mismatch",
        )

    def test_lookup_does_not_accept_raw_verifier_or_asset_selector(self):
        ledger = FakeLedger(record=record())
        response = lookup_verification_evidence(
            ledger,
            chain="x1",
            fact_type=None,
            subject_id=None,
        )
        self.assertEqual(response["status"], "error")
        self.assertNotIn("asset", response["data"])
        self.assertEqual(ledger.get_calls, [])
        self.assertEqual(ledger.latest_calls, [])


if __name__ == "__main__":
    unittest.main()
