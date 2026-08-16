"""CMIS v1.4.11 — cross-pool trusted semantics qualification for X1.

This layer consumes completed exact-pool reports and decides whether CMIS may
promote the already-proven canonical mapping and BUY/SELL semantics for the
specific pools represented by those reports.

The gate is deliberately narrower than a protocol-wide trust assertion:

* every promoted pool must independently pass the v1.4.10.3-or-newer exact
  semantics proof contract;
* at least two distinct pools and two distinct asset mints must qualify;
* all qualified pools must identify the same XDEX AMM program;
* every qualified pool must preserve its own proven structural anchor and the
  same reserve-flow BUY/SELL definitions;
* reports classified as INSUFFICIENT_EVIDENCE are excluded from the qualified
  sample and do not count as contradictory evidence;
* ambiguous, conflicting, malformed, stale, or data/transport-error reports
  fail the submitted evidence bundle closed;
* duplicate pool reports fail closed rather than being counted twice.

Promotion is scoped to ``qualified_pools_only``. A future or inactive pool never
inherits a canonical mapping from this cross-pool result and must still pass its
own exact proof. Signing and transaction execution remain disabled.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from liquidity_scout.providers.x1.proof_failure_diagnostics import (
    AMBIGUOUS,
    CONFLICTING_EVIDENCE,
    DATA_OR_TRANSPORT_ERROR,
    INSUFFICIENT_EVIDENCE,
    PROVEN,
)

VERSION = "1.4.11"
SERVICE = "cross_pool_trusted_semantics"
CHAIN = "x1"

MIN_EXACT_REPORT_VERSION = (1, 4, 10, 3)
MIN_PROVEN_POOLS = 2
MIN_DISTINCT_ASSETS = 2
REQUIRED_WINDOWS = ("1h", "6h", "24h")
PROMOTION_SCOPE = "qualified_pools_only"

BUY_DEFINITION = "canonical asset reserve OUT + canonical counter reserve IN"
SELL_DEFINITION = "canonical asset reserve IN + canonical counter reserve OUT"

_ALLOWED_OUTCOMES = {
    PROVEN,
    INSUFFICIENT_EVIDENCE,
    AMBIGUOUS,
    CONFLICTING_EVIDENCE,
    DATA_OR_TRANSPORT_ERROR,
}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return list(value)


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _version_tuple(value: Any) -> tuple[int, ...] | None:
    text = _text(value)
    if not text:
        return None
    parts = text.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def _version_at_least(value: Any, minimum: tuple[int, ...]) -> bool:
    parsed = _version_tuple(value)
    if parsed is None:
        return False
    size = max(len(parsed), len(minimum))
    left = parsed + (0,) * (size - len(parsed))
    right = minimum + (0,) * (size - len(minimum))
    return left >= right


def _direction_map(report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for raw in _sequence(report.get("directions")):
        if not isinstance(raw, Mapping):
            continue
        side = _text(raw.get("side"))
        if side in {"BUY", "SELL"} and side not in out:
            out[side] = dict(raw)
    return out


def _window_map(report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for raw in _sequence(report.get("windows")):
        if not isinstance(raw, Mapping):
            continue
        label = _text(raw.get("label"))
        if label and label not in out:
            out[label] = dict(raw)
    return out


def _mapping_identity(value: Any) -> dict[str, str] | None:
    raw = _mapping(value)
    item = {
        "asset_account": _text(raw.get("asset_account")),
        "counter_account": _text(raw.get("counter_account")),
        "counter_mint": _text(raw.get("counter_mint")),
        "shared_owner": _text(raw.get("shared_owner")),
    }
    return item if all(item.values()) else None


def _anchor(value: Any) -> dict[str, Any] | None:
    raw = _mapping(value)
    program_id = _text(raw.get("program_id"))
    pool_position = _nonnegative_int(raw.get("pool_position"))
    if not program_id or pool_position is None:
        return None
    return {"program_id": program_id, "pool_position": pool_position}


def _report_outcome(report: Mapping[str, Any]) -> str | None:
    diagnosis = _mapping(report.get("proof_diagnosis"))
    outcome = _text(diagnosis.get("proof_outcome"))
    return outcome if outcome in _ALLOWED_OUTCOMES else None


def _qualified_pool_candidate(report: Mapping[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Cross-check one claimed PROVEN exact-semantics report."""

    reasons: list[str] = []
    summary = _mapping(report.get("summary"))
    diagnosis = _mapping(report.get("proof_diagnosis"))
    operation_counts = _mapping(report.get("operation_counts"))
    pool_address = _text(report.get("pool_address"))
    asset_mint = _text(report.get("asset_mint"))
    pair = _text(report.get("pair"))
    mapping = _mapping_identity(report.get("canonical_vault_mapping"))
    anchor = _anchor(report.get("structural_anchor"))
    windows = _window_map(report)
    directions = _direction_map(report)

    if _text(report.get("service")) != "exact_pool_leg_semantics":
        reasons.append("service_mismatch")
    if _text(report.get("chain")) != CHAIN:
        reasons.append("chain_mismatch")
    if not _version_at_least(report.get("version"), MIN_EXACT_REPORT_VERSION):
        reasons.append("exact_report_version_too_old")
    if _report_outcome(report) != PROVEN:
        reasons.append("proof_outcome_not_proven")
    if _text(report.get("status")) != "exact_pool_leg_semantics_proven":
        reasons.append("terminal_status_not_proven")
    if not pool_address:
        reasons.append("pool_address_missing")
    if not asset_mint:
        reasons.append("asset_mint_missing")
    if mapping is None:
        reasons.append("canonical_vault_mapping_incomplete")
    if anchor is None:
        reasons.append("structural_anchor_incomplete")

    required_true = (
        "canonical_vault_mapping_proven",
        "history_range_proven",
        "all_successful_history_transactions_fetched",
        "all_required_windows_semantically_complete",
        "buy_semantics_proven",
        "sell_semantics_proven",
        "cross_direction_structural_anchor_consistent",
        "amm_operation_classification_available",
        "all_recognized_pool_operations_classified",
        "exact_pool_leg_semantics_proven",
    )
    for key in required_true:
        if summary.get(key) is not True:
            reasons.append(f"summary_gate_false:{key}")

    if _nonnegative_int(summary.get("unknown_pool_operation_count")) != 0:
        reasons.append("unknown_pool_operations_present")
    recognized = _nonnegative_int(summary.get("recognized_pool_operation_count"))
    if recognized is None or recognized <= 0:
        reasons.append("recognized_pool_operation_count_missing_or_zero")

    if operation_counts:
        if _nonnegative_int(operation_counts.get("unknown")) != 0:
            reasons.append("operation_counts_unknown_nonzero")
        op_recognized = _nonnegative_int(operation_counts.get("recognized"))
        if op_recognized is None or op_recognized <= 0:
            reasons.append("operation_counts_recognized_missing_or_zero")
        if recognized is not None and op_recognized is not None and recognized != op_recognized:
            reasons.append("recognized_operation_count_mismatch")
    else:
        reasons.append("operation_counts_missing")

    if report.get("transaction_execution_enabled") is True:
        reasons.append("input_report_execution_enabled")
    if report.get("signing_enabled") is True:
        reasons.append("input_report_signing_enabled")
    if summary.get("transaction_execution_enabled") is True:
        reasons.append("input_summary_execution_enabled")
    if summary.get("signing_enabled") is True:
        reasons.append("input_summary_signing_enabled")

    if diagnosis.get("blocking_stage") is not None:
        reasons.append("proven_report_has_blocking_stage")
    if diagnosis.get("blocking_code") is not None:
        reasons.append("proven_report_has_blocking_code")
    if diagnosis.get("conflicting_evidence_observed") is True:
        reasons.append("proven_report_marks_conflicting_evidence")

    if set(windows) != set(REQUIRED_WINDOWS):
        reasons.append("required_window_set_mismatch")
    for label in REQUIRED_WINDOWS:
        window = windows.get(label)
        if not window:
            continue
        if window.get("all_recognized_pool_operations_classified") is not True:
            reasons.append(f"window_unclassified:{label}")
        if window.get("all_proven_swaps_semantically_resolved") is not True:
            reasons.append(f"window_swaps_unresolved:{label}")
        window_recognized = _nonnegative_int(window.get("recognized_pool_transaction_count"))
        if window_recognized is None or window_recognized <= 0:
            reasons.append(f"window_recognized_count_missing_or_zero:{label}")
        if _nonnegative_int(window.get("unknown_pool_operation_count")) != 0:
            reasons.append(f"window_unknown_operation_present:{label}")
        if window.get("operation_classification_ratio") != 1.0:
            reasons.append(f"window_operation_classification_ratio_not_one:{label}")
        if window.get("semantic_resolution_ratio") != 1.0:
            reasons.append(f"window_semantic_resolution_ratio_not_one:{label}")

    expected_definitions = {"BUY": BUY_DEFINITION, "SELL": SELL_DEFINITION}
    for side, expected in expected_definitions.items():
        direction = directions.get(side)
        if not direction:
            reasons.append(f"direction_missing:{side}")
            continue
        if direction.get("side_semantics_proven") is not True:
            reasons.append(f"direction_unproven:{side}")
        if _text(direction.get("semantic_definition")) != expected:
            reasons.append(f"semantic_definition_mismatch:{side}")
        fingerprint = _anchor(direction.get("stable_structural_fingerprint"))
        if fingerprint is None:
            reasons.append(f"stable_structural_fingerprint_missing:{side}")
        elif anchor is not None and (
            fingerprint["program_id"] != anchor["program_id"]
            or fingerprint["pool_position"] != anchor["pool_position"]
        ):
            reasons.append(f"direction_anchor_mismatch:{side}")

    reasons = list(dict.fromkeys(reasons))
    if reasons:
        return None, reasons

    assert pool_address is not None
    assert asset_mint is not None
    assert mapping is not None
    assert anchor is not None

    return {
        "pool_address": pool_address,
        "asset_mint": asset_mint,
        "pair": pair,
        "exact_report_version": _text(report.get("version")),
        "recognized_pool_operation_count": recognized,
        "canonical_vault_mapping": mapping,
        "structural_anchor": anchor,
        "semantics": {
            "BUY": BUY_DEFINITION,
            "SELL": SELL_DEFINITION,
        },
    }, []


