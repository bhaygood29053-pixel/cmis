"""Verify exact pool-account membership in recognized X1 DEX AMM instructions.

This module answers one narrow question from an already-fetched X1 transaction:
was a caller-supplied pool address passed as an account to an instruction whose
program id is a recognized XDEX/XenDEX AMM program?

It does not infer that the pool was mutated, that a swap succeeded economically,
that the pool was the only route used, or that the provider row is complete or
correct. A pool merely appearing in the transaction message account-key list is
not sufficient; the exact address must occur in the account list of a recognized
AMM instruction. Outer and inner instructions are inspected deterministically.

Read-only evidence only. No network transport, signing, transaction preparation,
broadcasting, execution, or value movement belongs here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    XENDEX_AMM_PROGRAM_ID,
    account_key_info,
)


CONTRACT_VERSION = "x1_dex_pool_instruction_membership/v1"
CHAIN = "x1"
SOURCE = "X1 RPC parsed transaction"
RECOGNIZED_AMM_PROGRAM_IDS = frozenset(
    {
        XDEX_MAINNET_OBSERVED_PROGRAM_ID,
        XENDEX_AMM_PROGRAM_ID,
    }
)


class X1DexPoolInstructionMembershipError(ValueError):
    """Raised when transaction membership evidence is malformed or mismatched."""


def _required_text(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise X1DexPoolInstructionMembershipError(f"{name} must be a string")
    text = value.strip()
    if not text:
        raise X1DexPoolInstructionMembershipError(f"{name} is required")
    return text


def _instruction_program_id(
    instruction: Mapping[str, Any],
    account_keys: Sequence[str],
) -> str | None:
    direct = instruction.get("programId")
    if isinstance(direct, str) and direct:
        return direct
    if isinstance(direct, Mapping):
        value = direct.get("pubkey") or direct.get("address")
        if isinstance(value, str) and value:
            return value

    index = instruction.get("programIdIndex")
    if (
        not isinstance(index, bool)
        and isinstance(index, int)
        and 0 <= index < len(account_keys)
    ):
        value = account_keys[index]
        return value or None
    return None


def _instruction_accounts(
    instruction: Mapping[str, Any],
    account_keys: Sequence[str],
) -> tuple[str, ...]:
    raw_accounts = instruction.get("accounts")
    if not isinstance(raw_accounts, list):
        return ()

    resolved: list[str] = []
    for item in raw_accounts:
        address: str | None = None
        if isinstance(item, str):
            address = item
        elif isinstance(item, Mapping):
            value = item.get("pubkey") or item.get("address")
            if isinstance(value, str):
                address = value
        elif (
            not isinstance(item, bool)
            and isinstance(item, int)
            and 0 <= item < len(account_keys)
        ):
            address = account_keys[item]

        if address and address not in resolved:
            resolved.append(address)
    return tuple(resolved)


def _transaction_signature(tx: Mapping[str, Any]) -> str:
    transaction = tx.get("transaction")
    if not isinstance(transaction, Mapping):
        raise X1DexPoolInstructionMembershipError(
            "transaction envelope is required"
        )
    signatures = transaction.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        raise X1DexPoolInstructionMembershipError(
            "transaction.signatures must contain the requested signature"
        )
    return _required_text("transaction.signatures[0]", signatures[0])


def verify_dex_pool_instruction_membership(
    *,
    tx: Mapping[str, Any],
    signature: str,
    pool_address: str,
    pool_identity_verified: bool,
) -> dict[str, Any]:
    """Return bounded evidence for exact recognized-AMM instruction membership."""

    if not isinstance(tx, Mapping):
        raise TypeError("tx must be a mapping")
    signature = _required_text("signature", signature)
    pool_address = _required_text("pool_address", pool_address)
    if not isinstance(pool_identity_verified, bool):
        raise X1DexPoolInstructionMembershipError(
            "pool_identity_verified must be a boolean"
        )
    if pool_identity_verified is not True:
        raise X1DexPoolInstructionMembershipError(
            "pool_identity_verified must be verified"
        )

    observed_signature = _transaction_signature(tx)
    if observed_signature != signature:
        raise X1DexPoolInstructionMembershipError(
            "transaction signature does not match requested signature"
        )

    account_keys, _ = account_key_info(dict(tx))
    transaction = tx.get("transaction") or {}
    message = transaction.get("message") if isinstance(transaction, Mapping) else None
    if not isinstance(message, Mapping):
        raise X1DexPoolInstructionMembershipError("transaction.message is required")

    meta = tx.get("meta")
    if not isinstance(meta, Mapping):
        raise X1DexPoolInstructionMembershipError("transaction meta is required")

    hits: list[dict[str, Any]] = []

    def inspect(
        instructions: Any,
        *,
        location: str,
        inner_group_index: int | None = None,
    ) -> None:
        if not isinstance(instructions, list):
            return
        for instruction_index, instruction in enumerate(instructions):
            if not isinstance(instruction, Mapping):
                continue
            program_id = _instruction_program_id(instruction, account_keys)
            if program_id not in RECOGNIZED_AMM_PROGRAM_IDS:
                continue
            accounts = _instruction_accounts(instruction, account_keys)
            if pool_address not in accounts:
                continue
            hits.append(
                {
                    "location": location,
                    "instruction_index": instruction_index,
                    "inner_group_index": inner_group_index,
                    "program_id": program_id,
                    "pool_address": pool_address,
                }
            )

    inspect(message.get("instructions"), location="outer")

    inner_groups = meta.get("innerInstructions")
    if isinstance(inner_groups, list):
        for group_index, group in enumerate(inner_groups):
            if not isinstance(group, Mapping):
                continue
            inspect(
                group.get("instructions"),
                location="inner",
                inner_group_index=group_index,
            )

    transaction_succeeded = meta.get("err") is None
    membership_verified = bool(hits)

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "source": SOURCE,
        "signature": signature,
        "signature_identity_verified": True,
        "pool_address": pool_address,
        "pool_identity_verified": True,
        "recognized_amm_program_ids": sorted(RECOGNIZED_AMM_PROGRAM_IDS),
        "recognized_amm_instruction_pool_account_membership_verified": (
            membership_verified
        ),
        "successful_recognized_amm_instruction_pool_account_membership_verified": (
            membership_verified and transaction_succeeded
        ),
        "transaction_succeeded": transaction_succeeded,
        "hit_count": len(hits),
        "hits": hits,
        "pool_mutation_verified": False,
        "provider_trade_row_verified": False,
        "route_exclusivity_verified": False,
        "source_independence_verified": False,
        "cmis_promotable": False,
        "warnings": [
            "instruction_account_membership_is_not_pool_mutation_proof",
            "instruction_account_membership_is_not_route_exclusivity_proof",
            "provider_trade_semantics_require_separate_evidence",
        ],
    }


__all__ = [
    "CHAIN",
    "CONTRACT_VERSION",
    "RECOGNIZED_AMM_PROGRAM_IDS",
    "SOURCE",
    "X1DexPoolInstructionMembershipError",
    "verify_dex_pool_instruction_membership",
]
