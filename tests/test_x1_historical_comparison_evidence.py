from datetime import datetime, timezone
import unittest

from liquidity_scout.providers.x1.historical_block_comparison import HistoricalBlockComparison
from liquidity_scout.providers.x1.historical_comparison_evidence import build_historical_comparison_evidence


class HistoricalComparisonEvidenceTests(unittest.TestCase):
    def _comparison(self, **overrides):
        values = dict(
            requested_slot=42,
            status="AGREEMENT",
            official_source="x1_official_rpc",
            secondary_source="secondary_rpc",
            compared_fields=("blockhash", "previous_blockhash", "parent_slot", "block_height"),
            conflicts=(),
            same_fact_identity_verified=True,
            source_independence_verified=True,
        )
        values.update(overrides)
        return HistoricalBlockComparison(**values)

    def test_agreement_retains_exact_fact_and_never_promotes_archive(self):
        evidence = build_historical_comparison_evidence(
            self._comparison(), observed_at=datetime(2026, 8, 18, 5, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(evidence.subject_id, "x1:block:42")
        self.assertEqual(evidence.status, "AGREEMENT")
        self.assertEqual(evidence.data_quality, "HIGH")
        self.assertFalse(evidence.archival_completeness_verified)
        self.assertFalse(evidence.retention_verified)
        self.assertFalse(evidence.finality_semantics_verified)
        self.assertFalse(evidence.cmis_promotable)

    def test_conflict_is_preserved_without_reconciliation(self):
        evidence = build_historical_comparison_evidence(
            self._comparison(status="CONFLICT", conflicts=("blockhash",)),
            observed_at=datetime(2026, 8, 18, 5, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(evidence.status, "CONFLICT")
        self.assertEqual(evidence.conflicts, ("blockhash",))
        self.assertEqual(evidence.data_quality, "HIGH")
        self.assertFalse(evidence.cmis_promotable)

    def test_insufficient_evidence_is_low_quality(self):
        evidence = build_historical_comparison_evidence(
            self._comparison(
                status="INSUFFICIENT_EVIDENCE",
                compared_fields=(),
                same_fact_identity_verified=False,
                source_independence_verified=False,
            ),
            observed_at=datetime(2026, 8, 18, 5, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(evidence.data_quality, "LOW")

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            build_historical_comparison_evidence(
                self._comparison(), observed_at=datetime(2026, 8, 18, 5, 0)
            )

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValueError):
            build_historical_comparison_evidence(
                self._comparison(status="MAYBE"),
                observed_at=datetime(2026, 8, 18, 5, 0, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
