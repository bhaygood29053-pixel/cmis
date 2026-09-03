"""Read-only Warp transaction-history discovery helpers for Issue #433.

This module intentionally does not promote transaction lifecycle semantics.  It
sanitizes live read-only API responses so CI can inspect exact field presence,
pagination metadata, and per-transaction signature/message structure without
committing raw response bodies or guardian signatures.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

CONTRACT = "warp_transaction_history_discovery/v1"
BASE_URL = "https://api.bridge.mainnet.x1.xyz"
TRANSACTIONS_PATH = "/transactions"
SOURCE_PROVENANCE = {
    "candidate_base_url": BASE_URL,
    "public_corroboration_repository": "nibty/warp-bridge-dashboard",
    "public_corroboration_commit": "6a9ea7187879778d3a46e313d1fec177541adce8",
    "public_corroboration_path": "docs/superpowers/specs/2026-07-17-offchain-partial-signatures-design.md",
    "trust": "candidate_until_live_provenance_and_semantics_are_accepted",
}

_ALLOWED_STATUSES = {"pending", "signing", "submitted", "executed", "failed"}


class WarpTransactionHistoryDiscoveryError(ValueError):
    """Raised when discovery input is malformed."""


def build_transactions_url(*, status: str, limit: int = 5, page: int = 1) -> str:
    status_value = str(status or "").strip().casefold()
    if status_value not in _ALLOWED_STATUSES:
        raise WarpTransactionHistoryDiscoveryError("unsupported status")
    if isinstance(limit, bool) or not isinstance(limit, int) or not (1 <= limit <= 500):
        raise WarpTransactionHistoryDiscoveryError("limit must be an integer from 1 to 500")
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise WarpTransactionHistoryDiscoveryError("page must be a positive integer")
    return f"{BASE_URL}{TRANSACTIONS_PATH}?status={status_value}&limit={limit}&page={page}"


def build_signatures_url(tx_sig: str) -> str:
    value = str(tx_sig or "").strip()
    if not value:
        raise WarpTransactionHistoryDiscoveryError("tx_sig is required")
    if "/" in value or "?" in value or "#" in value:
        raise WarpTransactionHistoryDiscoveryError("tx_sig contains invalid URL characters")
    return f"{BASE_URL}{TRANSACTIONS_PATH}/{value}/signatures"


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WarpTransactionHistoryDiscoveryError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise WarpTransactionHistoryDiscoveryError(f"{field} must be a sequence")
    return value


def _sanitized_transaction(record: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "txSig",
        "from",
        "to",
        "status",
        "token",
        "amount",
        "sender",
        "recipient",
        "sourceSlot",
        "timestamp",
        "signaturesCollected",
        "signaturesRequired",
    )
    return {
        key: record.get(key)
        for key in allowed
        if key in record
    }


def summarize_transactions_page(payload: Any, *, requested_status: str) -> dict[str, Any]:
    document = _mapping(payload, "payload")
    rows = _sequence(document.get("transactions"), "transactions")
    status = str(requested_status or "").strip().casefold()
    if status not in _ALLOWED_STATUSES:
        raise WarpTransactionHistoryDiscoveryError("unsupported requested_status")

    sanitized = []
    field_union: set[str] = set()
    status_values: set[str] = set()
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        field_union.update(str(key) for key in item.keys())
        if item.get("status") is not None:
            status_values.add(str(item.get("status")))
        sanitized.append(_sanitized_transaction(item))

    metadata = {}
    for key in ("total", "page", "pageSize", "limit", "hasMore", "nextPage"):
        if key in document:
            metadata[key] = document.get(key)

    return {
        "contract": CONTRACT,
        "source_url": build_transactions_url(status=status, limit=5, page=1),
        "requested_status": status,
        "response_sha256": canonical_sha256(document),
        "top_level_keys": sorted(str(key) for key in document.keys()),
        "transaction_count": len(rows),
        "transaction_record_field_union": sorted(field_union),
        "observed_status_values": sorted(status_values),
        "pagination_metadata": metadata,
        "sample_transactions": sanitized[:5],
        "source_provenance": dict(SOURCE_PROVENANCE),
        "field_semantics_verified": False,
        "pagination_semantics_verified": False,
        "coverage_complete_verified": False,
        "flow_event_normalization_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


def summarize_signatures_response(payload: Any, *, tx_sig: str) -> dict[str, Any]:
    document = _mapping(payload, "payload")
    signatures = _sequence(document.get("signatures"), "signatures")

    signature_field_union: set[str] = set()
    message_field_union: set[str] = set()
    messages = []
    guardian_pubkeys = []
    for item in signatures:
        if not isinstance(item, Mapping):
            continue
        signature_field_union.update(str(key) for key in item.keys())
        if item.get("guardianPubkey") is not None:
            guardian_pubkeys.append(str(item.get("guardianPubkey")))
        message = item.get("message")
        if isinstance(message, Mapping):
            message_field_union.update(str(key) for key in message.keys())
            safe = {}
            for key in (
                "seq",
                "sourceChainId",
                "destChainId",
                "guardianSetIndex",
                "sender",
                "token",
                "amount",
                "timestamp",
            ):
                if key in message:
                    safe[key] = message.get(key)
            messages.append(safe)

    return {
        "contract": CONTRACT,
        "source_url": build_signatures_url(tx_sig),
        "tx_sig": str(document.get("txSig") or tx_sig),
        "response_sha256": canonical_sha256(document),
        "signature_count": len(signatures),
        "signature_record_field_union": sorted(signature_field_union),
        "message_field_union": sorted(message_field_union),
        "guardian_pubkeys": guardian_pubkeys,
        "sample_messages": messages[:5],
        "raw_guardian_signatures_retained": False,
        "message_semantics_verified": False,
        "flow_event_normalization_authorized": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "BASE_URL",
    "CONTRACT",
    "SOURCE_PROVENANCE",
    "WarpTransactionHistoryDiscoveryError",
    "build_signatures_url",
    "build_transactions_url",
    "canonical_sha256",
    "summarize_signatures_response",
    "summarize_transactions_page",
]
