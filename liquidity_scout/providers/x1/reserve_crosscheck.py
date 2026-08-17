"""Compose the accepted X1 reserve trust gates without adding inference.

This module is deliberately transport-free. It does not fetch X1.Ninja or RPC
state, discover vaults, infer provider fields, infer units, prove freshness, or
apply a tolerance. Callers must supply already-collected provider/RPC artifacts,
a verified pool/vault identity, and an explicit semantic proof manifest.

The orchestrator exists to make the reserve proof chain replayable:

semantic proof gate -> RPC identity binding -> reserve evidence -> exact verifier

Both asset and counter reserve legs must independently satisfy the existing
value verifier and the stronger RPC account/mint/authority identity binding
before the overall cross-check can become CMIS-promotable.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.cmis.evidence import AGREEMENT, CONFLICT, INSUFFICIENT_EVIDENCE
from liquidity_scout.providers.x1.ninja_reserve_semantics import (
    validate_reserve_semantic_proof,
)
from liquidity_scout.providers.x1.reserve_evidence import (
    build_x1_reserve_evidence_pair,
)
from liquidity_scout.providers.x1.reserve_rpc_identity import (
    bind_x1_reserve_rpc_identities,
)
from liquidity_scout.providers.x1.reserve_verification import (
    verify_x1_pool_reserve,
)


VERSION = "1.1"
ROLES = ("asset", "counter")
SEMANTIC_PROOF_REJECTED = "SEMANTIC_PROOF_REJECTED"
RPC_BALANCE_MISSING = "RPC_BALANCE_MISSING"
RPC_IDENTITY_UNVERIFIED = "RPC_IDENTITY_UNVERIFIED"
EVIDENCE_NOT_READY = "EVIDENCE_NOT_READY"
OBSERVED_AT_MISSING = "OBSERVED_AT_MISSING"


def _insufficient(code: str) -> dict[str, Any]:
    return {
        "verification": {
            "status": INSUFFICIENT_EVIDENCE,
            "code": code,
            "agreement": None,
        },
        "data_quality": None,
        "cmis_promotable": False,
    }


def _value_status(result: Mapping[str, Any]) -> str:
    verification_result = result.get("verification")
    verification = (
        verification_result.get("verification")
        if isinstance(verification_result, Mapping)
        else None
    )
    status = verification.get("status") if isinstance(verification, Mapping) else None
    return status or INSUFFICIENT_EVIDENCE


def _overall_status(role_results: Mapping[str, Any]) -> str:
    results = [
        role_results.get(role) if isinstance(role_results.get(role), Mapping) else {}
        for role in ROLES
    ]
    statuses = [_value_status(result) for result in results]

    if CONFLICT in statuses:
        return CONFLICT
    if any(result.get("rpc_identity_verified") is not True for result in results):
        return INSUFFICIENT_EVIDENCE
    if statuses and all(status == AGREEMENT for status in statuses):
        return AGREEMENT
    return INSUFFICIENT_EVIDENCE


def run_x1_reserve_crosscheck(
    pool_detail: Mapping[str, Any],
    vault_identity: Mapping[str, Any],
    semantic_manifest: Mapping[str, Any],
    rpc_balances: Mapping[str, Any],
    *,
    observed_at: Any,
    rpc_identities: Mapping[str, Any] | None = None,
    observation_scope_verified: bool = False,
) -> dict[str, Any]:
    """Replay the two-leg X1 reserve verification chain, failing closed.

    ``rpc_balances`` must map ``asset`` and ``counter`` to already-collected
    ``getTokenAccountBalance`` observations. ``rpc_identities`` must map those
    same roles to verified outputs from ``verify_x1_rpc_token_account_identity``.

    ``observation_scope_verified`` is caller-supplied proof state; this function
    never derives freshness from wall-clock proximity, provider timestamps, or
    RPC slots. A verified observation scope also requires an explicit
    ``observed_at`` value so the proof remains auditable.
    """
    for name, value in (
        ("pool_detail", pool_detail),
        ("vault_identity", vault_identity),
        ("semantic_manifest", semantic_manifest),
        ("rpc_balances", rpc_balances),
    ):
        if not isinstance(value, Mapping):
            raise TypeError(f"{name} must be a mapping")
    if rpc_identities is not None and not isinstance(rpc_identities, Mapping):
        raise TypeError("rpc_identities must be a mapping when supplied")

    scope_requested = bool(observation_scope_verified)
    scope_verified = scope_requested and observed_at is not None
    warnings: list[str] = []
    errors: list[str] = []
    if not scope_verified:
        warnings.append("observation_scope_unverified")
    if scope_requested and observed_at is None:
        errors.append(f"observation_scope:{OBSERVED_AT_MISSING}")

    semantic_proof = validate_reserve_semantic_proof(
        pool_detail,
        vault_identity,
        semantic_manifest,
    )
    rpc_identity_binding = bind_x1_reserve_rpc_identities(
        vault_identity,
        rpc_identities or {},
    )

    if semantic_proof.get("semantic_contract_verified") is not True:
        errors.extend(
            f"semantic_proof:{reason}"
            for reason in semantic_proof.get("rejection_reasons", [])
        )
    if rpc_identity_binding.get("identity_binding_verified") is not True:
        errors.extend(
            f"rpc_identity:{reason}"
            for reason in rpc_identity_binding.get("rejection_reasons", [])
        )

    role_results: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        role_identity = rpc_identity_binding.get("roles", {}).get(role, {})
        rpc_identity_verified = (
            isinstance(role_identity, Mapping)
            and role_identity.get("identity_verified") is True
        )

        if semantic_proof.get("semantic_contract_verified") is not True:
            role_results[role] = {
                "rpc_identity": dict(role_identity) if isinstance(role_identity, Mapping) else None,
                "rpc_identity_verified": rpc_identity_verified,
                "evidence": None,
                "verification": _insufficient(SEMANTIC_PROOF_REJECTED),
                "cmis_promotable": False,
            }
            continue

        rpc_balance = rpc_balances.get(role)
        if not isinstance(rpc_balance, Mapping):
            errors.append(f"{role}_rpc:{RPC_BALANCE_MISSING}")
            role_results[role] = {
                "rpc_identity": dict(role_identity) if isinstance(role_identity, Mapping) else None,
                "rpc_identity_verified": rpc_identity_verified,
                "evidence": None,
                "verification": _insufficient(RPC_BALANCE_MISSING),
                "cmis_promotable": False,
            }
            continue

        evidence = build_x1_reserve_evidence_pair(
            semantic_proof,
            rpc_balance,
            role=role,
            observed_at=observed_at,
            freshness_verified=scope_verified,
        )
        if evidence.get("evidence_ready") is not True:
            errors.extend(
                f"{role}_evidence:{reason}"
                for reason in evidence.get("rejection_reasons", [])
            )
            role_results[role] = {
                "rpc_identity": dict(role_identity) if isinstance(role_identity, Mapping) else None,
                "rpc_identity_verified": rpc_identity_verified,
                "evidence": evidence,
                "verification": _insufficient(EVIDENCE_NOT_READY),
                "cmis_promotable": False,
            }
            continue

        verification = verify_x1_pool_reserve(
            evidence["provider"],
            evidence["rpc"],
        )
        role_results[role] = {
            "rpc_identity": dict(role_identity) if isinstance(role_identity, Mapping) else None,
            "rpc_identity_verified": rpc_identity_verified,
            "evidence": evidence,
            "verification": verification,
            "cmis_promotable": (
                rpc_identity_verified
                and verification.get("cmis_promotable") is True
            ),
        }
        if not rpc_identity_verified:
            errors.append(f"{role}_rpc_identity:{RPC_IDENTITY_UNVERIFIED}")

    overall_verification = _overall_status(role_results)
    cmis_promotable = (
        overall_verification == AGREEMENT
        and rpc_identity_binding.get("identity_binding_verified") is True
        and all(
            role_results.get(role, {}).get("cmis_promotable") is True
            for role in ROLES
        )
    )

    return {
        "service": "x1_reserve_crosscheck",
        "version": VERSION,
        "chain": "x1",
        "pool_address": semantic_proof.get("pool_address"),
        "overall_verification": overall_verification,
        "observation_scope_verified": scope_verified,
        "semantic_proof": semantic_proof,
        "rpc_identity_binding": rpc_identity_binding,
        "roles": role_results,
        "cmis_promotable": cmis_promotable,
        "warnings": warnings,
        "errors": list(dict.fromkeys(errors)),
    }


__all__ = [
    "EVIDENCE_NOT_READY",
    "OBSERVED_AT_MISSING",
    "RPC_BALANCE_MISSING",
    "RPC_IDENTITY_UNVERIFIED",
    "ROLES",
    "SEMANTIC_PROOF_REJECTED",
    "VERSION",
    "run_x1_reserve_crosscheck",
]
