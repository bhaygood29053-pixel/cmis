from dataclasses import replace
from datetime import datetime, timezone
import unittest

from liquidity_scout.providers.x1.historical_comparison_evidence import HistoricalComparisonEvidence
from liquidity_scout.providers.x1.historical_retention_samples import build_historical_retention_sample_set


def evidence(slot: int, *, status: str = "AGREEMENT", quality: str = "HIGH") -> HistoricalComparisonEvidence:
    return HistoricalComparisonEvidence(
        schema_version="x1_historical_comparison_evidence.v1",
        fact_type="historical_block_identity_comparison",
        subject_id=f"x1:block:{slot}",
        chain="x1",
        requested_slot=slot,
        observed_at=datetime(2026, 8, 18, 5, slot % 60, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        status=status,
        official_source="x1_official_rpc",
        secondary_source="secondary_x1_rpc",
        compared_fields=("blockhash", "parentSlot"),
        conflicts=(),
        same_fact_identity_verified=status != "INSUFFICIENT_EVIDENCE",
        source_independence_verified=True,
        data_quality=quality,
    )


class HistoricalRetentionSamplesTests(unittest.TestCase):
    def test_sparse_agreements_never_prove_continuous_retention(self):
        result = build_historical_retention_sample_set((evidence(300), evidence(100), evidence(200)))
        self.assertEqual(result.requested_slots, (100, 200, 300))
        self.assertEqual(result.sample_count, 3)
        self.assertTrue(result.sampled_range_observed)
        self.assertFalse(result.continuous_coverage_verified)
        self.assertFalse(result.archival_completeness_verified)
        self.assertFalse(result.retention_verified)
        self.assertFalse(result.cmis_promotable)

    def test_conflict_is_retained_as_observed_sample_not_reconciled(self):
        result = build_historical_retention_sample_set((evidence(100), evidence(200, status="CONFLICT")))
        self.assertEqual(result.statuses, ("AGREEMENT", "CONFLICT"))
        self.assertTrue(result.sampled_range_observed)
        self.assertFalse(result.retention_verified)

    def test_insufficient_sample_prevents_sampled_range_observed(self):
        result = build_historical_retention_sample_set(
            (evidence(100), evidence(200, status="INSUFFICIENT_EVIDENCE", quality="LOW"))
        )
        self.assertFalse(result.sampled_range_observed)
        self.assertFalse(result.all_samples_same_fact_verified)

    def test_duplicate_slot_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_historical_retention_sample_set((evidence(100), evidence(100)))

    def test_source_pair_must_be_stable_and_independent(self):
        with self.assertRaisesRegex(ValueError, "same source pair"):
            build_historical_retention_sample_set(
                (evidence(100), replace(evidence(200), secondary_source="other_secondary"))
            )
        with self.assertRaisesRegex(ValueError, "distinct"):
            build_historical_retention_sample_set(
                (replace(evidence(100), secondary_source="x1_official_rpc"),)
            )

    def test_wrong_chain_or_fact_type_rejected(self):
        with self.assertRaisesRegex(ValueError, "X1"):
            build_historical_retention_sample_set((replace(evidence(100), chain="solana"),))
        with self.assertRaisesRegex(ValueError, "fact type"):
            build_historical_retention_sample_set((replace(evidence(100), fact_type="holder_count"),))

    def test_empty_and_wrong_type_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            build_historical_retention_sample_set(())
        with self.assertRaisesRegex(TypeError, "HistoricalComparisonEvidence"):
            build_historical_retention_sample_set((object(),))


if __name__ == "__main__":
    unittest.main()
