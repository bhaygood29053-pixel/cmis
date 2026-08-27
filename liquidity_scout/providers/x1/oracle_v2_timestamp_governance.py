"""Oracle V2 timestamp-unit promotion governance.

This module turns already-collected Oracle V2 timestamp correlation evidence into
an accepted timestamp-unit verification result only when an explicit,
provenance-bearing governance policy is supplied.

It owns no live collection and provides no numerical promotion defaults.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .oracle_v2_policy import (
    TIMESTAMP_UNIT_METHOD_X1_BLOCK_TIME,
    TIMESTAMP_UNIT_UNIX_MS,
)


VERSION = "1.0"

ORACLE_V2_TIMESTAMP_EVIDENCE_SERVICE = "x1_oracle_v2_timestamp_unit_probe"
ORACLE_V2_REPOSITORY = "jacklevin74/oracle-v2"
ORACLE_V2_PINNED_COMMIT = "97177f772689e44ca4eed9bb95be32ffdf0c5e66"
ORACLE_V2_PROGRAM_ID = "9mPmjK8NxJadYDiHiYAQH4WFCnKJr7ZV8ria63ZkMtv2"
ORACLE_V2_STATE_PDA = "8XZBqbKhFXHqNGzxV3Tt6gEs9r8ZrNghsRg7zBwLMGJf"

TEMPORAL_MODE_MINIMUM_SPAN = "minimum_span_ms"
TEMPORAL_MODE_SINGLE_BOUNDED_WINDOW = "single_bounded_window"
TEMPORAL_MODES = frozenset({
    TEMPORAL_MODE_MINIMUM_SPAN,
    TEMPORAL_MODE_SINGLE_BOUNDED_WINDOW,
})


def _text(value: Any) -> str | None:
    rendered = str(value or "").strip()
    return rendered or None


def _integer(
    value: Any,
    *,
    name: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if str(value).strip() not in {str(parsed), f"+{parsed}"}:
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return parsed


def _required_bool(value: Any, *, name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _valid_sha256(value: Any) -> str | None:
    text = _text(value)
    if text is None or len(text) != 64:
        return None
    try:
        int(text, 16)
    except ValueError:
        return None
    return text.lower()


def normalize_oracle_v2_timestamp_promotion_policy(
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalize explicit promotion policy without inventing defaults."""
    if policy is None:
        policy = {}
    if not isinstance(policy, Mapping):
        raise ValueError("Oracle V2 timestamp promotion policy must be a mapping")

    max_difference_ms = _integer(
        policy.get("max_difference_ms"),
        name="max_difference_ms",
        minimum=0,
    )
    minimum_sample_count = _integer(
        policy.get("minimum_sample_count"),
        name="minimum_sample_count",
        minimum=1,
    )
    minimum_distinct_relay_count = _integer(
        policy.get("minimum_distinct_relay_count"),
        name="minimum_distinct_relay_count",
        minimum=1,
        maximum=5,
    )

    max_difference_provenance = _text(
        policy.get("max_difference_provenance")
    )
    minimum_sample_count_provenance = _text(
        policy.get("minimum_sample_count_provenance")
    )
    minimum_distinct_relay_count_provenance = _text(
        policy.get("minimum_distinct_relay_count_provenance")
    )

    temporal_coverage_mode = _text(policy.get("temporal_coverage_mode"))
    temporal_coverage_provenance = _text(
        policy.get("temporal_coverage_provenance")
    )

    minimum_evidence_span_ms = None
    if temporal_coverage_mode == TEMPORAL_MODE_MINIMUM_SPAN:
        minimum_evidence_span_ms = _integer(
            policy.get("minimum_evidence_span_ms"),
            name="minimum_evidence_span_ms",
            minimum=0,
        )
    elif temporal_coverage_mode == TEMPORAL_MODE_SINGLE_BOUNDED_WINDOW:
        if policy.get("minimum_evidence_span_ms") not in {None, ""}:
            raise ValueError(
                "minimum_evidence_span_ms must be omitted for "
                "single_bounded_window mode"
            )
    elif temporal_coverage_mode is not None:
        raise ValueError(
            "temporal_coverage_mode must be one of: "
            + ", ".join(sorted(TEMPORAL_MODES))
        )

    require_deployed_binary_equivalence = _required_bool(
        policy.get("require_deployed_binary_equivalence"),
        name="require_deployed_binary_equivalence",
    )
    binary_equivalence_requirement_provenance = _text(
        policy.get("binary_equivalence_requirement_provenance")
    )

    temporal_complete = bool(
        temporal_coverage_mode in TEMPORAL_MODES
        and temporal_coverage_provenance
        and (
            temporal_coverage_mode == TEMPORAL_MODE_SINGLE_BOUNDED_WINDOW
            or minimum_evidence_span_ms is not None
        )
    )

    complete = bool(
        max_difference_ms is not None
        and max_difference_provenance
        and minimum_sample_count is not None
        and minimum_sample_count_provenance
        and minimum_distinct_relay_count is not None
        and minimum_distinct_relay_count_provenance
        and temporal_complete
        and require_deployed_binary_equivalence is not None
        and binary_equivalence_requirement_provenance
    )

    normalized = {
        "max_difference_ms": max_difference_ms,
        "max_difference_provenance": max_difference_provenance,
        "minimum_sample_count": minimum_sample_count,
        "minimum_sample_count_provenance": (
            minimum_sample_count_provenance
        ),
        "minimum_distinct_relay_count": minimum_distinct_relay_count,
        "minimum_distinct_relay_count_provenance": (
            minimum_distinct_relay_count_provenance
        ),
        "temporal_coverage_mode": temporal_coverage_mode,
        "minimum_evidence_span_ms": minimum_evidence_span_ms,
        "temporal_coverage_provenance": temporal_coverage_provenance,
        "require_deployed_binary_equivalence": (
            require_deployed_binary_equivalence
        ),
        "binary_equivalence_requirement_provenance": (
            binary_equivalence_requirement_provenance
        ),
        "policy_complete": complete,
        "has_hidden_defaults": False,
    }
    normalized["policy_sha256"] = _sha256_json({
        key: value
        for key, value in normalized.items()
        if key != "policy_sha256"
    })
    return normalized


