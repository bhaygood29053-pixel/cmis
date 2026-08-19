"""Prove one verified X1 transaction belongs to one separately verified pool.

This module is transport-free. It composes an existing ``VerificationReport``,
the exact already-fetched transaction payload used as structural evidence, and a
separately verified pool/vault identity. It does not infer pool membership from
symbols, provider labels, balances, or transaction-wide AMM presence alone.

Membership is proven only when:
- the transaction payload carries the same exact signature as the report;
- the transaction was found and succeeded;
- a recognized XDEX/XenDEX AMM was invoked;
- the selected pool plus both exact verified vault accounts co-occur in the same
  recognized AMM instruction occurrence collected from that exact transaction;
- both exact vault accounts have non-zero token deltas with the expected mints;
- both vault deltas retain the separately verified shared token-account owner.

This proves transaction-to-pool membership for that exact pool identity only. It
does not prove provider history completeness, amount semantics, trade price,
finality equivalence, source independence, or CMIS promotion.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from liquidity_scout.providers.x1.transaction_semantics import VerificationReport
from liquidity_scout.providers.x1.vault_pair_correlation import (
    RECOGNIZED_AMM_PROGRAM_IDS,
    collect_recognized_amm_instruction_occurrences,
)


CONTRACT_VERSION = "x1_transaction_pool_membership/v3"


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


def _transaction_signature(transaction: Mapping[str, Any]) -> str:
    raw_transaction = transaction.get("transaction")
    if not isinstance(raw_transaction, Mapping):
        raise X1TransactionPoolMembershipError(
            "transaction.transaction object is required"
        )
    signatures = raw_transaction.get("signatures")
    if (
        isinstance(signatures, (str, bytes))
        or not isinstance(signatures, Sequence)
        or not signatures
    ):
        raise X1TransactionPoolMembershipError(
            "transaction.transaction.signatures is required"
        )
    signature = signatures[0]
    if not isinstance(signature, str) or not signature.strip():
        raise X1TransactionPoolMembershipError(
            "transaction primary signature is required"
        )
    return signature.strip()


def _matching_pool_occurrences(
    instruction_occurrences: Sequence[Mapping[str, Any]],
    *,
    pool_address: str,
    asset_vault: str,
    counter_vault: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    recognized = set(RECOGNIZED_AMM_PROGRAM_IDS)
    for raw in instruction_occurrences:
        if not isinstance(raw, Mapping):
            continue
        program_id = raw.get("program_id")
        accounts = raw.get("accounts")
        if program_id not in recognized:
            continue
        if not isinstance(accounts, Sequence) or isinstance(accounts, (str, bytes)):
            continue
        normalized_accounts = [
            str(item).strip() for item in accounts if str(item).strip()
        ]
        if (
            pool_address in normalized_accounts
            and asset_vault in normalized_accounts
            and counter_vault in normalized_accounts
        ):
            matches.append(
                {
                    "program_id": program_id,
                    "scope": raw.get("scope"),
                    "group_index": raw.get("group_index"),
                    "instruction_index": raw.get("instruction_index"),
                }
            )
    return matches


def prove_transaction_pool_membership(
    *,
    verification_report: VerificationReport,
    pool_identity: Mapping[str, Any],
    transaction: Mapping[str, Any],
) -> dict[str, Any]:
    """Return fail-closed exact-pool membership evidence for one transaction."""
    if not isinstance(verification_report, VerificationReport):
        raise TypeError("verification_report must be a VerificationReport")
    if not isinstance(pool_identity, Mapping):
        raise TypeError("pool_identity must be a mapping")
    if not isinstance(transaction, Mapping):
        raise TypeError("transaction must be a mapping")

    report_signature = _text(
        "verification_report.signature", verification_report.signature
    )
    transaction_signature = _transaction_signature(transaction)
    if transaction_signature != report_signature:
        raise X1TransactionPoolMembershipError(
            "transaction signature does not match verification_report.signature"
        )

    if pool_identity.get("chain") != "x1":
        raise X1TransactionPoolMembershipError("pool_identity chain must be x1")
    _strict_true(
        "pool_identity.identity_verified", pool_identity.get("identity_verified")
    )

    pool_address = _text(
        "pool_identity.pool_address", pool_identity.get("pool_address")
    )
    asset_mint = _text("pool_identity.asset_mint", pool_identity.get("asset_mint"))
    asset_vault = _text(
        "pool_identity.asset_vault", pool_identity.get("asset_vault")
    )
    counter_mint = _text(
        "pool_identity.counter_mint", pool_identity.get("counter_mint")
    )
    counter_vault = _text(
        "pool_identity.counter_vault", pool_identity.get("counter_vault")
    )
    shared_owner = _text(
        "pool_identity.shared_owner", pool_identity.get("shared_owner")
    )

    if asset_vault == counter_vault:
        raise X1TransactionPoolMembershipError(
            "verified vault accounts must be distinct"
        )
    if asset_mint == counter_mint:
        raise X1TransactionPoolMembershipError("verified vault mints must be distinct")

    instruction_occurrences = collect_recognized_amm_instruction_occurrences(
        transaction
    )

    reasons: list[str] = []
    if not verification_report.found:
        reasons.append("transaction_not_found")
    if not verification_report.succeeded:
        reasons.append("transaction_not_successful")
    general_amm_invoked = bool(
        verification_report.xdex_amm_invoked
        or verification_report.xendex_amm_invoked
    )
    if not general_amm_invoked:
        reasons.append("recognized_amm_not_invoked")

    matching_occurrences = _matching_pool_occurrences(
        instruction_occurrences,
        pool_address=pool_address,
        asset_vault=asset_vault,
        counter_vault=counter_vault,
    )
    if not matching_occurrences:
        reasons.append(
            "selected_pool_vaults_not_coupled_in_recognized_amm_instruction"
        )

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
    else:
        if asset_delta.mint != asset_mint:
            reasons.append("asset_vault_mint_mismatch")
        if asset_delta.owner != shared_owner:
            reasons.append("asset_vault_owner_mismatch")
        if asset_delta.delta_raw == 0:
            reasons.append("asset_vault_not_mutated")

    if counter_delta is None:
        reasons.append("counter_vault_delta_missing")
    else:
        if counter_delta.mint != counter_mint:
            reasons.append("counter_vault_mint_mismatch")
        if counter_delta.owner != shared_owner:
            reasons.append("counter_vault_owner_mismatch")
        if counter_delta.delta_raw == 0:
            reasons.append("counter_vault_not_mutated")

    reasons = list(dict.fromkeys(reasons))
    membership_verified = not reasons

    asset_vault_verified = bool(
        asset_delta is not None
        and asset_delta.mint == asset_mint
        and asset_delta.owner == shared_owner
        and asset_delta.delta_raw != 0
    )
    counter_vault_verified = bool(
        counter_delta is not None
        and counter_delta.mint == counter_mint
        and counter_delta.owner == shared_owner
        and counter_delta.delta_raw != 0
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": "x1",
        "transaction_signature": report_signature,
        "transaction_instruction_evidence_bound": True,
        "pool_address": pool_address,
        "asset_mint": asset_mint,
        "asset_vault": asset_vault,
        "counter_mint": counter_mint,
        "counter_vault": counter_vault,
        "shared_owner": shared_owner,
        "transaction_found": verification_report.found is True,
        "transaction_succeeded": verification_report.succeeded is True,
        "recognized_amm_invoked": general_amm_invoked,
        "recognized_amm_instruction_count": len(instruction_occurrences),
        "selected_pool_instruction_verified": bool(matching_occurrences),
        "selected_pool_instruction_count": len(matching_occurrences),
        "selected_pool_instruction_evidence": matching_occurrences,
        "asset_vault_mutated": asset_vault_verified,
        "counter_vault_mutated": counter_vault_verified,
        "vault_authority_verified": bool(
            asset_vault_verified and counter_vault_verified
        ),
        "transaction_pool_membership_verified": membership_verified,
        "provider_row_pool_claim_verified": None,
        "source_independence_verified": None,
        "history_completeness_verified": None,
        "finality_semantics_verified": None,
        "amount_semantics_verified": None,
        "price_semantics_verified": None,
        "cmis_promotable": False,
        "rejection_reasons": reasons,
    }


__all__ = [
    "CONTRACT_VERSION",
    "X1TransactionPoolMembershipError",
    "prove_transaction_pool_membership",
]
