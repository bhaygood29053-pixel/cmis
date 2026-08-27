import copy
import hashlib
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import cmis_x1_oracle_v2_timestamp_unit_promote as promote
from liquidity_scout.providers.x1.oracle_v2_timestamp_promotion_policy import (
    ACCEPTED_DISTINCT_RELAY_COUNT,
    ACCEPTED_EVIDENCE_ARTIFACT_ID,
    ACCEPTED_EVIDENCE_ARTIFACT_SHA256,
    ACCEPTED_EVIDENCE_RUN_ID,
    ACCEPTED_MAX_OBSERVED_DIFFERENCE_MS,
    ACCEPTED_SAMPLE_COUNT,
    accepted_oracle_v2_timestamp_promotion_policy,
)
from liquidity_scout.providers.x1.oracle_v2_timestamp_governance import (
    ORACLE_V2_PINNED_COMMIT,
    ORACLE_V2_PROGRAM_ID,
    ORACLE_V2_REPOSITORY,
    ORACLE_V2_STATE_PDA,
    ORACLE_V2_TIMESTAMP_EVIDENCE_SERVICE,
)


ORACLE_KEY_HASH = hashlib.sha256(bytes([7]) * 32).hexdigest()


def _sample(*, index, relay_index, block_time_seconds, difference_ms):
    timestamp_raw = block_time_seconds * 1000 + difference_ms
    return {
        "signature": f"sig-{index:02d}",
        "slot": 70000000 + index,
        "verified_block_time_seconds": block_time_seconds,
        "relay_index": relay_index,
        "oracle_instruction_index": 2,
        "ed25519_instruction_index": 1,
        "timestamp_raw": timestamp_raw,
        "candidate_unix_ms_difference_ms": difference_ms,
        "signed_message_sha256": hashlib.sha256(
            f"message-{index}".encode()
        ).hexdigest(),
        "instruction_signature_sha256": hashlib.sha256(
            f"signature-{index}".encode()
        ).hexdigest(),
        "ed25519_signature_sha256": hashlib.sha256(
            f"signature-{index}".encode()
        ).hexdigest(),
        "ed25519_pubkey_sha256": ORACLE_KEY_HASH,
        "configured_oracle_pubkey_sha256": ORACLE_KEY_HASH,
        "ed25519_signature_matches_batch_argument": True,
        "ed25519_pubkey_matches_current_state": True,
        "ed25519_precedes_oracle_instruction": True,
        "source_contract_timestamp_unit": "unix_ms",
        "deployed_binary_source_equivalence_verified": False,
    }


def _accepted_evidence():
    samples = []
    differences = [576]
    differences.extend([1000] * 23)
    differences.append(1604)
    for index, difference in enumerate(differences, start=1):
        samples.append(
            _sample(
                index=index,
                relay_index=((index - 1) % 5) + 1,
                block_time_seconds=1_774_600_000 + index,
                difference_ms=difference,
            )
        )

    return {
        "service": ORACLE_V2_TIMESTAMP_EVIDENCE_SERVICE,
        "version": "0.1.0",
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
            "deployed_binary_source_equivalence_verified": False,
        },
        "oracle_key_evidence": {
            "oracle_pubkey_sha256": ORACLE_KEY_HASH,
            "source": "test current Oracle state",
            "historical_key_continuity_verified": False,
        },
        "samples": samples,
        "summary": {
            "decoded_verified_batch_samples": 25,
            "candidate_unix_ms_min_difference_ms": 576,
            "candidate_unix_ms_max_difference_ms": 1604,
        },
    }


