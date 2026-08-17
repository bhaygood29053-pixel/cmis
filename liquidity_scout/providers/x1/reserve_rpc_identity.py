"""Bind verified X1 RPC token-account identities to reserve vault identity.

This adapter does not perform network calls and does not discover vaults. It
accepts the already-verified pool/vault identity plus per-role outputs from
``verify_x1_rpc_token_account_identity`` and proves that the RPC observations
refer to the exact asset/counter vaults, mints, and shared authority expected by
the reserve proof chain.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


VERSION = "1.0"
ROLES = ("asset", "counter")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def bind_x1_reserve_rpc_identities(
    vault_identity: Mapping[str, Any],
    rpc_identities: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind both verified RPC token-account identities to one pool identity."""
    if not isinstance(vault_identity, Mapping):
        raise TypeError("vault_identity must be a mapping")
    if not isinstance(rpc_identities, Mapping):
        raise TypeError("rpc_identities must be a mapping")

    reasons: list[str] = []
    if vault_identity.get("chain") != "x1":
        reasons.append("vault_identity_wrong_chain")
    if vault_identity.get("identity_verified") is not True:
        reasons.append("vault_identity_unverified")

    pool_address = _text(vault_identity.get("pool_address"))
    shared_owner = _text(vault_identity.get("shared_owner"))
    if pool_address is None:
        reasons.append("pool_address_missing")
    if shared_owner is None:
        reasons.append("shared_owner_missing")

    roles: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        expected_vault = _text(vault_identity.get(f"{role}_vault"))
        expected_mint = _text(vault_identity.get(f"{role}_mint"))
        proof = rpc_identities.get(role)
        role_reasons: list[str] = []

        if expected_vault is None:
            role_reasons.append("expected_vault_missing")
        if expected_mint is None:
            role_reasons.append("expected_mint_missing")
        if not isinstance(proof, Mapping):
            role_reasons.append("rpc_identity_missing")
            proof = {}

        observed_account = _text(proof.get("account"))
        observed_mint = _text(proof.get("mint"))
        observed_authority = _text(proof.get("authority"))
        expected = proof.get("expected")
        expected = expected if isinstance(expected, Mapping) else {}

        if proof.get("service") != "x1_rpc_token_account_identity":
            role_reasons.append("rpc_identity_service_mismatch")
        if proof.get("chain") != "x1":
            role_reasons.append("rpc_identity_wrong_chain")
        if proof.get("identity_verified") is not True:
            role_reasons.append("rpc_identity_unverified")
        if observed_account != expected_vault:
            role_reasons.append("rpc_account_vault_mismatch")
        if observed_mint != expected_mint:
            role_reasons.append("rpc_mint_identity_mismatch")
        if observed_authority != shared_owner:
            role_reasons.append("rpc_authority_identity_mismatch")
        if _text(expected.get("account")) != expected_vault:
            role_reasons.append("rpc_expected_account_scope_mismatch")
        if _text(expected.get("mint")) != expected_mint:
            role_reasons.append("rpc_expected_mint_scope_mismatch")
        if _text(expected.get("authority")) != shared_owner:
            role_reasons.append("rpc_expected_authority_scope_mismatch")

        role_reasons = list(dict.fromkeys(role_reasons))
        verified = not role_reasons
        roles[role] = {
            "account": observed_account,
            "mint": observed_mint,
            "authority": observed_authority,
            "slot": proof.get("slot"),
            "identity_verified": verified,
            "rejection_reasons": role_reasons,
        }
        reasons.extend(f"{role}:{reason}" for reason in role_reasons)

    reasons = list(dict.fromkeys(reasons))
    binding_verified = not reasons and all(
        roles.get(role, {}).get("identity_verified") is True for role in ROLES
    )

    return {
        "service": "x1_reserve_rpc_identity_binding",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "shared_owner": shared_owner,
        "roles": roles,
        "identity_binding_verified": binding_verified,
        "cmis_promotable": False,
        "rejection_reasons": reasons,
    }


__all__ = ["ROLES", "VERSION", "bind_x1_reserve_rpc_identities"]
