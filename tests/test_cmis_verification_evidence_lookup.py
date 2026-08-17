import copy
import unittest

from liquidity_scout.services.cmis_verification_evidence_lookup import (
    lookup_verification_evidence,
)


EVIDENCE_ID = "ve_abc123"
SUBJECT = "x1:pool111:mint111:vault111"


def stored_envelope():
    return {
        "service": "verification_evidence",
        "chain": "x1",
        "status": "ok",
        "asset": {"symbol": "REF", "mint": "mint111"},
        "data": {
            "fact": {
                "fact_type": "pool_reserve",
                "subject_id": SUBJECT,
                "normalized_value": "42",
                "unit": "TOKEN_UNITS",
            },
            "verification": {
                "status": "AGREEMENT",
                "code": "VALUES_AGREE",
                "agreement": True,
            },
            "data_quality": {"quality": "HIGH", "reasons": []},
            "observations": {"primary": {}, "verifier": {}},
            "cmis_promotable": True,
        },
        "risk": None,
        "confidence": {"quality": "HIGH", "cmis_promotable": True},
        "sources": [{"source": "X1.Ninja"}, {"source": "X1 RPC"}],
        "observed_at": 1001.0,
        "warnings": [],
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


def record(envelope=None):
    return {
        "evidence_id": EVIDENCE_ID,
        "recorded_at": 2000.0,
        "envelope": envelope or stored_envelope(),
    }


class CMISVerificationEvidenceLookupTests(unittest.TestCase):
    def test_lookup_by_content_addressed_evidence_id_preserves_stored_truth(self):
        ledger = FakeLedger(record=record())
        response = lookup_verification_evidence(
            ledger,
            chain="x1",
            evidence_id=EVIDENCE_ID,
        )

        self.assertEqual(ledger.get_calls, [EVIDENCE_ID])
        self.assertEqual(ledger.latest_calls, [])
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["data"]["verification"]["status"], "AGREEMENT")
        self.assertEqual(response["data"]["fact"]["normalized_value"], "42")
        self.assertTrue(response["data"]["cmis_promotable"])
        self.assertEqual(
            response["data"]["evidence_ref"],
            {"evidence_id": EVIDENCE_ID, "recorded_at": 2000.0},
        )

    def test_lookup_by_exact_fact_identity_uses_latest_only(self):
        ledger = FakeLedger(record=record())
        response = lookup_verification_evidence(
            ledger,
            chain="X1",
            fact_type="pool_reserve",
            subject_id=SUBJECT,
        )

        self.assertEqual(
            ledger.latest_calls,
            [("x1", "pool_reserve", SUBJECT)],
        )
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["data"]["fact"]["subject_id"], SUBJECT)

    def test_lookup_does_not_mutate_persisted_record(self):
        original = record()
        original_copy = copy.deepcopy(original)
        response = lookup_verification_evidence(
            FakeLedger(record=original),
            chain="x1",
            evidence_id=EVIDENCE_ID,
        )

        self.assertEqual(original, original_copy)
        self.assertIn("evidence_ref", response["data"])
        self.assertNotIn("evidence_ref", original["envelope"]["data"])

    def test_unconfigured_or_missing_ledger_record_is_unavailable(self):
        response = lookup_verification_evidence(
            None,
            chain="x1",
            evidence_id=EVIDENCE_ID,
        )
        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["warnings"][0]["code"],
            "verification_evidence_ledger_not_configured",
        )

        response = lookup_verification_evidence(
            FakeLedger(record=None),
            chain="x1",
            evidence_id=EVIDENCE_ID,
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
            evidence_id=EVIDENCE_ID,
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
            evidence_id=EVIDENCE_ID,
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

    def test_evidence_id_or_chain_mismatch_fails_closed(self):
        mismatched_id = record()
        mismatched_id["evidence_id"] = "ve_other"
        response = lookup_verification_evidence(
            FakeLedger(record=mismatched_id),
            chain="x1",
            evidence_id=EVIDENCE_ID,
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_id_mismatch",
        )

        wrong_chain = stored_envelope()
        wrong_chain["chain"] = "solana"
        response = lookup_verification_evidence(
            FakeLedger(record=record(wrong_chain)),
            chain="x1",
            evidence_id=EVIDENCE_ID,
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_evidence_record_chain_mismatch",
        )

    def test_exact_fact_lookup_rechecks_returned_fact_identity(self):
        wrong = stored_envelope()
        wrong["data"]["fact"]["subject_id"] = "other"
        response = lookup_verification_evidence(
            FakeLedger(record=record(wrong)),
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
