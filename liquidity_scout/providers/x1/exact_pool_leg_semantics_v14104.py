"""CMIS v1.4.10.4 — precise per-window canonical coupling diagnostics.

v1.4.10.3 remains the proof engine and literal-window diagnostic contract.
This wrapper preserves every existing fail-closed proof gate, then refines only
one generic failure class: a uniquely qualified vault family that fails
v1.4.9 canonical pool-vault coupling because one or more required 1h/6h/24h
window gates are unmet.

No proof threshold is lowered. No historical success is reused as current proof.
Signing and transaction execution remain disabled.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.exact_pool_leg_semantics_v14103 import (
    prove_exact_pool_leg_semantics as prove_v1_4_10_3,
)

VERSION = "1.4.10.4"
REQUIRED_WINDOWS = ("1h", "6h", "24h")

_GENERIC_COUPLING_CODE = "CANONICAL_POOL_VAULT_COUPLING_UNPROVEN"

_WINDOW_GATE_CODES = {
    "candidate_missing": "REQUIRED_WINDOW_VAULT_CANDIDATE_MISSING",
    "history_unproven": "REQUIRED_WINDOW_HISTORY_UNPROVEN",
    "pool_instruction_coverage_incomplete": (
        "REQUIRED_WINDOW_POOL_INSTRUCTION_COVERAGE_INCOMPLETE"
    ),
    "directional_pair_unstable": "REQUIRED_WINDOW_DIRECTIONAL_PAIR_UNSTABLE",
    "opposite_flow_unqualified": "REQUIRED_WINDOW_OPPOSITE_FLOW_UNQUALIFIED",
    "coupling_unproven": "REQUIRED_WINDOW_COUPLING_UNPROVEN",
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


def _candidate_pair_counts(report: Mapping[str, Any]) -> dict[str, int]:
    coupling = _mapping(report.get("coupling"))
    qualification = _mapping(coupling.get("qualification"))
    attribution = _mapping(qualification.get("family_attribution"))
    out: dict[str, int] = {}
    for raw in _sequence(attribution.get("windows")):
        if not isinstance(raw, Mapping):
            continue
        label = _text(raw.get("label"))
        if not label:
            continue
        try:
            count = int(raw.get("candidate_pair_count") or 0)
        except (TypeError, ValueError):
            count = 0
        out[label] = max(0, count)
    return out


def _qualified_coupling_families(coupling: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(raw)
        for raw in _sequence(coupling.get("families"))
        if isinstance(raw, Mapping) and raw.get("v1_4_8_qualified") is True
    ]


def _window_failure(row: Mapping[str, Any]) -> str | None:
    if row.get("candidate_present") is not True:
        return "candidate_missing"
    if row.get("range_proven") is not True or row.get("integrity_verified") is not True:
        return "history_unproven"
    if row.get("full_pool_instruction_coverage") is not True:
        return "pool_instruction_coverage_incomplete"
    if row.get("stable_directional_pair_candidate") is not True:
        return "directional_pair_unstable"
    if row.get("qualifying_family_evidence") is not True:
        return "opposite_flow_unqualified"
    if row.get("pool_instruction_coupled") is not True:
        return "coupling_unproven"
    return None


def _ordered_window_rows(family: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_label: dict[str, dict[str, Any]] = {}
    for raw in _sequence(family.get("window_coupling")):
        if not isinstance(raw, Mapping):
            continue
        label = _text(raw.get("window"))
        if label and label not in by_label:
            by_label[label] = dict(raw)
    return [by_label.get(label, {"window": label}) for label in REQUIRED_WINDOWS]


def _failure_reason(code: str, blocking_windows: Sequence[str]) -> str:
    labels = ", ".join(blocking_windows)
    if code == "REQUIRED_WINDOW_VAULT_CANDIDATE_MISSING":
        return (
            "A uniquely RPC-qualified recurrent vault family exists, but it is "
            f"absent from required coupling window(s): {labels}. CMIS requires "
            "the same qualified family to be present and coupled in every "
            "1h/6h/24h window, so canonical mapping remains fail-closed."
        )
    if code == "REQUIRED_WINDOW_HISTORY_UNPROVEN":
        return (
            f"Canonical coupling evidence is incomplete because required window(s) "
            f"{labels} do not have fully proven history/integrity."
        )
    if code == "REQUIRED_WINDOW_POOL_INSTRUCTION_COVERAGE_INCOMPLETE":
        return (
            f"The qualified vault family does not cover 100% of recognized selected-"
            f"pool AMM transactions in required window(s): {labels}."
        )
    if code == "REQUIRED_WINDOW_DIRECTIONAL_PAIR_UNSTABLE":
        return (
            f"The qualified vault family is not a stable directional pair candidate "
            f"in required window(s): {labels}."
        )
    if code == "REQUIRED_WINDOW_OPPOSITE_FLOW_UNQUALIFIED":
        return (
            f"The qualified vault family lacks qualifying opposite-flow evidence in "
            f"required window(s): {labels}."
        )
    if code == "REQUIRED_WINDOW_COUPLING_UNPROVEN":
        return (
            f"The qualified vault family does not satisfy the complete canonical "
            f"coupling gate in required window(s): {labels}."
        )
    return (
        "Multiple required canonical coupling window gates are unmet. CMIS reports "
        "each failing window explicitly and keeps the mapping unproven."
    )


def refine_per_window_coupling_diagnosis(report: Mapping[str, Any]) -> dict[str, Any]:
    """Refine the generic v1.4.10.3 coupling diagnosis without changing proof."""

    report = _mapping(report)
    diagnosis = _mapping(report.get("proof_diagnosis"))
    if diagnosis.get("blocking_code") != _GENERIC_COUPLING_CODE:
        return diagnosis

    coupling = _mapping(report.get("coupling"))
    if _text(coupling.get("status")) != "no_pool_vault_coupling_proven":
        return diagnosis

    coupling_summary = _mapping(coupling.get("summary"))
    if coupling_summary.get("qualified_family_count") != 1:
        return diagnosis

    families = _qualified_coupling_families(coupling)
    if len(families) != 1:
        return diagnosis

    family_record = families[0]
    failures: list[dict[str, Any]] = []
    failure_kinds: list[str] = []
    for row in _ordered_window_rows(family_record):
        label = _text(row.get("window")) or "unknown"
        kind = _window_failure(row)
        if kind is None:
            continue
        failure_kinds.append(kind)
        failures.append(
            {
                "window": label,
                "failure": kind,
                "candidate_present": row.get("candidate_present") is True,
                "range_proven": row.get("range_proven") is True,
                "integrity_verified": row.get("integrity_verified") is True,
                "transaction_occurrence_count": row.get("transaction_occurrence_count"),
                "recognized_pool_instruction_transaction_ratio": row.get(
                    "recognized_pool_instruction_transaction_ratio"
                ),
                "required_pool_instruction_transaction_ratio": row.get(
                    "required_pool_instruction_transaction_ratio"
                ),
                "full_pool_instruction_coverage": row.get(
                    "full_pool_instruction_coverage"
                ) is True,
                "stable_directional_pair_candidate": row.get(
                    "stable_directional_pair_candidate"
                ) is True,
                "qualifying_family_evidence": row.get("qualifying_family_evidence")
                is True,
                "pool_instruction_coupled": row.get("pool_instruction_coupled") is True,
            }
        )

    if not failures:
        return diagnosis

    distinct_kinds = list(dict.fromkeys(failure_kinds))
    if len(distinct_kinds) == 1:
        blocking_code = _WINDOW_GATE_CODES[distinct_kinds[0]]
    else:
        blocking_code = "REQUIRED_WINDOW_COUPLING_GATES_UNMET"

    blocking_windows = [raw["window"] for raw in failures]
    evidence = _mapping(diagnosis.get("evidence"))
    evidence.update(
        {
            "coupling_status": coupling.get("status"),
            "qualified_family_count": 1,
            "candidate_pair_counts": _candidate_pair_counts(report),
            "required_windows": list(REQUIRED_WINDOWS),
            "blocking_windows": blocking_windows,
            "window_failures": failures,
            "qualified_family": _mapping(family_record.get("family")),
            "coupling_rejection_reasons": list(
                dict.fromkeys(str(item) for item in _sequence(family_record.get("rejection_reasons")))
            ),
        }
    )

    return {
        "proof_outcome": diagnosis.get("proof_outcome") or "INSUFFICIENT_EVIDENCE",
        "blocking_stage": "canonical_pool_vault_coupling",
        "blocking_code": blocking_code,
        "blocking_reason": _failure_reason(blocking_code, blocking_windows),
        "evidence": evidence,
        "conflicting_evidence_observed": False,
        "retryable": True,
    }


def prove_exact_pool_leg_semantics(
    *,
    pool_address: str,
    asset_mint: str,
    end_epoch: float,
    pair: str | None = None,
    rpc_url: str | None = None,
    page_size: int = 1000,
    max_signatures: int = 5000,
    base_provider: Callable[..., Mapping[str, Any]] = prove_v1_4_10_3,
    **proof_kwargs: Any,
) -> dict[str, Any]:
    """Run unchanged v1.4.10.3 proof, then refine per-window coupling diagnosis."""

    raw = base_provider(
        pool_address=pool_address,
        asset_mint=asset_mint,
        end_epoch=end_epoch,
        pair=pair,
        rpc_url=rpc_url,
        page_size=page_size,
        max_signatures=max_signatures,
        **proof_kwargs,
    )
    result = dict(raw) if isinstance(raw, Mapping) else {}
    result["version"] = VERSION

    diagnosis = refine_per_window_coupling_diagnosis(result)
    result["proof_diagnosis"] = diagnosis

    summary = _mapping(result.get("summary"))
    summary.update(
        {
            "proof_diagnosis_available": True,
            "proof_outcome": diagnosis.get("proof_outcome"),
            "blocking_stage": diagnosis.get("blocking_stage"),
            "blocking_code": diagnosis.get("blocking_code"),
            "blocking_reason": diagnosis.get("blocking_reason"),
            "conflicting_evidence_observed": diagnosis.get(
                "conflicting_evidence_observed"
            ) is True,
            "retryable": diagnosis.get("retryable") is True,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "transaction_execution_enabled": False,
            "signing_enabled": False,
        }
    )
    result["summary"] = summary
    result["transaction_execution_enabled"] = False
    result["signing_enabled"] = False
    return result


__all__ = [
    "REQUIRED_WINDOWS",
    "VERSION",
    "prove_exact_pool_leg_semantics",
    "refine_per_window_coupling_diagnosis",
]
