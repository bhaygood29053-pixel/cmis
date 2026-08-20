from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from liquidity_scout.cmis.concentration import build_top_account_concentration
from liquidity_scout.cmis.concentration_change import compare_top_account_concentration
from liquidity_scout.cmis.evidence_receipt import build_evidence_receipt
from liquidity_scout.cmis.intelligence_evidence import build_intelligence_evidence_bundle
from liquidity_scout.cmis.intelligence_evidence_ledger import IntelligenceEvidenceLedger
from liquidity_scout.cmis.proof_score import build_proof_score


def canonical_bundle(*, chain="x1", conclusion_type="top_account_concentration_change"):
    observed_at = "2026-08-18T12:00:00Z"
    envelope = {
        "service": "market_report",
        "chain": chain,
        "status": "ok",
        "asset": {"canonical_id": "mint-1", "mint": "mint-1"},
        "data": {
            "scope": "asset_exact",
            "asset_identity_verified": True,
            "field_semantics_verified": True,
            "freshness_verified": True,
            "source_independence_verified": True,
            "cmis_promotable": True,
            "verification": {"status": "AGREEMENT", "code": "test"},
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
    evidence = {"evidence_receipt": receipt, "proof_score": build_proof_score(receipt)}

    before = build_top_account_concentration(
        chain=chain,
        asset_id="mint-1",
        source="X1.Ninja",
        supply_raw=1000,
        supply_decimals=0,
        requested_account_limit=2,
        accounts=[
            {"address": "acct-a", "amount": 250, "decimals": 0},
            {"address": "acct-b", "amount": 150, "decimals": 0},
        ],
        supply_identity_verified=True,
        account_identity_verified=True,
    )
    if conclusion_type == "top_account_concentration":
        conclusion = before
    else:
        after = build_top_account_concentration(
            chain=chain,
            asset_id="mint-1",
            source="X1.Ninja",
            supply_raw=1000,
            supply_decimals=0,
            requested_account_limit=2,
            accounts=[
                {"address": "acct-a", "amount": 300, "decimals": 0},
                {"address": "acct-b", "amount": 150, "decimals": 0},
            ],
            supply_identity_verified=True,
            account_identity_verified=True,
        )
        conclusion = compare_top_account_concentration(
            before=before,
            after=after,
            before_observed_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
            after_observed_at=datetime(2026, 8, 18, 13, tzinfo=timezone.utc),
        )
    return build_intelligence_evidence_bundle(
        conclusion_type=conclusion_type,
        conclusion=conclusion,
        evidence_bundles=[evidence],
    )


class CMISIntelligenceEvidenceLedgerTests(unittest.TestCase):
    def test_store_and_resolve_exact_cmis_owned_bundle(self):
        bundle = canonical_bundle()
        with TemporaryDirectory() as directory:
            ledger = IntelligenceEvidenceLedger(str(Path(directory) / "intelligence.sqlite3"))
            stored = ledger.store(bundle, recorded_at=123.0)
            resolved = ledger.get(bundle["intelligence_evidence_id"])

        self.assertTrue(stored["inserted"])
        self.assertEqual(stored["intelligence_evidence_id"], bundle["intelligence_evidence_id"])
        self.assertEqual(resolved, bundle)

    def test_store_is_idempotent_by_content_addressed_id(self):
        bundle = canonical_bundle()
        with TemporaryDirectory() as directory:
            ledger = IntelligenceEvidenceLedger(str(Path(directory) / "intelligence.sqlite3"))
            first = ledger.store(bundle, recorded_at=123.0)
            second = ledger.store(bundle, recorded_at=456.0)
        self.assertTrue(first["inserted"])
        self.assertFalse(second["inserted"])

    def test_tampered_bundle_is_rejected_before_persistence(self):
        bundle = canonical_bundle()
        tampered = deepcopy(bundle)
        tampered["conclusion"]["direction"] = "DECREASE"
        with TemporaryDirectory() as directory:
            ledger = IntelligenceEvidenceLedger(str(Path(directory) / "intelligence.sqlite3"))
            with self.assertRaisesRegex(ValueError, "direction is inconsistent"):
                ledger.store(tampered)

    def test_store_rejects_broader_phase11_conclusion_types(self):
        snapshot = canonical_bundle(conclusion_type="top_account_concentration")
        with TemporaryDirectory() as directory:
            ledger = IntelligenceEvidenceLedger(str(Path(directory) / "intelligence.sqlite3"))
            with self.assertRaisesRegex(
                ValueError,
                "only top_account_concentration_change",
            ):
                ledger.store(snapshot)

    def test_store_rejects_non_x1_evidence_even_when_structurally_valid(self):
        solana = canonical_bundle(chain="solana")
        with TemporaryDirectory() as directory:
            ledger = IntelligenceEvidenceLedger(str(Path(directory) / "intelligence.sqlite3"))
            with self.assertRaisesRegex(ValueError, "accepts only x1 evidence"):
                ledger.store(solana)

    def test_lookup_requires_canonical_content_id_and_missing_is_none(self):
        with TemporaryDirectory() as directory:
            ledger = IntelligenceEvidenceLedger(str(Path(directory) / "intelligence.sqlite3"))
            self.assertIsNone(ledger.get("ie_" + "a" * 64))
            with self.assertRaisesRegex(ValueError, "canonical ie_ content id"):
                ledger.get("not-an-evidence-id")


if __name__ == "__main__":
    unittest.main()
