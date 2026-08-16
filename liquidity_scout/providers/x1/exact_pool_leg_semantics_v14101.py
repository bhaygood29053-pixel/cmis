"""CMIS v1.4.10.1 — exact pool-leg semantics with AMM operation classification.

v1.4.10 proved BUY/SELL from canonical reserve deltas but deliberately failed
closed when a recognized pool transaction was not a normal swap. v1.4.10.1
classifies deterministically proven liquidity operations before evaluating the
swap-semantic denominator.

Proven ADD_LIQUIDITY and REMOVE_LIQUIDITY transactions are accounted for but do
not dilute swap semantics. UNKNOWN recognized pool operations still fail closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.amm_operation_classification import (
    ADD_LIQUIDITY,
    REMOVE_LIQUIDITY,
    SWAP_BUY,
    SWAP_SELL,
    UNKNOWN,
    classify_liquidity_operation,
)
from liquidity_scout.providers.x1.canonical_pool_vault_coupling import (
    prove_canonical_pool_vault_coupling,
)
from liquidity_scout.providers.x1.exact_pool_leg_semantics import (
    prove_exact_pool_leg_semantics as prove_v1_4_10,
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

VERSION = "1.4.10.1"


def _default_fetcher(signature: str, *, rpc_url: str):
    return fetch_transaction(signature, rpc_url=rpc_url)


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return list(value)


def _window_operation_summary(
    base_window: Mapping[str, Any],
    transaction_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    out = dict(base_window)
    start_epoch = base_window.get("start_epoch")
    end_epoch = base_window.get("end_epoch")
    if not isinstance(start_epoch, (int, float)) or isinstance(start_epoch, bool):
        start_epoch = None
    if not isinstance(end_epoch, (int, float)) or isinstance(end_epoch, bool):
        end_epoch = None

    records = []
    for raw in transaction_records:
        if not isinstance(raw, Mapping):
            continue
        block_time = raw.get("block_time")
        if not isinstance(block_time, (int, float)) or isinstance(block_time, bool):
            continue
        if start_epoch is not None and block_time < start_epoch:
            continue
        if end_epoch is not None and block_time > end_epoch:
            continue
        records.append(raw)

    recognized = [raw for raw in records if raw.get("recognized_pool_transaction") is True]
    classified = [raw for raw in recognized if raw.get("operation_classified") is True]
    swaps = [raw for raw in recognized if raw.get("proven_swap") is True]
    non_swaps = [raw for raw in recognized if raw.get("proven_non_swap") is True]
    unknown = [raw for raw in recognized if raw.get("operation_class") == UNKNOWN]
    resolved_swaps = [raw for raw in swaps if raw.get("semantic_resolved") is True]

    operation_ratio = len(classified) / len(recognized) if recognized else 0.0
    swap_ratio = len(resolved_swaps) / len(swaps) if swaps else 0.0
    all_classified = bool(recognized and not unknown and len(classified) == len(recognized))
    all_swaps_resolved = bool(swaps and len(resolved_swaps) == len(swaps))
    complete = bool(all_classified and all_swaps_resolved)

    out.update(
        {
            "recognized_pool_transaction_count": len(recognized),
            "operation_classified_pool_transaction_count": len(classified),
            "proven_swap_transaction_count": len(swaps),
            "proven_non_swap_transaction_count": len(non_swaps),
            "add_liquidity_transaction_count": sum(
                1 for raw in non_swaps if raw.get("operation_class") == ADD_LIQUIDITY
            ),
            "remove_liquidity_transaction_count": sum(
                1 for raw in non_swaps if raw.get("operation_class") == REMOVE_LIQUIDITY
            ),
            "unknown_pool_operation_count": len(unknown),
            "semantically_resolved_pool_transaction_count": len(resolved_swaps),
            "unresolved_pool_transaction_count": len(unknown),
            "buy_transaction_count": sum(
                1 for raw in resolved_swaps if raw.get("side") == "BUY"
            ),
            "sell_transaction_count": sum(
                1 for raw in resolved_swaps if raw.get("side") == "SELL"
            ),
            "operation_classification_ratio": round(operation_ratio, 6),
            "semantic_resolution_ratio": round(swap_ratio, 6),
            "required_semantic_resolution_ratio": 1.0,
            "all_recognized_pool_operations_classified": all_classified,
            "all_proven_swaps_semantically_resolved": all_swaps_resolved,
            # Compatibility field retained. In v1.4.10.1 it means every
            # recognized operation is classified and every proven swap resolves.
            "all_recognized_pool_transactions_semantically_resolved": complete,
        }
    )
    return out


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
    operation_classifier: Callable[..., Mapping[str, Any]] = classify_liquidity_operation,
) -> dict[str, Any]:
    """Prove exact swap semantics while explicitly classifying non-swap AMM ops."""

    tx_cache: dict[str, Mapping[str, Any]] = {}

    def caching_fetcher(signature: str, *, rpc_url: str):
        tx = fetcher(signature, rpc_url=rpc_url)
        if isinstance(tx, Mapping):
            tx_cache[signature] = tx
        return tx

    base = prove_v1_4_10(
        pool_address=pool_address,
        asset_mint=asset_mint,
        end_epoch=end_epoch,
        pair=pair,
        rpc_url=rpc_url,
        page_size=page_size,
        max_signatures=max_signatures,
        coupling_provider=coupling_provider,
        scanner=scanner,
        fetcher=caching_fetcher,
        occurrence_provider=occurrence_provider,
        delta_provider=delta_provider,
    )
    result = dict(base) if isinstance(base, Mapping) else {}
    result["version"] = VERSION

    summary = result.get("summary")
    summary = dict(summary) if isinstance(summary, Mapping) else {}
    mapping = result.get("canonical_vault_mapping")
    mapping = dict(mapping) if isinstance(mapping, Mapping) else None
    anchor = result.get("structural_anchor")
    anchor = dict(anchor) if isinstance(anchor, Mapping) else {}

    if not mapping or summary.get("canonical_vault_mapping_proven") is not True:
        summary["amm_operation_classification_available"] = False
        summary["interpretation"] = (
            "v1.4.10.1 requires the same v1.4.9 canonical mapping prerequisite "
            "as v1.4.10 before AMM operation classification can begin."
        )
        result["summary"] = summary
        return result

    transactions = []
    for raw in _sequence(result.get("transactions")):
        if not isinstance(raw, Mapping):
            continue
        record = dict(raw)
        record["swap_rejection_reasons"] = list(
            _sequence(record.get("rejection_reasons"))
        )
        record["operation_evidence"] = None
        record["operation_rejection_reasons"] = []
        record["proven_swap"] = False
        record["proven_non_swap"] = False

        if record.get("recognized_pool_transaction") is not True:
            record["operation_class"] = None
            record["operation_classified"] = False
            transactions.append(record)
            continue

        if record.get("semantic_resolved") is True and record.get("side") in {"BUY", "SELL"}:
            record["operation_class"] = (
                SWAP_BUY if record.get("side") == "BUY" else SWAP_SELL
            )
            record["operation_classified"] = True
            record["proven_swap"] = True
            record["rejection_reasons"] = []
            transactions.append(record)
            continue

        signature = _text(record.get("signature"))
        tx = tx_cache.get(signature or "")
        asset_delta = record.get("asset_vault_delta")
        counter_delta = record.get("counter_vault_delta")
        asset_delta = asset_delta if isinstance(asset_delta, Mapping) else {}
        counter_delta = counter_delta if isinstance(counter_delta, Mapping) else {}
        asset_delta_raw = asset_delta.get("delta_raw")
        counter_delta_raw = counter_delta.get("delta_raw")

        if (
            tx is None
            or isinstance(asset_delta_raw, bool)
            or not isinstance(asset_delta_raw, int)
            or isinstance(counter_delta_raw, bool)
            or not isinstance(counter_delta_raw, int)
            or not _text(anchor.get("program_id"))
        ):
            classification = {
                "operation_class": UNKNOWN,
                "operation_classified": False,
                "proven_non_swap": False,
                "evidence": None,
                "rejection_reasons": ["operation_classification_evidence_unavailable"],
            }
        else:
            try:
                classification = operation_classifier(
                    tx,
                    pool_address=pool_address,
                    asset_mint=asset_mint,
                    counter_mint=mapping["counter_mint"],
                    asset_account=mapping["asset_account"],
                    counter_account=mapping["counter_account"],
                    shared_owner=mapping["shared_owner"],
                    expected_program_id=anchor["program_id"],
                    asset_delta_raw=asset_delta_raw,
                    counter_delta_raw=counter_delta_raw,
                    occurrence_provider=occurrence_provider,
                )
            except Exception as exc:
                classification = {
                    "operation_class": UNKNOWN,
                    "operation_classified": False,
                    "proven_non_swap": False,
                    "evidence": None,
                    "rejection_reasons": [
                        f"operation_classifier_exception:{type(exc).__name__}:{exc}"
                    ],
                }

        operation_class = classification.get("operation_class") or UNKNOWN
        operation_classified = classification.get("operation_classified") is True
        record["operation_class"] = operation_class
        record["operation_classified"] = operation_classified
        record["proven_non_swap"] = classification.get("proven_non_swap") is True
        record["operation_evidence"] = classification.get("evidence")
        record["operation_rejection_reasons"] = list(
            _sequence(classification.get("rejection_reasons"))
        )
        if operation_classified and record["proven_non_swap"]:
            record["rejection_reasons"] = []
        else:
            record["rejection_reasons"] = list(
                dict.fromkeys(
                    record["swap_rejection_reasons"]
                    + record["operation_rejection_reasons"]
                )
            )
        transactions.append(record)

    base_windows = [
        dict(raw) for raw in _sequence(result.get("windows")) if isinstance(raw, Mapping)
    ]
    windows = [
        _window_operation_summary(raw, transactions)
        for raw in base_windows
    ]

    recognized = [
        raw for raw in transactions if raw.get("recognized_pool_transaction") is True
    ]
    unknown = [raw for raw in recognized if raw.get("operation_class") == UNKNOWN]
    remove_count = sum(
        1 for raw in recognized if raw.get("operation_class") == REMOVE_LIQUIDITY
    )
    add_count = sum(
        1 for raw in recognized if raw.get("operation_class") == ADD_LIQUIDITY
    )
    swap_count = sum(1 for raw in recognized if raw.get("proven_swap") is True)
    all_windows_complete = bool(
        windows
        and all(
            raw.get("all_recognized_pool_transactions_semantically_resolved") is True
            for raw in windows
        )
    )

    history_proven = summary.get("history_range_proven") is True
    all_fetched = summary.get("all_successful_history_transactions_fetched") is True
    buy_proven = summary.get("buy_semantics_proven") is True
    sell_proven = summary.get("sell_semantics_proven") is True
    anchor_consistent = summary.get("cross_direction_structural_anchor_consistent") is True

    exact_proven = bool(
        history_proven
        and all_fetched
        and all_windows_complete
        and not unknown
        and buy_proven
        and sell_proven
        and anchor_consistent
    )

    if not history_proven:
        status = "history_range_unproven"
    elif not all_fetched:
        status = "transaction_evidence_incomplete"
    elif unknown or not all_windows_complete:
        status = "amm_operation_classification_incomplete_or_conflicting"
    elif not (buy_proven and sell_proven):
        status = "bidirectional_semantics_unproven"
    elif not anchor_consistent:
        status = "directional_structural_anchor_conflict"
    elif exact_proven:
        status = "exact_pool_leg_semantics_proven"
    else:
        status = "exact_pool_leg_semantics_unproven"

    summary.update(
        {
            "amm_operation_classification_available": True,
            "recognized_pool_operation_count": len(recognized),
            "proven_swap_operation_count": swap_count,
            "proven_add_liquidity_operation_count": add_count,
            "proven_remove_liquidity_operation_count": remove_count,
            "unknown_pool_operation_count": len(unknown),
            "all_required_windows_semantically_complete": all_windows_complete,
            "all_recognized_pool_operations_classified": bool(recognized and not unknown),
            "exact_pool_leg_semantics_proven": exact_proven,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "interpretation": (
                "v1.4.10.1 first classifies every recognized canonical-pool AMM "
                "operation. Proven swaps retain v1.4.10 BUY/SELL semantics; proven "
                "ADD_LIQUIDITY and REMOVE_LIQUIDITY operations are explicitly "
                "accounted for but excluded from the swap-semantic denominator. "
                "UNKNOWN pool operations still fail closed. Liquidity removal "
                "requires both canonical reserves OUT plus a unique LP-token burn "
                "and exact reserve transfers from both canonical vaults in the same "
                "AMM instruction context. Addition requires the complementary "
                "reserves-IN, LP-mint, and exact inbound-transfer proof. Promotion "
                "and transaction execution remain disabled."
            ),
        }
    )

    result["status"] = status
    result["windows"] = windows
    result["transactions"] = transactions
    result["summary"] = summary
    result["operation_counts"] = {
        "recognized": len(recognized),
        "swaps": swap_count,
        "add_liquidity": add_count,
        "remove_liquidity": remove_count,
        "unknown": len(unknown),
    }
    return result


__all__ = ["VERSION", "prove_exact_pool_leg_semantics"]
