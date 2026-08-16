"""Chain-first X1 DEX activity enumeration for CMIS v1.4.

This module starts from proven X1 address-history ranges for selected asset pools,
deduplicates transaction signatures across pools, fetches each transaction once,
and reuses CMIS transaction semantics to classify chain activity.

Important epistemic boundary:
- selected_pool_chain_window_complete can be proven for the selected pool set;
- asset_window_complete is NOT promoted here because pool discovery itself is not
  yet independently proven exhaustive on-chain;
- BUY/SELL here is transaction-level direction supported by the existing
  deterministic transaction semantics. It is NOT an exact pool-leg amount claim.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Callable

from liquidity_scout.providers.x1.history_range import scan_address_history_range
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL
from liquidity_scout.providers.x1.transaction_semantics import (
    fetch_transaction,
    report_to_dict,
    verify_transaction,
)

VERSION = "1.4"

CLASS_BUY = "BUY"
CLASS_SELL = "SELL"
CLASS_MIXED = "MIXED"
CLASS_NON_DEX = "NON_DEX"
CLASS_NON_ASSET_ACTIVITY = "NON_ASSET_ACTIVITY"
CLASS_UNRESOLVED_DEX_ASSET_ACTIVITY = "UNRESOLVED_DEX_ASSET_ACTIVITY"
CLASS_CHAIN_FAILED = "CHAIN_FAILED"
CLASS_FETCH_UNAVAILABLE = "FETCH_UNAVAILABLE"
CLASS_CHAIN_IDENTITY_CONFLICT = "CHAIN_IDENTITY_CONFLICT"


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


def _iso(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _pool_descriptor(pool: Any) -> tuple[str | None, str | None]:
    if isinstance(pool, Mapping):
        address = _text(
            pool.get("pool_address")
            or pool.get("address")
            or pool.get("poolAddress")
        )
        pair = _text(pool.get("pair") or pool.get("pair_name") or pool.get("name"))
        return address, pair
    return _text(pool), None


def _window_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    start_epoch: float,
    end_epoch: float,
) -> list[dict[str, Any]]:
    out = []
    for raw in entries:
        if not isinstance(raw, Mapping):
            continue
        signature = _text(raw.get("signature"))
        slot = raw.get("slot")
        block_time = _epoch(raw.get("block_time"))
        if (
            not signature
            or isinstance(slot, bool)
            or not isinstance(slot, int)
            or slot < 0
            or block_time is None
        ):
            continue
        if start_epoch <= block_time <= end_epoch:
            out.append(
                {
                    "signature": signature,
                    "slot": slot,
                    "block_time": block_time,
                    "err": raw.get("err"),
                }
            )
    return out


def classify_transaction_verification(
    verification: Mapping[str, Any],
    *,
    expected_mint: str,
) -> dict[str, Any]:
    """Classify one fetched transaction without overstating pool-leg evidence."""

    expected_mint = _text(expected_mint)
    if not expected_mint:
        raise ValueError("expected_mint is required")

    if verification.get("found") is not True:
        return {
            "classification": CLASS_FETCH_UNAVAILABLE,
            "side": None,
            "side_hint": None,
            "asset_scope_observed": False,
            "reason": "Transaction was not available from X1 RPC.",
        }

    if verification.get("succeeded") is not True:
        return {
            "classification": CLASS_CHAIN_FAILED,
            "side": None,
            "side_hint": None,
            "asset_scope_observed": False,
            "reason": "The chain transaction failed.",
        }

    recognized_dex = bool(
        verification.get("xdex_amm_invoked") is True
        or verification.get("xendex_amm_invoked") is True
    )
    if not recognized_dex:
        return {
            "classification": CLASS_NON_DEX,
            "side": None,
            "side_hint": None,
            "asset_scope_observed": False,
            "reason": "No recognized XDEX/XenDEX AMM program was invoked.",
        }

    token_deltas = verification.get("token_deltas")
    token_deltas = (
        token_deltas
        if isinstance(token_deltas, Sequence)
        and not isinstance(token_deltas, (str, bytes))
        else []
    )
    target_deltas = [
        row
        for row in token_deltas
        if isinstance(row, Mapping)
        and _text(row.get("mint")) == expected_mint
    ]
    if not target_deltas:
        return {
            "classification": CLASS_NON_ASSET_ACTIVITY,
            "side": None,
            "side_hint": None,
            "asset_scope_observed": False,
            "reason": (
                "A recognized DEX was invoked, but the requested asset mint "
                "had no token-balance delta in this transaction."
            ),
        }

    inferred_side = _text(verification.get("inferred_side")) or "UNKNOWN"
    inferred_mint = _text(verification.get("inferred_asset_mint"))

    if inferred_mint == expected_mint and inferred_side in {CLASS_BUY, CLASS_SELL}:
        return {
            "classification": inferred_side,
            "side": inferred_side,
            "side_hint": inferred_side,
            "asset_scope_observed": True,
            "reason": (
                "Existing deterministic transaction semantics inferred a "
                f"{inferred_side} for the requested asset mint."
            ),
        }

    hint = None
    if inferred_mint == expected_mint and inferred_side in {
        "LIKELY_BUY",
        "LIKELY_SELL",
    }:
        hint = inferred_side.replace("LIKELY_", "")

    return {
        "classification": CLASS_UNRESOLVED_DEX_ASSET_ACTIVITY,
        "side": None,
        "side_hint": hint,
        "asset_scope_observed": True,
        "reason": (
            "The requested asset moved in a recognized DEX transaction, but "
            "transaction-level evidence was insufficient for deterministic "
            "BUY/SELL classification."
        ),
    }


def _default_fetcher(signature: str, *, rpc_url: str):
    return fetch_transaction(signature, rpc_url=rpc_url)


def _default_verifier(
    tx: Mapping[str, Any] | None,
    *,
    signature: str,
    rpc_url: str,
    expected_mint: str,
):
    report = verify_transaction(
        tx,
        signature=signature,
        rpc_url=rpc_url,
        expected_mint=expected_mint,
    )
    return report_to_dict(report)


def enumerate_chain_window_dex_activity(
    *,
    asset_mint: str,
    pools: Sequence[Any],
    start_epoch: float,
    end_epoch: float,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    page_size: int = 1000,
    max_signatures_per_pool: int = 5000,
    scanner: Callable[..., Mapping[str, Any]] = scan_address_history_range,
    fetcher: Callable[..., Any] = _default_fetcher,
    verifier: Callable[..., Mapping[str, Any]] = _default_verifier,
) -> dict[str, Any]:
    """Enumerate and classify X1 transactions in an exact requested window."""

    asset_mint = _text(asset_mint)
    if not asset_mint:
        raise ValueError("asset_mint is required")

    start_epoch = _epoch(start_epoch)
    end_epoch = _epoch(end_epoch)
    if start_epoch is None or end_epoch is None:
        raise ValueError("start_epoch and end_epoch must be non-negative times")
    if start_epoch > end_epoch:
        raise ValueError("start_epoch must be <= end_epoch")

    descriptors = []
    seen_pool_addresses = set()
    for pool in pools:
        address, pair = _pool_descriptor(pool)
        if not address or address in seen_pool_addresses:
            continue
        seen_pool_addresses.add(address)
        descriptors.append((address, pair))

    pool_reports = []
    memberships: dict[str, list[dict[str, Any]]] = {}

    for address, pair in descriptors:
        try:
            scan = scanner(
                address,
                start_epoch=start_epoch,
                end_epoch=end_epoch,
                rpc_url=rpc_url,
                page_size=page_size,
                max_signatures=max_signatures_per_pool,
            )
        except Exception as exc:
            scan = {
                "range_proven": False,
                "integrity_verified": False,
                "rpc_errors": 1,
                "error": f"{type(exc).__name__}: {exc}",
                "entries": [],
            }

        scan = dict(scan) if isinstance(scan, Mapping) else {
            "range_proven": False,
            "integrity_verified": False,
            "rpc_errors": 1,
            "error": "scanner returned a non-mapping result",
            "entries": [],
        }
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

        unique_pool_signatures = set()
        for entry in in_window:
            signature = entry["signature"]
            if signature in unique_pool_signatures:
                continue
            unique_pool_signatures.add(signature)
            memberships.setdefault(signature, []).append(
                {
                    "pool_address": address,
                    "pair": pair,
                    "slot": entry["slot"],
                    "block_time": entry["block_time"],
                    "err": entry["err"],
                }
            )

        pool_reports.append(
            {
                "pool_address": address,
                "pair": pair,
                "range_proven": scan.get("range_proven") is True,
                "integrity_verified": scan.get("integrity_verified") is True,
                "requested_window_signature_count": len(unique_pool_signatures),
                "proof_scan": scan,
            }
        )

    tx_records = []
    fetch_attempt_count = 0
    fetched_transaction_count = 0

    for signature in sorted(memberships):
        observed = memberships[signature]
        pools_seen = sorted(
            {
                item["pool_address"]
                for item in observed
                if item.get("pool_address")
            }
        )
        slots = {item["slot"] for item in observed}
        block_times = {item["block_time"] for item in observed}
        chain_success_flags = {item.get("err") is None for item in observed}

        identity_consistent = (
            len(slots) == 1
            and len(block_times) == 1
            and len(chain_success_flags) == 1
        )

        base_record = {
            "transaction_signature": signature,
            "observed_pool_count": len(pools_seen),
            "observed_pools": pools_seen,
            "enumeration_identity_consistent": identity_consistent,
            "enumerated_slot": next(iter(slots)) if len(slots) == 1 else None,
            "enumerated_block_time": (
                next(iter(block_times)) if len(block_times) == 1 else None
            ),
            "enumerated_block_time_utc": (
                _iso(next(iter(block_times))) if len(block_times) == 1 else None
            ),
        }

        if not identity_consistent:
            tx_records.append(
                {
                    **base_record,
                    "classification": CLASS_CHAIN_IDENTITY_CONFLICT,
                    "side": None,
                    "side_hint": None,
                    "asset_scope_observed": False,
                    "fetched": False,
                    "verification": None,
                    "reason": (
                        "The same signature had inconsistent slot/time/success "
                        "identity across selected pool-address scans."
                    ),
                }
            )
            continue

        if chain_success_flags == {False}:
            tx_records.append(
                {
                    **base_record,
                    "classification": CLASS_CHAIN_FAILED,
                    "side": None,
                    "side_hint": None,
                    "asset_scope_observed": False,
                    "fetched": False,
                    "verification": None,
                    "reason": "X1 address history marks this transaction failed.",
                }
            )
            continue

        try:
            fetch_attempt_count += 1
            tx = fetcher(signature, rpc_url=rpc_url)
        except Exception as exc:
            tx_records.append(
                {
                    **base_record,
                    "classification": CLASS_FETCH_UNAVAILABLE,
                    "side": None,
                    "side_hint": None,
                    "asset_scope_observed": False,
                    "fetched": False,
                    "verification": None,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        if tx is None:
            tx_records.append(
                {
                    **base_record,
                    "classification": CLASS_FETCH_UNAVAILABLE,
                    "side": None,
                    "side_hint": None,
                    "asset_scope_observed": False,
                    "fetched": False,
                    "verification": None,
                    "reason": "getTransaction returned no transaction.",
                }
            )
            continue

        fetched_transaction_count += 1

        try:
            verification = verifier(
                tx,
                signature=signature,
                rpc_url=rpc_url,
                expected_mint=asset_mint,
            )
        except Exception as exc:
            tx_records.append(
                {
                    **base_record,
                    "classification": CLASS_FETCH_UNAVAILABLE,
                    "side": None,
                    "side_hint": None,
                    "asset_scope_observed": False,
                    "fetched": True,
                    "verification": None,
                    "reason": f"verification error: {type(exc).__name__}: {exc}",
                }
            )
            continue

        verification = (
            dict(verification)
            if isinstance(verification, Mapping)
            else {}
        )

        verified_slot = verification.get("slot")
        verified_time = _epoch(verification.get("block_time"))
        if (
            verified_slot != base_record["enumerated_slot"]
            or verified_time != base_record["enumerated_block_time"]
        ):
            tx_records.append(
                {
                    **base_record,
                    "classification": CLASS_CHAIN_IDENTITY_CONFLICT,
                    "side": None,
                    "side_hint": None,
                    "asset_scope_observed": False,
                    "fetched": True,
                    "verification": {
                        "slot": verified_slot,
                        "block_time": verified_time,
                        "verification_level": verification.get(
                            "verification_level"
                        ),
                    },
                    "reason": (
                        "Fetched transaction slot/block time did not match the "
                        "address-history enumeration identity."
                    ),
                }
            )
            continue

        classification = classify_transaction_verification(
            verification,
            expected_mint=asset_mint,
        )

        target_asset_deltas = [
            row
            for row in (verification.get("token_deltas") or [])
            if isinstance(row, Mapping)
            and _text(row.get("mint")) == asset_mint
        ]

        tx_records.append(
            {
                **base_record,
                **classification,
                "fetched": True,
                "verification": {
                    "verification_level": verification.get("verification_level"),
                    "verification_basis": verification.get("verification_basis"),
                    "dex_protocol": verification.get("dex_protocol"),
                    "xdex_amm_invoked": verification.get("xdex_amm_invoked"),
                    "xendex_amm_invoked": verification.get("xendex_amm_invoked"),
                    "inferred_side": verification.get("inferred_side"),
                    "inferred_asset_mint": verification.get(
                        "inferred_asset_mint"
                    ),
                    "inferred_quote_mint": verification.get(
                        "inferred_quote_mint"
                    ),
                    "primary_signer": verification.get("primary_signer"),
                    "target_asset_delta_count": len(target_asset_deltas),
                    "target_asset_deltas": target_asset_deltas,
                },
            }
        )

    all_pool_ranges_proven = bool(pool_reports) and all(
        item["range_proven"] is True for item in pool_reports
    )

    def count_class(name: str) -> int:
        return sum(
            1 for item in tx_records if item.get("classification") == name
        )

    observed_memberships = sum(
        item["requested_window_signature_count"] for item in pool_reports
    )

    return {
        "service": "chain_window_dex_activity",
        "version": VERSION,
        "chain": "x1",
        "asset_mint": asset_mint,
        "requested_window": {
            "start_epoch": start_epoch,
            "start_utc": _iso(start_epoch),
            "end_epoch": end_epoch,
            "end_utc": _iso(end_epoch),
            "membership_basis": "X1_RPC_BLOCK_TIME",
        },
        "selected_pool_count": len(pool_reports),
        "pools": pool_reports,
        "summary": {
            "selected_pool_chain_window_complete": all_pool_ranges_proven,
            "asset_window_complete": False,
            "asset_window_completion_promoted": False,
            "asset_window_completion_reason": (
                "The selected pool address ranges can be proven on X1 RPC, but "
                "v1.4 does not independently prove that asset pool discovery is "
                "globally exhaustive."
            ),
            "observed_pool_signature_membership_count": observed_memberships,
            "unique_window_transaction_count": len(tx_records),
            "multi_pool_transaction_count": sum(
                1 for item in tx_records if item["observed_pool_count"] > 1
            ),
            "transaction_fetch_attempt_count": fetch_attempt_count,
            "fetched_transaction_count": fetched_transaction_count,
            "verified_buy_transaction_count": count_class(CLASS_BUY),
            "verified_sell_transaction_count": count_class(CLASS_SELL),
            "verified_mixed_transaction_count": count_class(CLASS_MIXED),
            "mixed_semantics_supported": False,
            "unresolved_dex_asset_transaction_count": count_class(
                CLASS_UNRESOLVED_DEX_ASSET_ACTIVITY
            ),
            "non_asset_activity_transaction_count": count_class(
                CLASS_NON_ASSET_ACTIVITY
            ),
            "non_dex_transaction_count": count_class(CLASS_NON_DEX),
            "failed_chain_transaction_count": count_class(CLASS_CHAIN_FAILED),
            "fetch_unavailable_transaction_count": count_class(
                CLASS_FETCH_UNAVAILABLE
            ),
            "chain_identity_conflict_count": count_class(
                CLASS_CHAIN_IDENTITY_CONFLICT
            ),
        },
        "transactions": tx_records,
    }


__all__ = [
    "CLASS_BUY",
    "CLASS_CHAIN_FAILED",
    "CLASS_CHAIN_IDENTITY_CONFLICT",
    "CLASS_FETCH_UNAVAILABLE",
    "CLASS_MIXED",
    "CLASS_NON_ASSET_ACTIVITY",
    "CLASS_NON_DEX",
    "CLASS_SELL",
    "CLASS_UNRESOLVED_DEX_ASSET_ACTIVITY",
    "VERSION",
    "classify_transaction_verification",
    "enumerate_chain_window_dex_activity",
]
