"""Prove one verified X1 transaction touched both vaults of one verified pool.

This module is transport-free. It composes an existing ``VerificationReport``
with an independently established pool/vault identity. It does not infer pool
membership from symbols, provider labels, balances, or a single token account.

Membership is proven only when a successful recognized XDEX/XenDEX transaction
has non-zero token deltas on both exact verified vault accounts with the exact
verified mints. This proves transaction-to-pool membership for that pool identity
only; it does not prove provider history completeness, amount semantics, trade
price, finality equivalence, source independence, or CMIS promotion.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.providers.x1.transaction_semantics import VerificationReport


CONTRACT_VERSION = "x1_transaction_pool_membership/v1"


class X1TransactionPoolMembershipError(ValueError):
    """Raised when supplied evidence cannot safely establish membership."""


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise X1TransactionPoolMembershipError(f"{name} is required")
    return value.strip()


def _strict_true(name: str, value: Any) -> None:
    if not isinstance(value, bool):
        raise X1TransactionPoolMembershipError(f"{name} must be a boolean")
    if value is not True:
        raise X1TransactionPoolMembershipError(f"{name} must be verified")


def prove_transaction_pool_membership(
    *,
    verification_report: VerificationReport,
    pool_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Return fail-closed exact-pool membership evidence for one transaction."""
    if not isinstance(verification_report, VerificationReport):
        raise TypeError("verification_report must be a VerificationReport")
    if not isinstance(pool_identity, Mapping):
        raise TypeError("pool_identity must be a mapping")

    if pool_identity.get("chain") != "x1":
        raise X1TransactionPoolMembershipError("pool_identity chain must be x1")
    _strict_true("pool_identity.identity_verified", pool_identity.get("identity_verified"))

    pool_address = _text("pool_identity.pool_address", pool_identity.get("pool_address"))
    asset_mint = _text("pool_identity.asset_mint", pool_identity.get("asset_mint"))
    asset_vault = _text("pool_identity.asset_vault", pool_identity.get("asset_vault"))
    counter_mint = _text("pool_identity.counter_mint", pool_identity.get("counter_mint"))
    counter_vault = _text("pool_identity.counter_vault", pool_identity.get("counter_vault"))

    if asset_vault == counter_vault:
        raise X1TransactionPoolMembershipError("verified vault accounts must be distinct")
    if asset_mint == counter_mint:
        raise X1TransactionPoolMembershipError("verified vault mints must be distinct")

    reasons: list[str] = []
    if not verification_report.found:
        reasons.append("transaction_not_found")
    if not verification_report.succeeded:
        reasons.append("transaction_not_successful")
    if not (verification_report.xdex_amm_invoked or verification_report.xendex_amm_invoked):
        reasons.append("recognized_amm_not_invoked")

    by_account = {}
    for delta in verification_report.token_deltas:
        if delta.account in by_account:
            reasons.append("duplicate_token_delta_account")
            continue
        by_account[delta.account] = delta

    asset_delta = by_account.get(asset_vault)
    counter_delta = by_account.get(counter_vault)
    if asset_delta is None:
        reasons.append("asset_vault_delta_missing")
    elif asset_delta.mint != asset_mint:
        reasons.append("asset_vault_mint_mismatch")
    elif asset_delta.delta_raw == 0:
        reasons.append("asset_vault_not_mutated")

    if counter_delta is None:
        reasons.append("counter_vault_delta_missing")
    elif counter_delta.mint != counter_mint:
        reasons.append("counter_vault_mint_mismatch")
    elif counter_delta.delta_raw == 0:
        reasons.append("counter_vault_not_mutated")

    reasons = list(dict.fromkeys(reasons))
    membership_verified = not reasons

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": "x1",
        "transaction_signature": verification_report.signature,
        "pool_address": pool_address,
        "asset_mint": asset_mint,
        "asset_vault": asset_vault,
        "counter_mint": counter_mint,
        "counter_vault": counter_vault,
        "transaction_found": verification_report.found is True,
        "transaction_succeeded": verification_report.succeeded is True,
        "recognized_amm_invoked": bool(
            verification_report.xdex_amm_invoked or verification_report.xendex_amm_invoked
        ),
        "asset_vault_mutated": asset_delta is not None and asset_delta.mint == asset_mint and asset_delta.delta_raw != 0,
        "counter_vault_mutated": counter_delta is not None and counter_delta.mint == counter_mint and counter_delta.delta_raw != 0,
        "transaction_pool_membership_verified": membership_verified,
        "provider_row_pool_claim_verified": False,
        "source_independence_verified": False,
        "history_completeness_verified": False,
        "finality_semantics_verified": False,
        "amount_semantics_verified": False,
        "price_semantics_verified": False,
        "cmis_promotable": False,
        "rejection_reasons": reasons,
    }


__all__ = [
    "CONTRACT_VERSION",
    "X1TransactionPoolMembershipError",
    "prove_transaction_pool_membership",
]