class AcceptedTimestampPromotionPolicyTests(unittest.TestCase):
    def test_policy_is_complete_and_exactly_evidence_bound(self):
        policy = accepted_oracle_v2_timestamp_promotion_policy()

        self.assertTrue(policy["policy_complete"])
        self.assertFalse(policy["has_hidden_defaults"])
        self.assertEqual(
            policy["max_difference_ms"],
            ACCEPTED_MAX_OBSERVED_DIFFERENCE_MS,
        )
        self.assertEqual(policy["max_difference_ms"], 1604)
        self.assertEqual(
            policy["minimum_sample_count"],
            ACCEPTED_SAMPLE_COUNT,
        )
        self.assertEqual(policy["minimum_sample_count"], 25)
        self.assertEqual(
            policy["minimum_distinct_relay_count"],
            ACCEPTED_DISTINCT_RELAY_COUNT,
        )
        self.assertEqual(policy["minimum_distinct_relay_count"], 5)
        self.assertEqual(
            policy["temporal_coverage_mode"],
            "single_bounded_window",
        )
        self.assertIsNone(policy["minimum_evidence_span_ms"])
        self.assertFalse(
            policy["require_deployed_binary_equivalence"]
        )

    def test_policy_provenance_pins_accepted_evidence(self):
        policy = accepted_oracle_v2_timestamp_promotion_policy()

        self.assertIn(
            str(ACCEPTED_EVIDENCE_RUN_ID),
            policy["max_difference_provenance"],
        )
        self.assertIn(
            str(ACCEPTED_EVIDENCE_ARTIFACT_ID),
            policy["max_difference_provenance"],
        )
        self.assertEqual(
            ACCEPTED_EVIDENCE_ARTIFACT_SHA256,
            "7dd0c340490aaf738299a0900722cbd0d515b2062038de30585f99359c2e90e0",
        )
        for field in (
            "max_difference_provenance",
            "minimum_sample_count_provenance",
            "minimum_distinct_relay_count_provenance",
            "temporal_coverage_provenance",
            "binary_equivalence_requirement_provenance",
        ):
            self.assertTrue(policy[field])

    def test_accepted_evidence_promotes_timestamp_unit_only(self):
        observed_at = datetime(
            2026,
            8,
            27,
            4,
            20,
            tzinfo=timezone.utc,
        )
        fixture = _accepted_evidence()

        with patch.object(
            promote,
            "probe_timestamp_unit_evidence",
            return_value=fixture,
        ):
            result = promote.evaluate_live_timestamp_unit_promotion(
                observed_at=observed_at,
            )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["timestamp_unit_verified"])
        self.assertTrue(result["all_governance_gates_passed"])
        self.assertTrue(
            all(result["governance"]["gates"].values())
        )

        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["price_correctness_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["current_price_use_authorized"])
        self.assertFalse(result["cmis_provider_promoted"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_one_millisecond_over_ceiling_blocks_promotion(self):
        fixture = _accepted_evidence()
        fixture["samples"][-1]["timestamp_raw"] += 1
        fixture["samples"][-1][
            "candidate_unix_ms_difference_ms"
        ] = 1605

        with patch.object(
            promote,
            "probe_timestamp_unit_evidence",
            return_value=fixture,
        ):
            result = promote.evaluate_live_timestamp_unit_promotion()

        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["timestamp_unit_verified"])
        self.assertFalse(
            result["governance"]["gates"][
                "all_samples_within_explicit_tolerance"
            ]
        )

    def test_fewer_than_25_unique_samples_blocks_promotion(self):
        fixture = _accepted_evidence()
        fixture["samples"] = fixture["samples"][:-1]

        with patch.object(
            promote,
            "probe_timestamp_unit_evidence",
            return_value=fixture,
        ):
            result = promote.evaluate_live_timestamp_unit_promotion()

        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["timestamp_unit_verified"])
        self.assertFalse(
            result["governance"]["gates"]["minimum_sample_count"]
        )

    def test_missing_one_relay_blocks_promotion(self):
        fixture = _accepted_evidence()
        for sample in fixture["samples"]:
            if sample["relay_index"] == 5:
                sample["relay_index"] = 4

        with patch.object(
            promote,
            "probe_timestamp_unit_evidence",
            return_value=fixture,
        ):
            result = promote.evaluate_live_timestamp_unit_promotion()

        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["timestamp_unit_verified"])
        self.assertFalse(
            result["governance"]["gates"][
                "minimum_distinct_relay_count"
            ]
        )

    def test_raw_evidence_digest_changes_with_proof_field(self):
        first_fixture = _accepted_evidence()
        second_fixture = copy.deepcopy(first_fixture)
        second_fixture["samples"][0]["slot"] += 1

        with patch.object(
            promote,
            "probe_timestamp_unit_evidence",
            return_value=first_fixture,
        ):
            first = promote.evaluate_live_timestamp_unit_promotion()

        with patch.object(
            promote,
            "probe_timestamp_unit_evidence",
            return_value=second_fixture,
        ):
            second = promote.evaluate_live_timestamp_unit_promotion()

        self.assertTrue(first["timestamp_unit_verified"])
        self.assertTrue(second["timestamp_unit_verified"])
        self.assertNotEqual(
            first["evidence_sha256"],
            second["evidence_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
