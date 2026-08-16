"""Deterministic proof-outcome diagnostics for the X1 CMIS proof chain.

A fail-closed proof result is not itself an explanation. This module classifies
why exact pool-leg semantics were not proven without weakening any proof gate.
It distinguishes proven results, insufficient evidence, ambiguity, conflicting
evidence, and data/transport failures.

For the specific case where vault-family discovery produced no candidates in
any required window, the diagnostic performs one read-only 24h signature scan.
That lets CMIS distinguish an inactive pool from an active pool whose observed
transactions did not expose a qualifying vault-pair topology.

No provider BUY/SELL label, balance ranking, liquidity size, or LLM inference is
used. This module is read-only and never signs or submits transactions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.history_range import scan_address_history_range
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL

PROVEN = "PROVEN"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
AMBIGUOUS = "AMBIGUOUS"
CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
DATA_OR_TRANSPORT_ERROR = "DATA_OR_TRANSPORT_ERROR"

PROOF_WINDOW_SECONDS = 86400


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return list(value)


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _result(
    *,
    outcome: str,
    stage: str | None,
    code: str | None,
    reason: str,
    evidence: Mapping[str, Any] | None = None,
    conflicting: bool = False,
    retryable: bool = False,
) -> dict[str, Any]:
    return {
        "proof_outcome": outcome,
        "blocking_stage": stage,
        "blocking_code": code,
        "blocking_reason": reason,
        "evidence": dict(evidence or {}),
        "conflicting_evidence_observed": conflicting,
        "retryable": retryable,
    }


def _nested_mapping_evidence(report: Mapping[str, Any]) -> dict[str, Any]:
    coupling = _mapping(report.get("coupling"))
    qualification = _mapping(coupling.get("qualification"))
    attribution = _mapping(qualification.get("family_attribution"))
    windows = [
        _mapping(raw)
        for raw in _sequence(attribution.get("windows"))
        if isinstance(raw, Mapping)
    ]
    return {
        "coupling": coupling,
        "qualification": qualification,
        "attribution": attribution,
        "windows": windows,
    }


def _candidate_window_counts(windows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for raw in windows:
        label = _text(raw.get("label"))
        if not label:
            continue
        try:
            count = int(raw.get("candidate_pair_count") or 0)
        except (TypeError, ValueError):
            count = 0
        out[label] = max(0, count)
    return out


def _all_windows_proven(windows: Sequence[Mapping[str, Any]]) -> bool:
    return bool(
        windows
        and all(
            raw.get("range_proven") is True
            and raw.get("integrity_verified") is True
            for raw in windows
        )
    )


def _has_structural_conflict(
    attribution: Mapping[str, Any],
    coupling: Mapping[str, Any],
) -> bool:
    summary = _mapping(attribution.get("summary"))
    if summary.get("recurrent_family_structural_conflict_observed") is True:
        return True
    for raw in _sequence(coupling.get("families")):
        if not isinstance(raw, Mapping):
            continue
        reasons = {str(item) for item in _sequence(raw.get("rejection_reasons"))}
        if any("conflict" in reason for reason in reasons):
            return True
    return False


def _diagnostic_activity_scan(
    *,
    pool_address: str,
    end_epoch: float,
    rpc_url: str,
    page_size: int,
    max_signatures: int,
    scanner: Callable[..., Mapping[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        raw = scanner(
            pool_address,
            start_epoch=end_epoch - PROOF_WINDOW_SECONDS,
            end_epoch=end_epoch,
            rpc_url=rpc_url,
            page_size=page_size,
            max_signatures=max_signatures,
        )
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"

    scan = _mapping(raw)
    entries = [raw for raw in _sequence(scan.get("entries")) if isinstance(raw, Mapping)]
    return {
        "range_proven": scan.get("range_proven") is True,
        "integrity_verified": scan.get("integrity_verified") is True,
        "transaction_signature_count": len(entries),
    }, None


def diagnose_exact_pool_leg_semantics(
    report: Mapping[str, Any],
    *,
    pool_address: str,
    asset_mint: str,
    end_epoch: float,
    rpc_url: str | None = None,
    page_size: int = 1000,
    max_signatures: int = 5000,
    scanner: Callable[..., Mapping[str, Any]] = scan_address_history_range,
) -> dict[str, Any]:
    """Return one deterministic explanation for the terminal proof outcome."""

    report = _mapping(report)
    summary = _mapping(report.get("summary"))
    status = _text(report.get("status")) or "unknown"

    if summary.get("exact_pool_leg_semantics_proven") is True:
        return _result(
            outcome=PROVEN,
            stage=None,
            code=None,
            reason=(
                "Exact canonical pool-leg semantics were proven from complete "
                "fail-closed evidence."
            ),
            evidence={
                "recognized_pool_operation_count": summary.get(
                    "recognized_pool_operation_count"
                ),
                "unknown_pool_operation_count": summary.get(
                    "unknown_pool_operation_count"
                ),
                "buy_semantics_proven": summary.get("buy_semantics_proven") is True,
                "sell_semantics_proven": summary.get("sell_semantics_proven") is True,
            },
        )

    nested = _nested_mapping_evidence(report)
    coupling = nested["coupling"]
    qualification = nested["qualification"]
    attribution = nested["attribution"]
    windows = nested["windows"]
    coupling_status = _text(coupling.get("status"))
    qualification_status = _text(qualification.get("status"))
    attribution_status = _text(attribution.get("status"))

    errors = [
        _mapping(raw)
        for raw in _sequence(report.get("errors"))
        if isinstance(raw, Mapping)
    ]
    coupling_errors = [
        _mapping(raw)
        for raw in _sequence(coupling.get("errors"))
        if isinstance(raw, Mapping)
    ]

    # v1.4.10 records an explanatory canonical_pool_vault_coupling error when a
    # mapping prerequisite is merely unproven. That is expected fail-closed
    # evidence, not a transport failure. Preserve it for later diagnosis.
    expected_mapping_prerequisite_error = bool(
        status == "canonical_vault_mapping_unproven"
        and errors
        and all(
            _text(raw.get("stage")) == "canonical_pool_vault_coupling"
            for raw in errors
        )
        and not coupling_errors
    )

    if status in {
        "canonical_vault_mapping_unavailable",
        "history_scan_unavailable",
        "transaction_evidence_incomplete",
    } or coupling_errors or (errors and not expected_mapping_prerequisite_error):
        first = (coupling_errors + errors)[0] if (coupling_errors or errors) else {}
        return _result(
            outcome=DATA_OR_TRANSPORT_ERROR,
            stage=_text(first.get("stage")) or status,
            code=(
                "TRANSACTION_EVIDENCE_INCOMPLETE"
                if status == "transaction_evidence_incomplete"
                else "UPSTREAM_DATA_OR_TRANSPORT_ERROR"
            ),
            reason=(
                "Required proof data could not be collected or fetched completely; "
                "CMIS failed closed rather than inferring missing evidence."
            ),
            evidence={
                "status": status,
                "error": first.get("error"),
            },
            retryable=True,
        )

    if coupling_status == "ambiguous_pool_vault_coupling" or qualification_status == "ambiguous_qualified_families":
        return _result(
            outcome=AMBIGUOUS,
            stage="canonical_pool_vault_coupling",
            code="AMBIGUOUS_CANONICAL_VAULT_FAMILIES",
            reason=(
                "More than one vault family satisfies the available proof gates, "
                "so CMIS refuses to select a canonical mapping."
            ),
            evidence={
                "coupling_status": coupling_status,
                "qualification_status": qualification_status,
                "qualified_family_count": _mapping(coupling.get("summary")).get(
                    "qualified_family_count"
                ),
                "pool_coupled_family_count": coupling.get("pool_coupled_family_count"),
            },
            retryable=True,
        )

    if _has_structural_conflict(attribution, coupling):
        return _result(
            outcome=CONFLICTING_EVIDENCE,
            stage="vault_pair_family_attribution",
            code="STRUCTURAL_VAULT_FAMILY_CONFLICT",
            reason=(
                "Observed recurrent vault-family structure conflicts across the "
                "proof windows, so canonical mapping remains unproven."
            ),
            evidence={
                "attribution_status": attribution_status,
                "coupling_status": coupling_status,
            },
            conflicting=True,
            retryable=True,
        )

    candidate_counts = _candidate_window_counts(windows)
    no_candidates = bool(candidate_counts) and all(
        count == 0 for count in candidate_counts.values()
    )
    ranges_proven = _all_windows_proven(windows)

    if status == "canonical_vault_mapping_unproven" and no_candidates and ranges_proven:
        try:
            end_epoch = float(end_epoch)
        except (TypeError, ValueError):
            return _result(
                outcome=DATA_OR_TRANSPORT_ERROR,
                stage="proof_diagnosis",
                code="INVALID_DIAGNOSTIC_END_EPOCH",
                reason="The proof end time could not be parsed for diagnostic scanning.",
                retryable=False,
            )

        scan, scan_error = _diagnostic_activity_scan(
            pool_address=pool_address,
            end_epoch=end_epoch,
            rpc_url=rpc_url or DEFAULT_X1_RPC_URL,
            page_size=page_size,
            max_signatures=max_signatures,
            scanner=scanner,
        )
        if scan_error is not None:
            return _result(
                outcome=DATA_OR_TRANSPORT_ERROR,
                stage="proof_diagnosis_history_scan",
                code="DIAGNOSTIC_HISTORY_SCAN_UNAVAILABLE",
                reason=(
                    "CMIS identified missing vault-pair evidence but could not "
                    "complete the read-only activity scan needed to explain why."
                ),
                evidence={"error": scan_error, "candidate_pair_counts": candidate_counts},
                retryable=True,
            )

        scan = scan or {}
        signature_count = int(scan.get("transaction_signature_count") or 0)
        evidence = {
            "history_ranges_proven": True,
            "candidate_pair_counts": candidate_counts,
            "diagnostic_24h_range_proven": scan.get("range_proven") is True,
            "diagnostic_24h_integrity_verified": scan.get("integrity_verified") is True,
            "diagnostic_24h_transaction_signature_count": signature_count,
        }
        if (
            scan.get("range_proven") is True
            and scan.get("integrity_verified") is True
            and signature_count == 0
        ):
            return _result(
                outcome=INSUFFICIENT_EVIDENCE,
                stage="vault_pair_discovery",
                code="NO_POOL_ACTIVITY_IN_PROOF_WINDOW",
                reason=(
                    "The required history ranges were proven, but no transaction "
                    "signatures were observed for the selected pool during the 24h "
                    "proof window. CMIS cannot derive canonical vaults from an "
                    "inactive window and therefore fails closed."
                ),
                evidence=evidence,
                retryable=True,
            )

        return _result(
            outcome=INSUFFICIENT_EVIDENCE,
            stage="vault_pair_discovery",
            code="NO_VAULT_PAIR_CANDIDATES",
            reason=(
                "Pool activity exists, but the observed transactions did not expose "
                "any vault-pair candidate satisfying the deterministic discovery "
                "model. CMIS refuses to manufacture a canonical mapping."
            ),
            evidence=evidence,
            retryable=True,
        )

    if status == "canonical_vault_mapping_unproven":
        code = "CANONICAL_POOL_VAULT_COUPLING_UNPROVEN"
        reason = (
            "Available evidence did not prove exactly one canonical pool-vault "
            "mapping with a stable structural anchor."
        )
        if qualification_status == "no_qualified_family":
            code = "NO_QUALIFIED_VAULT_FAMILY"
            reason = (
                "Observed vault-pair families did not pass the recurrent identity, "
                "RPC token-account, mint, and shared-authority qualification gates."
            )
        return _result(
            outcome=INSUFFICIENT_EVIDENCE,
            stage="canonical_pool_vault_coupling",
            code=code,
            reason=reason,
            evidence={
                "coupling_status": coupling_status,
                "qualification_status": qualification_status,
                "attribution_status": attribution_status,
                "candidate_pair_counts": candidate_counts,
            },
            retryable=True,
        )

    if status == "history_range_unproven":
        return _result(
            outcome=INSUFFICIENT_EVIDENCE,
            stage="history_range",
            code="HISTORY_RANGE_UNPROVEN",
            reason=(
                "The requested history range was not completely proven, so semantic "
                "promotion is blocked."
            ),
            evidence={"history_range_proven": False},
            retryable=True,
        )

    if status == "amm_operation_classification_incomplete_or_conflicting":
        unknown = int(summary.get("unknown_pool_operation_count") or 0)
        return _result(
            outcome=INSUFFICIENT_EVIDENCE,
            stage="amm_operation_classification",
            code="UNKNOWN_AMM_OPERATION",
            reason=(
                "At least one recognized canonical-pool AMM operation could not be "
                "classified deterministically, so exact semantics remain fail-closed."
            ),
            evidence={"unknown_pool_operation_count": unknown},
            retryable=True,
        )

    if status == "directional_structural_anchor_conflict":
        return _result(
            outcome=CONFLICTING_EVIDENCE,
            stage="exact_pool_leg_semantics",
            code="DIRECTIONAL_STRUCTURAL_ANCHOR_CONFLICT",
            reason=(
                "BUY and SELL evidence do not preserve one consistent structural "
                "pool anchor."
            ),
            evidence={"cross_direction_structural_anchor_consistent": False},
            conflicting=True,
            retryable=True,
        )

    if status == "bidirectional_semantics_unproven":
        return _result(
            outcome=INSUFFICIENT_EVIDENCE,
            stage="exact_pool_leg_semantics",
            code="BIDIRECTIONAL_SEMANTICS_UNPROVEN",
            reason=(
                "The proof window does not contain sufficient stable evidence for "
                "both BUY and SELL canonical reserve semantics."
            ),
            evidence={
                "buy_semantics_proven": summary.get("buy_semantics_proven") is True,
                "sell_semantics_proven": summary.get("sell_semantics_proven") is True,
            },
            retryable=True,
        )

    return _result(
        outcome=INSUFFICIENT_EVIDENCE,
        stage="exact_pool_leg_semantics",
        code="PROOF_PREREQUISITE_UNPROVEN",
        reason=(
            "One or more deterministic proof prerequisites remain unproven; CMIS "
            "fails closed without guessing."
        ),
        evidence={"status": status},
        retryable=True,
    )


__all__ = [
    "AMBIGUOUS",
    "CONFLICTING_EVIDENCE",
    "DATA_OR_TRANSPORT_ERROR",
    "INSUFFICIENT_EVIDENCE",
    "PROVEN",
    "diagnose_exact_pool_leg_semantics",
]
