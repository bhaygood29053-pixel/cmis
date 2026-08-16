"""Read-only X1 pool/vault topology discovery for CMIS v1.4.1.

This module does not declare any account to be an official pool vault. It gathers
repeatable on-chain evidence for selected pool addresses:

- exact-window signatures from X1 RPC;
- recognized XDEX/XenDEX transaction presence;
- whether the selected pool address is passed to a recognized AMM instruction;
- recurring asset/quote token accounts and their owners;
- recurring asset+quote account ownership pairings.

All outputs remain observations/candidates. Promotion to canonical pool-leg
semantics is intentionally deferred.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.history_range import scan_address_history_range
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL
from liquidity_scout.providers.x1.transaction_semantics import (
    DEFAULT_QUOTE_MINTS,
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    XENDEX_AMM_PROGRAM_ID,
    account_key_info,
    collect_program_ids,
    compute_token_deltas,
    fetch_transaction,
)

VERSION = "1.4.1"
RECOGNIZED_AMM_PROGRAM_IDS = (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    XENDEX_AMM_PROGRAM_ID,
)


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _epoch(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _resolve_program_id(
    instruction: Mapping[str, Any],
    account_keys: Sequence[str],
) -> str | None:
    direct = instruction.get("programId")
    if isinstance(direct, str):
        return _text(direct)
    if isinstance(direct, Mapping):
        return _text(direct.get("pubkey") or direct.get("address"))

    index = instruction.get("programIdIndex")
    if isinstance(index, int) and not isinstance(index, bool):
        if 0 <= index < len(account_keys):
            return _text(account_keys[index])
    return None


def _resolve_account_ref(
    value: Any,
    account_keys: Sequence[str],
) -> str | None:
    if isinstance(value, int) and not isinstance(value, bool):
        if 0 <= value < len(account_keys):
            return _text(account_keys[value])
        return None
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, Mapping):
        return _text(value.get("pubkey") or value.get("address"))
    return None


def collect_recognized_amm_instruction_accounts(
    tx: Mapping[str, Any],
    *,
    program_ids: Sequence[str] = RECOGNIZED_AMM_PROGRAM_IDS,
) -> dict[str, list[str]]:
    """Return recognized AMM program -> unique accounts explicitly passed to it."""

    account_keys, _ = account_key_info(dict(tx))
    wanted = set(program_ids)
    found: dict[str, list[str]] = {program_id: [] for program_id in wanted}

    def inspect(instruction: Any) -> None:
        if not isinstance(instruction, Mapping):
            return
        program_id = _resolve_program_id(instruction, account_keys)
        if program_id not in wanted:
            return

        raw_accounts = instruction.get("accounts")
        if not isinstance(raw_accounts, Sequence) or isinstance(
            raw_accounts, (str, bytes)
        ):
            raw_accounts = []

        bucket = found.setdefault(program_id, [])
        for raw in raw_accounts:
            address = _resolve_account_ref(raw, account_keys)
            if address and address not in bucket:
                bucket.append(address)

    message = (
        ((tx.get("transaction") or {}).get("message") or {})
        if isinstance(tx, Mapping)
        else {}
    )
    for instruction in message.get("instructions") or []:
        inspect(instruction)

    meta = tx.get("meta") or {}
    for group in meta.get("innerInstructions") or []:
        if not isinstance(group, Mapping):
            continue
        for instruction in group.get("instructions") or []:
            inspect(instruction)

    return {
        program_id: accounts
        for program_id, accounts in found.items()
        if accounts
    }


def _window_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    start_epoch: float,
    end_epoch: float,
) -> list[dict[str, Any]]:
    out = []
    seen = set()
    for raw in entries:
        if not isinstance(raw, Mapping):
            continue
        signature = _text(raw.get("signature"))
        slot = raw.get("slot")
        block_time = _epoch(raw.get("block_time"))
        if (
            not signature
            or signature in seen
            or isinstance(slot, bool)
            or not isinstance(slot, int)
            or slot < 0
            or block_time is None
        ):
            continue
        if start_epoch <= block_time <= end_epoch:
            seen.add(signature)
            out.append(
                {
                    "signature": signature,
                    "slot": slot,
                    "block_time": block_time,
                    "err": raw.get("err"),
                }
            )
    return out


def _default_fetcher(signature: str, *, rpc_url: str):
    return fetch_transaction(signature, rpc_url=rpc_url)


def _candidate_role(mint: str, asset_mint: str, quote_mints: set[str]) -> str:
    if mint == asset_mint:
        return "ASSET_VAULT_CANDIDATE"
    if mint in quote_mints:
        return "QUOTE_VAULT_CANDIDATE"
    return "OTHER_TOKEN_ACCOUNT"


def discover_pool_topology(
    *,
    pool_address: str,
    asset_mint: str,
    start_epoch: float,
    end_epoch: float,
    pair: str | None = None,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    quote_mints: Sequence[str] = DEFAULT_QUOTE_MINTS,
    page_size: int = 1000,
    max_signatures: int = 5000,
    min_occurrences: int = 2,
    scanner: Callable[..., Mapping[str, Any]] = scan_address_history_range,
    fetcher: Callable[..., Any] = _default_fetcher,
) -> dict[str, Any]:
    """Gather non-promoting topology evidence for one selected pool address."""

    pool_address = _text(pool_address)
    asset_mint = _text(asset_mint)
    if not pool_address:
        raise ValueError("pool_address is required")
    if not asset_mint:
        raise ValueError("asset_mint is required")

    start_epoch = _epoch(start_epoch)
    end_epoch = _epoch(end_epoch)
    if start_epoch is None or end_epoch is None:
        raise ValueError("start_epoch and end_epoch must be non-negative times")
    if start_epoch > end_epoch:
        raise ValueError("start_epoch must be <= end_epoch")
    if isinstance(min_occurrences, bool) or not isinstance(min_occurrences, int):
        raise ValueError("min_occurrences must be an integer >= 1")
    if min_occurrences < 1:
        raise ValueError("min_occurrences must be an integer >= 1")

    scan = scanner(
        pool_address,
        start_epoch=start_epoch,
        end_epoch=end_epoch,
        rpc_url=rpc_url,
        page_size=page_size,
        max_signatures=max_signatures,
    )
    scan = dict(scan) if isinstance(scan, Mapping) else {}
    entries = scan.pop("entries", [])
    entries = (
        entries
        if isinstance(entries, Sequence)
        and not isinstance(entries, (str, bytes))
        else []
    )
    in_window = _window_entries(
        entries,
        start_epoch=start_epoch,
        end_epoch=end_epoch,
    )

    quote_set = {
        mint for mint in (_text(item) for item in quote_mints) if mint
    }

    # Candidate account evidence is tracked by unique transaction signature.
    account_evidence: dict[tuple[str, str], dict[str, Any]] = {}
    owner_role_accounts: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    owner_tx_signatures: dict[str, set[str]] = defaultdict(set)

    tx_records = []
    recognized_dex_tx_count = 0
    successful_fetch_count = 0
    pool_address_in_message_count = 0
    pool_address_in_amm_instruction_count = 0

    for history in in_window:
        signature = history["signature"]
        if history.get("err") is not None:
            tx_records.append(
                {
                    "signature": signature,
                    "slot": history["slot"],
                    "block_time": history["block_time"],
                    "chain_succeeded": False,
                    "fetched": False,
                    "recognized_amm": False,
                    "pool_address_in_message": None,
                    "pool_address_in_amm_instruction": None,
                }
            )
            continue

        try:
            tx = fetcher(signature, rpc_url=rpc_url)
        except Exception as exc:
            tx_records.append(
                {
                    "signature": signature,
                    "slot": history["slot"],
                    "block_time": history["block_time"],
                    "chain_succeeded": True,
                    "fetched": False,
                    "fetch_error": f"{type(exc).__name__}: {exc}",
                    "recognized_amm": None,
                    "pool_address_in_message": None,
                    "pool_address_in_amm_instruction": None,
                }
            )
            continue

        if not isinstance(tx, Mapping):
            tx_records.append(
                {
                    "signature": signature,
                    "slot": history["slot"],
                    "block_time": history["block_time"],
                    "chain_succeeded": True,
                    "fetched": False,
                    "fetch_error": "getTransaction returned no mapping transaction",
                    "recognized_amm": None,
                    "pool_address_in_message": None,
                    "pool_address_in_amm_instruction": None,
                }
            )
            continue

        successful_fetch_count += 1
        account_keys, _ = account_key_info(dict(tx))
        program_ids = collect_program_ids(dict(tx))
        recognized = any(
            program_id in RECOGNIZED_AMM_PROGRAM_IDS
            for program_id in program_ids
        )
        if recognized:
            recognized_dex_tx_count += 1

        pool_in_message = pool_address in account_keys
        if pool_in_message:
            pool_address_in_message_count += 1

        amm_instruction_accounts = collect_recognized_amm_instruction_accounts(
            tx
        )
        flattened_amm_accounts = {
            account
            for accounts in amm_instruction_accounts.values()
            for account in accounts
        }
        pool_in_amm_instruction = pool_address in flattened_amm_accounts
        if pool_in_amm_instruction:
            pool_address_in_amm_instruction_count += 1

        token_deltas = compute_token_deltas(dict(tx))
        relevant_rows = [
            row
            for row in token_deltas
            if row.mint == asset_mint or row.mint in quote_set
        ]

        if recognized:
            for row in relevant_rows:
                key = (row.account, row.mint)
                evidence = account_evidence.setdefault(
                    key,
                    {
                        "account": row.account,
                        "owner": row.owner,
                        "mint": row.mint,
                        "role_hypothesis": _candidate_role(
                            row.mint,
                            asset_mint,
                            quote_set,
                        ),
                        "transaction_signatures": set(),
                        "dex_instruction_signatures": set(),
                        "positive_delta_count": 0,
                        "negative_delta_count": 0,
                        "absolute_delta_total": 0.0,
                    },
                )
                evidence["transaction_signatures"].add(signature)
                if row.account in flattened_amm_accounts:
                    evidence["dex_instruction_signatures"].add(signature)
                if row.delta_raw > 0:
                    evidence["positive_delta_count"] += 1
                elif row.delta_raw < 0:
                    evidence["negative_delta_count"] += 1
                evidence["absolute_delta_total"] += abs(float(row.delta_ui))

                owner = _text(row.owner)
                if owner:
                    owner_role_accounts[owner][
                        evidence["role_hypothesis"]
                    ].add(row.account)
                    owner_tx_signatures[owner].add(signature)

        tx_records.append(
            {
                "signature": signature,
                "slot": history["slot"],
                "block_time": history["block_time"],
                "chain_succeeded": True,
                "fetched": True,
                "recognized_amm": recognized,
                "recognized_amm_program_ids": [
                    program_id
                    for program_id in program_ids
                    if program_id in RECOGNIZED_AMM_PROGRAM_IDS
                ],
                "pool_address_in_message": pool_in_message,
                "pool_address_in_amm_instruction": pool_in_amm_instruction,
                "relevant_token_delta_count": len(relevant_rows),
            }
        )

    denominator = recognized_dex_tx_count if recognized_dex_tx_count > 0 else 1

    candidates = []
    for evidence in account_evidence.values():
        tx_sigs = evidence.pop("transaction_signatures")
        dex_sigs = evidence.pop("dex_instruction_signatures")
        occurrence_count = len(tx_sigs)
        instruction_occurrence_count = len(dex_sigs)
        occurrence_ratio = occurrence_count / denominator
        instruction_ratio = instruction_occurrence_count / denominator
        persistent = occurrence_count >= min_occurrences

        candidates.append(
            {
                **evidence,
                "transaction_occurrence_count": occurrence_count,
                "recognized_amm_transaction_ratio": round(
                    occurrence_ratio, 6
                ),
                "dex_instruction_occurrence_count": (
                    instruction_occurrence_count
                ),
                "dex_instruction_transaction_ratio": round(
                    instruction_ratio, 6
                ),
                "persistent_candidate": persistent,
                "topology_promoted": False,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["persistent_candidate"],
            item["dex_instruction_occurrence_count"],
            item["transaction_occurrence_count"],
            item["absolute_delta_total"],
        ),
        reverse=True,
    )

    owner_candidates = []
    for owner, roles in owner_role_accounts.items():
        asset_accounts = sorted(
            roles.get("ASSET_VAULT_CANDIDATE", set())
        )
        quote_accounts = sorted(
            roles.get("QUOTE_VAULT_CANDIDATE", set())
        )
        tx_count = len(owner_tx_signatures[owner])
        owner_candidates.append(
            {
                "owner": owner,
                "asset_candidate_accounts": asset_accounts,
                "quote_candidate_accounts": quote_accounts,
                "transaction_occurrence_count": tx_count,
                "asset_quote_pair_observed": bool(
                    asset_accounts and quote_accounts
                ),
                "persistent_candidate": tx_count >= min_occurrences,
                "topology_promoted": False,
            }
        )

    owner_candidates.sort(
        key=lambda item: (
            item["asset_quote_pair_observed"],
            item["persistent_candidate"],
            item["transaction_occurrence_count"],
        ),
        reverse=True,
    )

    persistent_asset = [
        item
        for item in candidates
        if item["persistent_candidate"]
        and item["role_hypothesis"] == "ASSET_VAULT_CANDIDATE"
    ]
    persistent_quote = [
        item
        for item in candidates
        if item["persistent_candidate"]
        and item["role_hypothesis"] == "QUOTE_VAULT_CANDIDATE"
    ]
    paired_owner = any(
        item["persistent_candidate"]
        and item["asset_quote_pair_observed"]
        for item in owner_candidates
    )

    topology_observed = bool(
        recognized_dex_tx_count > 0
        and persistent_asset
        and persistent_quote
    )

    return {
        "service": "pool_topology_discovery",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "pair": pair,
        "asset_mint": asset_mint,
        "quote_mints": sorted(quote_set),
        "range_proven": scan.get("range_proven") is True,
        "integrity_verified": scan.get("integrity_verified") is True,
        "requested_window_signature_count": len(in_window),
        "successful_transaction_fetch_count": successful_fetch_count,
        "recognized_amm_transaction_count": recognized_dex_tx_count,
        "pool_address_in_message_count": pool_address_in_message_count,
        "pool_address_in_amm_instruction_count": (
            pool_address_in_amm_instruction_count
        ),
        "pool_address_in_amm_instruction_ratio": round(
            (
                pool_address_in_amm_instruction_count / denominator
                if recognized_dex_tx_count > 0
                else 0.0
            ),
            6,
        ),
        "candidate_token_accounts": candidates,
        "candidate_owner_groups": owner_candidates,
        "summary": {
            "persistent_asset_candidate_count": len(persistent_asset),
            "persistent_quote_candidate_count": len(persistent_quote),
            "persistent_asset_quote_owner_pair_observed": paired_owner,
            "candidate_topology_observed": topology_observed,
            "topology_promoted": False,
            "canonical_vault_mapping_proven": False,
            "interpretation": (
                "Recurring token accounts and instruction relationships are "
                "candidate topology evidence only. v1.4.1 does not declare "
                "official vault roles or promote exact pool-leg semantics."
            ),
        },
        "transactions": tx_records,
        "proof_scan": scan,
    }


__all__ = [
    "RECOGNIZED_AMM_PROGRAM_IDS",
    "VERSION",
    "collect_recognized_amm_instruction_accounts",
    "discover_pool_topology",
]
