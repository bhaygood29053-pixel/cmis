"""Diagnose recognized-AMM instruction multiplicity for exact X1 pool transactions.

This module exists for issue #367. It is deliberately diagnostic: it explains
why an otherwise exact pool/vault transaction is rejected as routed or
multi-AMM by #360, but it does not relax the accepted fail-closed swap gate.

A representation artifact is considered deterministically proven only when the
same recognized instruction occurrence is duplicated with the exact same
program id, scope, source parent outer-instruction index, instruction index,
and resolved account list. The RPC inner-group `index` is preserved separately
from list position so duplicated group representations can be detected.
Different outer/inner locations remain distinct instructions even when their
program/account fingerprints match.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from liquidity_scout.providers.x1.candidate_pool_role import (
    verify_candidate_pool_role,
)
from liquidity_scout.providers.x1.ninja_vault_activity_correlation import (
    _verified_pool_structure,
)
from liquidity_scout.providers.x1.program_accounts import (
    RECOGNIZED_AMM_PROGRAM_IDS,
)
from liquidity_scout.providers.x1.transaction_pool_membership import (
    prove_transaction_pool_membership,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    VerificationReport,
    account_key_info,
    fetch_transaction,
    verify_transaction,
)
from liquidity_scout.providers.x1.vault_pair_correlation import (
    _resolve_account_ref,
    _resolve_program_id,
)
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL


VERSION = "1.0"

CAUSE_DUPLICATE_REPRESENTATION = "duplicate_occurrence_representation"
CAUSE_MULTIPLE_SELECTED_POOL = "multiple_selected_pool_instruction_occurrences"
CAUSE_SELECTED_PLUS_ADDITIONAL = (
    "selected_pool_plus_additional_recognized_amm_instruction"
)
CAUSE_MULTI_WITHOUT_SELECTED = "multiple_recognized_amm_without_selected_pool"
CAUSE_SINGLE_OR_NONE = "single_or_no_recognized_amm_instruction"


def _text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def _default_identity_resolver(
    pool_address: str,
    *,
    rpc_url: str,
) -> Mapping[str, Any]:
    identity, _program_id = _verified_pool_structure(
        pool_address,
        structural_verifier=verify_candidate_pool_role,
        recognized_program_ids=RECOGNIZED_AMM_PROGRAM_IDS,
        rpc_url=rpc_url,
    )
    return identity


def _collect_source_aware_occurrences(
    transaction: Mapping[str, Any],
) -> list[dict[str, Any]]:
    account_keys, _ = account_key_info(dict(transaction))
    wanted = set(RECOGNIZED_AMM_PROGRAM_IDS)
    rows: list[dict[str, Any]] = []

    def inspect(
        instruction: Any,
        *,
        scope: str,
        parent_outer_instruction_index: int | None,
        source_group_position: int | None,
        instruction_index: int,
    ) -> None:
        if not isinstance(instruction, Mapping):
            return
        program_id = _resolve_program_id(instruction, account_keys)
        if program_id not in wanted:
            return
        raw_accounts = instruction.get("accounts")
        raw_accounts = (
            raw_accounts
            if isinstance(raw_accounts, Sequence)
            and not isinstance(raw_accounts, (str, bytes))
            else []
        )
        accounts = []
        for value in raw_accounts:
            address = _resolve_account_ref(value, account_keys)
            if not address:
                raise ValueError(
                    "recognized AMM instruction account reference unresolved"
                )
            accounts.append(address)
        rows.append({
            "program_id": program_id,
            "scope": scope,
            "parent_outer_instruction_index": (
                parent_outer_instruction_index
            ),
            "source_group_position": source_group_position,
            "instruction_index": instruction_index,
            "accounts": accounts,
        })

    raw_tx = transaction.get("transaction")
    raw_tx = raw_tx if isinstance(raw_tx, Mapping) else {}
    message = raw_tx.get("message")
    message = message if isinstance(message, Mapping) else {}
    outer = message.get("instructions")
    outer = (
        outer
        if isinstance(outer, Sequence)
        and not isinstance(outer, (str, bytes))
        else []
    )
    for instruction_index, instruction in enumerate(outer):
        inspect(
            instruction,
            scope="outer",
            parent_outer_instruction_index=None,
            source_group_position=None,
            instruction_index=instruction_index,
        )

    meta = transaction.get("meta")
    meta = meta if isinstance(meta, Mapping) else {}
    inner_groups = meta.get("innerInstructions")
    inner_groups = (
        inner_groups
        if isinstance(inner_groups, Sequence)
        and not isinstance(inner_groups, (str, bytes))
        else []
    )
    for source_group_position, group in enumerate(inner_groups):
        if not isinstance(group, Mapping):
            continue
        parent_index = group.get("index")
        if (
            isinstance(parent_index, bool)
            or not isinstance(parent_index, int)
            or parent_index < 0
            or parent_index >= len(outer)
        ):
            raise ValueError(
                "inner instruction group source index unavailable"
            )
        instructions = group.get("instructions")
        instructions = (
            instructions
            if isinstance(instructions, Sequence)
            and not isinstance(instructions, (str, bytes))
            else []
        )
        for instruction_index, instruction in enumerate(instructions):
            inspect(
                instruction,
                scope="inner",
                parent_outer_instruction_index=parent_index,
                source_group_position=source_group_position,
                instruction_index=instruction_index,
            )

    return rows


def _occurrence_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    accounts = row.get("accounts")
    accounts = (
        tuple(str(value) for value in accounts)
        if isinstance(accounts, Sequence)
        and not isinstance(accounts, (str, bytes))
        else tuple()
    )
    return (
        row.get("program_id"),
        row.get("scope"),
        row.get("parent_outer_instruction_index"),
        row.get("instruction_index"),
        accounts,
    )


def _normalized_occurrence(row: Mapping[str, Any]) -> dict[str, Any]:
    accounts = row.get("accounts")
    accounts = (
        [str(value) for value in accounts]
        if isinstance(accounts, Sequence)
        and not isinstance(accounts, (str, bytes))
        else []
    )
    parent_index = row.get("parent_outer_instruction_index")
    if parent_index is None:
        parent_index = row.get("group_index")
    return {
        "program_id": _text(row.get("program_id")),
        "scope": _text(row.get("scope")),
        "parent_outer_instruction_index": parent_index,
        "source_group_position": row.get("source_group_position"),
        "instruction_index": row.get("instruction_index"),
        "accounts": accounts,
    }


def _selected_pool_occurrence(
    row: Mapping[str, Any],
    identity: Mapping[str, Any],
) -> bool:
    accounts = row.get("accounts")
    if not isinstance(accounts, Sequence) or isinstance(accounts, (str, bytes)):
        return False
    account_set = {str(value) for value in accounts}
    return {
        str(identity["pool_address"]),
        str(identity["asset_vault"]),
        str(identity["counter_vault"]),
    }.issubset(account_set)


def _exact_vault_delta(
    report: VerificationReport,
    *,
    account: str,
    mint: str,
) -> dict[str, Any] | None:
    rows = [
        row
        for row in report.token_deltas
        if row.account == account and row.mint == mint
    ]
    if len(rows) > 1:
        raise ValueError("duplicate exact vault token delta")
    if not rows:
        return None
    row = rows[0]
    return {
        "account": row.account,
        "mint": row.mint,
        "owner": row.owner,
        "delta_raw": row.delta_raw,
        "delta_ui": format(row.delta_ui, "f"),
    }


def characterize_routed_multi_amm_ambiguity(
    *,
    signature: str,
    pool_address: str,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    identity_resolver: Callable[..., Mapping[str, Any]] = (
        _default_identity_resolver
    ),
    transaction_fetcher: Callable[..., Mapping[str, Any] | None] = (
        fetch_transaction
    ),
    transaction_verifier: Callable[..., VerificationReport] = (
        verify_transaction
    ),
    membership_prover: Callable[..., Mapping[str, Any]] = (
        prove_transaction_pool_membership
    ),
    occurrence_collector: Callable[
        [Mapping[str, Any]], Sequence[Mapping[str, Any]]
    ] = _collect_source_aware_occurrences,
) -> dict[str, Any]:
    """Return instruction-level evidence for one #360 ambiguity signature."""

    signature = _text(signature)
    pool_address = _text(pool_address)
    if not signature:
        raise ValueError("signature is required")
    if not pool_address:
        raise ValueError("pool_address is required")

    identity_raw = identity_resolver(pool_address, rpc_url=rpc_url)
    if not isinstance(identity_raw, Mapping):
        raise ValueError("exact pool identity unavailable")
    identity = dict(identity_raw)
    required = (
        "pool_address",
        "asset_mint",
        "asset_vault",
        "counter_mint",
        "counter_vault",
        "shared_owner",
    )
    if identity.get("identity_verified") is not True or any(
        not _text(identity.get(name)) for name in required
    ):
        raise ValueError("exact verified pool/vault identity required")
    if _text(identity.get("pool_address")) != pool_address:
        raise ValueError("resolved pool identity does not match requested pool")

    transaction = transaction_fetcher(signature, rpc_url=rpc_url)
    if not isinstance(transaction, Mapping):
        raise ValueError("transaction unavailable")

    report = transaction_verifier(
        transaction,
        signature=signature,
        rpc_url=rpc_url,
    )
    if not isinstance(report, VerificationReport):
        raise TypeError("transaction verifier must return VerificationReport")
    if report.signature != signature:
        raise ValueError("verification report signature mismatch")
    if report.found is not True or report.succeeded is not True:
        raise ValueError("transaction must be found and successful")

    membership_raw = membership_prover(
        verification_report=report,
        pool_identity=identity,
        transaction=transaction,
    )
    if not isinstance(membership_raw, Mapping):
        raise ValueError("transaction-pool membership evidence unavailable")
    membership = dict(membership_raw)
    if membership.get("transaction_pool_membership_verified") is not True:
        raise ValueError("exact transaction-to-pool membership unverified")

    raw_occurrences = occurrence_collector(transaction)
    if (
        not isinstance(raw_occurrences, Sequence)
        or isinstance(raw_occurrences, (str, bytes))
    ):
        raise ValueError("recognized AMM instruction evidence unavailable")
    occurrences = [
        _normalized_occurrence(row)
        for row in raw_occurrences
        if isinstance(row, Mapping)
    ]

    raw_selected = [
        row for row in occurrences
        if _selected_pool_occurrence(row, identity)
    ]

    if membership.get("recognized_amm_instruction_count") != len(occurrences):
        raise ValueError("membership recognized-instruction count mismatch")
    if membership.get("selected_pool_instruction_count") != len(raw_selected):
        raise ValueError("membership selected-pool instruction count mismatch")

    seen = set()
    normalized = []
    duplicate_rows = []
    for row in occurrences:
        key = _occurrence_key(row)
        if key in seen:
            duplicate_rows.append(row)
            continue
        seen.add(key)
        normalized.append(row)

    normalized_selected = [
        row for row in normalized
        if _selected_pool_occurrence(row, identity)
    ]
    normalized_additional = [
        row for row in normalized
        if not _selected_pool_occurrence(row, identity)
    ]

    duplicate_representation_verified = bool(duplicate_rows)
    if (
        duplicate_representation_verified
        and len(normalized) == 1
        and len(normalized_selected) == 1
    ):
        cause = CAUSE_DUPLICATE_REPRESENTATION
    elif len(normalized_selected) > 1:
        cause = CAUSE_MULTIPLE_SELECTED_POOL
    elif len(normalized_selected) == 1 and normalized_additional:
        cause = CAUSE_SELECTED_PLUS_ADDITIONAL
    elif len(normalized) > 1 and not normalized_selected:
        cause = CAUSE_MULTI_WITHOUT_SELECTED
    else:
        cause = CAUSE_SINGLE_OR_NONE

    asset_delta = _exact_vault_delta(
        report,
        account=str(identity["asset_vault"]),
        mint=str(identity["asset_mint"]),
    )
    counter_delta = _exact_vault_delta(
        report,
        account=str(identity["counter_vault"]),
        mint=str(identity["counter_mint"]),
    )
    exact_vault_deltas_verified = bool(
        asset_delta
        and counter_delta
        and asset_delta["delta_raw"] != 0
        and counter_delta["delta_raw"] != 0
        and asset_delta["owner"] == identity["shared_owner"]
        and counter_delta["owner"] == identity["shared_owner"]
    )

    scope_counts = Counter(
        row.get("scope") or "unknown"
        for row in normalized
    )
    occurrence_program_ids = sorted({
        row["program_id"]
        for row in normalized
        if row.get("program_id")
    })

    return {
        "service": "x1_routed_multi_amm_ambiguity",
        "version": VERSION,
        "chain": "x1",
        "status": "verified",
        "signature": signature,
        "slot": report.slot,
        "block_time": report.block_time,
        "pool_address": pool_address,
        "identity": identity,
        "program_ids": list(report.program_ids),
        "recognized_occurrence_program_ids": occurrence_program_ids,
        "recognized_amm_instruction_count_raw": len(occurrences),
        "recognized_amm_instruction_count_normalized": len(normalized),
        "selected_pool_instruction_count_raw": len(raw_selected),
        "selected_pool_instruction_count_normalized": len(normalized_selected),
        "additional_recognized_instruction_count_normalized": len(
            normalized_additional
        ),
        "instruction_scope_counts_normalized": dict(scope_counts),
        "recognized_amm_instruction_occurrences": occurrences,
        "selected_pool_instruction_occurrences": normalized_selected,
        "additional_recognized_instruction_occurrences": normalized_additional,
        "duplicate_occurrence_rows": duplicate_rows,
        "duplicate_occurrence_representation_verified": (
            duplicate_representation_verified
        ),
        "exact_vault_deltas_verified": exact_vault_deltas_verified,
        "asset_vault_delta": asset_delta,
        "counter_vault_delta": counter_delta,
        "membership": membership,
        "ambiguity_cause": cause,
        "genuine_instruction_multiplicity_observed": len(normalized) > 1,
        "classification_change_authorized": False,
        "existing_fail_closed_block_should_remain": True,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def aggregate_routed_multi_amm_characterizations(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize exact-signature diagnostics without changing #360 semantics."""

    values = [dict(row) for row in rows if isinstance(row, Mapping)]
    cause_counts = Counter(
        str(row.get("ambiguity_cause") or "unknown")
        for row in values
    )
    all_verified = bool(
        values
        and all(row.get("status") == "verified" for row in values)
    )
    all_exact_vaults = bool(
        values
        and all(row.get("exact_vault_deltas_verified") is True for row in values)
    )
    any_artifact = any(
        row.get("duplicate_occurrence_representation_verified") is True
        for row in values
    )

    return {
        "service": "x1_routed_multi_amm_ambiguity_aggregate",
        "version": VERSION,
        "chain": "x1",
        "status": "verified" if all_verified else (
            "partial" if values else "unavailable"
        ),
        "signature_count": len(values),
        "all_signatures_verified": all_verified,
        "all_exact_vault_deltas_verified": all_exact_vaults,
        "ambiguity_cause_counts": dict(cause_counts),
        "duplicate_occurrence_representation_observed": any_artifact,
        "classification_change_authorized": False,
        "departure_pattern_verified": False,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
        "rows": values,
    }


__all__ = [
    "CAUSE_DUPLICATE_REPRESENTATION",
    "CAUSE_MULTIPLE_SELECTED_POOL",
    "CAUSE_SELECTED_PLUS_ADDITIONAL",
    "CAUSE_MULTI_WITHOUT_SELECTED",
    "CAUSE_SINGLE_OR_NONE",
    "VERSION",
    "aggregate_routed_multi_amm_characterizations",
    "characterize_routed_multi_amm_ambiguity",
]
