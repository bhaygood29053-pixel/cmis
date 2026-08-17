"""Fail-closed gate for externally proven X1.Ninja reserve semantics.

This module does not discover or infer reserve fields. It accepts a raw
X1.Ninja pool-detail observation, a separately verified X1 pool/vault identity,
and an explicit semantic proof manifest. It only exposes reserve candidates
when those three artifacts are structurally consistent.

A manifest is an input assertion backed by evidence references; this adapter
does not make that assertion true. Consequently this module never marks a
reserve observation CMIS-promotable by itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


VERSION = "1.0"
PROOF_STATUS = "externally_proven"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _numeric_text(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = _text(value)
    if text is None:
        return None
    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite():
        return None
    return text


def _field_at_path(body: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    """Resolve a conservative dot-separated object path.

    Array traversal is intentionally unsupported until a live provider schema
    proves it is needed; ambiguous array selection would weaken identity.
    """
    current: Any = body
    parts = [part.strip() for part in path.split(".") if part.strip()]
    if not parts or "[]" in path:
        return False, None
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def validate_reserve_semantic_proof(
    pool_detail: Mapping[str, Any],
    vault_identity: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate structural consistency of an external reserve-semantics proof.

    The manifest must explicitly bind provider field paths and units to the
    already-proven pool/vault/mint identity. No field-name, balance, ordering,
    or decimal inference is performed here.
    """
    if not isinstance(pool_detail, Mapping):
        raise TypeError("pool_detail must be a mapping")
    if not isinstance(vault_identity, Mapping):
        raise TypeError("vault_identity must be a mapping")
    if not isinstance(manifest, Mapping):
        raise TypeError("manifest must be a mapping")

    reasons: list[str] = []
    if pool_detail.get("chain") != "x1":
        reasons.append("pool_detail_wrong_chain")
    if vault_identity.get("chain") != "x1":
        reasons.append("vault_identity_wrong_chain")
    if vault_identity.get("identity_verified") is not True:
        reasons.append("vault_identity_unverified")
    if manifest.get("proof_status") != PROOF_STATUS:
        reasons.append("semantic_proof_status_unproven")

    requested_pool = _text(pool_detail.get("pool_address_requested"))
    identity_pool = _text(vault_identity.get("pool_address"))
    manifest_pool = _text(manifest.get("pool_address"))
    if not requested_pool or not identity_pool or not manifest_pool:
        reasons.append("pool_identity_incomplete")
    elif len({requested_pool, identity_pool, manifest_pool}) != 1:
        reasons.append("pool_identity_mismatch")

    raw = pool_detail.get("raw_response")
    if not isinstance(raw, Mapping):
        reasons.append("raw_pool_detail_missing")
        raw = {}

    evidence_refs = manifest.get("evidence_refs")
    if (
        not isinstance(evidence_refs, Sequence)
        or isinstance(evidence_refs, (str, bytes))
        or not [_text(item) for item in evidence_refs if _text(item)]
    ):
        reasons.append("semantic_evidence_refs_missing")

    roles: dict[str, dict[str, Any]] = {}
    field_paths: list[str] = []
    for role in ("asset", "counter"):
        spec = manifest.get(role)
        if not isinstance(spec, Mapping):
            reasons.append(f"{role}_semantic_binding_missing")
            continue

        field_path = _text(spec.get("field_path"))
        unit = _text(spec.get("unit"))
        mint = _text(spec.get("mint"))
        vault = _text(spec.get("vault"))
        decimals = _nonnegative_int(spec.get("decimals"))

        if not field_path:
            reasons.append(f"{role}_field_path_missing")
        else:
            field_paths.append(field_path)
        if not unit:
            reasons.append(f"{role}_unit_missing")
        if decimals is None:
            reasons.append(f"{role}_decimals_invalid")

        expected_mint = _text(vault_identity.get(f"{role}_mint"))
        expected_vault = _text(vault_identity.get(f"{role}_vault"))
        if not mint or mint != expected_mint:
            reasons.append(f"{role}_mint_identity_mismatch")
        if not vault or vault != expected_vault:
            reasons.append(f"{role}_vault_identity_mismatch")

        found, raw_value = _field_at_path(raw, field_path or "")
        if not found:
            reasons.append(f"{role}_field_path_not_found")
        elif _numeric_text(raw_value) is None:
            reasons.append(f"{role}_reserve_value_not_numeric")

        roles[role] = {
            "field_path": field_path,
            "raw_value": raw_value if found else None,
            "unit": unit,
            "decimals": decimals,
            "mint": mint,
            "vault": vault,
        }

    if len(field_paths) == 2 and field_paths[0] == field_paths[1]:
        reasons.append("reserve_field_paths_not_distinct")

    reasons = list(dict.fromkeys(reasons))
    contract_verified = not reasons
    return {
        "service": "x1_ninja_reserve_semantic_proof_gate",
        "version": VERSION,
        "chain": "x1",
        "pool_address": identity_pool,
        "semantic_contract_verified": contract_verified,
        "reserve_field_roles_verified": contract_verified,
        "reserve_units_declared": contract_verified,
        "identity_binding_verified": contract_verified,
        "freshness_verified": False,
        "value_agreement_verified": False,
        "cmis_promotable": False,
        "roles": roles,
        "proof": {
            "proof_status": _text(manifest.get("proof_status")),
            "proof_version": _text(manifest.get("proof_version")),
            "evidence_refs": [
                text for item in (evidence_refs or [])
                if (text := _text(item)) is not None
            ] if isinstance(evidence_refs, Sequence) and not isinstance(evidence_refs, (str, bytes)) else [],
        },
        "rejection_reasons": reasons,
    }


__all__ = ["PROOF_STATUS", "VERSION", "validate_reserve_semantic_proof"]
