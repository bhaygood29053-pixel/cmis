"""Fail-closed comparison gate for provider holder counts and independent evidence.

The gate compares counts only when the X1.Ninja semantic proof explicitly says
that the provider field counts *all token accounts* for the exact mint and the
independent observation explicitly represents a total token-account count for
that same mint. Largest-account lists, partial scans, wallet counts, and
beneficial-owner estimates are never coerced into comparable facts.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


VERSION = "1.0"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def compare_x1_holder_count_evidence(
    semantic_proof: Mapping[str, Any],
    independent_observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare only exact, semantically equivalent total token-account counts."""
    if not isinstance(semantic_proof, Mapping):
        raise TypeError("semantic_proof must be a mapping")
    if not isinstance(independent_observation, Mapping):
        raise TypeError("independent_observation must be a mapping")

    reasons: list[str] = []

    if semantic_proof.get("chain") != "x1":
        reasons.append("provider_wrong_chain")
    if semantic_proof.get("service") != "x1_ninja_holder_semantic_proof":
        reasons.append("unexpected_provider_semantic_service")
    if semantic_proof.get("semantic_contract_verified") is not True:
        reasons.append("provider_semantic_contract_unverified")
    if semantic_proof.get("rpc_total_token_account_count_comparison_eligible") is not True:
        reasons.append("provider_semantics_not_total_token_accounts")
    if semantic_proof.get("counted_entity") != "token_accounts":
        reasons.append("provider_counted_entity_not_token_accounts")
    if semantic_proof.get("coverage") != "total":
        reasons.append("provider_coverage_not_total")

    provider_mint = _text(semantic_proof.get("asset_mint"))
    provider_count = semantic_proof.get("raw_count")
    if provider_mint is None:
        reasons.append("provider_asset_mint_missing")
    if isinstance(provider_count, bool) or not isinstance(provider_count, int) or provider_count < 0:
        reasons.append("provider_count_invalid")

    if independent_observation.get("chain") != "x1":
        reasons.append("independent_wrong_chain")
    if independent_observation.get("fact_type") != "total_token_account_count":
        reasons.append("independent_fact_not_total_token_account_count")
    if independent_observation.get("counted_entity") != "token_accounts":
        reasons.append("independent_counted_entity_not_token_accounts")
    if independent_observation.get("coverage") != "total":
        reasons.append("independent_coverage_not_total")
    if independent_observation.get("identity_verified") is not True:
        reasons.append("independent_identity_unverified")
    if independent_observation.get("coverage_verified") is not True:
        reasons.append("independent_coverage_unverified")

    independent_mint = _text(independent_observation.get("asset_mint"))
    independent_count = independent_observation.get("count")
    if independent_mint is None:
        reasons.append("independent_asset_mint_missing")
    if provider_mint is not None and independent_mint is not None and provider_mint != independent_mint:
        reasons.append("asset_mint_mismatch")
    if isinstance(independent_count, bool) or not isinstance(independent_count, int) or independent_count < 0:
        reasons.append("independent_count_invalid")

    source = _text(independent_observation.get("source"))
    if source in {None, "x1_ninja"}:
        reasons.append("independent_source_not_distinct")

    reasons = list(dict.fromkeys(reasons))
    comparable = not reasons

    if not comparable:
        status = "INSUFFICIENT_EVIDENCE"
        agreement = None
    elif provider_count == independent_count:
        status = "AGREEMENT"
        agreement = True
    else:
        status = "CONFLICT"
        agreement = False

    return {
        "service": "x1_holder_count_crosscheck",
        "version": VERSION,
        "chain": "x1",
        "fact_type": "total_token_account_count",
        "asset_mint": provider_mint,
        "provider_count": provider_count if isinstance(provider_count, int) and not isinstance(provider_count, bool) else None,
        "independent_count": independent_count if isinstance(independent_count, int) and not isinstance(independent_count, bool) else None,
        "independent_source": source,
        "comparison_semantics_verified": comparable,
        "verification_status": status,
        "agreement": agreement,
        "cmis_promotable": False,
        "rejection_reasons": reasons,
    }


__all__ = ["VERSION", "compare_x1_holder_count_evidence"]