def _validate_source_bundle(evidence: Mapping[str, Any]) -> list[str]:
    errors = []

    if evidence.get("service") != ORACLE_V2_TIMESTAMP_EVIDENCE_SERVICE:
        errors.append("unexpected_evidence_service")
    if evidence.get("chain") != "x1":
        errors.append("unexpected_chain")
    if evidence.get("status") != "evidence_collected":
        errors.append("evidence_status_not_collected")

    source = evidence.get("source")
    if not isinstance(source, Mapping):
        errors.append("source_missing_or_invalid")
        return errors

    expected = {
        "repository": ORACLE_V2_REPOSITORY,
        "pinned_commit": ORACLE_V2_PINNED_COMMIT,
        "program_id": ORACLE_V2_PROGRAM_ID,
        "state_pda": ORACLE_V2_STATE_PDA,
    }
    for field, expected_value in expected.items():
        if source.get(field) != expected_value:
            errors.append(f"source_{field}_mismatch")

    return errors


def _validate_oracle_key_evidence(
    evidence: Mapping[str, Any],
) -> tuple[str | None, list[str]]:
    errors = []
    key_evidence = evidence.get("oracle_key_evidence")
    if not isinstance(key_evidence, Mapping):
        return None, ["oracle_key_evidence_missing_or_invalid"]

    oracle_pubkey_sha256 = _valid_sha256(
        key_evidence.get("oracle_pubkey_sha256")
    )
    if oracle_pubkey_sha256 is None:
        errors.append("oracle_pubkey_sha256_invalid")

    if not _text(key_evidence.get("source")):
        errors.append("oracle_key_source_missing")

    return oracle_pubkey_sha256, errors


