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
        self.assertEqual(evidence.schema_version, "x1_historical_comparison_evidence.v2")
        self.assertEqual(evidence.subject_id, "x1:block:42")
        self.assertEqual(evidence.status, "AGREEMENT")
        self.assertEqual(evidence.data_quality, "HIGH")
        self.assertIs(evidence.source_independence_verified, True)
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

    def test_unknown_independence_is_preserved_as_null(self):
        evidence = build_historical_comparison_evidence(
            self._comparison(
                status="INSUFFICIENT_EVIDENCE",
                compared_fields=(),
                same_fact_identity_verified=False,
                source_independence_verified=None,
            ),
            observed_at=datetime(2026, 8, 18, 5, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(evidence.data_quality, "LOW")
        self.assertIsNone(evidence.source_independence_verified)
        self.assertIsNone(evidence.to_dict()["source_independence_verified"])

    def test_explicit_failed_independence_is_preserved_as_false(self):
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
        self.assertIs(evidence.source_independence_verified, False)
        self.assertIs(evidence.to_dict()["source_independence_verified"], False)

    def test_non_boolean_non_null_independence_is_rejected(self):
        comparison = self._comparison()
        object.__setattr__(comparison, "source_independence_verified", "yes")
        with self.assertRaisesRegex(TypeError, "boolean or None"):
            build_historical_comparison_evidence(
                comparison,
                observed_at=datetime(2026, 8, 18, 5, 0, tzinfo=timezone.utc),
            )

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
