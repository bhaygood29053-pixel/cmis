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
import time
from typing import Any, Callable

import requests

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


def _batch_fetch_transactions(
    signatures: Sequence[str],
    *,
    rpc_url: str,
    batch_size: int = 50,
    batch_workers: int = 4,
    retries: int = 4,
    timeout: int = 40,
    post: Callable[..., Any] = requests.post,
    sleep: Callable[[float], Any] = time.sleep,
) -> dict[str, tuple[Any, str | None]]:
    """Fetch getTransaction responses through bounded JSON-RPC batches.

    The return mapping preserves one explicit availability/error state per
    requested signature. A transport or malformed-response failure never
    becomes an empty successful transaction.
    """

    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or batch_size < 1
        or batch_size > 100
    ):
        raise XDEXProgramWindowActivityError(
            "batch_size must be an integer between 1 and 100"
        )
    if (
        isinstance(batch_workers, bool)
        or not isinstance(batch_workers, int)
        or batch_workers < 1
        or batch_workers > 8
    ):
        raise XDEXProgramWindowActivityError(
            "batch_workers must be an integer between 1 and 8"
        )

    normalized = [_text(value, "signature") for value in signatures]
    chunks = [
        normalized[index : index + batch_size]
        for index in range(0, len(normalized), batch_size)
    ]

    def fetch_chunk(chunk: list[str]) -> dict[str, tuple[Any, str | None]]:
        payload = [
            {
                "jsonrpc": "2.0",
                "id": index + 1,
                "method": "getTransaction",
                "params": [
                    signature,
                    {
                        "encoding": "jsonParsed",
                        "commitment": "confirmed",
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
            }
            for index, signature in enumerate(chunk)
        ]
        last_error = "unknown batch transport error"
        for attempt in range(retries):
            try:
                response = post(rpc_url, json=payload, timeout=timeout)
                status = getattr(response, "status_code", None)
                if status == 429 or (
                    isinstance(status, int) and status >= 500
                ):
                    raise RuntimeError(f"HTTP {status}")
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, list):
                    raise RuntimeError("non-list JSON-RPC batch response")
                indexed: dict[int, Mapping[str, Any]] = {}
                for item in body:
                    if not isinstance(item, Mapping):
                        raise RuntimeError("malformed JSON-RPC batch item")
                    item_id = item.get("id")
                    if isinstance(item_id, bool) or not isinstance(item_id, int):
                        raise RuntimeError("batch item missing integer id")
                    if item_id in indexed:
                        raise RuntimeError("duplicate JSON-RPC batch id")
                    indexed[item_id] = item

                result: dict[str, tuple[Any, str | None]] = {}
                for index, signature in enumerate(chunk, start=1):
                    item = indexed.get(index)
                    if item is None:
                        result[signature] = (None, "missing JSON-RPC batch item")
                    elif item.get("error") is not None:
                        result[signature] = (
                            None,
                            "getTransaction JSON-RPC error",
                        )
                    elif "result" not in item:
                        result[signature] = (
                            None,
                            "getTransaction batch item missing result",
                        )
                    elif item.get("result") is None:
                        result[signature] = (
                            None,
                            "getTransaction returned no transaction",
                        )
                    elif not isinstance(item.get("result"), Mapping):
                        result[signature] = (
                            None,
                            "getTransaction returned malformed transaction",
                        )
                    else:
                        result[signature] = (item.get("result"), None)
                return result
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < retries - 1:
                    sleep(0.75 * (2 ** attempt))

        return {
            signature: (None, f"batch transport unavailable: {last_error}")
            for signature in chunk
        }

    merged: dict[str, tuple[Any, str | None]] = {}
    if not chunks:
        return merged
    if batch_workers == 1:
        chunk_results = [fetch_chunk(chunk) for chunk in chunks]
    else:
        with ThreadPoolExecutor(max_workers=batch_workers) as executor:
            chunk_results = list(executor.map(fetch_chunk, chunks))
    for result in chunk_results:
        merged.update(result)
    return merged


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
    batch_fetch_size: int = 50,
    batch_fetch_workers: int = 4,
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
    if (
        isinstance(batch_fetch_size, bool)
        or not isinstance(batch_fetch_size, int)
        or batch_fetch_size < 1
        or batch_fetch_size > 100
    ):
        raise XDEXProgramWindowActivityError(
            "batch_fetch_size must be an integer between 1 and 100"
        )
    if (
        isinstance(batch_fetch_workers, bool)
        or not isinstance(batch_fetch_workers, int)
        or batch_fetch_workers < 1
        or batch_fetch_workers > 8
    ):
        raise XDEXProgramWindowActivityError(
            "batch_fetch_workers must be an integer between 1 and 8"
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

    if not range_proven or not integrity_verified:
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
            "transaction_fetch_unavailable_count": 0,
            "transaction_fetch_worker_count": fetch_workers,
        "transaction_batch_size": (
            batch_fetch_size if fetcher is _default_fetcher else 1
        ),
        "transaction_batch_worker_count": (
            batch_fetch_workers if fetcher is _default_fetcher else 0
        ),
            "transaction_identity_conflict_count": 0,
            "transaction_verification_error_count": 0,
            "all_successful_transactions_verified": False,
            "target_mint_activity_transaction_count": 0,
            "target_mint_delta_count": 0,
            "window_trace_complete_verified": False,
            "program_scoped_asset_activity_zero_verified": False,
            "volume_24h_window_coverage_verified": False,
            "volume_24h_semantics_verified": False,
            "verified_volume_24h_value": None,
            "verified_volume_24h_unit": None,
            "zero_authorization_basis": None,
            "global_onchain_pool_discovery_proven": False,
            "recognized_program_registry_globally_exhaustive": False,
            "causal_claim_authorized": False,
            "adoption_claim_authorized": False,
            "read_only": True,
            "execution_authorized": False,
            "transactions": [],
        }

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

    if fetcher is _default_fetcher and batch_fetch_size > 1:
        batch = _batch_fetch_transactions(
            [_text(row.get("signature"), "signature") for row in successful_rows],
            rpc_url=rpc_url,
            batch_size=batch_fetch_size,
            batch_workers=batch_fetch_workers,
        )
        fetched_rows = []
        for row in successful_rows:
            clean = dict(row)
            signature = _text(clean.get("signature"), "signature")
            tx, fetch_error = batch.get(
                signature,
                (None, "missing batch fetch result"),
            )
            fetched_rows.append((clean, tx, fetch_error))
    elif fetch_workers == 1:
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
    "_batch_fetch_transactions",
    "prove_xdex_program_asset_window_activity",
]
