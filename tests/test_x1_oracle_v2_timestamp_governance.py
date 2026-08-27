import copy
import hashlib
import unittest

from liquidity_scout.providers.x1.oracle_v2_policy import (
    normalize_timestamp_unit_evidence,
)
from liquidity_scout.providers.x1.oracle_v2_timestamp_governance import (
    ORACLE_V2_PINNED_COMMIT,
    ORACLE_V2_PROGRAM_ID,
    ORACLE_V2_REPOSITORY,
    ORACLE_V2_STATE_PDA,
    ORACLE_V2_TIMESTAMP_EVIDENCE_SERVICE,
    TEMPORAL_MODE_MINIMUM_SPAN,
    TEMPORAL_MODE_SINGLE_BOUNDED_WINDOW,
    evaluate_oracle_v2_timestamp_unit_promotion,
    normalize_oracle_v2_timestamp_promotion_policy,
)


ORACLE_KEY_HASH = hashlib.sha256(bytes([7]) * 32).hexdigest()


def policy(**overrides):
    value = {
        "max_difference_ms": 2_000,
        "max_difference_provenance": "test fixture only",
        "minimum_sample_count": 3,
        "minimum_sample_count_provenance": "test fixture only",
        "minimum_distinct_relay_count": 3,
        "minimum_distinct_relay_count_provenance": "test fixture only",
        "temporal_coverage_mode": TEMPORAL_MODE_MINIMUM_SPAN,
        "minimum_evidence_span_ms": 10_000,
        "temporal_coverage_provenance": "test fixture only",
        "require_deployed_binary_equivalence": False,
        "binary_equivalence_requirement_provenance": "test fixture only",
    }
    value.update(overrides)
    return value


def sample(
    *,
    signature,
    relay_index,
    block_time_seconds,
    offset_ms=1_000,
    deployed_binary=False,
):
    timestamp_raw = block_time_seconds * 1000 + offset_ms
    return {
        "signature": signature,
        "relay_index": relay_index,
        "timestamp_raw": timestamp_raw,
        "verified_block_time_seconds": block_time_seconds,
        "candidate_unix_ms_difference_ms": abs(offset_ms),
        "ed25519_signature_matches_batch_argument": True,
        "ed25519_pubkey_matches_current_state": True,
        "ed25519_precedes_oracle_instruction": True,
        "configured_oracle_pubkey_sha256": ORACLE_KEY_HASH,
        "ed25519_pubkey_sha256": ORACLE_KEY_HASH,
        "source_contract_timestamp_unit": "unix_ms",
        "deployed_binary_source_equivalence_verified": deployed_binary,
    }


def evidence(*, samples=None, deployed_binary=False):
    if samples is None:
        samples = [
            sample(
                signature="sig-a",
                relay_index=1,
                block_time_seconds=1_780_000_000,
                offset_ms=500,
                deployed_binary=deployed_binary,
            ),
            sample(
                signature="sig-b",
                relay_index=2,
                block_time_seconds=1_780_000_010,
                offset_ms=1_200,
                deployed_binary=deployed_binary,
            ),
            sample(
                signature="sig-c",
                relay_index=3,
                block_time_seconds=1_780_000_020,
                offset_ms=2_000,
                deployed_binary=deployed_binary,
            ),
        ]

    return {
        "service": ORACLE_V2_TIMESTAMP_EVIDENCE_SERVICE,
        "chain": "x1",
        "status": "evidence_collected",
        "source": {
            "repository": ORACLE_V2_REPOSITORY,
            "pinned_commit": ORACLE_V2_PINNED_COMMIT,
            "program_id": ORACLE_V2_PROGRAM_ID,
            "state_pda": ORACLE_V2_STATE_PDA,
        },
        "contract": {
            "source_contract_timestamp_unit": "unix_ms",
            "deployed_binary_source_equivalence_verified": deployed_binary,
        },
        "oracle_key_evidence": {
            "oracle_pubkey_sha256": ORACLE_KEY_HASH,
            "source": "test Oracle state evidence",
            "historical_key_continuity_verified": False,
        },
        "samples": samples,
        # These aggregate claims are deliberately ignored by governance.
        "summary": {
            "decoded_verified_batch_samples": 999,
            "candidate_unix_ms_min_difference_ms": 0,
            "candidate_unix_ms_max_difference_ms": 0,
        },
    }


