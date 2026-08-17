import unittest

from liquidity_scout.cmis.evidence import (
    AGREEMENT,
    CONFLICT,
    IDENTITY_MISMATCH,
    INSUFFICIENT_EVIDENCE,
    UNIT_MISMATCH,
    VALUE_MISSING,
    VALUES_AGREE,
    VALUES_DISAGREE,
    build_data_quality_assessment,
    build_evidence_observation,
    compare_same_fact_exact,
)


class CMISEvidenceTests(unittest.TestCase):
    def _observation(self, **overrides):
        values = {
            "chain": "x1",
            "fact_type": "pool_reserve",
            "subject_id": "pool:asset-vault",
            "source": "X1.Ninja",
            "source_role": "market_provider",
            "observed_at": 1234.5,
            "raw_value": "1000.000000",
            "normalized_value": "1000.000000",
            "unit": "TOKEN_UNITS",
            "block_slot": 42,
            "raw_identifier": "pool-address",
            "calculation_version": "reserve-v1",
            "identity_verified": True,
            "semantics_verified": True,
            "freshness_verified": True,
        }
        values.update(overrides)
        return build_evidence_observation(**values)

    def test_observation_preserves_provenance_and_normalizes_decimal(self):
        record = self._observation(normalized_value="001000.500000")

        self.assertEqual(record["chain"], "x1")
        self.assertEqual(record["fact_type"], "pool_reserve")
        self.assertEqual(record["source_role"], "market_provider")
        self.assertEqual(record["block_slot"], 42)
        self.assertEqual(record["raw_value"], "1000.000000")
        self.assertEqual(record["normalized_value"], "1000.5")
        self.assertEqual(record["calculation_version"], "reserve-v1")

    def test_zero_is_a_valid_normalized_value(self):
        record = self._observation(raw_value="0", normalized_value=0)
        self.assertEqual(record["normalized_value"], "0")

    def test_required_identity_fields_fail_closed(self):
        with self.assertRaises(ValueError):
            self._observation(subject_id="")

    def test_exact_same_fact_agreement(self):
        primary = self._observation(normalized_value="1000.0")
        verifier = self._observation(
            source="X1 RPC",
            source_role="onchain_verifier",
            normalized_value="1000.000000",
        )

        result = compare_same_fact_exact(primary, verifier)

        self.assertEqual(result["status"], AGREEMENT)
        self.assertEqual(result["code"], VALUES_AGREE)
        self.assertTrue(result["agreement"])
        self.assertEqual(result["primary_value"], "1000")
        self.assertEqual(result["verifier_value"], "1000")

    def test_conflicting_values_are_not_averaged(self):
        primary = self._observation(normalized_value="1000")
        verifier = self._observation(
            source="X1 RPC",
            source_role="onchain_verifier",
            normalized_value="900",
        )

        result = compare_same_fact_exact(primary, verifier)

        self.assertEqual(result["status"], CONFLICT)
        self.assertEqual(result["code"], VALUES_DISAGREE)
        self.assertFalse(result["agreement"])
        self.assertNotIn("average", result)
        self.assertNotIn("value", result)

    def test_identity_mismatch_blocks_comparison(self):
        primary = self._observation()
        verifier = self._observation(
            source="X1 RPC",
            source_role="onchain_verifier",
            subject_id="different-vault",
        )

        result = compare_same_fact_exact(primary, verifier)

        self.assertEqual(result["status"], CONFLICT)
        self.assertEqual(result["code"], IDENTITY_MISMATCH)
        self.assertFalse(result["agreement"])

    def test_unit_mismatch_blocks_comparison(self):
        primary = self._observation(unit="TOKEN_UNITS")
        verifier = self._observation(
            source="X1 RPC",
            source_role="onchain_verifier",
            unit="RAW_INTEGER_UNITS",
        )

        result = compare_same_fact_exact(primary, verifier)

        self.assertEqual(result["status"], CONFLICT)
        self.assertEqual(result["code"], UNIT_MISMATCH)

    def test_missing_normalized_value_is_insufficient_evidence(self):
        primary = self._observation(normalized_value=None)
        verifier = self._observation(
            source="X1 RPC",
            source_role="onchain_verifier",
        )

        result = compare_same_fact_exact(primary, verifier)

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertEqual(result["code"], VALUE_MISSING)
        self.assertIsNone(result["agreement"])

    def test_high_quality_requires_two_sources_and_verified_agreement(self):
        primary = self._observation()
        verifier = self._observation(
            source="X1 RPC",
            source_role="onchain_verifier",
        )
        verification = compare_same_fact_exact(primary, verifier)

        quality = build_data_quality_assessment(
            observations=[primary, verifier],
            verification=verification,
        )

        self.assertEqual(quality["quality"], "HIGH")
        self.assertEqual(quality["independent_source_count"], 2)
        self.assertTrue(quality["independent_agreement_verified"])
        self.assertEqual(quality["reasons"], [])

    def test_same_source_with_two_roles_is_not_independent(self):
        primary = self._observation(source_role="market_provider")
        verifier = self._observation(source_role="onchain_verifier")
        verification = compare_same_fact_exact(primary, verifier)

        quality = build_data_quality_assessment(
            observations=[primary, verifier],
            verification=verification,
        )

        self.assertEqual(quality["quality"], "MEDIUM")
        self.assertEqual(quality["independent_source_count"], 1)
        self.assertIn("SINGLE_SOURCE_ONLY", quality["reasons"])

    def test_single_fresh_verified_source_is_medium_not_high(self):
        primary = self._observation()

        quality = build_data_quality_assessment(observations=[primary])

        self.assertEqual(quality["quality"], "MEDIUM")
        self.assertEqual(quality["independent_source_count"], 1)
        self.assertIn("SINGLE_SOURCE_ONLY", quality["reasons"])

    def test_conflict_forces_low_quality(self):
        primary = self._observation(normalized_value="1000")
        verifier = self._observation(
            source="X1 RPC",
            source_role="onchain_verifier",
            normalized_value="900",
        )
        verification = compare_same_fact_exact(primary, verifier)

        quality = build_data_quality_assessment(
            observations=[primary, verifier],
            verification=verification,
        )

        self.assertEqual(quality["quality"], "LOW")
        self.assertFalse(quality["independent_agreement_verified"])
        self.assertIn("INDEPENDENT_SOURCE_CONFLICT", quality["reasons"])

    def test_unverified_semantics_stays_low(self):
        primary = self._observation(semantics_verified=False)

        quality = build_data_quality_assessment(observations=[primary])

        self.assertEqual(quality["quality"], "LOW")
        self.assertIn("SEMANTICS_UNVERIFIED", quality["reasons"])


if __name__ == "__main__":
    unittest.main()
