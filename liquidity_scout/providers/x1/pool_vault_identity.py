"""Fail-closed adapter from canonical X1 coupling proof to vault identity.

This module does not discover vaults and does not use balances or ranking to
choose them.  It accepts only the output of the existing canonical
pool-vault-coupling proof and exposes a compact identity record when that proof
has exactly one canonical family.

The resulting record proves pool/account/mint relationships only.  It does not
prove X1.Ninja reserve-field semantics, reserve units, observation freshness,
or value agreement with RPC.  Those remain separate promotion gates.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


VERSION = "1.0"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def extract_pool_vault_identity(
    proof: Mapping[str, Any],
    *,
    expected_pool_address: str | None = None,
    expected_asset_mint: str | None = None,
) -> dict[str, Any]:
    """Extract a verified pool/vault identity from canonical coupling evidence.

    The adapter fails closed unless the upstream proof explicitly reports a
    unique canonical mapping and the candidate contains all required identity
    fields. Optional expected identifiers bind the proof to caller scope.
    """

    if not isinstance(proof, Mapping):
        raise TypeError("proof must be a mapping")

    pool_address = _text(proof.get("pool_address"))
    asset_mint = _text(proof.get("asset_mint"))
    summary = proof.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    candidate = proof.get("canonical_vault_mapping_candidate")
    candidate = candidate if isinstance(candidate, Mapping) else {}

    reasons: list[str] = []

    if proof.get("chain") != "x1":
        reasons.append("wrong_chain")
    if proof.get("status") != "canonical_pool_vault_coupling_proven":
        reasons.append("canonical_coupling_status_unproven")
    if summary.get("canonical_vault_mapping_proven") is not True:
        reasons.append("canonical_mapping_summary_unproven")
    if summary.get("unique_pool_coupled_family") is not True:
        reasons.append("unique_pool_coupled_family_unproven")
    if not pool_address:
        reasons.append("pool_address_missing")
    if not asset_mint:
        reasons.append("asset_mint_missing")

    asset_account = _text(candidate.get("asset_account"))
    counter_account = _text(candidate.get("counter_account"))
    counter_mint = _text(candidate.get("counter_mint"))
    shared_owner = _text(candidate.get("shared_owner"))

    if not asset_account:
        reasons.append("asset_vault_missing")
    if not counter_account:
        reasons.append("counter_vault_missing")
    if not counter_mint:
        reasons.append("counter_mint_missing")
    if not shared_owner:
        reasons.append("shared_owner_missing")
    if asset_account and counter_account and asset_account == counter_account:
        reasons.append("vault_accounts_not_distinct")
    if asset_mint and counter_mint and asset_mint == counter_mint:
        reasons.append("vault_mints_not_distinct")

    expected_pool = _text(expected_pool_address)
    expected_mint = _text(expected_asset_mint)
    if expected_pool and pool_address != expected_pool:
        reasons.append("pool_scope_mismatch")
    if expected_mint and asset_mint != expected_mint:
        reasons.append("asset_mint_scope_mismatch")

    reasons = list(dict.fromkeys(reasons))
    identity_verified = not reasons

    return {
        "service": "x1_pool_vault_identity",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "asset_mint": asset_mint,
        "asset_vault": asset_account,
        "counter_mint": counter_mint,
        "counter_vault": counter_account,
        "shared_owner": shared_owner,
        "identity_verified": identity_verified,
        "reserve_semantics_verified": False,
        "reserve_units_verified": False,
        "cmis_promotable": False,
        "rejection_reasons": reasons,
        "source_proof": {
            "service": _text(proof.get("service")),
            "version": _text(proof.get("version")),
            "status": _text(proof.get("status")),
        },
    }


__all__ = ["VERSION", "extract_pool_vault_identity"]
