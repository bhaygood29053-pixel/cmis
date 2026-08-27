from dataclasses import replace
from datetime import datetime, timezone
import unittest

from liquidity_scout.providers.x1.historical_comparison_evidence import HistoricalComparisonEvidence
from liquidity_scout.providers.x1.historical_retention_samples import build_historical_retention_sample_set


_BASE_FIELDS = ("blockhash", "previous_blockhash", "parent_slot")


def evidence(
    slot: int,
    *,
    status: str = "AGREEMENT",
    quality: str = "HIGH",
) -> HistoricalComparisonEvidence:
    insufficient = status == "INSUFFICIENT_EVIDENCE"
    conflicts = ("blockhash",) if status == "CONFLICT" else ()
    return HistoricalComparisonEvidence(
        schema_version="x1_historical_comparison_evidence.v2",
        fact_type="historical_block_identity_comparison",
        subject_id=f"x1:block:{slot}",
        chain="x1",
        requested_slot=slot,
        observed_at=datetime(
            2026, 8, 18, 5, slot % 60, tzinfo=timezone.utc
        ).isoformat().replace("+00:00", "Z"),
        status=status,
        official_source="x1_official_rpc",
        secondary_source="secondary_x1_rpc",
        compared_fields=() if insufficient else _BASE_FIELDS,
        conflicts=() if insufficient else conflicts,
        same_fact_identity_verified=not insufficient,
        source_independence_verified=True,
        data_quality=quality,
    )


