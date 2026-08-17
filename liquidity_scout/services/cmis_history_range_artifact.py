"""Sanitized retained-artifact contract for bounded X1 history-range probes.

This module summarizes an already-produced ``history_range_probe`` result. It
never performs provider/RPC collection, never decides archival completeness,
and never promotes provider range semantics. Raw transaction signatures and
provider payloads are intentionally excluded from the retained artifact.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SERVICE = "x1_history_range_evidence"
VERSION = "1.0"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _bool(value: Any) -> bool:
    return value is True


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _number_or_none(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _window(value: Any) -> dict[str, Any]:
    raw = _mapping(value)
    return {
        "label": _text(raw.get("label")),
        "duration_seconds": _number_or_none(raw.get("duration_seconds")),
        "start_epoch": _number_or_none(raw.get("start_epoch")),
        "start_utc": _text(raw.get("start_utc")),
        "end_epoch": _number_or_none(raw.get("end_epoch")),
        "end_utc": _text(raw.get("end_utc")),
        "membership_basis": _text(raw.get("membership_basis")),
    }


def _provider_history(value: Any) -> dict[str, Any]:
    raw = _mapping(value)
    return {
        "returned_row_count": _int_or_none(raw.get("returned_row_count")),
        "provider_total_observed": raw.get("provider_total_raw"),
        "provider_last_updated_observed": raw.get("provider_last_updated_raw"),
        "transport_pagination_or_range_verified": _bool(
            raw.get("transport_pagination_or_range_verified")
        ),
    }


def _requested_window_chain(value: Any) -> dict[str, Any]:
    raw = _mapping(value)
    return {
        "start_epoch": _number_or_none(raw.get("start_epoch")),
        "start_utc": _text(raw.get("start_utc")),
        "end_epoch": _number_or_none(raw.get("end_epoch")),
        "end_utc": _text(raw.get("end_utc")),
        "membership_basis": _text(raw.get("membership_basis")),
        "signature_count": _int_or_none(raw.get("signature_count")),
        "successful_signature_count": _int_or_none(
            raw.get("successful_signature_count")
        ),
        "failed_signature_count": _int_or_none(raw.get("failed_signature_count")),
        "scanned_entries_without_block_time": _int_or_none(
            raw.get("scanned_entries_without_block_time")
        ),
        "oldest_signature_time_utc": _text(raw.get("oldest_signature_time_utc")),
        "newest_signature_time_utc": _text(raw.get("newest_signature_time_utc")),
    }


def _proof_scan(value: Any) -> dict[str, Any]:
    raw = _mapping(value)
    # Deliberately omit address, newest_signature, oldest_signature, and entries.
    return {
        "source": _text(raw.get("source")),
        "scan_start_epoch": _number_or_none(raw.get("scan_start_epoch")),
        "scan_start_utc": _text(raw.get("scan_start_utc")),
        "scan_end_epoch": _number_or_none(raw.get("scan_end_epoch")),
        "scan_end_utc": _text(raw.get("scan_end_utc")),
        "page_size": _int_or_none(raw.get("page_size")),
        "max_signatures": _int_or_none(raw.get("max_signatures")),
        "pages_fetched": _int_or_none(raw.get("pages_fetched")),
        "signature_count": _int_or_none(raw.get("signature_count")),
        "successful_signature_count": _int_or_none(
            raw.get("successful_signature_count")
        ),
        "failed_signature_count": _int_or_none(raw.get("failed_signature_count")),
        "scan_interval_signature_count": _int_or_none(
            raw.get("scan_interval_signature_count")
        ),
        "rpc_errors": _int_or_none(raw.get("rpc_errors")),
        "malformed_entries": _int_or_none(raw.get("malformed_entries")),
        "duplicate_signatures": _int_or_none(raw.get("duplicate_signatures")),
        "cursor_stalls": _int_or_none(raw.get("cursor_stalls")),
        "history_exhausted": _bool(raw.get("history_exhausted")),
        "start_boundary_reached": _bool(raw.get("start_boundary_reached")),
        "bound_reached": _bool(raw.get("bound_reached")),
        "slot_order_verified": _bool(raw.get("slot_order_verified")),
        "block_time_complete": _bool(raw.get("block_time_complete")),
        "block_time_order_verified": _bool(raw.get("block_time_order_verified")),
        "integrity_verified": _bool(raw.get("integrity_verified")),
        "range_proven": _bool(raw.get("range_proven")),
        "coverage_scope": _text(raw.get("coverage_scope")),
        "newest_slot": _int_or_none(raw.get("newest_slot")),
        "newest_block_time_utc": _text(raw.get("newest_block_time_utc")),
        "oldest_slot": _int_or_none(raw.get("oldest_slot")),
        "oldest_block_time_utc": _text(raw.get("oldest_block_time_utc")),
    }


def _comparison(value: Any) -> dict[str, Any]:
    raw = _mapping(value)
    if raw.get("provider_range_contract_verified") is True:
        raise ValueError(
            "history evidence artifact cannot accept provider range promotion"
        )
    return {
        "provider_row_count": _int_or_none(raw.get("provider_row_count")),
        "provider_valid_identity_row_count": _int_or_none(
            raw.get("provider_valid_identity_row_count")
        ),
        "provider_malformed_row_count": _int_or_none(
            raw.get("provider_malformed_row_count")
        ),
        "provider_duplicate_signature_count": _int_or_none(
            raw.get("provider_duplicate_signature_count")
        ),
        "provider_slot_order_newest_to_oldest_observed": _bool(
            raw.get("provider_slot_order_newest_to_oldest_observed")
        ),
        "provider_time_order_newest_to_oldest_observed": _bool(
            raw.get("provider_time_order_newest_to_oldest_observed")
        ),
        "provider_ordering_observed_consistent": _bool(
            raw.get("provider_ordering_observed_consistent")
        ),
        "provider_oldest_timestamp_utc": _text(
            raw.get("provider_oldest_timestamp_utc")
        ),
        "provider_newest_timestamp_utc": _text(
            raw.get("provider_newest_timestamp_utc")
        ),
        "provider_signatures_found_in_chain_scan": _int_or_none(
            raw.get("provider_signatures_found_in_chain_scan")
        ),
        "provider_chain_slot_match_count": _int_or_none(
            raw.get("provider_chain_slot_match_count")
        ),
        "provider_chain_timestamp_match_count": _int_or_none(
            raw.get("provider_chain_timestamp_match_count")
        ),
        "provider_chain_timestamp_comparable_count": _int_or_none(
            raw.get("provider_chain_timestamp_comparable_count")
        ),
        "overlapping_identity_verified": _bool(
            raw.get("overlapping_identity_verified")
        ),
        "provider_range_contract_verified": False,
        "provider_range_contract_reason": _text(
            raw.get("provider_range_contract_reason")
        ),
    }


def _pool(value: Any) -> dict[str, Any]:
    raw = _mapping(value)
    return {
        "pool_address": _text(raw.get("pool_address")),
        "pair": _text(raw.get("pair")),
        "provider_history": _provider_history(raw.get("provider_history")),
        "requested_window_chain": _requested_window_chain(
            raw.get("requested_window_chain")
        ),
        "proof_scan": _proof_scan(raw.get("proof_scan")),
        "provider_chain_comparison": _comparison(
            raw.get("provider_chain_comparison")
        ),
    }


def sanitize_history_range_probe_result(result: Any) -> dict[str, Any]:
    """Return a bounded retained artifact from one history-range probe result."""
    raw = _mapping(result)
    if raw.get("service") != "history_range_probe" or raw.get("chain") != "x1":
        raise ValueError("expected an X1 history_range_probe result")

    summary = _mapping(raw.get("summary"))
    if summary.get("provider_range_contract_verified") is True:
        raise ValueError(
            "history evidence artifact cannot accept provider range promotion"
        )
    if summary.get("cmis_window_completion_promoted") is True:
        raise ValueError(
            "history evidence artifact cannot accept CMIS window promotion"
        )

    pools_raw = raw.get("pools")
    pools = [_pool(item) for item in pools_raw] if isinstance(pools_raw, list) else []

    asset_raw = _mapping(raw.get("asset"))
    warnings: list[str] = []
    if not pools:
        warnings.append("no_selected_pool_history_evidence")
    if any(
        not item["provider_chain_comparison"]["overlapping_identity_verified"]
        for item in pools
    ):
        warnings.append("provider_chain_overlap_identity_incomplete")
    if any(not item["proof_scan"]["range_proven"] for item in pools):
        warnings.append("one_or_more_rpc_proof_ranges_incomplete")

    return {
        "service": SERVICE,
        "version": VERSION,
        "chain": "x1",
        "status": _text(raw.get("status")) or "partial",
        "asset": {
            "symbol": _text(asset_raw.get("symbol")),
            "mint": _text(asset_raw.get("mint") or asset_raw.get("address")),
        },
        "requested_window": _window(raw.get("requested_window")),
        "market_snapshot_status": _text(raw.get("market_snapshot_status")),
        "matched_pool_count": _int_or_none(raw.get("matched_pool_count")),
        "selected_pool_count": _int_or_none(raw.get("selected_pool_count")),
        "pools": pools,
        "summary": {
            "all_selected_pool_proof_ranges_proven": _bool(
                summary.get("all_selected_pool_proof_ranges_proven")
            ),
            "all_provider_ordering_observed_consistent": _bool(
                summary.get("all_provider_ordering_observed_consistent")
            ),
            "all_overlapping_provider_chain_identity_verified": _bool(
                summary.get("all_overlapping_provider_chain_identity_verified")
            ),
            "provider_range_contract_verified": False,
            "cmis_window_completion_promoted": False,
            "interpretation": _text(summary.get("interpretation")),
        },
        "raw_signatures_retained": False,
        "raw_provider_payloads_retained": False,
        "provider_range_contract_verified": False,
        "cmis_promotable": False,
        "warnings": warnings,
        "errors": [],
    }


__all__ = [
    "SERVICE",
    "VERSION",
    "sanitize_history_range_probe_result",
]