class OracleV2TimestampGovernanceTests(unittest.TestCase):
    def test_policy_has_no_hidden_defaults(self):
        normalized = normalize_oracle_v2_timestamp_promotion_policy(None)

        self.assertIsNone(normalized["max_difference_ms"])
        self.assertIsNone(normalized["minimum_sample_count"])
        self.assertIsNone(normalized["minimum_distinct_relay_count"])
        self.assertIsNone(normalized["temporal_coverage_mode"])
        self.assertIsNone(
            normalized["require_deployed_binary_equivalence"]
        )
        self.assertFalse(normalized["policy_complete"])
        self.assertFalse(normalized["has_hidden_defaults"])

    def test_every_numerical_threshold_requires_provenance(self):
        value = policy()
        value["max_difference_provenance"] = None

        normalized = normalize_oracle_v2_timestamp_promotion_policy(value)

        self.assertFalse(normalized["policy_complete"])

    def test_single_window_mode_requires_explicit_provenance_but_no_span(self):
        value = policy(
            temporal_coverage_mode=TEMPORAL_MODE_SINGLE_BOUNDED_WINDOW,
            minimum_evidence_span_ms=None,
        )

        normalized = normalize_oracle_v2_timestamp_promotion_policy(value)

        self.assertTrue(normalized["policy_complete"])
        self.assertIsNone(normalized["minimum_evidence_span_ms"])

    def test_single_window_mode_rejects_hidden_span_value(self):
        value = policy(
            temporal_coverage_mode=TEMPORAL_MODE_SINGLE_BOUNDED_WINDOW,
            minimum_evidence_span_ms=1,
        )

        with self.assertRaisesRegex(
            ValueError,
            "minimum_evidence_span_ms must be omitted",
        ):
            normalize_oracle_v2_timestamp_promotion_policy(value)

    def test_incomplete_policy_fails_closed(self):
        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(),
            policy={},
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["timestamp_unit_verified"])
        self.assertEqual(
            result["reason"],
            "promotion_policy_incomplete",
        )

    def test_all_explicit_gates_can_verify_timestamp_unit_only(self):
        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(),
            policy=policy(),
        )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["timestamp_unit_verified"])
        self.assertTrue(all(result["gates"].values()))
        self.assertEqual(
            result["evidence_summary"]["unique_signature_count"],
            3,
        )
        self.assertEqual(
            result["evidence_summary"]["distinct_relay_indexes"],
            [1, 2, 3],
        )
        self.assertEqual(
            result["evidence_summary"]["verified_block_time_span_ms"],
            20_000,
        )
        self.assertEqual(
            result["evidence_summary"]["minimum_recomputed_difference_ms"],
            500,
        )
        self.assertEqual(
            result["evidence_summary"]["maximum_recomputed_difference_ms"],
            2_000,
        )

        # Governance verifies only the timestamp unit.
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["price_correctness_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["current_price_use_authorized"])
        self.assertFalse(result["cmis_provider_promoted"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])

        normalized = normalize_timestamp_unit_evidence(
            result["timestamp_unit_evidence"]
        )
        self.assertTrue(normalized["accepted_for_policy"])

    def test_difference_equal_to_explicit_tolerance_passes(self):
        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(),
            policy=policy(max_difference_ms=2_000),
        )

        self.assertTrue(
            result["gates"]["all_samples_within_explicit_tolerance"]
        )
        self.assertTrue(result["timestamp_unit_verified"])

    def test_any_sample_outside_tolerance_blocks_verification(self):
        samples = evidence()["samples"]
        samples[2]["timestamp_raw"] = 1_780_000_020_001 + 2_000
        samples[2]["candidate_unix_ms_difference_ms"] = 2_001

        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(samples=samples),
            policy=policy(max_difference_ms=2_000),
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(
            result["gates"]["all_samples_within_explicit_tolerance"]
        )
        self.assertFalse(result["timestamp_unit_verified"])

    def test_duplicate_signatures_fail_integrity_and_do_not_inflate_count(self):
        samples = [
            sample(
                signature="dup",
                relay_index=1,
                block_time_seconds=1_780_000_000,
            ),
            sample(
                signature="dup",
                relay_index=2,
                block_time_seconds=1_780_000_010,
            ),
            sample(
                signature="sig-c",
                relay_index=3,
                block_time_seconds=1_780_000_020,
            ),
        ]

        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(samples=samples),
            policy=policy(),
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["evidence_summary"]["input_sample_count"],
            3,
        )
        self.assertEqual(
            result["evidence_summary"]["unique_signature_count"],
            2,
        )
        self.assertEqual(
            result["evidence_summary"]["duplicate_signature_count"],
            1,
        )
        self.assertIn(
            "duplicate_transaction_signatures",
            result["errors"],
        )
        self.assertFalse(result["timestamp_unit_verified"])

    def test_caller_aggregate_claims_do_not_control_sample_count(self):
        value = evidence(samples=[
            sample(
                signature="sig-a",
                relay_index=1,
                block_time_seconds=1_780_000_000,
            ),
        ])
        value["summary"]["decoded_verified_batch_samples"] = 1_000_000

        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=value,
            policy=policy(
                minimum_sample_count=2,
                minimum_distinct_relay_count=1,
                minimum_evidence_span_ms=0,
            ),
        )

        self.assertEqual(
            result["evidence_summary"]["unique_signature_count"],
            1,
        )
        self.assertFalse(result["gates"]["minimum_sample_count"])
        self.assertFalse(result["timestamp_unit_verified"])

    def test_insufficient_relay_coverage_blocks_verification(self):
        samples = [
            sample(
                signature="sig-a",
                relay_index=1,
                block_time_seconds=1_780_000_000,
            ),
            sample(
                signature="sig-b",
                relay_index=1,
                block_time_seconds=1_780_000_010,
            ),
            sample(
                signature="sig-c",
                relay_index=2,
                block_time_seconds=1_780_000_020,
            ),
        ]

        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(samples=samples),
            policy=policy(minimum_distinct_relay_count=3),
        )

        self.assertFalse(
            result["gates"]["minimum_distinct_relay_count"]
        )
        self.assertFalse(result["timestamp_unit_verified"])

    def test_temporal_span_boundary_is_inclusive(self):
        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(),
            policy=policy(minimum_evidence_span_ms=20_000),
        )

        self.assertTrue(result["gates"]["temporal_coverage"])
        self.assertTrue(result["timestamp_unit_verified"])

    def test_temporal_span_below_policy_blocks_verification(self):
        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(),
            policy=policy(minimum_evidence_span_ms=20_001),
        )

        self.assertFalse(result["gates"]["temporal_coverage"])
        self.assertFalse(result["timestamp_unit_verified"])

    def test_single_bounded_window_mode_is_explicitly_supported(self):
        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(samples=[
                sample(
                    signature="sig-a",
                    relay_index=1,
                    block_time_seconds=1_780_000_000,
                ),
            ]),
            policy=policy(
                minimum_sample_count=1,
                minimum_distinct_relay_count=1,
                temporal_coverage_mode=(
                    TEMPORAL_MODE_SINGLE_BOUNDED_WINDOW
                ),
                minimum_evidence_span_ms=None,
            ),
        )

        self.assertTrue(result["gates"]["temporal_coverage"])
        self.assertTrue(result["timestamp_unit_verified"])

    def test_bad_current_key_binding_fails_evidence_integrity(self):
        value = evidence()
        value["samples"][0]["configured_oracle_pubkey_sha256"] = (
            "00" * 32
        )

        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=value,
            policy=policy(),
        )

        self.assertEqual(result["status"], "error")
        self.assertIn(
            "sample_0:configured_oracle_pubkey_mismatch",
            result["errors"],
        )
        self.assertFalse(result["timestamp_unit_verified"])

    def test_reported_difference_is_recomputed_and_mismatch_fails(self):
        value = evidence()
        value["samples"][0]["candidate_unix_ms_difference_ms"] = 1

        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=value,
            policy=policy(),
        )

        self.assertEqual(result["status"], "error")
        self.assertIn(
            "sample_0:reported_difference_mismatch",
            result["errors"],
        )
        self.assertFalse(result["timestamp_unit_verified"])

    def test_wrong_deployment_identity_fails_closed(self):
        value = evidence()
        value["source"]["program_id"] = "WrongProgram"

        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=value,
            policy=policy(),
        )

        self.assertEqual(result["status"], "error")
        self.assertIn("source_program_id_mismatch", result["errors"])
        self.assertFalse(result["timestamp_unit_verified"])

    def test_binary_equivalence_requirement_is_explicit(self):
        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(deployed_binary=False),
            policy=policy(require_deployed_binary_equivalence=True),
        )

        self.assertFalse(
            result["gates"]["deployed_binary_equivalence_requirement"]
        )
        self.assertFalse(result["timestamp_unit_verified"])

    def test_binary_equivalence_can_be_required_and_satisfied(self):
        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(deployed_binary=True),
            policy=policy(require_deployed_binary_equivalence=True),
        )

        self.assertTrue(
            result["gates"]["deployed_binary_equivalence_requirement"]
        )
        self.assertTrue(result["timestamp_unit_verified"])

    def test_historical_key_continuity_is_preserved_but_not_inferred(self):
        result = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(),
            policy=policy(),
        )

        self.assertTrue(result["timestamp_unit_verified"])
        self.assertFalse(
            result["evidence_summary"][
                "historical_key_continuity_verified"
            ]
        )
        self.assertTrue(
            any(
                "Historical Oracle-key continuity" in warning
                for warning in result["warnings"]
            )
        )

    def test_policy_and_evidence_digests_are_deterministic(self):
        first = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=evidence(),
            policy=policy(),
        )
        second = evaluate_oracle_v2_timestamp_unit_promotion(
            evidence=copy.deepcopy(evidence()),
            policy=copy.deepcopy(policy()),
        )

        self.assertEqual(first["policy_sha256"], second["policy_sha256"])
        self.assertEqual(
            first["evidence_sha256"],
            second["evidence_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
