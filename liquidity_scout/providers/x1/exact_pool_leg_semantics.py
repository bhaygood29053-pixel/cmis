"""CMIS v1.4.10 — exact canonical pool-leg semantics proof for X1.

v1.4.9 proves which token-account pair is canonically coupled to a selected
XDEX/XenDEX pool. v1.4.10 proves what those two canonical reserve legs mean in
actual swaps by re-reading recent X1 transactions and evaluating the canonical
vault deltas directly.

The semantic convention is deliberately pool-reserve based:

    BUY  => canonical asset reserve decreases; counter reserve increases.
    SELL => canonical asset reserve increases; counter reserve decreases.

The labels describe the trader-side action implied by the *proven canonical
reserve flows*. They are not inferred from token symbol order, pool balance
size, provider BUY/SELL labels, candidate rank, or an LLM.

Proof is fail-closed. A result is promoted to ``exact_pool_leg_semantics_proven``
only when:
- v1.4.9 has already proven exactly one canonical pool-vault mapping;
- one 24h X1 RPC history scan proves the full nested 1h/6h/24h evidence range;
- every successful history signature is fetchable;
- every recognized selected-pool AMM transaction is semantically resolved in
  each required window;
- the canonical asset and counter vault rows have expected mint/authority and
  opposite non-zero deltas;
- the selected pool plus both canonical vaults co-occur in one unambiguous
  recognized AMM structural fingerprint for each resolved transaction;
- BUY and SELL are each observed at least twice and keep one stable,
  direction-specific structural fingerprint.

This module is read-only. It never signs or submits a transaction. v1.4.10 may
prove exact pool-leg semantics, but mapping/semantic promotion for execution
remains disabled.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.canonical_pool_vault_coupling import (
    prove_canonical_pool_vault_coupling,
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

VERSION = "1.4.10"
REQUIRED_WINDOWS = (
    ("1h", 3600),
    ("6h", 21600),
    ("24h", 86400),
)
MIN_SIDE_OCCURRENCES = 2
MIN_SIDE_EVIDENCE_WINDOWS = 2
REQUIRED_SEMANTIC_RESOLUTION_RATIO = 1.0


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


def _sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return list(value)


def _family(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, Mapping):
        return None
    out = {
        "asset_account": _text(raw.get("asset_account")),
        "counter_account": _text(raw.get("counter_account")),
        "counter_mint": _text(raw.get("counter_mint")),
        "shared_owner": _text(raw.get("shared_owner")),
    }
    return out if all(out.values()) else None


def _family_key(raw: Any) -> tuple[str, str, str, str] | None:
    item = _family(raw)
    if item is None:
        return None
    return (
        item["asset_account"],
        item["counter_account"],
        item["counter_mint"],
        item["shared_owner"],
    )


def _default_fetcher(signature: str, *, rpc_url: str):
    return fetch_transaction(signature, rpc_url=rpc_url)


def _mapping_evidence(coupling: Mapping[str, Any]) -> dict[str, Any]:
    summary = coupling.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    candidate = _family(coupling.get("canonical_vault_mapping_candidate"))
    mapping_proven = bool(
        summary.get("canonical_vault_mapping_proven") is True
        and candidate is not None
    )

    matching = []
    candidate_key = _family_key(candidate)
    for raw in _sequence(coupling.get("families")):
        if not isinstance(raw, Mapping):
            continue
        if (
            raw.get("canonical_pool_vault_coupling_proven") is True
            and _family_key(raw.get("family")) == candidate_key
        ):
            matching.append(dict(raw))

    coupled_record = matching[0] if len(matching) == 1 else None
    structural = (
        coupled_record.get("structural_pool_anchor")
        if isinstance(coupled_record, Mapping)
        else None
    )
    structural = structural if isinstance(structural, Mapping) else {}
    stable_program_id = _text(structural.get("stable_program_id"))
    stable_pool_position = structural.get("stable_pool_position")
    if (
        isinstance(stable_pool_position, bool)
        or not isinstance(stable_pool_position, int)
        or stable_pool_position < 0
    ):
        stable_pool_position = None

    structural_anchor_proven = bool(
        structural.get("structural_pool_anchor_verified") is True
        and stable_program_id
        and stable_pool_position is not None
    )

    return {
        "canonical_vault_mapping_proven": mapping_proven,
        "canonical_vault_mapping": candidate,
        "coupled_family_record_count": len(matching),
        "stable_program_id": stable_program_id,
        "stable_pool_position": stable_pool_position,
        "structural_pool_anchor_verified": structural_anchor_proven,
    }


def _normalized_history_entries(
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
        block_time = _epoch(raw.get("block_time"))
        slot = raw.get("slot")
        if (
            not signature
            or signature in seen
            or block_time is None
            or isinstance(slot, bool)
            or not isinstance(slot, int)
            or slot < 0
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


def _position_map(accounts: Sequence[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for index, account in enumerate(accounts):
        out.setdefault(account, []).append(index)
    return out


def _fingerprint_dict(value: tuple[str, int, int, int] | None):
    if value is None:
        return None
    return {
        "program_id": value[0],
        "pool_position": value[1],
        "asset_position": value[2],
        "counter_position": value[3],
    }


def _matching_fingerprints(
    occurrences: Sequence[Mapping[str, Any]],
    *,
    pool_address: str,
    asset_account: str,
    counter_account: str,
    expected_program_id: str,
) -> set[tuple[str, int, int, int]]:
    fingerprints: set[tuple[str, int, int, int]] = set()
    for raw in occurrences:
        if not isinstance(raw, Mapping):
            continue
        program_id = _text(raw.get("program_id"))
        if program_id != expected_program_id:
            continue
        accounts = raw.get("accounts")
        if not isinstance(accounts, Sequence) or isinstance(accounts, (str, bytes)):
            continue
        accounts = [str(item) for item in accounts]
        if (
            pool_address not in accounts
            or asset_account not in accounts
            or counter_account not in accounts
        ):
            continue
        positions = _position_map(accounts)
        for pool_position in positions.get(pool_address, []):
            for asset_position in positions.get(asset_account, []):
                for counter_position in positions.get(counter_account, []):
                    if len({pool_position, asset_position, counter_position}) != 3:
                        continue
                    fingerprints.add(
                        (
                            program_id,
                            pool_position,
                            asset_position,
                            counter_position,
                        )
                    )
    return fingerprints


def _row_evidence(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "account": getattr(row, "account", None),
        "owner": getattr(row, "owner", None),
        "mint": getattr(row, "mint", None),
        "decimals": getattr(row, "decimals", None),
        "pre_amount_raw": getattr(row, "pre_amount_raw", None),
        "post_amount_raw": getattr(row, "post_amount_raw", None),
        "delta_raw": getattr(row, "delta_raw", None),
        "delta_ui": str(getattr(row, "delta_ui", "")),
    }


def _evaluate_pool_transaction(
    *,
    signature: str,
    slot: int,
    block_time: float,
    tx: Mapping[str, Any],
    pool_address: str,
    asset_mint: str,
    mapping: Mapping[str, str],
    expected_program_id: str,
    expected_pool_position: int,
    occurrence_provider: Callable[[Mapping[str, Any]], Sequence[Mapping[str, Any]]],
    delta_provider: Callable[[dict[str, Any]], Sequence[Any]],
) -> dict[str, Any]:
    occurrences = list(occurrence_provider(tx) or [])
    pool_occurrences = [
        raw
        for raw in occurrences
        if isinstance(raw, Mapping)
        and pool_address in _sequence(raw.get("accounts"))
    ]
    if not pool_occurrences:
        return {
            "signature": signature,
            "slot": slot,
            "block_time": block_time,
            "recognized_pool_transaction": False,
            "semantic_resolved": False,
            "side": None,
            "rejection_reasons": [],
        }

    reasons = []
    token_rows = list(delta_provider(dict(tx)) or [])
    asset_rows = [
        row for row in token_rows
        if getattr(row, "account", None) == mapping["asset_account"]
    ]
    counter_rows = [
        row for row in token_rows
        if getattr(row, "account", None) == mapping["counter_account"]
    ]

    asset_row = asset_rows[0] if len(asset_rows) == 1 else None
    counter_row = counter_rows[0] if len(counter_rows) == 1 else None
    if len(asset_rows) != 1:
        reasons.append("canonical_asset_delta_row_missing_or_ambiguous")
    if len(counter_rows) != 1:
        reasons.append("canonical_counter_delta_row_missing_or_ambiguous")

    if asset_row is not None:
        if _text(getattr(asset_row, "mint", None)) != asset_mint:
            reasons.append("canonical_asset_mint_mismatch")
        if _text(getattr(asset_row, "owner", None)) != mapping["shared_owner"]:
            reasons.append("canonical_asset_authority_mismatch")
    if counter_row is not None:
        if _text(getattr(counter_row, "mint", None)) != mapping["counter_mint"]:
            reasons.append("canonical_counter_mint_mismatch")
        if _text(getattr(counter_row, "owner", None)) != mapping["shared_owner"]:
            reasons.append("canonical_counter_authority_mismatch")

    side = None
    reserve_flow = None
    if asset_row is not None and counter_row is not None:
        asset_delta_raw = getattr(asset_row, "delta_raw", 0)
        counter_delta_raw = getattr(counter_row, "delta_raw", 0)
        if asset_delta_raw < 0 and counter_delta_raw > 0:
            side = "BUY"
            reserve_flow = {
                "asset_reserve": "OUT",
                "counter_reserve": "IN",
                "trader_side": "BUY",
            }
        elif asset_delta_raw > 0 and counter_delta_raw < 0:
            side = "SELL"
            reserve_flow = {
                "asset_reserve": "IN",
                "counter_reserve": "OUT",
                "trader_side": "SELL",
            }
        else:
            reasons.append("canonical_reserve_deltas_not_opposite_nonzero")

    fingerprints = _matching_fingerprints(
        pool_occurrences,
        pool_address=pool_address,
        asset_account=mapping["asset_account"],
        counter_account=mapping["counter_account"],
        expected_program_id=expected_program_id,
    )
    if not fingerprints:
        reasons.append("canonical_vaults_not_coupled_in_expected_program_instruction")
    elif len(fingerprints) > 1:
        reasons.append("canonical_instruction_fingerprint_ambiguous")

    fingerprint = next(iter(fingerprints)) if len(fingerprints) == 1 else None
    if fingerprint is not None and fingerprint[1] != expected_pool_position:
        reasons.append("canonical_pool_position_mismatch")

    reasons = list(dict.fromkeys(reasons))
    resolved = bool(side and fingerprint is not None and not reasons)

    return {
        "signature": signature,
        "slot": slot,
        "block_time": block_time,
        "recognized_pool_transaction": True,
        "recognized_pool_instruction_count": len(pool_occurrences),
        "semantic_resolved": resolved,
        "side": side if resolved else None,
        "reserve_flow": reserve_flow if resolved else None,
        "structural_fingerprint": _fingerprint_dict(fingerprint),
        "asset_vault_delta": _row_evidence(asset_row),
        "counter_vault_delta": _row_evidence(counter_row),
        "rejection_reasons": reasons,
    }


def _window_summary(
    *,
    label: str,
    duration_seconds: int,
    end_epoch: float,
    history_entries: Sequence[Mapping[str, Any]],
    transaction_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    start_epoch = end_epoch - duration_seconds
    signatures = {
        _text(raw.get("signature"))
        for raw in history_entries
        if isinstance(raw, Mapping)
        and _epoch(raw.get("block_time")) is not None
        and start_epoch <= float(raw["block_time"]) <= end_epoch
        and _text(raw.get("signature"))
    }
    successful_signatures = {
        _text(raw.get("signature"))
        for raw in history_entries
        if isinstance(raw, Mapping)
        and _text(raw.get("signature")) in signatures
        and raw.get("err") is None
    }
    records = [
        raw
        for raw in transaction_records
        if isinstance(raw, Mapping)
        and _text(raw.get("signature")) in successful_signatures
    ]
    fetch_failures = [raw for raw in records if raw.get("fetched") is False]
    recognized = [
        raw for raw in records
        if raw.get("recognized_pool_transaction") is True
    ]
    resolved = [raw for raw in recognized if raw.get("semantic_resolved") is True]
    unresolved = [raw for raw in recognized if raw.get("semantic_resolved") is not True]
    ratio = len(resolved) / len(recognized) if recognized else 0.0
    complete = bool(
        successful_signatures
        and not fetch_failures
        and recognized
        and ratio >= REQUIRED_SEMANTIC_RESOLUTION_RATIO
        and not unresolved
    )

    return {
        "label": label,
        "duration_seconds": duration_seconds,
        "start_epoch": start_epoch,
        "end_epoch": end_epoch,
        "history_signature_count": len(signatures),
        "successful_history_signature_count": len(successful_signatures),
        "transaction_fetch_failure_count": len(fetch_failures),
        "recognized_pool_transaction_count": len(recognized),
        "semantically_resolved_pool_transaction_count": len(resolved),
        "unresolved_pool_transaction_count": len(unresolved),
        "buy_transaction_count": sum(1 for raw in resolved if raw.get("side") == "BUY"),
        "sell_transaction_count": sum(1 for raw in resolved if raw.get("side") == "SELL"),
        "semantic_resolution_ratio": round(ratio, 6),
        "required_semantic_resolution_ratio": REQUIRED_SEMANTIC_RESOLUTION_RATIO,
        "all_recognized_pool_transactions_semantically_resolved": complete,
    }


def _direction_summary(
    side: str,
    *,
    transaction_records: Sequence[Mapping[str, Any]],
    window_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    records = [
        raw
        for raw in transaction_records
        if isinstance(raw, Mapping)
        and raw.get("semantic_resolved") is True
        and raw.get("side") == side
    ]
    fingerprints = set()
    for raw in records:
        fingerprint = raw.get("structural_fingerprint")
        if not isinstance(fingerprint, Mapping):
            continue
        key = (
            _text(fingerprint.get("program_id")),
            fingerprint.get("pool_position"),
            fingerprint.get("asset_position"),
            fingerprint.get("counter_position"),
        )
        if all(value is not None for value in key):
            fingerprints.add(key)

    evidence_windows = [
        raw.get("label")
        for raw in window_summaries
        if isinstance(raw, Mapping)
        and int(raw.get("buy_transaction_count") or 0) > 0
        if side == "BUY"
    ] if side == "BUY" else [
        raw.get("label")
        for raw in window_summaries
        if isinstance(raw, Mapping)
        and int(raw.get("sell_transaction_count") or 0) > 0
    ]

    fingerprint_stable = len(fingerprints) == 1
    semantics_proven = bool(
        len(records) >= MIN_SIDE_OCCURRENCES
        and len(evidence_windows) >= MIN_SIDE_EVIDENCE_WINDOWS
        and fingerprint_stable
    )
    stable = next(iter(fingerprints)) if fingerprint_stable else None

    return {
        "side": side,
        "semantic_definition": (
            "canonical asset reserve OUT + canonical counter reserve IN"
            if side == "BUY"
            else "canonical asset reserve IN + canonical counter reserve OUT"
        ),
        "transaction_count": len(records),
        "minimum_transaction_count": MIN_SIDE_OCCURRENCES,
        "evidence_windows": evidence_windows,
        "evidence_window_count": len(evidence_windows),
        "minimum_evidence_windows": MIN_SIDE_EVIDENCE_WINDOWS,
        "structural_fingerprint_count": len(fingerprints),
        "structural_fingerprint_stable": fingerprint_stable,
        "stable_structural_fingerprint": _fingerprint_dict(stable),
        "side_semantics_proven": semantics_proven,
    }


def _unavailable_result(
    *,
    pool_address: str,
    asset_mint: str,
    pair: str | None,
    status: str,
    stage: str,
    error: str,
    coupling: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "service": "exact_pool_leg_semantics",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "pair": pair,
        "asset_mint": asset_mint,
        "status": status,
        "canonical_vault_mapping": None,
        "windows": [],
        "directions": [],
        "transactions": [],
        "summary": {
            "canonical_vault_mapping_proven": False,
            "exact_pool_leg_semantics_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
        },
        "coupling": dict(coupling) if isinstance(coupling, Mapping) else None,
        "history_scan": None,
        "errors": [{"stage": stage, "error": error}],
    }


def prove_exact_pool_leg_semantics(
    *,
    pool_address: str,
    asset_mint: str,
    end_epoch: float,
    pair: str | None = None,
    rpc_url: str | None = None,
    page_size: int = 1000,
    max_signatures: int = 5000,
    coupling_provider: Callable[..., Mapping[str, Any]] = (
        prove_canonical_pool_vault_coupling
    ),
    scanner: Callable[..., Mapping[str, Any]] = scan_address_history_range,
    fetcher: Callable[..., Any] = _default_fetcher,
    occurrence_provider: Callable[[Mapping[str, Any]], Sequence[Mapping[str, Any]]] = (
        collect_recognized_amm_instruction_occurrences
    ),
    delta_provider: Callable[[dict[str, Any]], Sequence[Any]] = compute_token_deltas,
) -> dict[str, Any]:
    """Prove exact BUY/SELL semantics from canonical reserve flows."""

    pool_address = _text(pool_address)
    asset_mint = _text(asset_mint)
    if not pool_address:
        raise ValueError("pool_address is required")
    if not asset_mint:
        raise ValueError("asset_mint is required")
    end_epoch = _epoch(end_epoch)
    if end_epoch is None:
        raise ValueError("end_epoch must be a non-negative numeric time")

    coupling_kwargs = {
        "pool_address": pool_address,
        "asset_mint": asset_mint,
        "end_epoch": end_epoch,
        "pair": pair,
        "page_size": page_size,
        "max_signatures": max_signatures,
    }
    if rpc_url is not None:
        coupling_kwargs["rpc_url"] = rpc_url

    try:
        raw_coupling = coupling_provider(**coupling_kwargs)
    except Exception as exc:
        return _unavailable_result(
            pool_address=pool_address,
            asset_mint=asset_mint,
            pair=pair,
            status="canonical_vault_mapping_unavailable",
            stage="canonical_pool_vault_coupling",
            error=f"{type(exc).__name__}: {exc}",
        )

    coupling = dict(raw_coupling) if isinstance(raw_coupling, Mapping) else {}
    mapping_evidence = _mapping_evidence(coupling)
    mapping = mapping_evidence["canonical_vault_mapping"]
    if (
        not mapping_evidence["canonical_vault_mapping_proven"]
        or not mapping_evidence["structural_pool_anchor_verified"]
        or mapping_evidence["coupled_family_record_count"] != 1
        or mapping is None
    ):
        result = _unavailable_result(
            pool_address=pool_address,
            asset_mint=asset_mint,
            pair=pair,
            status="canonical_vault_mapping_unproven",
            stage="canonical_pool_vault_coupling",
            error="v1.4.9 did not expose exactly one proven mapping with a stable pool structural anchor",
            coupling=coupling,
        )
        result["summary"]["canonical_vault_mapping_proven"] = bool(
            mapping_evidence["canonical_vault_mapping_proven"]
        )
        return result

    rpc = rpc_url or DEFAULT_X1_RPC_URL
    scan_start = end_epoch - REQUIRED_WINDOWS[-1][1]
    try:
        raw_scan = scanner(
            pool_address,
            start_epoch=scan_start,
            end_epoch=end_epoch,
            rpc_url=rpc,
            page_size=page_size,
            max_signatures=max_signatures,
        )
    except Exception as exc:
        return _unavailable_result(
            pool_address=pool_address,
            asset_mint=asset_mint,
            pair=pair,
            status="history_scan_unavailable",
            stage="history_scan",
            error=f"{type(exc).__name__}: {exc}",
            coupling=coupling,
        )

    scan = dict(raw_scan) if isinstance(raw_scan, Mapping) else {}
    raw_entries = scan.get("entries")
    entries = _normalized_history_entries(
        _sequence(raw_entries),
        start_epoch=scan_start,
        end_epoch=end_epoch,
    )

    transaction_records = []
    errors = []
    for history in entries:
        signature = history["signature"]
        if history.get("err") is not None:
            transaction_records.append(
                {
                    "signature": signature,
                    "slot": history["slot"],
                    "block_time": history["block_time"],
                    "chain_succeeded": False,
                    "fetched": False,
                    "recognized_pool_transaction": False,
                    "semantic_resolved": False,
                    "side": None,
                    "rejection_reasons": ["history_transaction_failed_on_chain"],
                }
            )
            continue

        try:
            tx = fetcher(signature, rpc_url=rpc)
        except Exception as exc:
            errors.append(
                {
                    "stage": "transaction_fetch",
                    "signature": signature,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            transaction_records.append(
                {
                    "signature": signature,
                    "slot": history["slot"],
                    "block_time": history["block_time"],
                    "chain_succeeded": True,
                    "fetched": False,
                    "recognized_pool_transaction": None,
                    "semantic_resolved": False,
                    "side": None,
                    "rejection_reasons": ["transaction_fetch_unavailable"],
                }
            )
            continue

        if not isinstance(tx, Mapping):
            errors.append(
                {
                    "stage": "transaction_fetch",
                    "signature": signature,
                    "error": "getTransaction returned no mapping transaction",
                }
            )
            transaction_records.append(
                {
                    "signature": signature,
                    "slot": history["slot"],
                    "block_time": history["block_time"],
                    "chain_succeeded": True,
                    "fetched": False,
                    "recognized_pool_transaction": None,
                    "semantic_resolved": False,
                    "side": None,
                    "rejection_reasons": ["transaction_fetch_unavailable"],
                }
            )
            continue

        meta = tx.get("meta")
        if isinstance(meta, Mapping) and meta.get("err") is not None:
            transaction_records.append(
                {
                    "signature": signature,
                    "slot": history["slot"],
                    "block_time": history["block_time"],
                    "chain_succeeded": False,
                    "fetched": True,
                    "recognized_pool_transaction": False,
                    "semantic_resolved": False,
                    "side": None,
                    "rejection_reasons": ["fetched_transaction_failed_on_chain"],
                }
            )
            continue

        record = _evaluate_pool_transaction(
            signature=signature,
            slot=history["slot"],
            block_time=history["block_time"],
            tx=tx,
            pool_address=pool_address,
            asset_mint=asset_mint,
            mapping=mapping,
            expected_program_id=mapping_evidence["stable_program_id"],
            expected_pool_position=mapping_evidence["stable_pool_position"],
            occurrence_provider=occurrence_provider,
            delta_provider=delta_provider,
        )
        record["chain_succeeded"] = True
        record["fetched"] = True
        transaction_records.append(record)

    windows = [
        _window_summary(
            label=label,
            duration_seconds=duration,
            end_epoch=end_epoch,
            history_entries=entries,
            transaction_records=transaction_records,
        )
        for label, duration in REQUIRED_WINDOWS
    ]
    directions = [
        _direction_summary(
            side,
            transaction_records=transaction_records,
            window_summaries=windows,
        )
        for side in ("BUY", "SELL")
    ]

    range_proven = bool(
        scan.get("range_proven") is True
        and scan.get("integrity_verified") is True
    )
    successful_entries = [raw for raw in entries if raw.get("err") is None]
    fetch_failures = [
        raw
        for raw in transaction_records
        if raw.get("chain_succeeded") is True and raw.get("fetched") is False
    ]
    all_fetched = bool(successful_entries and not fetch_failures)
    all_windows_complete = bool(
        len(windows) == len(REQUIRED_WINDOWS)
        and all(
            raw.get("all_recognized_pool_transactions_semantically_resolved") is True
            for raw in windows
        )
    )
    both_sides_proven = bool(
        len(directions) == 2
        and all(raw.get("side_semantics_proven") is True for raw in directions)
    )

    buy = directions[0]
    sell = directions[1]
    buy_fp = buy.get("stable_structural_fingerprint")
    sell_fp = sell.get("stable_structural_fingerprint")
    buy_fp = buy_fp if isinstance(buy_fp, Mapping) else {}
    sell_fp = sell_fp if isinstance(sell_fp, Mapping) else {}
    cross_direction_anchor_consistent = bool(
        both_sides_proven
        and buy_fp.get("program_id") == mapping_evidence["stable_program_id"]
        and sell_fp.get("program_id") == mapping_evidence["stable_program_id"]
        and buy_fp.get("pool_position") == mapping_evidence["stable_pool_position"]
        and sell_fp.get("pool_position") == mapping_evidence["stable_pool_position"]
    )

    exact_proven = bool(
        range_proven
        and all_fetched
        and all_windows_complete
        and both_sides_proven
        and cross_direction_anchor_consistent
    )

    if not range_proven:
        status = "history_range_unproven"
    elif not all_fetched:
        status = "transaction_evidence_incomplete"
    elif not all_windows_complete:
        status = "pool_leg_semantics_incomplete_or_conflicting"
    elif not both_sides_proven:
        status = "bidirectional_semantics_unproven"
    elif not cross_direction_anchor_consistent:
        status = "directional_structural_anchor_conflict"
    elif exact_proven:
        status = "exact_pool_leg_semantics_proven"
    else:
        status = "exact_pool_leg_semantics_unproven"

    scan_summary = {
        key: value
        for key, value in scan.items()
        if key != "entries"
    }

    return {
        "service": "exact_pool_leg_semantics",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "pair": pair,
        "asset_mint": asset_mint,
        "status": status,
        "canonical_vault_mapping": mapping,
        "structural_anchor": {
            "program_id": mapping_evidence["stable_program_id"],
            "pool_position": mapping_evidence["stable_pool_position"],
        },
        "thresholds": {
            "required_windows": [label for label, _ in REQUIRED_WINDOWS],
            "minimum_side_occurrences": MIN_SIDE_OCCURRENCES,
            "minimum_side_evidence_windows": MIN_SIDE_EVIDENCE_WINDOWS,
            "required_semantic_resolution_ratio": REQUIRED_SEMANTIC_RESOLUTION_RATIO,
        },
        "windows": windows,
        "directions": directions,
        "transactions": transaction_records,
        "summary": {
            "canonical_vault_mapping_proven": True,
            "history_range_proven": range_proven,
            "all_successful_history_transactions_fetched": all_fetched,
            "all_required_windows_semantically_complete": all_windows_complete,
            "buy_semantics_proven": buy.get("side_semantics_proven") is True,
            "sell_semantics_proven": sell.get("side_semantics_proven") is True,
            "cross_direction_structural_anchor_consistent": (
                cross_direction_anchor_consistent
            ),
            "exact_pool_leg_semantics_proven": exact_proven,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "interpretation": (
                "v1.4.10 proves trader-side BUY only from canonical reserve "
                "asset OUT + counter IN, and SELL only from canonical reserve "
                "asset IN + counter OUT. Every recognized selected-pool AMM "
                "transaction in each nested 1h/6h/24h window must resolve, "
                "both directions must have repeated evidence with one stable "
                "direction-specific instruction fingerprint, and both "
                "fingerprints must preserve the v1.4.9 program/pool anchor. "
                "Token order, balances, provider side labels, ranking and LLM "
                "inference are not proof inputs. Promotion remains disabled."
            ),
        },
        "coupling": coupling,
        "history_scan": scan_summary,
        "errors": errors,
    }


__all__ = [
    "MIN_SIDE_EVIDENCE_WINDOWS",
    "MIN_SIDE_OCCURRENCES",
    "REQUIRED_SEMANTIC_RESOLUTION_RATIO",
    "REQUIRED_WINDOWS",
    "VERSION",
    "prove_exact_pool_leg_semantics",
]
