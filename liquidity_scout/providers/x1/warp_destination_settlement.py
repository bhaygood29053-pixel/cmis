"""Canonical X1 RPC corroboration for one Warp destination execution."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from liquidity_scout.providers.x1.rpc import (
    DEFAULT_X1_RPC_URL,
    rpc_request,
)

CONTRACT = "warp_destination_rpc_settlement/v1"


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be positive")
    return parsed


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def collect_warp_destination_settlement_evidence(
    *,
    transaction_signature: Any,
    slot: Any,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    rpc_call: Callable[..., Any] = rpc_request,
) -> dict[str, Any]:
    """Verify one provider-declared destination tx/slot against finalized X1 RPC."""

    signature = _text(transaction_signature, "transaction_signature")
    expected_slot = _positive_int(slot, "slot")

    transaction = rpc_call(
        "getTransaction",
        [
            signature,
            {
                "encoding": "jsonParsed",
                "commitment": "finalized",
                "maxSupportedTransactionVersion": 0,
            },
        ],
        rpc_url=rpc_url,
    )
    block_time = rpc_call(
        "getBlockTime",
        [expected_slot],
        rpc_url=rpc_url,
    )

    transaction_found = isinstance(transaction, dict)
    observed_slot = transaction.get("slot") if transaction_found else None
    slot_verified = (
        isinstance(observed_slot, int)
        and not isinstance(observed_slot, bool)
        and observed_slot == expected_slot
    )

    tx_body = transaction.get("transaction") if transaction_found else None
    signatures = tx_body.get("signatures") if isinstance(tx_body, dict) else None
    signature_verified = bool(
        isinstance(signatures, list)
        and signatures
        and str(signatures[0] or "").strip() == signature
    )

    meta = transaction.get("meta") if transaction_found else None
    transaction_succeeded = bool(
        isinstance(meta, dict)
        and "err" in meta
        and meta.get("err") is None
    )

    transaction_block_time = (
        transaction.get("blockTime") if transaction_found else None
    )
    block_time_numeric = (
        isinstance(block_time, (int, float))
        and not isinstance(block_time, bool)
        and block_time > 0
    )
    transaction_block_time_numeric = (
        isinstance(transaction_block_time, (int, float))
        and not isinstance(transaction_block_time, bool)
        and transaction_block_time > 0
    )
    block_time_matches_transaction = bool(
        block_time_numeric
        and (
            not transaction_block_time_numeric
            or float(transaction_block_time) == float(block_time)
        )
    )
    block_time_verified = bool(
        block_time_numeric and block_time_matches_transaction
    )

    settlement_verified = bool(
        transaction_found
        and slot_verified
        and signature_verified
        and transaction_succeeded
        and block_time_verified
    )

    core = {
        "contract": CONTRACT,
        "transaction_signature": signature,
        "slot": expected_slot,
        "transaction_found": transaction_found,
        "slot_verified": slot_verified,
        "signature_verified": signature_verified,
        "transaction_succeeded": transaction_succeeded,
        "finalized": settlement_verified,
        "block_time": float(block_time) if block_time_numeric else None,
        "block_time_verified": block_time_verified,
        "block_time_matches_transaction": block_time_matches_transaction,
        "settlement_verified": settlement_verified,
    }

    return {
        **core,
        "evidence_sha256": _canonical_sha256(core),
        "source": "canonical X1 RPC getTransaction(finalized)+getBlockTime",
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT",
    "collect_warp_destination_settlement_evidence",
]
