"""CMIS v1.4.4 — fingerprint variant attribution.

v1.4.3 proved that BUY-like and SELL-like flows can have distinct stable AMM
instruction-position fingerprints. The AGI/rXNT live probe still showed one
SELL transaction outside the dominant SELL fingerprint.

v1.4.4 does not lower thresholds and does not declare alternate layouts valid.
It attributes every non-dominant fingerprint to exact transaction signatures
and records how the layout differs from the dominant fingerprint.

This is a read-only evidence phase. Canonical vault mapping and exact pool-leg
semantics remain unpromoted.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.directional_vault_fingerprints import (
    correlate_directional_vault_pairs,
)
from liquidity_scout.providers.x1.history_range import scan_address_history_range
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL
from liquidity_scout.providers.x1.transaction_semantics import (
    compute_token_deltas,
    fetch_transaction,
)
from liquidity_scout.providers.x1.vault_pair_correlation import (
    collect_recognized_amm_instruction_occurrences,
)

VERSION = "1.4.4"


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
    if asset_delta < 0 and counter_delta > 0:
        return "BUY"
    if asset_delta > 0 and counter_delta < 0:
        return "SELL"
    return "SAME_DIRECTION_OR_UNRESOLVED"


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


def _fingerprint_sort_key(fingerprint):
    return tuple("" if value is None else str(value) for value in fingerprint)


def _fingerprint_difference(dominant, variant):
    if dominant is None or variant is None:
        return None
    return {
        "program_id_changed": dominant[0] != variant[0],
        "scope_changed": dominant[1] != variant[1],
        "pool_position_changed": dominant[2] != variant[2],
        "asset_position_changed": dominant[3] != variant[3],
        "counter_position_changed": dominant[4] != variant[4],
    }


def _select_leading_pair(report: Mapping[str, Any]) -> dict[str, Any] | None:
    pairs = report.get("candidate_pairs")
    if not isinstance(pairs, Sequence) or isinstance(pairs, (str, bytes)):
        return None
    candidates = [item for item in pairs if isinstance(item, Mapping)]
    if not candidates:
        return None
    # The v1.4.3 report is already sorted by stability, coverage, opposite-flow
    # consistency, and occurrence count. Preserve that evidence ordering.
    return dict(candidates[0])


def _direction_attribution(
    direction: str,
    records: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    signatures = [
        signature
        for signature, evidence in records.items()
        if evidence.get("direction") == direction
    ]
    signature_set = set(signatures)

    fingerprint_signatures: dict[tuple, set[str]] = defaultdict(set)
    for signature in signatures:
        evidence = records[signature]
        for fingerprint in evidence.get("fingerprints") or set():
            fingerprint_signatures[fingerprint].add(signature)

    dominant = None
    dominant_signatures: set[str] = set()
    if fingerprint_signatures:
        dominant, dominant_signatures = max(
            fingerprint_signatures.items(),
            key=lambda item: (
                len(item[1]),
                _fingerprint_sort_key(item[0]),
            ),
        )

    dominant_count = len(dominant_signatures)
    count = len(signatures)
    dominant_ratio = dominant_count / count if count else 0.0
    outlier_signatures = sorted(signature_set - dominant_signatures)

    distributions = []
    for fingerprint, observed_signatures in sorted(
        fingerprint_signatures.items(),
        key=lambda item: (
            -len(item[1]),
            _fingerprint_sort_key(item[0]),
        ),
    ):
        distributions.append(
            {
                "fingerprint": _fingerprint_to_dict(fingerprint),
                "signature_count": len(observed_signatures),
                "signature_ratio": round(
                    len(observed_signatures) / count if count else 0.0,
                    6,
                ),
                "signatures": sorted(observed_signatures),
                "is_dominant": fingerprint == dominant,
                "difference_from_dominant": (
                    None
                    if fingerprint == dominant
                    else _fingerprint_difference(dominant, fingerprint)
                ),
            }
        )

    outliers = []
    for signature in outlier_signatures:
        evidence = records[signature]
        fingerprints = sorted(
            evidence.get("fingerprints") or set(),
            key=_fingerprint_sort_key,
        )
        contexts = evidence.get("contexts") or []
        outliers.append(
            {
                "signature": signature,
                "direction": direction,
                "classification": "unresolved_variant",
                "candidate_fingerprints": [
                    _fingerprint_to_dict(fp) for fp in fingerprints
                ],
                "differences_from_dominant": [
                    {
                        "fingerprint": _fingerprint_to_dict(fp),
                        "difference": _fingerprint_difference(
                            dominant, fp
                        ),
                    }
                    for fp in fingerprints
                ],
                "recognized_pool_instruction_occurrence_count": len(
                    contexts
                ),
                "instruction_contexts": contexts,
            }
        )

    non_dominant_distributions = [
        item for item in distributions if not item["is_dominant"]
    ]
    repeated_variant_observed = any(
        item["signature_count"] >= 2
        for item in non_dominant_distributions
    )

    return {
        "direction": direction,
        "transaction_count": count,
        "dominant_fingerprint": _fingerprint_to_dict(dominant),
        "dominant_fingerprint_count": dominant_count,
        "dominant_fingerprint_ratio": round(dominant_ratio, 6),
        "fingerprint_distribution": distributions,
        "outlier_signature_count": len(outlier_signatures),
        "outlier_signatures": outlier_signatures,
        "outliers": outliers,
        "repeated_non_dominant_variant_observed": repeated_variant_observed,
        "variant_legitimacy_proven": False,
    }


def attribute_pool_fingerprint_variants(
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
    baseline_correlator: Callable[..., Mapping[str, Any]] = (
        correlate_directional_vault_pairs
    ),
    scanner: Callable[..., Mapping[str, Any]] = scan_address_history_range,
    fetcher: Callable[..., Any] = _default_fetcher,
) -> dict[str, Any]:
    """Attribute non-dominant fingerprints for the leading v1.4.3 pair."""

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

    baseline = baseline_correlator(
        pool_address=pool_address,
        asset_mint=asset_mint,
        start_epoch=start_epoch,
        end_epoch=end_epoch,
        pair=pair,
        rpc_url=rpc_url,
        page_size=page_size,
        max_signatures=max_signatures,
        min_occurrences=min_occurrences,
        min_coverage_ratio=min_coverage_ratio,
        min_opposite_direction_ratio=min_opposite_direction_ratio,
        min_direction_occurrences=min_direction_occurrences,
        min_fingerprint_ratio=min_fingerprint_ratio,
        min_dominance_margin=min_dominance_margin,
    )
    baseline = dict(baseline) if isinstance(baseline, Mapping) else {}
    leading = _select_leading_pair(baseline)

    if leading is None:
        return {
            "service": "fingerprint_variant_attribution",
            "version": VERSION,
            "chain": "x1",
            "pool_address": pool_address,
            "pair": pair,
            "asset_mint": asset_mint,
            "status": "no_candidate_pair",
            "baseline": {
                "range_proven": baseline.get("range_proven") is True,
                "integrity_verified": (
                    baseline.get("integrity_verified") is True
                ),
                "candidate_pair_count": len(
                    baseline.get("candidate_pairs") or []
                ),
            },
            "leading_pair": None,
            "directions": [],
            "summary": {
                "variant_outlier_observed": False,
                "variant_legitimacy_proven": False,
                "canonical_vault_mapping_proven": False,
                "canonical_vault_mapping_promoted": False,
                "exact_pool_leg_semantics_promoted": False,
            },
            "proof_scan": None,
        }

    asset_account = _text(leading.get("asset_account"))
    counter_account = _text(leading.get("counter_account"))
    counter_mint = _text(leading.get("counter_mint"))
    shared_owner = _text(leading.get("shared_owner"))

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

    records: dict[str, dict[str, Any]] = {}
    fetched_count = 0
    failed_history_transaction_count = 0
    fetch_unavailable_count = 0

    for history in in_window:
        signature = history["signature"]
        if history.get("err") is not None:
            failed_history_transaction_count += 1
            continue

        try:
            tx = fetcher(signature, rpc_url=rpc_url)
        except Exception:
            fetch_unavailable_count += 1
            continue
        if not isinstance(tx, Mapping):
            fetch_unavailable_count += 1
            continue

        fetched_count += 1
        token_rows = compute_token_deltas(dict(tx))
        by_account = {row.account: row for row in token_rows}
        asset_row = by_account.get(asset_account)
        counter_row = by_account.get(counter_account)
        if asset_row is None or counter_row is None:
            continue
        if asset_row.mint != asset_mint:
            continue
        if counter_mint and counter_row.mint != counter_mint:
            continue
        if (
            not asset_row.owner
            or asset_row.owner != counter_row.owner
            or (shared_owner and asset_row.owner != shared_owner)
        ):
            continue

        direction = _pair_direction(
            asset_row.delta_ui,
            counter_row.delta_ui,
        )

        occurrences = collect_recognized_amm_instruction_occurrences(tx)
        pool_occurrences = [
            occurrence
            for occurrence in occurrences
            if pool_address in occurrence.get("accounts", [])
            and asset_account in occurrence.get("accounts", [])
            and counter_account in occurrence.get("accounts", [])
        ]
        if not pool_occurrences:
            continue

        fingerprints = set()
        contexts = []
        for occurrence in pool_occurrences:
            accounts = occurrence.get("accounts") or []
            positions = _position_map(accounts)
            for pool_position in positions.get(pool_address, []):
                for asset_position in positions.get(asset_account, []):
                    for counter_position in positions.get(
                        counter_account, []
                    ):
                        fingerprint = (
                            occurrence.get("program_id"),
                            occurrence.get("scope"),
                            pool_position,
                            asset_position,
                            counter_position,
                        )
                        fingerprints.add(fingerprint)
                        contexts.append(
                            {
                                "program_id": occurrence.get(
                                    "program_id"
                                ),
                                "scope": occurrence.get("scope"),
                                "group_index": occurrence.get(
                                    "group_index"
                                ),
                                "instruction_index": occurrence.get(
                                    "instruction_index"
                                ),
                                "account_count": len(accounts),
                                "pool_position": pool_position,
                                "asset_position": asset_position,
                                "counter_position": counter_position,
                            }
                        )

        records[signature] = {
            "direction": direction,
            "fingerprints": fingerprints,
            "contexts": contexts,
        }

    directions = [
        _direction_attribution("BUY", records),
        _direction_attribution("SELL", records),
    ]
    directions = [
        item for item in directions if item["transaction_count"] > 0
    ]

    outlier_count = sum(
        item["outlier_signature_count"] for item in directions
    )
    repeated_variant_observed = any(
        item["repeated_non_dominant_variant_observed"]
        for item in directions
    )

    status = (
        "variant_outliers_observed"
        if outlier_count > 0
        else "no_variant_outliers_observed"
    )

    return {
        "service": "fingerprint_variant_attribution",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "pair": pair,
        "asset_mint": asset_mint,
        "status": status,
        "baseline": {
            "range_proven": baseline.get("range_proven") is True,
            "integrity_verified": (
                baseline.get("integrity_verified") is True
            ),
            "candidate_pair_count": len(
                baseline.get("candidate_pairs") or []
            ),
            "stable_directional_pair_candidate_count": (
                (baseline.get("summary") or {}).get(
                    "stable_directional_pair_candidate_count"
                )
            ),
        },
        "leading_pair": {
            "asset_account": asset_account,
            "asset_mint": asset_mint,
            "counter_account": counter_account,
            "counter_mint": counter_mint,
            "shared_owner": shared_owner,
            "baseline_coverage_ratio": leading.get(
                "recognized_pool_instruction_transaction_ratio"
            ),
            "baseline_opposite_direction_ratio": leading.get(
                "opposite_direction_ratio"
            ),
            "baseline_stable_directional_pair_candidate": leading.get(
                "stable_directional_pair_candidate"
            ) is True,
        },
        "requested_window_signature_count": len(in_window),
        "successful_transaction_fetch_count": fetched_count,
        "failed_history_transaction_count": (
            failed_history_transaction_count
        ),
        "fetch_unavailable_count": fetch_unavailable_count,
        "directions": directions,
        "summary": {
            "attributed_pair_transaction_count": len(records),
            "variant_outlier_signature_count": outlier_count,
            "variant_outlier_observed": outlier_count > 0,
            "repeated_non_dominant_variant_observed": (
                repeated_variant_observed
            ),
            "variant_legitimacy_proven": False,
            "canonical_vault_mapping_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "interpretation": (
                "v1.4.4 attributes every signature that does not contain "
                "the direction's dominant fingerprint and records exact "
                "layout differences. Alternate fingerprints remain "
                "unresolved variants; recurrence alone does not prove "
                "legitimacy or canonical vault truth."
            ),
        },
        "proof_scan": scan,
    }


__all__ = [
    "VERSION",
    "attribute_pool_fingerprint_variants",
]