def _evaluate_sample(
    sample: Mapping[str, Any],
    *,
    oracle_pubkey_sha256: str,
    max_difference_ms: int,
) -> tuple[dict[str, Any], list[str]]:
    errors = []

    signature = _text(sample.get("signature"))
    if signature is None:
        errors.append("signature_missing")

    try:
        relay_index = _integer(
            sample.get("relay_index"),
            name="relay_index",
            minimum=1,
            maximum=5,
        )
    except ValueError:
        relay_index = None
        errors.append("relay_index_invalid")

    try:
        timestamp_raw = _integer(
            sample.get("timestamp_raw"),
            name="timestamp_raw",
            minimum=1,
        )
    except ValueError:
        timestamp_raw = None
        errors.append("timestamp_raw_invalid")

    try:
        block_time_seconds = _integer(
            sample.get("verified_block_time_seconds"),
            name="verified_block_time_seconds",
            minimum=0,
        )
    except ValueError:
        block_time_seconds = None
        errors.append("verified_block_time_invalid")

    if sample.get("ed25519_signature_matches_batch_argument") is not True:
        errors.append("ed25519_signature_not_bound_to_batch")
    if sample.get("ed25519_pubkey_matches_current_state") is not True:
        errors.append("ed25519_pubkey_not_bound_to_current_state")
    if sample.get("ed25519_precedes_oracle_instruction") is not True:
        errors.append("ed25519_not_preinstruction")

    configured_key = _valid_sha256(
        sample.get("configured_oracle_pubkey_sha256")
    )
    ed25519_key = _valid_sha256(sample.get("ed25519_pubkey_sha256"))
    if configured_key != oracle_pubkey_sha256:
        errors.append("configured_oracle_pubkey_mismatch")
    if ed25519_key != oracle_pubkey_sha256:
        errors.append("ed25519_pubkey_mismatch")

    if sample.get("source_contract_timestamp_unit") != TIMESTAMP_UNIT_UNIX_MS:
        errors.append("source_contract_timestamp_unit_mismatch")

    deployed_binary_equivalence = (
        sample.get("deployed_binary_source_equivalence_verified") is True
    )

    recomputed_difference_ms = None
    within_tolerance = False
    if timestamp_raw is not None and block_time_seconds is not None:
        recomputed_difference_ms = abs(
            timestamp_raw - block_time_seconds * 1000
        )
        reported_difference = sample.get("candidate_unix_ms_difference_ms")
        if reported_difference is not None:
            try:
                normalized_reported = _integer(
                    reported_difference,
                    name="candidate_unix_ms_difference_ms",
                    minimum=0,
                )
            except ValueError:
                errors.append("reported_difference_invalid")
            else:
                if normalized_reported != recomputed_difference_ms:
                    errors.append("reported_difference_mismatch")
        within_tolerance = recomputed_difference_ms <= max_difference_ms

    return {
        "signature": signature,
        "relay_index": relay_index,
        "timestamp_raw": timestamp_raw,
        "verified_block_time_seconds": block_time_seconds,
        "recomputed_difference_ms": recomputed_difference_ms,
        "within_explicit_tolerance": within_tolerance,
        "deployed_binary_source_equivalence_verified": (
            deployed_binary_equivalence
        ),
        "integrity_valid": not errors,
        "errors": errors,
    }, errors


