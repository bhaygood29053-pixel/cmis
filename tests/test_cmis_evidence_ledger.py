import copy
import os
import tempfile
import unittest

from liquidity_scout.cmis.evidence import build_evidence_observation
from liquidity_scout.cmis.evidence_ledger import (
    VerificationEvidenceLedger,
    evidence_id_for,
    sanitize_verification_envelope,
)
from liquidity_scout.providers.x1.reserve_verification import verify_x1_pool_reserve
from liquidity_scout.services.cmis_verification_evidence import (
    build_verification_evidence_response,
)


SUBJECT = "x1:pool111:mint111:vault111"


def observation(source, value="42", *, freshness=True, slot=100):
    return build_evidence_observation(
        chain="x1",
        fact_type="pool_reserve",
        subject_id=SUBJECT,
        source=source,
        source_role="market_provider" if source == "X1.Ninja" else "onchain_verifier",
        observed_at=1000.0,
        block_slot=slot,
        raw_identifier="pool.pooledBase" if source == "X1.Ninja" else "vault111",
        raw_value=value,
        normalized_value=value,
        unit="TOKEN_UNITS",
        calculation_version="test-1",
        identity_verified=True,
        semantics_verified=True,
        freshness_verified=freshness,
        warnings=[],
    )


def envelope(value="42", *, verifier_value=None, freshness=True):
    result = verify_x1_pool_reserve(
        observation("X1.Ninja", value, freshness=freshness),
        observation(
            "X1 RPC",
            verifier_value if verifier_value is not None else value,
            freshness=freshness,
            slot=101,
        ),
    )
    return build_verification_evidence_response(
        result,
        chain="x1",
        asset={
            "symbol": "REF",
            "name": "Reference",
            "mint": "mint111",
            "api_key": "must-not-persist",
        },
        observed_at=1001.0,
    )


class VerificationEvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "evidence.db")
        self.ledger = VerificationEvidenceLedger(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_store_get_is_content_addressed_and_idempotent(self):
        item = envelope()

        first = self.ledger.store(item, recorded_at=2000.0)
        second = self.ledger.store(item, recorded_at=3000.0)

        self.assertTrue(first["inserted"])
        self.assertFalse(second["inserted"])
        self.assertEqual(first["evidence_id"], second["evidence_id"])
        self.assertTrue(first["evidence_id"].startswith("ve_"))

        stored = self.ledger.get(first["evidence_id"])
        self.assertEqual(stored["recorded_at"], 2000.0)
        self.assertEqual(stored["envelope"]["service"], "verification_evidence")
        self.assertEqual(
            stored["envelope"]["data"]["fact"]["subject_id"],
            SUBJECT,
        )
        self.assertTrue(stored["envelope"]["data"]["cmis_promotable"])

    def test_content_id_changes_when_sanitized_evidence_changes(self):
        agreement = sanitize_verification_envelope(envelope("42"))
        conflict = sanitize_verification_envelope(
            envelope("42", verifier_value="43")
        )

        self.assertNotEqual(evidence_id_for(agreement), evidence_id_for(conflict))

    def test_sanitization_drops_unknown_asset_and_transport_payload_fields(self):
        item = envelope()
        item = copy.deepcopy(item)
        item["asset"]["private_note"] = "secret"
        item["sources"][0]["headers"] = {"Authorization": "Bearer secret"}
        item["data"]["observations"]["primary"]["raw_response"] = {
            "secret": True
        }
        item["data"]["observations"]["primary"]["rpc_url"] = (
            "https://secret.example"
        )

        safe = sanitize_verification_envelope(item)
        rendered = str(safe)

        self.assertNotIn("api_key", safe["asset"])
        self.assertNotIn("private_note", safe["asset"])
        self.assertNotIn("headers", safe["sources"][0])
        self.assertNotIn("raw_response", safe["data"]["observations"]["primary"])
        self.assertNotIn("rpc_url", safe["data"]["observations"]["primary"])
        self.assertNotIn("Bearer secret", rendered)
        self.assertNotIn("secret.example", rendered)

    def test_find_and_latest_filter_one_exact_fact_identity(self):
        older = envelope("42")
        newer = envelope("43")
        other = copy.deepcopy(envelope("44"))
        for side in ("primary", "verifier"):
            other["data"]["observations"][side]["subject_id"] = "other-subject"
        other["data"]["fact"]["subject_id"] = "other-subject"

        older_id = self.ledger.store(older, recorded_at=100.0)["evidence_id"]
        newer_id = self.ledger.store(newer, recorded_at=200.0)["evidence_id"]
        self.ledger.store(other, recorded_at=300.0)

        rows = self.ledger.find(
            chain="x1",
            fact_type="pool_reserve",
            subject_id=SUBJECT,
        )
        self.assertEqual([row["evidence_id"] for row in rows], [newer_id, older_id])

        latest = self.ledger.latest(
            chain="x1",
            fact_type="pool_reserve",
            subject_id=SUBJECT,
        )
        self.assertEqual(latest["evidence_id"], newer_id)

    def test_database_reopen_preserves_records(self):
        stored = self.ledger.store(envelope(), recorded_at=123.0)

        reopened = VerificationEvidenceLedger(self.db_path)
        loaded = reopened.get(stored["evidence_id"])

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["recorded_at"], 123.0)

    def test_conflict_and_nonpromotable_agreement_can_be_stored_as_partial(self):
        conflict = envelope("42", verifier_value="43")
        stale = envelope("42", freshness=False)

        conflict_id = self.ledger.store(conflict, recorded_at=1.0)["evidence_id"]
        stale_id = self.ledger.store(stale, recorded_at=2.0)["evidence_id"]

        self.assertEqual(
            self.ledger.get(conflict_id)["envelope"]["data"]["verification"]["status"],
            "CONFLICT",
        )
        self.assertFalse(
            self.ledger.get(stale_id)["envelope"]["data"]["cmis_promotable"]
        )

    def test_error_or_wrong_service_envelopes_are_not_persisted(self):
        item = envelope()
        item["status"] = "error"
        with self.assertRaisesRegex(ValueError, "completed ok/partial"):
            self.ledger.store(item)

        item = envelope()
        item["service"] = "market_report"
        with self.assertRaisesRegex(ValueError, "only verification_evidence"):
            self.ledger.store(item)

    def test_identity_mismatch_is_rejected_even_if_envelope_shape_looks_valid(self):
        item = envelope()
        item = copy.deepcopy(item)
        item["data"]["observations"]["verifier"]["subject_id"] = "other"

        with self.assertRaisesRegex(ValueError, "observation subject mismatch"):
            self.ledger.store(item)

    def test_invalid_promotion_or_agreement_state_is_rejected(self):
        item = envelope("42", verifier_value="43")
        item = copy.deepcopy(item)
        item["data"]["cmis_promotable"] = True
        with self.assertRaisesRegex(ValueError, "only AGREEMENT"):
            self.ledger.store(item)

        item = envelope()
        item = copy.deepcopy(item)
        item["data"]["verification"]["agreement"] = "yes"
        with self.assertRaisesRegex(ValueError, "agreement state is invalid"):
            self.ledger.store(item)

    def test_recorded_at_and_limit_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "recorded_at must be finite"):
            self.ledger.store(envelope(), recorded_at=float("nan"))
        with self.assertRaisesRegex(ValueError, "limit must be an integer"):
            self.ledger.find(chain="x1", limit=0)
        with self.assertRaisesRegex(ValueError, "chain is required"):
            self.ledger.find(chain=" ")

    def test_unknown_evidence_id_returns_none(self):
        self.assertIsNone(self.ledger.get("ve_missing"))
        self.assertIsNone(self.ledger.get(" "))


if __name__ == "__main__":
    unittest.main()