def _diagnosis(
    *,
    outcome: str,
    stage: str | None,
    code: str | None,
    reason: str,
    evidence: Mapping[str, Any],
    conflicting: bool = False,
    retryable: bool = False,
) -> dict[str, Any]:
    return {
        "proof_outcome": outcome,
        "blocking_stage": stage,
        "blocking_code": code,
        "blocking_reason": reason,
        "evidence": dict(evidence),
        "conflicting_evidence_observed": conflicting,
        "retryable": retryable,
    }


def qualify_cross_pool_trusted_semantics(
    reports: Sequence[Mapping[str, Any]],
    *,
    min_proven_pools: int = MIN_PROVEN_POOLS,
    min_distinct_assets: int = MIN_DISTINCT_ASSETS,
) -> dict[str, Any]:
    """Promote trusted semantics only for a fail-closed, cross-pool evidence bundle."""

    if isinstance(min_proven_pools, bool) or not isinstance(min_proven_pools, int):
        raise ValueError("min_proven_pools must be an integer")
    if isinstance(min_distinct_assets, bool) or not isinstance(min_distinct_assets, int):
        raise ValueError("min_distinct_assets must be an integer")
    if min_proven_pools < MIN_PROVEN_POOLS:
        raise ValueError(f"min_proven_pools cannot be lower than {MIN_PROVEN_POOLS}")
    if min_distinct_assets < MIN_DISTINCT_ASSETS:
        raise ValueError(f"min_distinct_assets cannot be lower than {MIN_DISTINCT_ASSETS}")
    if not isinstance(reports, Sequence) or isinstance(reports, (str, bytes)):
        raise ValueError("reports must be a sequence of exact-semantics report mappings")

    report_records: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    seen_pools: set[str] = set()

    for index, raw in enumerate(reports):
        if not isinstance(raw, Mapping):
            blockers.append(
                {
                    "index": index,
                    "pool_address": None,
                    "asset_mint": None,
                    "blocking_code": "INVALID_REPORT_MAPPING",
                    "reason": "Submitted evidence item is not a mapping.",
                }
            )
            report_records.append(
                {
                    "index": index,
                    "pool_address": None,
                    "asset_mint": None,
                    "proof_outcome": None,
                    "disposition": "BLOCKED",
                    "blocking_code": "INVALID_REPORT_MAPPING",
                }
            )
            continue

        report = dict(raw)
        pool_address = _text(report.get("pool_address"))
        asset_mint = _text(report.get("asset_mint"))
        outcome = _report_outcome(report)
        diagnosis = _mapping(report.get("proof_diagnosis"))
        report_version = _text(report.get("version"))

        record = {
            "index": index,
            "pool_address": pool_address,
            "asset_mint": asset_mint,
            "report_version": report_version,
            "status": _text(report.get("status")),
            "proof_outcome": outcome,
            "blocking_code": _text(diagnosis.get("blocking_code")),
            "disposition": None,
        }

        if not pool_address:
            record["disposition"] = "BLOCKED"
            record["blocking_code"] = "POOL_ADDRESS_MISSING"
            blockers.append(
                {
                    "index": index,
                    "pool_address": None,
                    "asset_mint": asset_mint,
                    "blocking_code": "POOL_ADDRESS_MISSING",
                    "reason": "Exact-semantics report does not identify a pool address.",
                }
            )
            report_records.append(record)
            continue

        if pool_address in seen_pools:
            record["disposition"] = "BLOCKED"
            record["blocking_code"] = "DUPLICATE_POOL_REPORT"
            blockers.append(
                {
                    "index": index,
                    "pool_address": pool_address,
                    "asset_mint": asset_mint,
                    "blocking_code": "DUPLICATE_POOL_REPORT",
                    "reason": "The same pool appears more than once in the evidence bundle.",
                }
            )
            report_records.append(record)
            continue
        seen_pools.add(pool_address)

        if not _version_at_least(report_version, MIN_EXACT_REPORT_VERSION):
            record["disposition"] = "BLOCKED"
            record["blocking_code"] = "EXACT_REPORT_VERSION_TOO_OLD"
            blockers.append(
                {
                    "index": index,
                    "pool_address": pool_address,
                    "asset_mint": asset_mint,
                    "blocking_code": "EXACT_REPORT_VERSION_TOO_OLD",
                    "reason": (
                        "Cross-pool promotion requires literal-window diagnostics "
                        "from exact-semantics v1.4.10.3 or newer."
                    ),
                }
            )
            report_records.append(record)
            continue

        if outcome == INSUFFICIENT_EVIDENCE:
            record["disposition"] = "EXCLUDED_INSUFFICIENT_EVIDENCE"
            excluded_item = {
                "index": index,
                "pool_address": pool_address,
                "asset_mint": asset_mint,
                "proof_outcome": outcome,
                "blocking_stage": _text(diagnosis.get("blocking_stage")),
                "blocking_code": _text(diagnosis.get("blocking_code")),
                "blocking_reason": _text(diagnosis.get("blocking_reason")),
                "retryable": diagnosis.get("retryable") is True,
            }
            excluded.append(excluded_item)
            report_records.append(record)
            continue

        if outcome in {AMBIGUOUS, CONFLICTING_EVIDENCE, DATA_OR_TRANSPORT_ERROR}:
            record["disposition"] = "BLOCKED"
            blockers.append(
                {
                    "index": index,
                    "pool_address": pool_address,
                    "asset_mint": asset_mint,
                    "proof_outcome": outcome,
                    "blocking_code": _text(diagnosis.get("blocking_code")) or outcome,
                    "reason": _text(diagnosis.get("blocking_reason")) or (
                        "Submitted report contains blocking evidence."
                    ),
                }
            )
            report_records.append(record)
            continue

        if outcome != PROVEN:
            record["disposition"] = "BLOCKED"
            record["blocking_code"] = "MISSING_OR_UNKNOWN_PROOF_OUTCOME"
            blockers.append(
                {
                    "index": index,
                    "pool_address": pool_address,
                    "asset_mint": asset_mint,
                    "blocking_code": "MISSING_OR_UNKNOWN_PROOF_OUTCOME",
                    "reason": (
                        "Exact-semantics report does not expose a recognized proof "
                        "diagnosis and cannot participate in promotion."
                    ),
                }
            )
            report_records.append(record)
            continue

        candidate, reasons = _qualified_pool_candidate(report)
        if candidate is None:
            record["disposition"] = "BLOCKED"
            record["blocking_code"] = "PROVEN_REPORT_CROSSCHECK_FAILED"
            blockers.append(
                {
                    "index": index,
                    "pool_address": pool_address,
                    "asset_mint": asset_mint,
                    "blocking_code": "PROVEN_REPORT_CROSSCHECK_FAILED",
                    "reason": (
                        "A report claiming PROVEN did not satisfy every deterministic "
                        "v1.4.11 cross-check."
                    ),
                    "rejection_reasons": reasons,
                }
            )
        else:
            record["disposition"] = "QUALIFIED_CANDIDATE"
            candidates.append(candidate)
        report_records.append(record)

    program_ids = {
        item["structural_anchor"]["program_id"]
        for item in candidates
    }
    distinct_assets = {item["asset_mint"] for item in candidates}
    mapping_pairs = {
        (
            item["canonical_vault_mapping"]["asset_account"],
            item["canonical_vault_mapping"]["counter_account"],
        )
        for item in candidates
    }
    mapping_identity_unique = len(mapping_pairs) == len(candidates)
    program_consistent = bool(candidates and len(program_ids) == 1)
    common_program_id = next(iter(program_ids)) if program_consistent else None

    if candidates and not mapping_identity_unique:
        blockers.append(
            {
                "blocking_code": "CANONICAL_VAULT_PAIR_REUSED_ACROSS_POOLS",
                "reason": (
                    "Two distinct submitted pools resolve to the same canonical vault "
                    "account pair; CMIS refuses cross-pool promotion."
                ),
            }
        )

    if len(candidates) >= min_proven_pools and not program_consistent:
        blockers.append(
            {
                "blocking_code": "CROSS_POOL_PROGRAM_ID_CONFLICT",
                "reason": (
                    "Individually proven pools do not share one XDEX AMM program "
                    "identity, so a common trusted semantics profile is unproven."
                ),
                "program_ids": sorted(program_ids),
            }
        )

    qualified_count = len(candidates)
    enough_pools = qualified_count >= min_proven_pools
    enough_assets = len(distinct_assets) >= min_distinct_assets
    no_blockers = not blockers

    promoted = bool(
        no_blockers
        and enough_pools
        and enough_assets
        and program_consistent
        and mapping_identity_unique
    )

    evidence = {
        "submitted_report_count": len(reports),
        "qualified_pool_count": qualified_count,
        "excluded_insufficient_evidence_count": len(excluded),
        "blocking_report_count": len(blockers),
        "distinct_qualified_asset_count": len(distinct_assets),
        "required_minimum_proven_pools": min_proven_pools,
        "required_minimum_distinct_assets": min_distinct_assets,
        "qualified_program_ids": sorted(program_ids),
        "cross_pool_program_consistent": program_consistent,
        "canonical_vault_pair_identity_unique": mapping_identity_unique,
    }

    if promoted:
        status = "trusted_semantics_promoted"
        diagnosis = _diagnosis(
            outcome=PROVEN,
            stage=None,
            code=None,
            reason=(
                "Multiple distinct X1/XDEX pools independently proved canonical "
                "reserve semantics under one AMM program. Trust is promoted only "
                "for those individually proven pools."
            ),
            evidence=evidence,
        )
    elif blockers:
        blocker_outcomes = {
            _text(item.get("proof_outcome"))
            for item in blockers
            if _text(item.get("proof_outcome"))
        }
        conflicting = bool(
            CONFLICTING_EVIDENCE in blocker_outcomes
            or AMBIGUOUS in blocker_outcomes
            or any(
                item.get("blocking_code") in {
                    "CROSS_POOL_PROGRAM_ID_CONFLICT",
                    "CANONICAL_VAULT_PAIR_REUSED_ACROSS_POOLS",
                }
                for item in blockers
            )
        )
        if DATA_OR_TRANSPORT_ERROR in blocker_outcomes:
            outcome = DATA_OR_TRANSPORT_ERROR
        elif conflicting:
            outcome = CONFLICTING_EVIDENCE
        else:
            outcome = INSUFFICIENT_EVIDENCE
        status = "cross_pool_evidence_blocked"
        diagnosis = _diagnosis(
            outcome=outcome,
            stage="cross_pool_trusted_semantics",
            code=_text(blockers[0].get("blocking_code")) or "CROSS_POOL_EVIDENCE_BLOCKED",
            reason=(
                "At least one submitted report or cross-pool structural comparison "
                "fails a mandatory qualification gate. Promotion remains disabled."
            ),
            evidence={**evidence, "blockers": blockers},
            conflicting=conflicting,
            retryable=True,
        )
    else:
        status = "insufficient_cross_pool_evidence"
        if not enough_pools:
            code = "MINIMUM_PROVEN_POOL_COUNT_NOT_MET"
            reason = (
                "Too few distinct pools independently prove exact semantics for "
                "cross-pool promotion."
            )
        elif not enough_assets:
            code = "MINIMUM_DISTINCT_ASSET_COUNT_NOT_MET"
            reason = (
                "The qualified pool set does not cover enough distinct asset mints "
                "for cross-pool promotion."
            )
        else:
            code = "CROSS_POOL_PROMOTION_GATES_UNMET"
            reason = "Cross-pool promotion prerequisites remain incomplete."
        diagnosis = _diagnosis(
            outcome=INSUFFICIENT_EVIDENCE,
            stage="cross_pool_trusted_semantics",
            code=code,
            reason=reason,
            evidence=evidence,
            retryable=True,
        )

    trusted_pool_profiles = []
    if promoted:
        for item in candidates:
            promoted_item = dict(item)
            promoted_item.update(
                {
                    "canonical_vault_mapping_promoted": True,
                    "exact_pool_leg_semantics_promoted": True,
                    "promotion_scope": PROMOTION_SCOPE,
                    "transaction_execution_enabled": False,
                    "signing_enabled": False,
                }
            )
            trusted_pool_profiles.append(promoted_item)

    trusted_profile = None
    if promoted:
        trusted_profile = {
            "chain": CHAIN,
            "program_id": common_program_id,
            "semantic_convention": {
                "BUY": BUY_DEFINITION,
                "SELL": SELL_DEFINITION,
            },
            "promotion_scope": PROMOTION_SCOPE,
            "qualified_pool_addresses": [item["pool_address"] for item in candidates],
            "qualified_asset_mints": [item["asset_mint"] for item in candidates],
            "pool_structural_anchors_remain_pool_specific": True,
            "future_pool_requires_individual_proof": True,
            "transaction_execution_enabled": False,
            "signing_enabled": False,
        }

    summary = {
        **evidence,
        "common_program_id": common_program_id,
        "cross_pool_trusted_semantics_proven": promoted,
        "canonical_vault_mapping_promoted": promoted,
        "exact_pool_leg_semantics_promoted": promoted,
        "promotion_scope": PROMOTION_SCOPE if promoted else None,
        "future_pool_requires_individual_proof": True,
        "transaction_execution_enabled": False,
        "signing_enabled": False,
        "interpretation": (
            "v1.4.11 promotes internal CMIS trust only for pools that each pass the "
            "current exact-semantics proof and collectively satisfy the cross-pool "
            "qualification gate. INSUFFICIENT_EVIDENCE pools are excluded rather "
            "than treated as contradictory evidence. Ambiguity, structural conflict, "
            "data/transport failure, stale diagnostics, duplicate pool evidence, or "
            "program-identity disagreement blocks the submitted bundle. Promotion "
            "never authorizes signing or transaction execution, and unproven future "
            "pools must still pass their own exact proof."
        ),
    }

    return {
        "service": SERVICE,
        "version": VERSION,
        "chain": CHAIN,
        "status": status,
        "thresholds": {
            "minimum_exact_report_version": ".".join(
                str(item) for item in MIN_EXACT_REPORT_VERSION
            ),
            "minimum_proven_pools": min_proven_pools,
            "minimum_distinct_assets": min_distinct_assets,
            "required_windows": list(REQUIRED_WINDOWS),
            "required_operation_classification_ratio": 1.0,
            "required_swap_semantic_resolution_ratio": 1.0,
            "required_unknown_pool_operation_count": 0,
        },
        "reports": report_records,
        "qualified_candidates": candidates,
        "excluded_insufficient_evidence": excluded,
        "blocking_evidence": blockers,
        "trusted_pool_profiles": trusted_pool_profiles,
        "trusted_semantics_profile": trusted_profile,
        "proof_diagnosis": diagnosis,
        "summary": summary,
        "transaction_execution_enabled": False,
        "signing_enabled": False,
    }


__all__ = [
    "BUY_DEFINITION",
    "CHAIN",
    "MIN_DISTINCT_ASSETS",
    "MIN_EXACT_REPORT_VERSION",
    "MIN_PROVEN_POOLS",
    "PROMOTION_SCOPE",
    "REQUIRED_WINDOWS",
    "SELL_DEFINITION",
    "SERVICE",
    "VERSION",
    "qualify_cross_pool_trusted_semantics",
]
