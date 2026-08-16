"""CMIS v1.4.3 — direction-aware vault-pair fingerprints.

v1.4.2 showed that a real candidate vault pair can use different XDEX account
positions for BUY-like and SELL-like flows. Requiring one global instruction
fingerprint therefore creates a false negative.

v1.4.3 preserves the strict evidence model but evaluates instruction-position
stability separately for BUY and SELL:

    candidate pair
        -> same owner
        -> same selected pool AMM instruction
        -> opposite asset/counter flow
        -> BUY fingerprint stability
        -> SELL fingerprint stability

No canonical vault mapping is promoted here. This is a read-only evidence phase.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.history_range import scan_address_history_range
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL
from liquidity_scout.providers.x1.transaction_semantics import (
    compute_token_deltas,
    fetch_transaction,
)
from liquidity_scout.providers.x1.vault_pair_correlation import (
    collect_recognized_amm_instruction_occurrences,
)

VERSION = "1.4.3"


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
    # Trader-side direction inferred from the candidate pool-vault signs.
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


def _fingerprint_to_dict(fingerprint):
    if fingerprint is None:
        return None
    return {
        "program_id": fingerprint[0],
        "scope": fingerprint[1],
        "pool_position": fingerprint[2],
        "asset_position": fingerprint[3],
        "counter_position": fingerprint[4],
    }


def _direction_summary(
    direction: str,
    records: Mapping[str, Mapping[str, Any]],
    *,
    min_direction_occurrences: int,
    min_fingerprint_ratio: float,
) -> dict[str, Any]:
    """Summarize dominant instruction fingerprint for one direction."""

    fingerprint_signatures: dict[tuple, set[str]] = defaultdict(set)
    direction_signatures = []

    for signature, evidence in records.items():
        if evidence.get("direction") != direction:
            continue
        direction_signatures.append(signature)
        for fingerprint in evidence.get("fingerprints") or set():
            fingerprint_signatures[fingerprint].add(signature)

    count = len(direction_signatures)
    dominant = None
    dominant_count = 0
    if fingerprint_signatures:
        dominant, signatures = max(
            fingerprint_signatures.items(),
            key=lambda item: (len(item[1]), item[0]),
        )
        dominant_count = len(signatures)

    ratio = dominant_count / count if count else 0.0
    sufficient_sample = count >= min_direction_occurrences
    stable = bool(
        sufficient_sample
        and dominant is not None
        and ratio >= min_fingerprint_ratio
    )

    return {
        "direction": direction,
        "transaction_count": count,
        "min_direction_occurrences": min_direction_occurrences,
        "sufficient_sample": sufficient_sample,
        "dominant_instruction_fingerprint": _fingerprint_to_dict(dominant),
        "dominant_instruction_fingerprint_count": dominant_count,
        "dominant_instruction_fingerprint_ratio": round(ratio, 6),
        "fingerprint_stable": stable,
    }


def correlate_directional_vault_pairs(
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
    min_direction_occurrences: int = 2,
    min_fingerprint_ratio: float = 0.95,
    min_dominance_margin: float = 0.10,
    scanner: Callable[..., Mapping[str, Any]] = scan_address_history_range,
    fetcher: Callable[..., Any] = _default_fetcher,
) -> dict[str, Any]:
    """Evaluate same-owner vault-pair candidates with per-direction fingerprints."""

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

    for name, value in (
        ("min_occurrences", min_occurrences),
        ("min_direction_occurrences", min_direction_occurrences),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be an integer >= 1")

    for name, value in (
        ("min_coverage_ratio", min_coverage_ratio),
        ("min_opposite_direction_ratio", min_opposite_direction_ratio),
        ("min_fingerprint_ratio", min_fingerprint_ratio),
        ("min_dominance_margin", min_dominance_margin),
    ):
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
            or value > 1
        ):
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

    pair_tx_evidence: dict[tuple, dict[str, dict[str, Any]]] = defaultdict(dict)
    fetched_count = 0
    recognized_amm_tx_count = 0
    recognized_pool_instruction_tx_count = 0
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
            if pool_address in item.get("accounts", [])
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
            accounts = occurrence.get("accounts") or []
            positions = _position_map(accounts)
            pool_positions = positions.get(pool_address) or []
            if not pool_positions:
                continue

            asset_rows = {
                address: by_account[address]
                for address in accounts
                if address in by_account
                and by_account[address].mint == asset_mint
            }
            counter_rows = {
                address: by_account[address]
                for address in accounts
                if address in by_account
                and by_account[address].mint != asset_mint
            }

            for asset_row in asset_rows.values():
                for counter_row in counter_rows.values():
                    if (
                        not asset_row.owner
                        or asset_row.owner != counter_row.owner
                        or asset_row.account == counter_row.account
                    ):
                        continue

                    direction = _pair_direction(
                        asset_row.delta_ui,
                        counter_row.delta_ui,
                    )
                    key = _pair_key(asset_row, counter_row)

                    fingerprints = set()
                    for asset_position in positions.get(asset_row.account, []):
                        for counter_position in positions.get(
                            counter_row.account, []
                        ):
                            for pool_position in pool_positions:
                                fingerprints.add(
                                    (
                                        occurrence.get("program_id"),
                                        occurrence.get("scope"),
                                        pool_position,
                                        asset_position,
                                        counter_position,
                                    )
                                )

                    existing = pair_tx_evidence[key].get(signature)
                    if existing is None:
                        pair_tx_evidence[key][signature] = {
                            "direction": direction,
                            "fingerprints": set(fingerprints),
                        }
                    else:
                        # Multiple pool instructions in the same tx must agree
                        # on direction. Conflicting interpretations are not
                        # promoted to BUY or SELL evidence.
                        if existing["direction"] != direction:
                            existing["direction"] = (
                                "SAME_DIRECTION_OR_UNRESOLVED"
                            )
                        existing["fingerprints"].update(fingerprints)

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
    for key, records in pair_tx_evidence.items():
        (
            asset_account,
            pair_asset_mint,
            counter_account,
            counter_mint,
            owner,
        ) = key

        buy_count = sum(
            1 for item in records.values()
            if item.get("direction") == "BUY"
        )
        sell_count = sum(
            1 for item in records.values()
            if item.get("direction") == "SELL"
        )
        unresolved_count = len(records) - buy_count - sell_count
        occurrence_count = len(records)
        opposite_count = buy_count + sell_count
        coverage_ratio = occurrence_count / denominator
        opposite_ratio = (
            opposite_count / occurrence_count
            if occurrence_count
            else 0.0
        )

        buy_summary = _direction_summary(
            "BUY",
            records,
            min_direction_occurrences=min_direction_occurrences,
            min_fingerprint_ratio=min_fingerprint_ratio,
        )
        sell_summary = _direction_summary(
            "SELL",
            records,
            min_direction_occurrences=min_direction_occurrences,
            min_fingerprint_ratio=min_fingerprint_ratio,
        )

        observed_direction_summaries = [
            summary
            for summary in (buy_summary, sell_summary)
            if summary["transaction_count"] > 0
        ]
        direction_samples_sufficient = bool(
            observed_direction_summaries
            and all(
                summary["sufficient_sample"]
                for summary in observed_direction_summaries
            )
        )
        directional_fingerprints_stable = bool(
            observed_direction_summaries
            and all(
                summary["fingerprint_stable"]
                for summary in observed_direction_summaries
            )
        )

        stable = bool(
            occurrence_count >= min_occurrences
            and coverage_ratio >= min_coverage_ratio
            and opposite_ratio >= min_opposite_direction_ratio
            and direction_samples_sufficient
            and directional_fingerprints_stable
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
                "same_direction_or_unresolved_count": unresolved_count,
                "opposite_direction_count": opposite_count,
                "opposite_direction_ratio": round(opposite_ratio, 6),
                "buy_fingerprint": buy_summary,
                "sell_fingerprint": sell_summary,
                "direction_samples_sufficient": (
                    direction_samples_sufficient
                ),
                "directional_fingerprints_stable": (
                    directional_fingerprints_stable
                ),
                "stable_directional_pair_candidate": stable,
                "canonical_vault_pair_proven": False,
                "canonical_vault_mapping_promoted": False,
                "exact_pool_leg_semantics_promoted": False,
            }
        )

    pairs.sort(
        key=lambda item: (
            item["stable_directional_pair_candidate"],
            item["recognized_pool_instruction_transaction_ratio"],
            item["opposite_direction_ratio"],
            item["transaction_occurrence_count"],
        ),
        reverse=True,
    )

    stable_pairs = [
        item for item in pairs
        if item["stable_directional_pair_candidate"]
    ]
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
        and leading["stable_directional_pair_candidate"]
        and dominance_margin >= min_dominance_margin
    )

    return {
        "service": "directional_vault_pair_correlation",
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
            "min_direction_occurrences": min_direction_occurrences,
            "min_fingerprint_ratio": min_fingerprint_ratio,
            "min_dominance_margin": min_dominance_margin,
        },
        "candidate_pairs": pairs,
        "summary": {
            "candidate_pair_count": len(pairs),
            "stable_directional_pair_candidate_count": len(stable_pairs),
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
                    "buy_fingerprint_stable": leading[
                        "buy_fingerprint"
                    ]["fingerprint_stable"],
                    "sell_fingerprint_stable": leading[
                        "sell_fingerprint"
                    ]["fingerprint_stable"],
                    "stable_directional_pair_candidate": leading[
                        "stable_directional_pair_candidate"
                    ],
                }
            ),
            "leading_pair_coverage_margin_over_second": round(
                dominance_margin, 6
            ),
            "uniquely_dominant_leading_pair_observed": uniquely_dominant,
            "directional_vault_pair_correlation_observed": bool(
                stable_pairs
            ),
            "canonical_vault_mapping_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "interpretation": (
                "v1.4.3 evaluates BUY and SELL instruction-position "
                "fingerprints independently. A stable directional pair still "
                "requires same-owner co-occurrence inside the selected pool's "
                "recognized AMM instruction, high opposite-flow consistency, "
                "adequate directional samples, and stable fingerprints for "
                "every observed direction. Canonical promotion remains disabled."
            ),
        },
        "transactions": tx_records,
        "proof_scan": scan,
    }


__all__ = [
    "VERSION",
    "correlate_directional_vault_pairs",
]
