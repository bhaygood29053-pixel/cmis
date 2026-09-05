"""Program-scoped 24h XDEX activity proof for CMIS #410.

This module scans the verified XDEX program address itself across an exact
requested window. It is designed specifically to close the historical gap that
a current zero pool set cannot answer.

If the complete X1 RPC signature trace contains no successful transaction with
an exact target-mint token-balance delta, CMIS may verify program-scoped zero
trading activity for that window. Any fetch/identity/verification gap fails
closed and zero is not authorized.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from liquidity_scout.providers.x1.history_range import scan_address_history_range
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL
from liquidity_scout.providers.x1.transaction_semantics import (
    fetch_transaction,
    report_to_dict,
    verify_transaction,
)

CONTRACT = "xdex_program_asset_window_activity/v1"


class XDEXProgramWindowActivityError(RuntimeError):
    pass


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise XDEXProgramWindowActivityError(f"{field} is required")
    return text


def _epoch(value: Any, field: str) -> float:
    if value is None or isinstance(value, bool):
        raise XDEXProgramWindowActivityError(f"{field} must be epoch seconds")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise XDEXProgramWindowActivityError(
            f"{field} must be epoch seconds"
        ) from exc
    if parsed < 0:
        raise XDEXProgramWindowActivityError(f"{field} must be nonnegative")
    return parsed


def _default_fetcher(signature: str, *, rpc_url: str):
    return fetch_transaction(signature, rpc_url=rpc_url)


def _default_verifier(
    tx: Mapping[str, Any] | None,
    *,
    signature: str,
    rpc_url: str,
    expected_mint: str,
):
    return report_to_dict(
        verify_transaction(
            tx,
            signature=signature,
            rpc_url=rpc_url,
            expected_mint=expected_mint,
        )
    )


def prove_xdex_program_asset_window_activity(
    *,
    program_id: str,
    asset_mint: str,
    start_epoch: Any,
    end_epoch: Any,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    page_size: int = 1000,
    max_signatures: int = 100000,
    fetch_workers: int = 12,
    scanner: Callable[..., Mapping[str, Any]] = scan_address_history_range,
    fetcher: Callable[..., Any] = _default_fetcher,
    verifier: Callable[..., Mapping[str, Any]] = _default_verifier,
) -> dict[str, Any]:
    program_id = _text(program_id, "program_id")
    asset_mint = _text(asset_mint, "asset_mint")
    start = _epoch(start_epoch, "start_epoch")
    end = _epoch(end_epoch, "end_epoch")
    if start >= end:
        raise XDEXProgramWindowActivityError("start_epoch must be < end_epoch")
    if (
        isinstance(fetch_workers, bool)
        or not isinstance(fetch_workers, int)
        or fetch_workers < 1
        or fetch_workers > 32
    ):
        raise XDEXProgramWindowActivityError(
            "fetch_workers must be an integer between 1 and 32"
        )

    raw_scan = scanner(
        program_id,
        start_epoch=start,
        end_epoch=end,
        rpc_url=rpc_url,
        page_size=page_size,
        max_signatures=max_signatures,
    )
    if not isinstance(raw_scan, Mapping):
        raise XDEXProgramWindowActivityError("scanner returned malformed result")
    scan = dict(raw_scan)
    entries = scan.pop("entries", [])
    if not isinstance(entries, Sequence) or isinstance(
        entries, (str, bytes, bytearray)
    ):
        raise XDEXProgramWindowActivityError("scan entries must be a sequence")

    range_proven = scan.get("range_proven") is True
    integrity_verified = scan.get("integrity_verified") is True

    in_window = []
    for row in entries:
        if not isinstance(row, Mapping):
            continue
        block_time = row.get("block_time")
        if isinstance(block_time, bool) or not isinstance(block_time, (int, float)):
            continue
        if start <= float(block_time) <= end:
            in_window.append(dict(row))

    successful_rows = [row for row in in_window if row.get("err") is None]
    failed_rows = [row for row in in_window if row.get("err") is not None]

    records: list[dict[str, Any]] = []
    fetch_unavailable = 0
    identity_conflicts = 0
    verification_errors = 0
    target_mint_activity_count = 0
    target_mint_delta_count = 0

    def fetch_one(row: Mapping[str, Any]) -> tuple[dict[str, Any], Any, str | None]:
        clean = dict(row)
        signature = _text(clean.get("signature"), "signature")
        try:
            tx = fetcher(signature, rpc_url=rpc_url)
        except Exception as exc:
            return clean, None, f"{type(exc).__name__}: {exc}"
        if tx is None:
            return clean, None, "getTransaction returned no transaction"
        return clean, tx, None

    if fetch_workers == 1:
        fetched_rows = [fetch_one(row) for row in successful_rows]
    else:
        with ThreadPoolExecutor(max_workers=fetch_workers) as executor:
            fetched_rows = list(executor.map(fetch_one, successful_rows))

    for row, tx, fetch_error in fetched_rows:
        signature = _text(row.get("signature"), "signature")
        slot = row.get("slot")
        block_time = row.get("block_time")
        if fetch_error is not None:
            fetch_unavailable += 1
            records.append({
                "signature": signature,
                "classification": "FETCH_UNAVAILABLE",
                "error": fetch_error,
            })
            continue

        try:
            verification = verifier(
                tx,
                signature=signature,
                rpc_url=rpc_url,
                expected_mint=asset_mint,
            )
        except Exception as exc:
            verification_errors += 1
            records.append({
                "signature": signature,
                "classification": "VERIFICATION_ERROR",
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        if not isinstance(verification, Mapping):
            verification_errors += 1
            records.append({
                "signature": signature,
                "classification": "VERIFICATION_ERROR",
                "error": "verifier returned malformed result",
            })
            continue
        if verification.get("found") is not True:
            verification_errors += 1
            records.append({
                "signature": signature,
                "classification": "VERIFICATION_ERROR",
                "error": "fetched transaction was not verified as found",
            })
            continue
        if verification.get("succeeded") is not True:
            verification_errors += 1
            records.append({
                "signature": signature,
                "classification": "VERIFICATION_ERROR",
                "error": "successful address-history row did not verify as succeeded",
            })
            continue

        verified_time = verification.get("block_time")
        if (
            verification.get("slot") != slot
            or verified_time is None
            or float(verified_time) != float(block_time)
        ):
            identity_conflicts += 1
            records.append({
                "signature": signature,
                "classification": "CHAIN_IDENTITY_CONFLICT",
            })
            continue

        token_deltas = verification.get("token_deltas")
        token_deltas = (
            token_deltas
            if isinstance(token_deltas, Sequence)
            and not isinstance(token_deltas, (str, bytes, bytearray))
            else []
        )
        target = [
            dict(delta)
            for delta in token_deltas
            if isinstance(delta, Mapping)
            and str(delta.get("mint") or "").strip() == asset_mint
        ]
        if target:
            target_mint_activity_count += 1
            target_mint_delta_count += len(target)

        records.append({
            "signature": signature,
            "slot": slot,
            "block_time": float(block_time),
            "succeeded": verification.get("succeeded") is True,
            "xdex_amm_invoked": verification.get("xdex_amm_invoked") is True,
            "xendex_amm_invoked": verification.get("xendex_amm_invoked") is True,
            "target_mint_delta_count": len(target),
            "target_mint_deltas": target,
            "classification": (
                "TARGET_MINT_ACTIVITY" if target else "NO_TARGET_MINT_ACTIVITY"
            ),
        })

    all_successful_transactions_verified = bool(
        fetch_unavailable == 0
        and identity_conflicts == 0
        and verification_errors == 0
        and len(records) == len(successful_rows)
    )
    window_trace_complete = bool(
        range_proven and integrity_verified and all_successful_transactions_verified
    )
    zero_activity_verified = bool(
        window_trace_complete and target_mint_activity_count == 0
    )

    return {
        "contract": CONTRACT,
        "chain": "x1",
        "program_id": program_id,
        "asset_mint": asset_mint,
        "requested_window": {
            "start_epoch": start,
            "end_epoch": end,
            "duration_seconds": end - start,
            "membership_basis": "X1_RPC_PROGRAM_ADDRESS_HISTORY_PLUS_TRANSACTION_TOKEN_DELTAS",
        },
        "program_signature_range_proven": range_proven,
        "program_signature_integrity_verified": integrity_verified,
        "program_signature_scan": scan,
        "window_signature_count": len(in_window),
        "successful_window_signature_count": len(successful_rows),
        "failed_window_signature_count": len(failed_rows),
        "transaction_fetch_unavailable_count": fetch_unavailable,
        "transaction_fetch_worker_count": fetch_workers,
        "transaction_identity_conflict_count": identity_conflicts,
        "transaction_verification_error_count": verification_errors,
        "all_successful_transactions_verified": all_successful_transactions_verified,
        "target_mint_activity_transaction_count": target_mint_activity_count,
        "target_mint_delta_count": target_mint_delta_count,
        "window_trace_complete_verified": window_trace_complete,
        "program_scoped_asset_activity_zero_verified": zero_activity_verified,
        "volume_24h_window_coverage_verified": zero_activity_verified,
        "volume_24h_semantics_verified": zero_activity_verified,
        "verified_volume_24h_value": "0" if zero_activity_verified else None,
        "verified_volume_24h_unit": "USD" if zero_activity_verified else None,
        "zero_authorization_basis": (
            "complete_program_signature_trace_contains_no_successful_target_mint_token_delta"
            if zero_activity_verified
            else None
        ),
        "global_onchain_pool_discovery_proven": False,
        "recognized_program_registry_globally_exhaustive": False,
        "causal_claim_authorized": False,
        "adoption_claim_authorized": False,
        "read_only": True,
        "execution_authorized": False,
        "transactions": records,
    }


__all__ = [
    "CONTRACT",
    "XDEXProgramWindowActivityError",
    "prove_xdex_program_asset_window_activity",
]
