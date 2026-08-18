from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from liquidity_scout.cmis.concentration import build_top_account_concentration
from liquidity_scout.cmis.concentration_change import compare_top_account_concentration
from liquidity_scout.cmis.evidence_receipt import build_evidence_receipt
from liquidity_scout.cmis.intelligence_evidence import build_intelligence_evidence_bundle
from liquidity_scout.cmis.intelligence_history import (
    IntelligenceHistoryLedger,
    build_history_observation,
)
from liquidity_scout.cmis.proof_score import build_proof_score
from liquidity_scout.cmis.wallet_activity import (
    build_wallet_activity_observation,
    summarize_wallet_activity,
)


class CMISIntelligenceEvidencePhase11Tests(unittest.TestCase):
    def evidence(
        self,
        *,
        chain="x1",
        source="X1.Ninja",
        verifier="X1 RPC",
        asset_id="mint-1",
        verification_status="AGREEMENT",
        promotable=True,
    ):
        observed_at = "2026-08-18T12:00:00Z"
        envelope = {
            "service": "market_report",
            "chain": chain,
            "status": "ok",
            "asset": {
                "canonical_id": asset_id,
                "mint": asset_id,
                "symbol": "TEST",
            },
            "data": {
                "scope": "asset_exact",
                "asset_identity_verified": True,
                "field_semantics_verified": True,
                "freshness_verified": True,
                "cmis_promotable": promotable,
                "verification": {
                    "status": verification_status,
                    "code": "test_verification",
                },
                "observations": {
                    "primary": {"source": source, "observed_at": observed_at},
                    "verifier": {"source": verifier, "observed_at": observed_at},
                },
            },
            "risk": None,
            "confidence": {},
            "sources": [{"source": source, "observed_at": observed_at}],
            "observed_at": observed_at,
            "warnings": [],
            "errors": [],
        }
        receipt = build_evidence_receipt(envelope)
        return {
            "evidence_receipt": receipt,
            "proof_score": build_proof_score(receipt),
        }

    def concentration(self):
        return build_top_account_concentration(
            chain="x1",
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

    def wallet(self, *, source="X1.Ninja", signature="sig-1", observed_at="2026-08-18T12:00:00Z"):
        return build_wallet_activity_observation(
            chain="x1",
            wallet="wallet-1",
            activity_type="TRANSFER_IN",
            transaction_signature=signature,
            observed_at=observed_at,
            source=source,
            verification_method="verified_transfer_v1",
            evidence_scope="transaction_exact",
            asset_id="mint-1",
            asset_amount="2",
            asset_unit="token",
            wallet_identity_verified=True,
            asset_identity_verified=True,
            transaction_identity_verified=True,
            amount_verified=True,
            transfer_direction_verified=True,
        )

    def history(self, *, value, observed_at, receipt_bundle=None):
        kwargs = {}
        if receipt_bundle is not None:
            receipt = receipt_bundle["evidence_receipt"]
            proof = receipt_bundle["proof_score"]
            kwargs = {
                "evidence_receipt_id": receipt["receipt_id"],
                "proof_strength": proof["proof_strength"],
                "proof_percent": proof["proof_percent"],
                "proof_score_method": proof["method"],
            }
        return build_history_observation(
            chain="x1",
            category="price",
            subject_id="mint-1",
            metric="price_usd",
            value=value,
            unit="USD",
            observed_at=observed_at,
            source="X1.Ninja",
            verification_method="verified_market_price_v1",
            evidence_scope="asset_exact",
            block_slot=123,
            identity_verified=True,
            semantics_verified=True,
            freshness_verified=True,
            scope_complete=False,
            **kwargs,
        )

    def test_binds_concentration_to_exact_receipt_and_proof(self):
        result = build_intelligence_evidence_bundle(
            conclusion_type="top_account_concentration",
            conclusion=self.concentration(),
            evidence_bundles=[self.evidence()],
        )
        self.assertTrue(result["intelligence_evidence_id"].startswith("ie_"))
        self.assertTrue(result["conclusion_fingerprint"].startswith("ic_"))
        self.assertTrue(result["binding"]["chain_verified"])
        self.assertTrue(result["binding"]["source_coverage_verified"])
        self.assertTrue(result["binding"]["asset_coverage_verified"])
        self.assertTrue(result["binding"]["independent_verification_present"])
        self.assertTrue(result["proof_strength_separate_from_risk"])
        self.assertFalse(result["risk_reinterpreted"])
        self.assertFalse(result["behavioral_interpretation_added"])
        self.assertFalse(result["provider_assertion_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_reported_and_verifier_observations_remain_distinct(self):
        result = build_intelligence_evidence_bundle(
            conclusion_type="top_account_concentration",
            conclusion=self.concentration(),
            evidence_bundles=[self.evidence()],
        )
        classes = result["source_classes"]
        self.assertGreaterEqual(len(classes["source_records"]), 1)
        self.assertEqual(classes["reported_observations"][0]["source"], "X1.Ninja")
        self.assertEqual(classes["verifier_observations"][0]["source"], "X1 RPC")
        self.assertEqual(classes["reported_observations"][0]["evidence_class"], "reported_observation")
        self.assertEqual(classes["verifier_observations"][0]["evidence_class"], "verifier_observation")

    def test_rejects_tampered_receipt_and_tampered_proof(self):
        bundle = self.evidence()
        tampered_receipt = deepcopy(bundle)
        tampered_receipt["evidence_receipt"]["service"] = "risk_check"
        with self.assertRaisesRegex(ValueError, "content-addressed id mismatch"):
            build_intelligence_evidence_bundle(
                conclusion_type="top_account_concentration",
                conclusion=self.concentration(),
                evidence_bundles=[tampered_receipt],
            )

        tampered_proof = deepcopy(bundle)
        tampered_proof["proof_score"]["proof_strength"] = "WEAK"
        with self.assertRaisesRegex(ValueError, "does not match"):
            build_intelligence_evidence_bundle(
                conclusion_type="top_account_concentration",
                conclusion=self.concentration(),
                evidence_bundles=[tampered_proof],
            )

    def test_rejects_wrong_chain_source_or_asset_coverage(self):
        with self.assertRaisesRegex(ValueError, "chain does not match"):
            build_intelligence_evidence_bundle(
                conclusion_type="top_account_concentration",
                conclusion=self.concentration(),
                evidence_bundles=[self.evidence(chain="solana")],
            )
        with self.assertRaisesRegex(ValueError, "do not cover conclusion sources"):
            build_intelligence_evidence_bundle(
                conclusion_type="top_account_concentration",
                conclusion=self.concentration(),
                evidence_bundles=[self.evidence(source="Other Provider", verifier="Other RPC")],
            )
        with self.assertRaisesRegex(ValueError, "do not cover conclusion assets"):
            build_intelligence_evidence_bundle(
                conclusion_type="top_account_concentration",
                conclusion=self.concentration(),
                evidence_bundles=[self.evidence(asset_id="other-mint")],
            )

    def test_rejects_duplicate_receipts_and_unsupported_conclusion_type(self):
        bundle = self.evidence()
        with self.assertRaisesRegex(ValueError, "duplicate evidence receipt"):
            build_intelligence_evidence_bundle(
                conclusion_type="top_account_concentration",
                conclusion=self.concentration(),
                evidence_bundles=[bundle, bundle],
            )
        with self.assertRaisesRegex(ValueError, "unsupported conclusion_type"):
            build_intelligence_evidence_bundle(
                conclusion_type="whale_label",
                conclusion=self.concentration(),
                evidence_bundles=[bundle],
            )

    def test_concentration_change_is_revalidated_before_evidence_binding(self):
        before = self.concentration()
        after = build_top_account_concentration(
            chain="x1",
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
        change = compare_top_account_concentration(
            before=before,
            after=after,
            before_observed_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
            after_observed_at=datetime(2026, 8, 18, 13, tzinfo=timezone.utc),
        )
        result = build_intelligence_evidence_bundle(
            conclusion_type="top_account_concentration_change",
            conclusion=change,
            evidence_bundles=[self.evidence()],
        )
        self.assertEqual(result["conclusion"]["direction"], "INCREASE")
        tampered = deepcopy(change)
        tampered["direction"] = "DECREASE"
        with self.assertRaisesRegex(ValueError, "direction is inconsistent"):
            build_intelligence_evidence_bundle(
                conclusion_type="top_account_concentration_change",
                conclusion=tampered,
                evidence_bundles=[self.evidence()],
            )

    def test_wallet_observation_and_summary_require_all_sources_and_assets(self):
        primary = self.wallet()
        verifier = self.wallet(
            source="X1 RPC",
            signature="sig-2",
            observed_at="2026-08-18T13:00:00Z",
        )
        summary = summarize_wallet_activity(
            chain="x1", wallet="wallet-1", observations=[primary, verifier]
        )
        evidence = self.evidence()
        observation_bundle = build_intelligence_evidence_bundle(
            conclusion_type="wallet_activity_observation",
            conclusion=primary,
            evidence_bundles=[evidence],
        )
        self.assertEqual(observation_bundle["binding"]["conclusion_assets"], ["mint-1"])
        summary_bundle = build_intelligence_evidence_bundle(
            conclusion_type="wallet_activity_summary",
            conclusion=summary,
            evidence_bundles=[evidence],
        )
        self.assertEqual(summary_bundle["binding"]["conclusion_sources"], ["X1 RPC", "X1.Ninja"])
        self.assertFalse(summary_bundle["behavioral_interpretation_added"])

    def test_history_observation_embedded_receipt_and_proof_must_match(self):
        evidence = self.evidence()
        observation = self.history(
            value="10",
            observed_at="2026-08-18T12:00:00Z",
            receipt_bundle=evidence,
        )
        result = build_intelligence_evidence_bundle(
            conclusion_type="history_observation",
            conclusion=observation,
            evidence_bundles=[evidence],
        )
        self.assertEqual(
            result["conclusion"]["evidence_receipt_id"],
            evidence["evidence_receipt"]["receipt_id"],
        )

        other = self.evidence(source="X1.Ninja", verifier="Verifier Two")
        with self.assertRaisesRegex(ValueError, "not present exactly once"):
            build_intelligence_evidence_bundle(
                conclusion_type="history_observation",
                conclusion=observation,
                evidence_bundles=[other],
            )

    def test_historical_comparison_accepts_integer_percent_without_truncation(self):
        evidence = self.evidence()
        with TemporaryDirectory() as directory:
            ledger = IntelligenceHistoryLedger(str(Path(directory) / "history.sqlite3"))
            ledger.store(self.history(value="10", observed_at="2026-08-18T12:00:00Z"))
            ledger.store(self.history(value="15", observed_at="2026-08-18T13:00:00Z"))
            comparison = ledger.compare_first_last(
                chain="x1",
                category="price",
                subject_id="mint-1",
                metric="price_usd",
                unit="USD",
                evidence_scope="asset_exact",
                source="X1.Ninja",
                verification_method="verified_market_price_v1",
            )
        self.assertEqual(comparison["absolute_change"], "5")
        self.assertEqual(comparison["percent_change"], "50")
        result = build_intelligence_evidence_bundle(
            conclusion_type="historical_comparison",
            conclusion=comparison,
            evidence_bundles=[evidence],
        )
        self.assertEqual(result["conclusion"]["percent_change"], "50")

        tampered = deepcopy(comparison)
        tampered["percent_change"] = "5"
        with self.assertRaisesRegex(ValueError, "change values are inconsistent"):
            build_intelligence_evidence_bundle(
                conclusion_type="historical_comparison",
                conclusion=tampered,
                evidence_bundles=[evidence],
            )

    def test_historical_comparison_cannot_promote_sparse_coverage(self):
        evidence = self.evidence()
        with TemporaryDirectory() as directory:
            ledger = IntelligenceHistoryLedger(str(Path(directory) / "history.sqlite3"))
            ledger.store(self.history(value="10", observed_at="2026-08-18T12:00:00Z"))
            ledger.store(self.history(value="15", observed_at="2026-08-18T13:00:00Z"))
            comparison = ledger.compare_first_last(
                chain="x1",
                category="price",
                subject_id="mint-1",
                metric="price_usd",
                unit="USD",
                evidence_scope="asset_exact",
                source="X1.Ninja",
                verification_method="verified_market_price_v1",
            )
        tampered = deepcopy(comparison)
        tampered["archival_completeness_proven"] = True
        with self.assertRaisesRegex(ValueError, "must remain false"):
            build_intelligence_evidence_bundle(
                conclusion_type="historical_comparison",
                conclusion=tampered,
                evidence_bundles=[evidence],
            )


if __name__ == "__main__":
    unittest.main()