def evaluate_oracle_v2_timestamp_unit_promotion(
    *,
    evidence: Mapping[str, Any] | None,
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate Oracle V2 timestamp-unit promotion from raw evidence samples."""
    normalized_policy = normalize_oracle_v2_timestamp_promotion_policy(policy)

    base_result = {
        "service": "oracle_v2_timestamp_unit_promotion_governance",
        "version": VERSION,
        "chain": "x1",
        "policy": normalized_policy,
        "timestamp_unit": TIMESTAMP_UNIT_UNIX_MS,
        "method": TIMESTAMP_UNIT_METHOD_X1_BLOCK_TIME,
        "timestamp_unit_verified": False,
        "freshness_verified": False,
        "price_correctness_verified": False,
        "source_independence_verified": False,
        "current_price_use_authorized": False,
        "cmis_provider_promoted": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }

    if not normalized_policy["policy_complete"]:
        return {
            **base_result,
            "status": "unavailable",
            "reason": "promotion_policy_incomplete",
            "gates": {},
            "sample_evaluations": [],
            "errors": [],
            "warnings": [
                "Timestamp-unit promotion policy is incomplete; fail closed."
            ],
            "timestamp_unit_evidence": {
                "timestamp_unit": TIMESTAMP_UNIT_UNIX_MS,
                "method": TIMESTAMP_UNIT_METHOD_X1_BLOCK_TIME,
                "verified": False,
                "provenance": None,
            },
        }

    if evidence is None or not isinstance(evidence, Mapping):
        return {
            **base_result,
            "status": "unavailable",
            "reason": "timestamp_evidence_missing_or_invalid",
            "gates": {},
            "sample_evaluations": [],
            "errors": ["timestamp_evidence_missing_or_invalid"],
            "warnings": [],
            "timestamp_unit_evidence": {
                "timestamp_unit": TIMESTAMP_UNIT_UNIX_MS,
                "method": TIMESTAMP_UNIT_METHOD_X1_BLOCK_TIME,
                "verified": False,
                "provenance": None,
            },
        }

    source_errors = _validate_source_bundle(evidence)
    oracle_pubkey_sha256, key_errors = _validate_oracle_key_evidence(evidence)

    contract = evidence.get("contract")
    contract = contract if isinstance(contract, Mapping) else {}
    top_level_binary_equivalence = (
        contract.get("deployed_binary_source_equivalence_verified") is True
    )

    samples = evidence.get("samples")
    if not isinstance(samples, list):
        samples = []
        source_errors.append("samples_missing_or_invalid")

    sample_evaluations = []
    sample_errors = []
    if oracle_pubkey_sha256 is not None:
        for index, sample in enumerate(samples):
            if not isinstance(sample, Mapping):
                evaluated = {
                    "signature": None,
                    "relay_index": None,
                    "timestamp_raw": None,
                    "verified_block_time_seconds": None,
                    "recomputed_difference_ms": None,
                    "within_explicit_tolerance": False,
                    "deployed_binary_source_equivalence_verified": False,
                    "integrity_valid": False,
                    "errors": ["sample_not_object"],
                }
                sample_evaluations.append(evaluated)
                sample_errors.append(f"sample_{index}:sample_not_object")
                continue

            evaluated, errors = _evaluate_sample(
                sample,
                oracle_pubkey_sha256=oracle_pubkey_sha256,
                max_difference_ms=normalized_policy["max_difference_ms"],
            )
            sample_evaluations.append(evaluated)
            sample_errors.extend(
                f"sample_{index}:{error}" for error in errors
            )

    signatures = [
        sample["signature"]
        for sample in sample_evaluations
        if sample["signature"] is not None
    ]
    unique_signatures = set(signatures)
    duplicate_signature_count = len(signatures) - len(unique_signatures)

    valid_samples = [
        sample for sample in sample_evaluations
        if sample["integrity_valid"]
    ]
    distinct_relays = sorted({
        sample["relay_index"]
        for sample in valid_samples
        if sample["relay_index"] is not None
    })
    block_times = [
        sample["verified_block_time_seconds"]
        for sample in valid_samples
        if sample["verified_block_time_seconds"] is not None
    ]
    raw_timestamps = [
        sample["timestamp_raw"]
        for sample in valid_samples
        if sample["timestamp_raw"] is not None
    ]

    block_time_span_ms = (
        (max(block_times) - min(block_times)) * 1000
        if block_times
        else None
    )
    raw_timestamp_span = (
        max(raw_timestamps) - min(raw_timestamps)
        if raw_timestamps
        else None
    )

    source_gate = not source_errors and not key_errors
    integrity_gate = bool(
        source_gate
        and sample_evaluations
        and not sample_errors
        and duplicate_signature_count == 0
        and len(valid_samples) == len(sample_evaluations)
    )
    correlation_gate = bool(
        integrity_gate
        and valid_samples
        and all(
            sample["within_explicit_tolerance"]
            for sample in valid_samples
        )
    )
    sample_count_gate = bool(
        integrity_gate
        and len(unique_signatures)
        >= normalized_policy["minimum_sample_count"]
    )
    relay_coverage_gate = bool(
        integrity_gate
        and len(distinct_relays)
        >= normalized_policy["minimum_distinct_relay_count"]
    )

    if (
        normalized_policy["temporal_coverage_mode"]
        == TEMPORAL_MODE_MINIMUM_SPAN
    ):
        temporal_coverage_gate = bool(
            integrity_gate
            and block_time_span_ms is not None
            and block_time_span_ms
            >= normalized_policy["minimum_evidence_span_ms"]
        )
    else:
        temporal_coverage_gate = bool(
            integrity_gate and bool(valid_samples) and block_time_span_ms is not None
        )

    if normalized_policy["require_deployed_binary_equivalence"]:
        binary_equivalence_gate = bool(
            top_level_binary_equivalence
            and valid_samples
            and all(
                sample["deployed_binary_source_equivalence_verified"]
                for sample in valid_samples
            )
        )
    else:
        binary_equivalence_gate = True

    gates = {
        "source_identity": source_gate,
        "sample_integrity": integrity_gate,
        "all_samples_within_explicit_tolerance": correlation_gate,
        "minimum_sample_count": sample_count_gate,
        "minimum_distinct_relay_count": relay_coverage_gate,
        "temporal_coverage": temporal_coverage_gate,
        "deployed_binary_equivalence_requirement": binary_equivalence_gate,
    }

    timestamp_unit_verified = all(gates.values())

    if timestamp_unit_verified:
        status = "ok"
        reason = "timestamp_unit_promotion_gates_satisfied"
    elif source_errors or key_errors or sample_errors or duplicate_signature_count:
        status = "error"
        reason = "timestamp_evidence_integrity_failed"
    else:
        status = "unavailable"
        reason = "timestamp_unit_promotion_gates_not_satisfied"

    # Bind provenance to the canonical raw evidence input, not the reduced
    # sample evaluations. Proof-bearing fields such as transaction slot,
    # instruction indexes, signed-message/signature hashes, and the presence
    # or absence of reported correlation values must remain distinguishable
    # to later Evidence Receipts.
    evidence_sha256 = _sha256_json(evidence)

    provenance = (
        "oracle_v2_timestamp_unit_promotion_governance/v1;"
        f"policy_sha256={normalized_policy['policy_sha256']};"
        f"evidence_sha256={evidence_sha256}"
    )

    errors = [
        *source_errors,
        *key_errors,
        *sample_errors,
    ]
    if duplicate_signature_count:
        errors.append("duplicate_transaction_signatures")

    warnings = [
        (
            "Timestamp-unit verification does not establish freshness, price "
            "correctness, source independence, or current-price authority."
        ),
        (
            "Historical Oracle-key continuity is preserved as a separate fact "
            "and is not inferred by this governance result."
        ),
    ]
    if not normalized_policy["require_deployed_binary_equivalence"]:
        warnings.append(
            "Policy explicitly does not require deployed binary/source "
            "equivalence for timestamp-unit verification."
        )

    return {
        **base_result,
        "status": status,
        "reason": reason,
        "timestamp_unit_verified": timestamp_unit_verified,
        "gates": gates,
        "evidence_summary": {
            "input_sample_count": len(sample_evaluations),
            "unique_signature_count": len(unique_signatures),
            "duplicate_signature_count": duplicate_signature_count,
            "valid_sample_count": len(valid_samples),
            "distinct_relay_indexes": distinct_relays,
            "distinct_relay_count": len(distinct_relays),
            "verified_block_time_span_ms": block_time_span_ms,
            "raw_timestamp_span": raw_timestamp_span,
            "maximum_recomputed_difference_ms": (
                max(
                    sample["recomputed_difference_ms"]
                    for sample in valid_samples
                    if sample["recomputed_difference_ms"] is not None
                )
                if valid_samples
                else None
            ),
            "minimum_recomputed_difference_ms": (
                min(
                    sample["recomputed_difference_ms"]
                    for sample in valid_samples
                    if sample["recomputed_difference_ms"] is not None
                )
                if valid_samples
                else None
            ),
            "historical_key_continuity_verified": (
                (
                    evidence.get("oracle_key_evidence") or {}
                ).get("historical_key_continuity_verified")
                is True
            ),
            "deployed_binary_source_equivalence_verified": (
                top_level_binary_equivalence
            ),
        },
        "sample_evaluations": sample_evaluations,
        "policy_sha256": normalized_policy["policy_sha256"],
        "evidence_sha256": evidence_sha256,
        "timestamp_unit_evidence": {
            "timestamp_unit": TIMESTAMP_UNIT_UNIX_MS,
            "method": TIMESTAMP_UNIT_METHOD_X1_BLOCK_TIME,
            "verified": timestamp_unit_verified,
            "provenance": provenance,
        },
        "errors": errors,
        "warnings": warnings,
    }


__all__ = [
    "ORACLE_V2_PINNED_COMMIT",
    "ORACLE_V2_PROGRAM_ID",
    "ORACLE_V2_REPOSITORY",
    "ORACLE_V2_STATE_PDA",
    "ORACLE_V2_TIMESTAMP_EVIDENCE_SERVICE",
    "TEMPORAL_MODE_MINIMUM_SPAN",
    "TEMPORAL_MODE_SINGLE_BOUNDED_WINDOW",
    "TEMPORAL_MODES",
    "VERSION",
    "evaluate_oracle_v2_timestamp_unit_promotion",
    "normalize_oracle_v2_timestamp_promotion_policy",
]
