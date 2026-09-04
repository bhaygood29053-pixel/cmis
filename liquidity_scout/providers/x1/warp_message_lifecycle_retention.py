"""Bounded Warp message-account lifecycle retention evidence for CMIS #441.

This module proves only a requested historical lookback for the exact Warp
program and the exact current OutgoingMsg/IncomingMsg PDA universe already
accepted by ``warp_message_retention_coverage/v1``.

The evidence path is read-only:
- finalized ``getSignaturesForAddress`` pagination for the exact Warp program;
- finalized ``getTransaction`` for every successful program transaction inside
  the required trace (or the complete program lifetime when younger);
- exact current message-PDA balance-transition inspection;
- fail-closed detection of closures, repeated creations, zero-to-zero ambiguous
  touches, pagination truncation, missing transaction bodies, and archive gaps.

A clean trace can promote bounded requested-window retention only when the
current-universe counter/account closure prerequisite is already verified.
It does not prove permanent retention, bridged supply, public-service
promotion, Scout reliance, or execution authority.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Callable

import requests

from liquidity_scout.providers.x1.warp_message_retention_coverage import (
    CONTRACT as COUNTER_CLOSURE_CONTRACT,
    REQUIRED_FLOW_LOOKBACK_SECONDS,
)
from liquidity_scout.providers.x1.warp_onchain_inventory import (
    SOLANA_RPC_URL,
    WARP_PROGRAM_ID,
    X1_RPC_URL,
)
from liquidity_scout.providers.x1.warp_onchain_transfer_history import (
    CONTRACT as MESSAGE_STATE_CONTRACT,
)

CONTRACT = "warp_message_lifecycle_retention/v1"
DEFAULT_COMMITMENT = "finalized"
DEFAULT_PAGE_SIZE = 1000
DEFAULT_MAX_PAGES = 64
DEFAULT_TRANSACTION_BATCH_SIZE = 50


class WarpMessageLifecycleRetentionError(RuntimeError):
    """Raised when lifecycle-retention evidence cannot be established safely."""


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise WarpMessageLifecycleRetentionError(
            f"{field} must be a non-negative integer"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise WarpMessageLifecycleRetentionError(
            f"{field} must be a non-negative integer"
        ) from None
    if parsed < 0:
        raise WarpMessageLifecycleRetentionError(
            f"{field} must be a non-negative integer"
        )
    return parsed


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _rpc_request(
    method: str,
    params: list[Any],
    *,
    rpc_url: str,
    timeout: int = 60,
    post: Callable[..., Any] = requests.post,
) -> Any:
    try:
        response = post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params,
            },
            headers={
                "content-type": "application/json",
                "user-agent": "CMIS-Warp-Lifecycle-Retention/1.0",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        raise WarpMessageLifecycleRetentionError(
            f"{method} transport failed ({type(exc).__name__})"
        ) from None
    if not isinstance(body, Mapping):
        raise WarpMessageLifecycleRetentionError(
            f"{method} returned non-object JSON-RPC body"
        )
    if body.get("error") is not None:
        error = body.get("error")
        code = error.get("code") if isinstance(error, Mapping) else None
        raise WarpMessageLifecycleRetentionError(
            f"{method} returned JSON-RPC error code {code!r}"
        )
    if "result" not in body:
        raise WarpMessageLifecycleRetentionError(
            f"{method} response missing result"
        )
    return body.get("result")


def _rpc_batch_get_transactions(
    signatures: Sequence[str],
    *,
    rpc_url: str,
    commitment: str = DEFAULT_COMMITMENT,
    timeout: int = 120,
    post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    if not signatures:
        return {}
    payload = [
        {
            "jsonrpc": "2.0",
            "id": index + 1,
            "method": "getTransaction",
            "params": [
                signature,
                {
                    "encoding": "json",
                    "commitment": commitment,
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        }
        for index, signature in enumerate(signatures)
    ]
    try:
        response = post(
            rpc_url,
            json=payload,
            headers={
                "content-type": "application/json",
                "user-agent": "CMIS-Warp-Lifecycle-Retention/1.0",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        raise WarpMessageLifecycleRetentionError(
            f"getTransaction batch transport failed ({type(exc).__name__})"
        ) from None
    if not isinstance(body, list):
        raise WarpMessageLifecycleRetentionError(
            "getTransaction batch returned non-list body"
        )
    by_id: dict[int, Mapping[str, Any]] = {}
    for row in body:
        if not isinstance(row, Mapping):
            raise WarpMessageLifecycleRetentionError(
                "getTransaction batch contained non-object response"
            )
        try:
            row_id = int(row.get("id"))
        except (TypeError, ValueError):
            raise WarpMessageLifecycleRetentionError(
                "getTransaction batch response has invalid id"
            ) from None
        if row_id in by_id:
            raise WarpMessageLifecycleRetentionError(
                "getTransaction batch returned duplicate id"
            )
        by_id[row_id] = row
    if len(by_id) != len(payload):
        raise WarpMessageLifecycleRetentionError(
            "getTransaction batch response count mismatch"
        )

    result: dict[str, Any] = {}
    for index, signature in enumerate(signatures, start=1):
        row = by_id.get(index)
        if row is None or row.get("error") is not None:
            raise WarpMessageLifecycleRetentionError(
                f"getTransaction failed for signature {signature}"
            )
        if "result" not in row or row.get("result") is None:
            raise WarpMessageLifecycleRetentionError(
                f"getTransaction body unavailable for signature {signature}"
            )
        result[signature] = row.get("result")
    return result


def _block_time_for_slot(
    slot: int,
    *,
    rpc_url: str,
    requester: Callable[..., Any] = _rpc_request,
) -> int | None:
    value = requester("getBlockTime", [int(slot)], rpc_url=rpc_url)
    if value is None:
        return None
    return _nonnegative_int(value, "getBlockTime.result")


def _archive_floor(
    *,
    rpc_url: str,
    requester: Callable[..., Any] = _rpc_request,
) -> dict[str, Any]:
    slot = requester("getFirstAvailableBlock", [], rpc_url=rpc_url)
    first_slot = _nonnegative_int(slot, "getFirstAvailableBlock.result")
    block_time = _block_time_for_slot(
        first_slot,
        rpc_url=rpc_url,
        requester=requester,
    )
    return {
        "first_available_slot": first_slot,
        "first_available_block_time": block_time,
    }


def _signature_row(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise WarpMessageLifecycleRetentionError(
            "getSignaturesForAddress returned non-object row"
        )
    signature = _text(raw.get("signature"))
    if not signature:
        raise WarpMessageLifecycleRetentionError(
            "signature row is missing signature"
        )
    slot = _nonnegative_int(raw.get("slot"), "signature.slot")
    block_time_raw = raw.get("blockTime")
    block_time = (
        None
        if block_time_raw is None
        else _nonnegative_int(block_time_raw, "signature.blockTime")
    )
    return {
        "signature": signature,
        "slot": slot,
        "block_time": block_time,
        "err": raw.get("err"),
        "confirmation_status": _text(raw.get("confirmationStatus")),
    }


def capture_program_signature_history(
    *,
    chain: str,
    as_of: int,
    lookback_seconds: int = REQUIRED_FLOW_LOOKBACK_SECONDS,
    rpc_url: str | None = None,
    commitment: str = DEFAULT_COMMITMENT,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES,
    requester: Callable[..., Any] = _rpc_request,
) -> dict[str, Any]:
    """Capture finalized Warp-program signatures through the requested start."""

    chain_value = str(chain or "").strip().casefold()
    if chain_value not in {"solana", "x1"}:
        raise ValueError("chain must be solana or x1")
    as_of_value = _nonnegative_int(as_of, "as_of")
    lookback_value = _nonnegative_int(lookback_seconds, "lookback_seconds")
    if lookback_value < REQUIRED_FLOW_LOOKBACK_SECONDS:
        raise ValueError(
            "lookback_seconds must cover the required 60-day Bridge Flow window"
        )
    if not 1 <= int(page_size) <= 1000:
        raise ValueError("page_size must be between 1 and 1000")
    if int(max_pages) < 1:
        raise ValueError("max_pages must be positive")

    rpc = rpc_url or (
        SOLANA_RPC_URL if chain_value == "solana" else X1_RPC_URL
    )
    requested_start = as_of_value - lookback_value
    before: str | None = None
    seen_signatures: set[str] = set()
    rows: list[dict[str, Any]] = []
    exhausted = False
    reached_requested_start = False
    pagination_truncated = False
    missing_block_time_count = 0

    for _page_index in range(int(max_pages)):
        config: dict[str, Any] = {
            "commitment": commitment,
            "limit": int(page_size),
        }
        if before is not None:
            config["before"] = before
        result = requester(
            "getSignaturesForAddress",
            [WARP_PROGRAM_ID, config],
            rpc_url=rpc,
        )
        if not isinstance(result, list):
            raise WarpMessageLifecycleRetentionError(
                "getSignaturesForAddress result is not a list"
            )
        if not result:
            exhausted = True
            break

        page_rows = [_signature_row(item) for item in result]
        for row in page_rows:
            signature = row["signature"]
            if signature in seen_signatures:
                raise WarpMessageLifecycleRetentionError(
                    "signature pagination repeated an already-seen signature"
                )
            seen_signatures.add(signature)
            rows.append(row)
            if row["block_time"] is None:
                missing_block_time_count += 1

        oldest = page_rows[-1]
        before = oldest["signature"]
        if (
            oldest["block_time"] is not None
            and int(oldest["block_time"]) <= requested_start
        ):
            reached_requested_start = True
            break

        if len(page_rows) < int(page_size):
            exhausted = True
            break
    else:
        pagination_truncated = True

    rows.sort(
        key=lambda item: (
            int(item["block_time"] or -1),
            int(item["slot"]),
            item["signature"],
        ),
        reverse=True,
    )
    archive = _archive_floor(rpc_url=rpc, requester=requester)
    return {
        "contract": CONTRACT,
        "chain": chain_value,
        "program_id": WARP_PROGRAM_ID,
        "rpc_url": rpc,
        "commitment": commitment,
        "as_of": as_of_value,
        "requested_start": requested_start,
        "lookback_seconds": lookback_value,
        "signature_count": len(rows),
        "signatures": rows,
        "pagination_exhausted": exhausted,
        "pagination_truncated": pagination_truncated,
        "reached_requested_start": reached_requested_start,
        "missing_block_time_count": missing_block_time_count,
        **archive,
        "read_only": True,
        "execution_authorized": False,
    }


def capture_program_transaction_trace(
    signature_history: Any,
    *,
    transaction_batch_size: int = DEFAULT_TRANSACTION_BATCH_SIZE,
    post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    history = signature_history
    if not isinstance(history, Mapping) or history.get("contract") != CONTRACT:
        raise WarpMessageLifecycleRetentionError(
            f"signature_history must use {CONTRACT}"
        )
    chain = _text(history.get("chain"))
    rpc_url = _text(history.get("rpc_url"))
    if chain not in {"solana", "x1"} or not rpc_url:
        raise WarpMessageLifecycleRetentionError(
            "signature history chain/RPC identity is incomplete"
        )
    rows = history.get("signatures")
    if not isinstance(rows, list):
        raise WarpMessageLifecycleRetentionError(
            "signature history rows are missing"
        )
    if int(transaction_batch_size) < 1:
        raise ValueError("transaction_batch_size must be positive")

    requested_start = _nonnegative_int(
        history.get("requested_start"), "signature_history.requested_start"
    )
    as_of = _nonnegative_int(history.get("as_of"), "signature_history.as_of")

    relevant = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get("block_time") is not None
        and requested_start <= int(row["block_time"]) <= as_of
    ]

    if history.get("pagination_exhausted") is True and history.get(
        "reached_requested_start"
    ) is not True:
        relevant = [
            row
            for row in rows
            if isinstance(row, Mapping)
            and row.get("block_time") is not None
            and int(row["block_time"]) <= as_of
        ]

    successful = [row for row in relevant if row.get("err") is None]
    signatures = [str(row["signature"]) for row in successful]

    transaction_map: dict[str, Any] = {}
    batch_size = int(transaction_batch_size)
    for offset in range(0, len(signatures), batch_size):
        batch = signatures[offset : offset + batch_size]
        transaction_map.update(
            _rpc_batch_get_transactions(
                batch,
                rpc_url=rpc_url,
                commitment=str(history.get("commitment") or DEFAULT_COMMITMENT),
                post=post,
            )
        )

    transactions = []
    for row in successful:
        signature = str(row["signature"])
        tx = transaction_map.get(signature)
        if tx is None:
            raise WarpMessageLifecycleRetentionError(
                f"missing fetched transaction for {signature}"
            )
        transactions.append(
            {
                "signature": signature,
                "slot": int(row["slot"]),
                "block_time": int(row["block_time"]),
                "transaction": tx,
            }
        )

    core = {
        "chain": chain,
        "program_id": WARP_PROGRAM_ID,
        "as_of": as_of,
        "requested_start": requested_start,
        "lookback_seconds": int(history["lookback_seconds"]),
        "signature_count_in_scope": len(relevant),
        "successful_signature_count_in_scope": len(successful),
        "failed_signature_count_in_scope": len(relevant) - len(successful),
        "transaction_count": len(transactions),
        "transactions": transactions,
        "pagination_exhausted": bool(history.get("pagination_exhausted")),
        "pagination_truncated": bool(history.get("pagination_truncated")),
        "reached_requested_start": bool(history.get("reached_requested_start")),
        "missing_block_time_count": int(history.get("missing_block_time_count") or 0),
        "first_available_slot": history.get("first_available_slot"),
        "first_available_block_time": history.get("first_available_block_time"),
    }
    return {
        "contract": CONTRACT,
        **core,
        "trace_sha256": _canonical_sha256(core),
        "read_only": True,
        "execution_authorized": False,
    }


def _message_universe(message_state: Any) -> dict[str, dict[str, dict[str, Any]]]:
    if not isinstance(message_state, Mapping):
        raise WarpMessageLifecycleRetentionError(
            "message_state must be a mapping"
        )
    if message_state.get("contract") != MESSAGE_STATE_CONTRACT:
        raise WarpMessageLifecycleRetentionError(
            f"message_state must use {MESSAGE_STATE_CONTRACT}"
        )

    universe: dict[str, dict[str, dict[str, Any]]] = {
        "solana": {},
        "x1": {},
    }
    for chain in ("solana", "x1"):
        chain_block = message_state.get(chain)
        if not isinstance(chain_block, Mapping):
            raise WarpMessageLifecycleRetentionError(
                f"{chain} message state is missing"
            )
        for side in ("outgoing", "incoming"):
            block = chain_block.get(side)
            if not isinstance(block, Mapping):
                raise WarpMessageLifecycleRetentionError(
                    f"{chain}.{side} message state is missing"
                )
            if block.get("account_type_identity_verified") is not True:
                raise WarpMessageLifecycleRetentionError(
                    f"{chain}.{side} account type identity is not verified"
                )
            if block.get("all_pda_identities_verified") is not True:
                raise WarpMessageLifecycleRetentionError(
                    f"{chain}.{side} PDA universe is not verified"
                )
            rows = block.get("accounts")
            if not isinstance(rows, list):
                raise WarpMessageLifecycleRetentionError(
                    f"{chain}.{side}.accounts must be a list"
                )
            for row in rows:
                if not isinstance(row, Mapping):
                    raise WarpMessageLifecycleRetentionError(
                        f"{chain}.{side} contains non-object account"
                    )
                if row.get("pda_identity_verified") is not True:
                    raise WarpMessageLifecycleRetentionError(
                        f"{chain}.{side} contains unverified PDA"
                    )
                pubkey = _text(row.get("pubkey"))
                if not pubkey:
                    raise WarpMessageLifecycleRetentionError(
                        f"{chain}.{side} account is missing pubkey"
                    )
                if pubkey in universe[chain]:
                    raise WarpMessageLifecycleRetentionError(
                        f"{chain} message PDA appears more than once"
                    )
                if side == "outgoing":
                    event_time = _nonnegative_int(
                        row.get("timestamp"),
                        f"{chain}.{side}.timestamp",
                    )
                    sequence = _nonnegative_int(
                        row.get("seq"),
                        f"{chain}.{side}.seq",
                    )
                else:
                    executed = row.get("executed_timestamp")
                    if executed in (None, 0, "0"):
                        event_time = _nonnegative_int(
                            row.get("source_timestamp"),
                            f"{chain}.{side}.source_timestamp",
                        )
                    else:
                        event_time = _nonnegative_int(
                            executed,
                            f"{chain}.{side}.executed_timestamp",
                        )
                    sequence = _nonnegative_int(
                        row.get("source_seq"),
                        f"{chain}.{side}.source_seq",
                    )
                universe[chain][pubkey] = {
                    "pubkey": pubkey,
                    "side": side,
                    "sequence": sequence,
                    "event_time": event_time,
                }
    return universe


def _transaction_account_keys_and_balances(
    tx_result: Any,
) -> tuple[list[str], list[int], list[int], list[str]]:
    if not isinstance(tx_result, Mapping):
        raise WarpMessageLifecycleRetentionError(
            "transaction result must be a mapping"
        )
    transaction = tx_result.get("transaction")
    meta = tx_result.get("meta")
    if not isinstance(transaction, Mapping) or not isinstance(meta, Mapping):
        raise WarpMessageLifecycleRetentionError(
            "transaction/message metadata is missing"
        )
    message = transaction.get("message")
    if not isinstance(message, Mapping):
        raise WarpMessageLifecycleRetentionError(
            "transaction message is missing"
        )
    raw_keys = message.get("accountKeys")
    if not isinstance(raw_keys, list):
        raise WarpMessageLifecycleRetentionError(
            "transaction accountKeys is missing"
        )
    keys: list[str] = []
    for raw in raw_keys:
        if isinstance(raw, str):
            key = _text(raw)
        elif isinstance(raw, Mapping):
            key = _text(raw.get("pubkey"))
        else:
            key = None
        if not key:
            raise WarpMessageLifecycleRetentionError(
                "transaction contains invalid account key"
            )
        keys.append(key)

    loaded = meta.get("loadedAddresses")
    if isinstance(loaded, Mapping):
        for group in ("writable", "readonly"):
            values = loaded.get(group)
            if isinstance(values, list):
                for raw in values:
                    key = _text(raw)
                    if key and key not in keys:
                        keys.append(key)

    pre_raw = meta.get("preBalances")
    post_raw = meta.get("postBalances")
    if not isinstance(pre_raw, list) or not isinstance(post_raw, list):
        raise WarpMessageLifecycleRetentionError(
            "transaction balance vectors are missing"
        )
    pre = [_nonnegative_int(value, "preBalance") for value in pre_raw]
    post = [_nonnegative_int(value, "postBalance") for value in post_raw]
    if len(keys) != len(pre) or len(keys) != len(post):
        raise WarpMessageLifecycleRetentionError(
            "transaction account/balance vector lengths do not match"
        )

    logs_raw = meta.get("logMessages")
    logs = [str(item) for item in logs_raw] if isinstance(logs_raw, list) else []
    return keys, pre, post, logs


def _scan_trace(
    *,
    chain: str,
    trace: Mapping[str, Any],
    universe: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    transitions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    program_transitions: list[dict[str, Any]] = []
    lifecycle_log_fragments: list[dict[str, Any]] = []
    transactions = trace.get("transactions")
    if not isinstance(transactions, list):
        raise WarpMessageLifecycleRetentionError(
            f"{chain} trace transactions are missing"
        )

    for row in transactions:
        if not isinstance(row, Mapping):
            raise WarpMessageLifecycleRetentionError(
                f"{chain} trace contains non-object transaction"
            )
        signature = _text(row.get("signature"))
        block_time = _nonnegative_int(
            row.get("block_time"),
            f"{chain}.transaction.block_time",
        )
        tx = row.get("transaction")
        keys, pre, post, logs = _transaction_account_keys_and_balances(tx)
        index = {key: pos for pos, key in enumerate(keys)}
        for pubkey in universe:
            pos = index.get(pubkey)
            if pos is None:
                continue
            before = pre[pos]
            after = post[pos]
            if before == 0 and after > 0:
                kind = "creation"
            elif before > 0 and after == 0:
                kind = "closure"
            elif before == 0 and after == 0:
                kind = "zero_zero_touch"
            else:
                kind = "touch"
            transitions[pubkey].append(
                {
                    "kind": kind,
                    "signature": signature,
                    "block_time": block_time,
                    "pre_lamports": before,
                    "post_lamports": after,
                }
            )

        program_pos = index.get(WARP_PROGRAM_ID)
        if program_pos is not None:
            before = pre[program_pos]
            after = post[program_pos]
            if before == 0 and after > 0:
                program_transitions.append(
                    {
                        "kind": "program_account_creation",
                        "signature": signature,
                        "block_time": block_time,
                        "pre_lamports": before,
                        "post_lamports": after,
                    }
                )

        interesting_logs = [
            log
            for log in logs
            if any(
                token in log.casefold()
                for token in (
                    "close",
                    "create",
                    "realloc",
                    "initialize",
                    "outgoing",
                    "incoming",
                )
            )
        ]
        if interesting_logs:
            lifecycle_log_fragments.append(
                {
                    "signature": signature,
                    "block_time": block_time,
                    "logs": interesting_logs[:32],
                }
            )

    return {
        "message_transitions": dict(transitions),
        "program_transitions": program_transitions,
        "lifecycle_log_fragments": lifecycle_log_fragments,
    }


def evaluate_warp_message_lifecycle_retention(
    *,
    counter_closure: Any,
    message_state: Any,
    traces: Any,
    as_of: int,
    lookback_seconds: int = REQUIRED_FLOW_LOOKBACK_SECONDS,
) -> dict[str, Any]:
    """Evaluate bounded lifecycle retention for the exact current message universe."""

    if not isinstance(counter_closure, Mapping):
        raise WarpMessageLifecycleRetentionError(
            "counter_closure must be a mapping"
        )
    if counter_closure.get("contract") != COUNTER_CLOSURE_CONTRACT:
        raise WarpMessageLifecycleRetentionError(
            f"counter_closure must use {COUNTER_CLOSURE_CONTRACT}"
        )
    if counter_closure.get("counter_account_closure_verified") is not True:
        raise WarpMessageLifecycleRetentionError(
            "counter/account closure prerequisite is not verified"
        )
    if counter_closure.get("current_message_universe_count_closed") is not True:
        raise WarpMessageLifecycleRetentionError(
            "current message universe is not count-closed"
        )

    as_of_value = _nonnegative_int(as_of, "as_of")
    lookback_value = _nonnegative_int(lookback_seconds, "lookback_seconds")
    if lookback_value < REQUIRED_FLOW_LOOKBACK_SECONDS:
        raise ValueError(
            "lookback_seconds must cover the required 60-day Bridge Flow window"
        )
    requested_start = as_of_value - lookback_value

    if not isinstance(traces, Mapping):
        raise WarpMessageLifecycleRetentionError("traces must be a mapping")
    universe = _message_universe(message_state)

    per_chain: dict[str, Any] = {}
    all_trace_complete = True
    all_no_closure = True
    all_no_recreation = True
    all_no_ambiguous = True
    all_expected_outgoing_creation_seen = True
    all_archive_or_window_coverage = True

    for chain in ("solana", "x1"):
        trace = traces.get(chain)
        if not isinstance(trace, Mapping) or trace.get("contract") != CONTRACT:
            raise WarpMessageLifecycleRetentionError(
                f"{chain} trace must use {CONTRACT}"
            )
        if trace.get("program_id") != WARP_PROGRAM_ID:
            raise WarpMessageLifecycleRetentionError(
                f"{chain} trace program id mismatch"
            )
        if _nonnegative_int(trace.get("as_of"), f"{chain}.trace.as_of") != as_of_value:
            raise WarpMessageLifecycleRetentionError(
                f"{chain} trace as_of does not match evaluation"
            )
        if _nonnegative_int(
            trace.get("requested_start"),
            f"{chain}.trace.requested_start",
        ) != requested_start:
            raise WarpMessageLifecycleRetentionError(
                f"{chain} trace requested_start does not match evaluation"
            )

        scan = _scan_trace(
            chain=chain,
            trace=trace,
            universe=universe[chain],
        )
        transitions = scan["message_transitions"]
        closure_count = 0
        repeated_creation_pdas: list[str] = []
        ambiguous_zero_zero_count = 0
        missing_expected_outgoing_creations: list[str] = []
        unexpected_old_message_creations: list[str] = []

        for pubkey, meta in universe[chain].items():
            observed = transitions.get(pubkey, [])
            creations = [row for row in observed if row["kind"] == "creation"]
            closures = [row for row in observed if row["kind"] == "closure"]
            ambiguous = [
                row for row in observed if row["kind"] == "zero_zero_touch"
            ]
            closure_count += len(closures)
            ambiguous_zero_zero_count += len(ambiguous)
            if len(creations) > 1:
                repeated_creation_pdas.append(pubkey)

            event_time = int(meta["event_time"])
            if meta["side"] == "outgoing":
                if requested_start <= event_time <= as_of_value:
                    if len(creations) != 1:
                        missing_expected_outgoing_creations.append(pubkey)
                elif event_time < requested_start and creations:
                    unexpected_old_message_creations.append(pubkey)

        reached_start = trace.get("reached_requested_start") is True
        exhausted = trace.get("pagination_exhausted") is True
        truncated = trace.get("pagination_truncated") is True
        missing_block_times = int(trace.get("missing_block_time_count") or 0)

        archive_time = trace.get("first_available_block_time")
        archive_covers_start = (
            archive_time is not None and int(archive_time) <= requested_start
        )
        program_creation_observed = any(
            row.get("kind") == "program_account_creation"
            for row in scan["program_transitions"]
        )
        lifetime_fallback_verified = (
            not reached_start
            and exhausted
            and archive_covers_start
            and program_creation_observed
        )
        requested_history_boundary_verified = (
            reached_start or lifetime_fallback_verified
        )

        transaction_count = int(trace.get("transaction_count") or 0)
        successful_count = int(
            trace.get("successful_signature_count_in_scope") or 0
        )
        transaction_fetch_complete = transaction_count == successful_count

        trace_complete = (
            not truncated
            and missing_block_times == 0
            and transaction_fetch_complete
            and requested_history_boundary_verified
        )
        no_closure = closure_count == 0
        no_recreation = (
            not repeated_creation_pdas
            and not unexpected_old_message_creations
        )
        no_ambiguous = ambiguous_zero_zero_count == 0
        expected_outgoing_creation_seen = (
            not missing_expected_outgoing_creations
        )

        all_trace_complete = all_trace_complete and trace_complete
        all_no_closure = all_no_closure and no_closure
        all_no_recreation = all_no_recreation and no_recreation
        all_no_ambiguous = all_no_ambiguous and no_ambiguous
        all_expected_outgoing_creation_seen = (
            all_expected_outgoing_creation_seen
            and expected_outgoing_creation_seen
        )
        all_archive_or_window_coverage = (
            all_archive_or_window_coverage
            and requested_history_boundary_verified
        )

        per_chain[chain] = {
            "message_pda_count": len(universe[chain]),
            "signature_count_in_scope": trace.get("signature_count_in_scope"),
            "successful_signature_count_in_scope": successful_count,
            "transaction_count": transaction_count,
            "reached_requested_start": reached_start,
            "pagination_exhausted": exhausted,
            "pagination_truncated": truncated,
            "first_available_slot": trace.get("first_available_slot"),
            "first_available_block_time": archive_time,
            "archive_covers_requested_start": archive_covers_start,
            "program_account_creation_observed": program_creation_observed,
            "program_lifetime_fallback_verified": lifetime_fallback_verified,
            "requested_history_boundary_verified": requested_history_boundary_verified,
            "transaction_fetch_complete": transaction_fetch_complete,
            "missing_block_time_count": missing_block_times,
            "closure_transition_count": closure_count,
            "repeated_creation_pda_count": len(repeated_creation_pdas),
            "repeated_creation_pdas": sorted(repeated_creation_pdas),
            "unexpected_old_message_creation_count": len(
                unexpected_old_message_creations
            ),
            "unexpected_old_message_creations": sorted(
                unexpected_old_message_creations
            ),
            "ambiguous_zero_zero_touch_count": ambiguous_zero_zero_count,
            "missing_expected_outgoing_creation_count": len(
                missing_expected_outgoing_creations
            ),
            "missing_expected_outgoing_creations": sorted(
                missing_expected_outgoing_creations
            ),
            "no_message_account_closure_observed": no_closure,
            "no_message_account_recreation_observed": no_recreation,
            "no_ambiguous_zero_zero_lifecycle_touch": no_ambiguous,
            "expected_outgoing_creations_verified": expected_outgoing_creation_seen,
            "lifecycle_trace_complete_verified": trace_complete,
            "lifecycle_log_fragment_count": len(
                scan["lifecycle_log_fragments"]
            ),
            "program_transition_evidence": scan["program_transitions"],
            "lifecycle_log_fragments": scan["lifecycle_log_fragments"],
        }

    retention_verified = (
        all_trace_complete
        and all_no_closure
        and all_no_recreation
        and all_no_ambiguous
        and all_expected_outgoing_creation_seen
        and all_archive_or_window_coverage
    )
    bounded_coverage = (
        retention_verified
        and counter_closure.get("counter_account_closure_verified") is True
        and counter_closure.get("current_message_universe_count_closed") is True
    )

    evidence_core = {
        "contract": CONTRACT,
        "program_id": WARP_PROGRAM_ID,
        "as_of": as_of_value,
        "requested_start": requested_start,
        "lookback_seconds": lookback_value,
        "required_flow_lookback_seconds": REQUIRED_FLOW_LOOKBACK_SECONDS,
        "counter_account_closure_prerequisite_verified": True,
        "current_message_universe_count_closed": True,
        "per_chain": per_chain,
        "program_signature_trace_complete_verified": all_trace_complete,
        "requested_history_boundary_verified": all_archive_or_window_coverage,
        "no_message_account_closure_observed": all_no_closure,
        "no_message_account_recreation_observed": all_no_recreation,
        "no_ambiguous_zero_zero_lifecycle_touch": all_no_ambiguous,
        "expected_outgoing_creations_verified": all_expected_outgoing_creation_seen,
        "retention_deletion_semantics_verified": retention_verified,
        "historical_retention_complete_verified": bounded_coverage,
        "requested_window_coverage_verified": bounded_coverage,
        "coverage_complete_verified": bounded_coverage,
        "missing_history_zero_authorized": bounded_coverage,
        "missing_history_zero_scope": (
            "exact_message_universe_requested_lookback_only"
            if bounded_coverage
            else None
        ),
        "bridged_supply_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }
    return {
        **evidence_core,
        "evidence_sha256": _canonical_sha256(evidence_core),
    }


def capture_warp_message_lifecycle_retention(
    *,
    counter_closure: Any,
    message_state: Any,
    as_of: int | None = None,
    lookback_seconds: int = REQUIRED_FLOW_LOOKBACK_SECONDS,
    solana_rpc_url: str = SOLANA_RPC_URL,
    x1_rpc_url: str = X1_RPC_URL,
    requester: Callable[..., Any] = _rpc_request,
    post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    """Capture and evaluate #441 evidence from both finalized read-only RPCs."""

    as_of_value = int(time.time()) if as_of is None else _nonnegative_int(as_of, "as_of")
    traces: dict[str, Any] = {}
    for chain, rpc in (
        ("solana", solana_rpc_url),
        ("x1", x1_rpc_url),
    ):
        history = capture_program_signature_history(
            chain=chain,
            as_of=as_of_value,
            lookback_seconds=lookback_seconds,
            rpc_url=rpc,
            requester=requester,
        )
        traces[chain] = capture_program_transaction_trace(
            history,
            post=post,
        )
    return evaluate_warp_message_lifecycle_retention(
        counter_closure=counter_closure,
        message_state=message_state,
        traces=traces,
        as_of=as_of_value,
        lookback_seconds=lookback_seconds,
    )


__all__ = [
    "CONTRACT",
    "DEFAULT_COMMITMENT",
    "DEFAULT_MAX_PAGES",
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_TRANSACTION_BATCH_SIZE",
    "WarpMessageLifecycleRetentionError",
    "capture_program_signature_history",
    "capture_program_transaction_trace",
    "capture_warp_message_lifecycle_retention",
    "evaluate_warp_message_lifecycle_retention",
]
