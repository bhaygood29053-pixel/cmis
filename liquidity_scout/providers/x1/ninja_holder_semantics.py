"""Validate an explicit external proof of X1.Ninja holder-field semantics.

This module does not discover holder fields or infer their meaning. It accepts
lexical candidates from ``extract_x1_ninja_holder_candidates`` plus a separately
constructed proof manifest. The manifest must explicitly bind one observed
field to one token role/mint, counted-entity semantics, and coverage semantics.

A structurally accepted manifest is still only an externally asserted proof
input. This adapter does not authenticate the referenced evidence and never
makes the result CMIS-promotable by itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


VERSION = "1.0"
PROOF_STATUS = "externally_proven"
ASSET_ROLES = frozenset({"base_token", "quote_token"})
COUNTED_ENTITIES = frozenset(
    {
        "token_accounts",
        "wallet_addresses",
        "beneficial_owners",
        "provider_defined_entities",
    }
)
COVERAGE_SEMANTICS = frozenset({"total", "partial"})


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _evidence_refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    refs: list[str] = []
    for item in value:
        text = _text(item)
        if text:
            refs.append(text)
    return list(dict.fromkeys(refs))


def _candidate_map(observation: Mapping[str, Any]) -> dict[str, Any]:
    value = observation.get("holder_field_candidates")
    if not isinstance(value, list):
        return {}
    result: dict[str, Any] = {}
    for item in value:
        if not isinstance(item, Mapping):
            continue
        path = _text(item.get("field_path"))
        if path is not None:
            result[path] = item.get("raw_value")
    return result


def validate_x1_ninja_holder_semantic_proof(
    holder_candidates: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate explicit holder semantics without authenticating external evidence."""
    if not isinstance(holder_candidates, Mapping):
        raise TypeError("holder_candidates must be a mapping")
    if not isinstance(manifest, Mapping):
        raise TypeError("manifest must be a mapping")

    reasons: list[str] = []

    if holder_candidates.get("chain") != "x1":
        reasons.append("wrong_chain")
    if holder_candidates.get("service") != "x1_ninja_holder_candidates":
        reasons.append("unexpected_candidate_service")
    if holder_candidates.get("status") == "error":
        reasons.append("holder_candidate_observation_rejected")
    if holder_candidates.get("pool_identity_transport_consistent") is not True:
        reasons.append("pool_identity_transport_unverified")

    candidate_pool = _text(holder_candidates.get("pool_address_requested"))
    manifest_pool = _text(manifest.get("pool_address"))
    if candidate_pool is None or manifest_pool is None:
        reasons.append("pool_address_missing")
    elif candidate_pool != manifest_pool:
        reasons.append("pool_identity_mismatch")

    if manifest.get("proof_status") != PROOF_STATUS:
        reasons.append("semantic_proof_status_unproven")

    refs = _evidence_refs(manifest.get("evidence_refs"))
    if not refs:
        reasons.append("semantic_evidence_refs_missing")

    field_path = _text(manifest.get("field_path"))
    candidates = _candidate_map(holder_candidates)
    if field_path is None:
        reasons.append("holder_field_path_missing")
        raw_count = None
    elif field_path not in candidates:
        reasons.append("holder_field_path_not_observed")
        raw_count = None
    else:
        raw_count = candidates[field_path]

    if isinstance(raw_count, bool) or not isinstance(raw_count, int) or raw_count < 0:
        reasons.append("holder_count_value_not_nonnegative_integer")

    asset_role = _text(manifest.get("asset_role"))
    if asset_role not in ASSET_ROLES:
        reasons.append("asset_role_unsupported")

    asset_mint = _text(manifest.get("asset_mint"))
    if asset_mint is None:
        reasons.append("asset_mint_missing")

    metadata = holder_candidates.get("token_metadata_candidates")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    role_metadata = metadata.get(asset_role) if asset_role in ASSET_ROLES else None
    role_metadata = role_metadata if isinstance(role_metadata, Mapping) else {}
    observed_role_mint = _text(role_metadata.get("address"))
    if asset_role in ASSET_ROLES:
        if observed_role_mint is None:
            reasons.append("asset_role_mint_unavailable")
        elif asset_mint is not None and asset_mint != observed_role_mint:
            reasons.append("asset_mint_binding_mismatch")

    counted_entity = _text(manifest.get("counted_entity"))
    if counted_entity not in COUNTED_ENTITIES:
        reasons.append("counted_entity_semantics_unsupported")

    coverage = _text(manifest.get("coverage"))
    if coverage not in COVERAGE_SEMANTICS:
        reasons.append("coverage_semantics_unsupported")

    reasons = list(dict.fromkeys(reasons))
    semantic_contract_verified = not reasons

    rpc_total_token_account_count_comparison_eligible = (
        semantic_contract_verified
        and counted_entity == "token_accounts"
        and coverage == "total"
    )

    return {
        "service": "x1_ninja_holder_semantic_proof",
        "version": VERSION,
        "chain": "x1",
        "pool_address": candidate_pool,
        "field_path": field_path,
        "raw_count": raw_count if isinstance(raw_count, int) and not isinstance(raw_count, bool) else None,
        "asset_role": asset_role,
        "asset_mint": asset_mint,
        "observed_role_mint": observed_role_mint,
        "counted_entity": counted_entity,
        "coverage": coverage,
        "semantic_contract_verified": semantic_contract_verified,
        "asset_binding_verified": (
            semantic_contract_verified and asset_mint == observed_role_mint
        ),
        "counted_entity_semantics_verified": semantic_contract_verified,
        "coverage_semantics_verified": semantic_contract_verified,
        "beneficial_owner_semantics_verified": (
            semantic_contract_verified and counted_entity == "beneficial_owners"
        ),
        "rpc_total_token_account_count_comparison_eligible": (
            rpc_total_token_account_count_comparison_eligible
        ),
        "external_evidence_refs": refs,
        "external_evidence_authenticity_verified": False,
        "cmis_promotable": False,
        "rejection_reasons": reasons,
    }


__all__ = [
    "ASSET_ROLES",
    "COUNTED_ENTITIES",
    "COVERAGE_SEMANTICS",
    "PROOF_STATUS",
    "VERSION",
    "validate_x1_ninja_holder_semantic_proof",
]
