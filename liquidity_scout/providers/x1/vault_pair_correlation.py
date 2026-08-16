"""CMIS v1.4.2 — read-only vault-pair correlation for X1 AMM pools.

Purpose
-------
v1.4.1 discovered recurring token-account topology. v1.4.2 asks a stricter
question: do one asset account and one counter-asset account repeatedly appear
together in the *same recognized AMM instruction*, under the same owner, in
stable instruction positions, with opposite balance-delta directions?

That is stronger evidence for a pool vault pair, but this module still does not
declare an official/canonical vault mapping. Promotion is deferred to a later
phase after broader validation.

No LLM logic belongs here. This module is read-only.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.history_range import scan_address_history_range
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    XENDEX_AMM_PROGRAM_ID,
    account_key_info,
    compute_token_deltas,
    fetch_transaction,
)

VERSION = "1.4.2"
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


def collect_recognized_amm_instruction_occurrences(
    tx: Mapping[str, Any],
    *,
    program_ids: Sequence[str] = RECOGNIZED_AMM_PROGRAM_IDS,
) -> list[dict[str, Any]]:
    """Return each recognized AMM instruction with ordered resolved accounts."""

    account_keys, _ = account_key_info(dict(tx))
    wanted = set(program_ids)
    out: list[dict[str, Any]] = []

    def inspect(
        instruction: Any,
        *,
        scope: str,
        group_index: int | None,
        instruction_index: int,
    ) -> None:
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

        accounts = []
        for raw in raw_accounts:
            address = _resolve_account_ref(raw, account_keys)
            if address:
                accounts.append(address)

        out.append(
            {
                "program_id": program_id,
                "scope": scope,
                "group_index": group_index,
                "instruction_index": instruction_index,
                "accounts": accounts,
            }
        )

    message = ((tx.get("transaction") or {}).get("message") or {})
    for index, instruction in enumerate(message.get("instructions") or []):
        inspect(
            instruction,
            scope="outer",
            group_index=None,
            instruction_index=index,
        )

    meta = tx.get("meta") or {}
    for group_index, group in enumerate(meta.get("innerInstructions") or []):
        if not isinstance(group, Mapping):
            continue
        for instruction_index, instruction in enumerate(
            group.get("instructions") or []
        ):
            inspect(
                instruction,
                scope="inner",
                group_index=group_index,
                instruction_index=instruction_index,
            )

    return out


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


def _position_map(accounts: Sequence[str]) -> dict[str, list[int]]:
    positions: dict[str, list[int]] = defaultdict(list)
    for index, account in enumerate(accounts):
        positions[account].append(index)
    return dict(positions)


def _pair_direction(asset_delta, counter_delta) -> str:
    """Return trader-side direction inferred from candidate pool-vault signs."""

    if asset_delta < 0 and counter_delta > 0:
        return "BUY"
    if asset_delta > 0 and counter_delta < 0:
        return "SELL"
    return "SAME_DIRECTION_OR_UNRESOLVED"


def _pair_key(asset_row, counter_row):
    return (
        asset_row.account,
        asset_row.mint,
        counter_row.account,
        counter_row.mint,
        asset_row.owner,
    )


def correlate_pool_vault_pairs(
    *,
    pool_address: str,
    asset_mint: str,
    start_epoch: float,
    end_epoch: float,
    pair: str | None = None,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    page_size: int = 1000,
    max_signatures: int = 5000,
    min_occurrences: int = 2,
    min_coverage_ratio: float = 0.50,
    min_opposite_direction_ratio: float = 0.95,
    min_fingerprint_ratio: float = 0.95,
    min_dominance_margin: float = 0.10,
    scanner: Callable[..., Mapping[str, Any]] = scan_address_history_range,
    fetcher: Callable[..., Any] = _default_fetcher,
) -> dict[str, Any]:
    """Correlate same-owner asset/counter-asset accounts inside AMM instructions."""

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
    if isinstance(min_occurrences, bool) or min_occurrences < 1:
        raise ValueError("min_occurrences must be >= 1")

    for name, value in (
        ("min_coverage_ratio", min_coverage_ratio),
        ("min_opposite_direction_ratio", min_opposite_direction_ratio),
        ("min_fingerprint_ratio", min_fingerprint_ratio),
        ("min_dominance_margin", min_dominance_margin),
    ):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{name} must be numeric")
        if value < 0 or value > 1:
            raise ValueError(f"{name} must be between 0 and 1")

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

    # Pair evidence is deduplicated by transaction signature. A transaction can
    # contain multiple recognized instructions; one signature must not inflate
    # pair occurrence counts.
    pair_tx_evidence: dict[tuple, dict[str, dict[str, Any]]] = defaultdict(dict)

    fetched_count = 0
    recognized_pool_instruction_tx_count = 0
    recognized_amm_tx_count = 0
    failed_history_tx_count = 0
    tx_records = []

    for history in in_window:
        signature = history["signature"]
        if history.get("err") is not None:
            failed_history_tx_count += 1
            tx_records.append(
                {
                    "signature": signature,
                    "chain_succeeded": False,
                    "fetched": False,
                    "recognized_pool_amm_instruction": False,
                }
            )
            continue

        try:
            tx = fetcher(signature, rpc_url=rpc_url)
        except Exception as exc:
            tx_records.append(
                {
                    "signature": signature,
                    "chain_succeeded": True,
                    "fetched": False,
                    "fetch_error": f"{type(exc).__name__}: {exc}",
                    "recognized_pool_amm_instruction": None,
                }
            )
            continue

        if not isinstance(tx, Mapping):
            tx_records.append(
                {
                    "signature": signature,
                    "chain_succeeded": True,
                    "fetched": False,
                    "fetch_error": "getTransaction returned no mapping transaction",
                    "recognized_pool_amm_instruction": None,
                }
            )
            continue

        fetched_count += 1
        occurrences = collect_recognized_amm_instruction_occurrences(tx)
        if occurrences:
            recognized_amm_tx_count += 1

        pool_occurrences = [
            item for item in occurrences
            if pool_address in item["accounts"]
        ]
        if not pool_occurrences:
            tx_records.append(
                {
                    "signature": signature,
                    "chain_succeeded": True,
                    "fetched": True,
                    "recognized_amm_instruction_count": len(occurrences),
                    "recognized_pool_amm_instruction": False,
                    "candidate_pair_count": 0,
                }
            )
            continue

        recognized_pool_instruction_tx_count += 1
        token_rows = compute_token_deltas(dict(tx))
        by_account = {row.account: row for row in token_rows}
        signature_pair_keys = set()

        for occurrence in pool_occurrences:
            accounts = occurrence["accounts"]
            positions = _position_map(accounts)
            pool_positions = positions.get(pool_address) or []
            if not pool_positions:
                continue

            asset_rows = [
                by_account[address]
                for address in accounts
                if address in by_account
                and by_account[address].mint == asset_mint
            ]
            counter_rows = [
                by_account[address]
                for address in accounts
                if address in by_account
                and by_account[address].mint != asset_mint
            ]

            # Deduplicate account rows when an address appears multiple times in
            # an instruction's account list.
            asset_rows = list({row.account: row for row in asset_rows}.values())
            counter_rows = list(
                {row.account: row for row in counter_rows}.values()
            )

            for asset_row in asset_rows:
                for counter_row in counter_rows:
                    if not asset_row.owner or asset_row.owner != counter_row.owner:
                        continue
                    if asset_row.account == counter_row.account:
                        continue

                    key = _pair_key(asset_row, counter_row)
                    direction = _pair_direction(
                        asset_row.delta_ui,
                        counter_row.delta_ui,
                    )

                    fingerprints = []
                    for asset_position in positions.get(asset_row.account, []):
                        for counter_position in positions.get(
                            counter_row.account, []
                        ):
                            for pool_position in pool_positions:
                                fingerprints.append(
                                    (
                                        occurrence["program_id"],
                                        occurrence["scope"],
                                        pool_position,
                                        asset_position,
                                        counter_position,
                                    )
                                )

                    record = pair_tx_evidence[key].setdefault(
                        signature,
                        {
                            "directions": set(),
                            "fingerprints": set(),
                            "asset_delta": str(asset_row.delta_ui),
                            "counter_delta": str(counter_row.delta_ui),
                        },
                    )
                    record["directions"].add(direction)
                    record["fingerprints"].update(fingerprints)
                    signature_pair_keys.add(key)

        tx_records.append(
            {
                "signature": signature,
                "chain_succeeded": True,
                "fetched": True,
                "recognized_amm_instruction_count": len(occurrences),
                "recognized_pool_amm_instruction": True,
                "candidate_pair_count": len(signature_pair_keys),
            }
        )

    denominator = (
        recognized_pool_instruction_tx_count
        if recognized_pool_instruction_tx_count > 0
        else 1
    )

    pairs = []
    for key, by_signature in pair_tx_evidence.items():
        (
            asset_account,
            pair_asset_mint,
            counter_account,
            counter_mint,
            owner,
        ) = key

        buy_count = 0
        sell_count = 0
        mixed_count = 0
        unresolved_count = 0
        fingerprint_signatures: dict[tuple, set[str]] = defaultdict(set)

        for signature, evidence in by_signature.items():
            directions = evidence["directions"]
            resolved = directions & {"BUY", "SELL"}
            unresolved_present = "SAME_DIRECTION_OR_UNRESOLVED" in directions

            if resolved == {"BUY"} and not unresolved_present:
                buy_count += 1
            elif resolved == {"SELL"} and not unresolved_present:
                sell_count += 1
            elif resolved == {"BUY", "SELL"}:
                mixed_count += 1
            else:
                unresolved_count += 1

            for fingerprint in evidence["fingerprints"]:
                fingerprint_signatures[fingerprint].add(signature)

        occurrence_count = len(by_signature)
        opposite_count = buy_count + sell_count
        coverage_ratio = occurrence_count / denominator
        opposite_ratio = (
            opposite_count / occurrence_count if occurrence_count else 0.0
        )

        dominant_fingerprint = None
        dominant_fingerprint_count = 0
        if fingerprint_signatures:
            dominant_fingerprint, sigs = max(
                fingerprint_signatures.items(),
                key=lambda item: (len(item[1]), item[0]),
            )
            dominant_fingerprint_count = len(sigs)

        fingerprint_ratio = (
            dominant_fingerprint_count / occurrence_count
            if occurrence_count
            else 0.0
        )

        stable = bool(
            occurrence_count >= min_occurrences
            and coverage_ratio >= min_coverage_ratio
            and opposite_ratio >= min_opposite_direction_ratio
            and fingerprint_ratio >= min_fingerprint_ratio
        )

        pairs.append(
            {
                "asset_account": asset_account,
                "asset_mint": pair_asset_mint,
                "counter_account": counter_account,
                "counter_mint": counter_mint,
                "shared_owner": owner,
                "transaction_occurrence_count": occurrence_count,
                "recognized_pool_instruction_transaction_ratio": round(
                    coverage_ratio, 6
                ),
                "buy_direction_count": buy_count,
                "sell_direction_count": sell_count,
                "mixed_direction_count": mixed_count,
                "same_direction_or_unresolved_count": unresolved_count,
                "opposite_direction_count": opposite_count,
                "opposite_direction_ratio": round(opposite_ratio, 6),
                "dominant_instruction_fingerprint": (
                    None
                    if dominant_fingerprint is None
                    else {
                        "program_id": dominant_fingerprint[0],
                        "scope": dominant_fingerprint[1],
                        "pool_position": dominant_fingerprint[2],
                        "asset_position": dominant_fingerprint[3],
                        "counter_position": dominant_fingerprint[4],
                    }
                ),
                "dominant_instruction_fingerprint_count": (
                    dominant_fingerprint_count
                ),
                "dominant_instruction_fingerprint_ratio": round(
                    fingerprint_ratio, 6
                ),
                "stable_pair_candidate": stable,
                "canonical_vault_pair_proven": False,
                "exact_pool_leg_semantics_promoted": False,
            }
        )

    pairs.sort(
        key=lambda item: (
            item["stable_pair_candidate"],
            item["recognized_pool_instruction_transaction_ratio"],
            item["opposite_direction_ratio"],
            item["dominant_instruction_fingerprint_ratio"],
            item["transaction_occurrence_count"],
        ),
        reverse=True,
    )

    stable_pairs = [item for item in pairs if item["stable_pair_candidate"]]
    leading = pairs[0] if pairs else None
    second_coverage = (
        pairs[1]["recognized_pool_instruction_transaction_ratio"]
        if len(pairs) > 1
        else 0.0
    )
    leading_coverage = (
        leading["recognized_pool_instruction_transaction_ratio"]
        if leading
        else 0.0
    )
    dominance_margin = max(0.0, leading_coverage - second_coverage)
    uniquely_dominant = bool(
        leading
        and leading["stable_pair_candidate"]
        and dominance_margin >= min_dominance_margin
    )

    return {
        "service": "vault_pair_correlation",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "pair": pair,
        "asset_mint": asset_mint,
        "range_proven": scan.get("range_proven") is True,
        "integrity_verified": scan.get("integrity_verified") is True,
        "requested_window_signature_count": len(in_window),
        "successful_transaction_fetch_count": fetched_count,
        "recognized_amm_transaction_count": recognized_amm_tx_count,
        "recognized_pool_instruction_transaction_count": (
            recognized_pool_instruction_tx_count
        ),
        "failed_history_transaction_count": failed_history_tx_count,
        "thresholds": {
            "min_occurrences": min_occurrences,
            "min_coverage_ratio": min_coverage_ratio,
            "min_opposite_direction_ratio": min_opposite_direction_ratio,
            "min_fingerprint_ratio": min_fingerprint_ratio,
            "min_dominance_margin": min_dominance_margin,
        },
        "candidate_pairs": pairs,
        "summary": {
            "candidate_pair_count": len(pairs),
            "stable_pair_candidate_count": len(stable_pairs),
            "leading_pair_candidate": (
                None if leading is None else {
                    "asset_account": leading["asset_account"],
                    "counter_account": leading["counter_account"],
                    "counter_mint": leading["counter_mint"],
                    "shared_owner": leading["shared_owner"],
                    "coverage_ratio": leading[
                        "recognized_pool_instruction_transaction_ratio"
                    ],
                    "opposite_direction_ratio": leading[
                        "opposite_direction_ratio"
                    ],
                    "fingerprint_ratio": leading[
                        "dominant_instruction_fingerprint_ratio"
                    ],
                    "stable_pair_candidate": leading[
                        "stable_pair_candidate"
                    ],
                }
            ),
            "leading_pair_coverage_margin_over_second": round(
                dominance_margin, 6
            ),
            "uniquely_dominant_leading_pair_observed": uniquely_dominant,
            "vault_pair_correlation_observed": bool(stable_pairs),
            "canonical_vault_mapping_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "interpretation": (
                "Stable pair candidates are repeated same-owner asset/counter "
                "accounts that co-occur inside the selected pool's recognized "
                "AMM instruction, move in opposite directions, and retain a "
                "stable instruction-position fingerprint. These observations "
                "are not yet promoted to canonical vault truth."
            ),
        },
        "transactions": tx_records,
        "proof_scan": scan,
    }


__all__ = [
    "RECOGNIZED_AMM_PROGRAM_IDS",
    "VERSION",
    "collect_recognized_amm_instruction_occurrences",
    "correlate_pool_vault_pairs",
]
