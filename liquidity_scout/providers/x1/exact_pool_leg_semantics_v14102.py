"""CMIS v1.4.10.2 — exact semantics with first-class proof diagnosis.

v1.4.10.1 remains the proof engine. This wrapper does not weaken or alter any
proof gate. It adds one deterministic explanation object describing why the
proof succeeded or why it failed closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.amm_operation_classification import (
    classify_liquidity_operation,
)
from liquidity_scout.providers.x1.canonical_pool_vault_coupling import (
    prove_canonical_pool_vault_coupling,
)
from liquidity_scout.providers.x1.exact_pool_leg_semantics_v14101 import (
    prove_exact_pool_leg_semantics as prove_v1_4_10_1,
)
from liquidity_scout.providers.x1.history_range import scan_address_history_range
from liquidity_scout.providers.x1.proof_failure_diagnostics import (
    diagnose_exact_pool_leg_semantics,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    compute_token_deltas,
    fetch_transaction,
)
from liquidity_scout.providers.x1.vault_pair_correlation import (
    collect_recognized_amm_instruction_occurrences,
)

VERSION = "1.4.10.2"


def _default_fetcher(signature: str, *, rpc_url: str):
    return fetch_transaction(signature, rpc_url=rpc_url)


def prove_exact_pool_leg_semantics(
    *,
    pool_address: str,
    asset_mint: str,
    end_epoch: float,
    pair: str | None = None,
    rpc_url: str | None = None,
    page_size: int = 1000,
    max_signatures: int = 5000,
    coupling_provider: Callable[..., Mapping[str, Any]] = (
        prove_canonical_pool_vault_coupling
    ),
    scanner: Callable[..., Mapping[str, Any]] = scan_address_history_range,
    fetcher: Callable[..., Any] = _default_fetcher,
    occurrence_provider: Callable[[Mapping[str, Any]], Sequence[Mapping[str, Any]]] = (
        collect_recognized_amm_instruction_occurrences
    ),
    delta_provider: Callable[[dict[str, Any]], Sequence[Any]] = compute_token_deltas,
    operation_classifier: Callable[..., Mapping[str, Any]] = classify_liquidity_operation,
    diagnostic_scanner: Callable[..., Mapping[str, Any]] = scan_address_history_range,
) -> dict[str, Any]:
    """Run v1.4.10.1 unchanged, then attach one deterministic proof diagnosis."""

    base = prove_v1_4_10_1(
        pool_address=pool_address,
        asset_mint=asset_mint,
        end_epoch=end_epoch,
        pair=pair,
        rpc_url=rpc_url,
        page_size=page_size,
        max_signatures=max_signatures,
        coupling_provider=coupling_provider,
        scanner=scanner,
        fetcher=fetcher,
        occurrence_provider=occurrence_provider,
        delta_provider=delta_provider,
        operation_classifier=operation_classifier,
    )
    result = dict(base) if isinstance(base, Mapping) else {}
    result["version"] = VERSION

    diagnosis = diagnose_exact_pool_leg_semantics(
        result,
        pool_address=pool_address,
        asset_mint=asset_mint,
        end_epoch=end_epoch,
        rpc_url=rpc_url,
        page_size=page_size,
        max_signatures=max_signatures,
        scanner=diagnostic_scanner,
    )
    result["proof_diagnosis"] = diagnosis

    summary = result.get("summary")
    summary = dict(summary) if isinstance(summary, Mapping) else {}
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
            # Diagnosis is explanatory only. Promotion and execution remain
            # exactly as restrictive as v1.4.10.1.
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "transaction_execution_enabled": False,
        }
    )
    result["summary"] = summary
    result["transaction_execution_enabled"] = False
    return result


__all__ = ["VERSION", "prove_exact_pool_leg_semantics"]