class HistoricalRetentionSamplesTests(unittest.TestCase):
    def test_sparse_agreements_never_prove_continuous_retention(self):
        result = build_historical_retention_sample_set(
            (evidence(300), evidence(100), evidence(200))
        )
        self.assertEqual(result.requested_slots, (100, 200, 300))
        self.assertEqual(result.sample_count, 3)
        self.assertTrue(result.sampled_range_observed)
        self.assertFalse(result.continuous_coverage_verified)
        self.assertFalse(result.archival_completeness_verified)
        self.assertFalse(result.retention_verified)
        self.assertFalse(result.cmis_promotable)

    def test_single_sample_is_not_a_sampled_range(self):
        result = build_historical_retention_sample_set((evidence(100),))
        self.assertEqual(result.sample_count, 1)
        self.assertFalse(result.sampled_range_observed)
        self.assertFalse(result.retention_verified)

    def test_conflict_is_retained_as_observed_sample_not_reconciled(self):
        result = build_historical_retention_sample_set(
            (evidence(100), evidence(200, status="CONFLICT"))
        )
        self.assertEqual(result.statuses, ("AGREEMENT", "CONFLICT"))
        self.assertTrue(result.sampled_range_observed)
        self.assertFalse(result.retention_verified)

    def test_insufficient_sample_prevents_sampled_range_observed(self):
        result = build_historical_retention_sample_set(
            (
                evidence(100),
                evidence(200, status="INSUFFICIENT_EVIDENCE", quality="LOW"),
            )
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
        with self.assertRaisesRegex(ValueError, "surrounding whitespace"):
            build_historical_retention_sample_set(
                (replace(evidence(100), official_source=" x1_official_rpc"),)
            )

    def test_wrong_chain_or_fact_type_rejected(self):
        with self.assertRaisesRegex(ValueError, "X1"):
            build_historical_retention_sample_set(
                (replace(evidence(100), chain="solana"),)
            )
        with self.assertRaisesRegex(ValueError, "fact type"):
            build_historical_retention_sample_set(
                (replace(evidence(100), fact_type="holder_count"),)
            )

    def test_v1_evidence_remains_backward_compatible(self):
        result = build_historical_retention_sample_set(
            (
                replace(
                    evidence(100),
                    schema_version="x1_historical_comparison_evidence.v1",
                ),
            )
        )
        self.assertEqual(result.sample_count, 1)
        self.assertEqual(result.requested_slots, (100,))

    def test_subject_identity_schema_and_slot_must_match(self):
        with self.assertRaisesRegex(ValueError, "subject_id"):
            build_historical_retention_sample_set(
                (replace(evidence(100), subject_id="x1:block:999"),)
            )
        with self.assertRaisesRegex(ValueError, "schema version"):
            build_historical_retention_sample_set(
                (replace(evidence(100), schema_version="future.v2"),)
            )
        with self.assertRaisesRegex(ValueError, "requested_slot"):
            build_historical_retention_sample_set(
                (replace(evidence(100), requested_slot=True, subject_id="x1:block:True"),)
            )
        with self.assertRaisesRegex(ValueError, "requested_slot"):
            build_historical_retention_sample_set(
                (replace(evidence(100), requested_slot=-1, subject_id="x1:block:-1"),)
            )

    def test_status_quality_and_verification_flags_cannot_be_forged(self):
        with self.assertRaisesRegex(ValueError, "HIGH data quality"):
            build_historical_retention_sample_set((evidence(100, quality="LOW"),))
        with self.assertRaisesRegex(ValueError, "verified fact identity"):
            build_historical_retention_sample_set(
                (replace(evidence(100), same_fact_identity_verified=False),)
            )
        with self.assertRaisesRegex(ValueError, "LOW data quality"):
            build_historical_retention_sample_set(
                (evidence(100, status="INSUFFICIENT_EVIDENCE", quality="HIGH"),)
            )
        with self.assertRaisesRegex(ValueError, "same-fact identity"):
            build_historical_retention_sample_set(
                (
                    replace(
                        evidence(100, status="INSUFFICIENT_EVIDENCE", quality="LOW"),
                        same_fact_identity_verified=True,
                    ),
                )
            )
        with self.assertRaisesRegex(ValueError, "status"):
            build_historical_retention_sample_set(
                (replace(evidence(100), status="UNKNOWN"),)
            )
        with self.assertRaisesRegex(ValueError, "data quality"):
            build_historical_retention_sample_set(
                (replace(evidence(100), data_quality="MEDIUM"),)
            )

    def test_compared_field_and_conflict_invariants_are_enforced(self):
        with self.assertRaisesRegex(ValueError, "required block identity fields"):
            build_historical_retention_sample_set(
                (replace(evidence(100), compared_fields=("blockhash",)),)
            )
        with self.assertRaisesRegex(ValueError, "unsupported compared fields"):
            build_historical_retention_sample_set(
                (replace(evidence(100), compared_fields=_BASE_FIELDS + ("made_up",)),)
            )
        with self.assertRaisesRegex(ValueError, "must not contain conflicts"):
            build_historical_retention_sample_set(
                (replace(evidence(100), conflicts=("blockhash",)),)
            )
        with self.assertRaisesRegex(ValueError, "at least one conflict"):
            build_historical_retention_sample_set(
                (replace(evidence(100, status="CONFLICT"), conflicts=()),)
            )
        with self.assertRaisesRegex(ValueError, "subset of compared fields"):
            build_historical_retention_sample_set(
                (
                    replace(
                        evidence(100, status="CONFLICT"),
                        conflicts=("block_height",),
                    ),
                )
            )

    def test_current_schema_cannot_smuggle_promotion_flags(self):
        for field in (
            "archival_completeness_verified",
            "retention_verified",
            "finality_semantics_verified",
            "cmis_promotable",
        ):
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "unsupported promotion"
            ):
                build_historical_retention_sample_set(
                    (replace(evidence(100), **{field: True}),)
                )

    def test_observed_at_must_be_canonical_utc(self):
        with self.assertRaisesRegex(ValueError, "canonical UTC"):
            build_historical_retention_sample_set(
                (replace(evidence(100), observed_at="2026-08-18T05:00:00+00:00"),)
            )
        with self.assertRaisesRegex(ValueError, "ISO-8601"):
            build_historical_retention_sample_set(
                (replace(evidence(100), observed_at="not-a-dateZ"),)
            )

    def test_empty_and_wrong_type_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            build_historical_retention_sample_set(())
        with self.assertRaisesRegex(TypeError, "HistoricalComparisonEvidence"):
            build_historical_retention_sample_set((object(),))


if __name__ == "__main__":
    unittest.main()
