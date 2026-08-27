"""Fail-closed X1 RPC-visible mint-address history coverage.

This module reports only what the configured X1 RPC can prove for the exact
mint address supplied by CMIS. It deliberately does not promote mint-address
history into asset-wide transfer/activity coverage or complete asset lifetime.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from typing import Any, Callable

from .history_range import (
    DEFAULT_MAX_SIGNATURES,
    DEFAULT_PAGE_SIZE,
    scan_address_history_range,
)


CHAIN = "x1"
COVERAGE_SCOPE = "x1_rpc_visible_mint_address_history"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clock_epoch(clock: Callable[[], Any]) -> float:
    if not callable(clock):
        raise ValueError("clock must be callable")
    value = clock()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("clock must return a non-negative finite epoch")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError("clock must return a non-negative finite epoch")
    return parsed


def _unavailable(mint: str, reason: str, *, details: str | None = None) -> dict[str, Any]:
    result = {
        "chain": CHAIN,
        "status": "unavailable",
        "reason": reason,
        "coverage_scope": COVERAGE_SCOPE,
        "subject_kind": "mint_address",
        "mint": mint,
        "source": None,
        "first_available_block": None,
        "rpc_block_boundary_verified": False,
        "signature_count": 0,
        "pages_fetched": 0,
        "rpc_history_exhausted": False,
        "scan_integrity_verified": False,
        "safety_bound_reached": False,
        "rpc_visible_mint_history_complete": False,
        "asset_wide_activity_verified": False,
        "asset_lifetime_start_verified": False,
        "full_asset_lifetime_verified": False,
        "continuous_coverage_verified": False,
        "archival_completeness_verified": False,
        "newest_verified_slot": None,
        "oldest_verified_slot": None,
        "newest_verified_time_utc": None,
        "oldest_verified_time_utc": None,
        "limitations": [
            "mint_address_history_is_not_asset_wide_transfer_history",
            "token_account_activity_can_exist_without_mint_address_membership",
            "rpc_block_boundary_does_not_prove_signature_index_archival_completeness",
            "asset_creation_or_first_trade_time_not_proven_by_this_coverage",
            "continuous_asset_activity_coverage_not_verified",
        ],
    }
    if details:
        result["details"] = details
    return result


def build_rpc_visible_mint_history_coverage(
    mint: Any,
    *,
    rpc_provider: Any,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_signatures: int = DEFAULT_MAX_SIGNATURES,
    clock: Callable[[], Any] = time.time,
) -> dict[str, Any]:
    """Measure complete or partial RPC-visible history for one exact mint address."""

    mint_text = _text(mint)
    if not mint_text:
        raise ValueError("mint is required")

    if rpc_provider is None:
        return _unavailable(mint_text, "x1_rpc_provider_not_configured")

    request = getattr(rpc_provider, "request", None)
    get_first_available_block = getattr(
        rpc_provider,
        "get_first_available_block",
        None,
    )
    if not callable(request) or not callable(get_first_available_block):
        return _unavailable(mint_text, "x1_rpc_history_interface_unavailable")

    boundary = None
    boundary_error = None
    try:
        boundary = get_first_available_block()
    except Exception as exc:
        boundary_error = f"{type(exc).__name__}: {exc}"

    boundary_verified = bool(
        isinstance(boundary, Mapping)
        and boundary.get("history_boundary_verified") is True
        and isinstance(boundary.get("first_available_block"), int)
        and not isinstance(boundary.get("first_available_block"), bool)
        and boundary.get("first_available_block") >= 0
    )

    scan = scan_address_history_range(
        mint_text,
        start_epoch=0,
        end_epoch=_clock_epoch(clock),
        rpc=request,
        page_size=page_size,
        max_signatures=max_signatures,
    )

    signature_count = int(scan.get("signature_count") or 0)
    history_exhausted = scan.get("history_exhausted") is True
    integrity_verified = scan.get("integrity_verified") is True
    bound_reached = scan.get("bound_reached") is True
    range_proven = scan.get("range_proven") is True

    full = bool(
        signature_count > 0
        and boundary_verified
        and history_exhausted
        and integrity_verified
        and range_proven
        and not bound_reached
    )

    if full:
        status = "full"
        reason = "rpc_visible_mint_address_history_exhausted"
    elif signature_count <= 0:
        status = "unavailable"
        reason = (
            "rpc_visible_mint_address_history_not_observed"
            if not scan.get("rpc_errors")
            else "x1_rpc_history_scan_failed"
        )
    else:
        status = "partial"
        if bound_reached:
            reason = "rpc_visible_mint_address_history_safety_bound_reached"
        elif scan.get("rpc_errors"):
            reason = "x1_rpc_history_scan_failed"
        elif not integrity_verified:
            reason = "rpc_visible_mint_address_history_integrity_unverified"
        elif not boundary_verified:
            reason = "x1_rpc_block_boundary_unverified"
        elif not history_exhausted:
            reason = "rpc_visible_mint_address_history_not_exhausted"
        else:
            reason = "rpc_visible_mint_address_history_partial"

    result = {
        "chain": CHAIN,
        "status": status,
        "reason": reason,
        "coverage_scope": COVERAGE_SCOPE,
        "subject_kind": "mint_address",
        "mint": mint_text,
        "source": "X1 RPC",
        "first_available_block": (
            boundary.get("first_available_block") if boundary_verified else None
        ),
        "rpc_block_boundary_verified": boundary_verified,
        "signature_count": signature_count,
        "successful_signature_count": int(
            scan.get("successful_signature_count") or 0
        ),
        "failed_signature_count": int(scan.get("failed_signature_count") or 0),
        "pages_fetched": int(scan.get("pages_fetched") or 0),
        "rpc_errors": int(scan.get("rpc_errors") or 0),
        "malformed_entries": int(scan.get("malformed_entries") or 0),
        "duplicate_signatures": int(scan.get("duplicate_signatures") or 0),
        "cursor_stalls": int(scan.get("cursor_stalls") or 0),
        "rpc_history_exhausted": history_exhausted,
        "scan_integrity_verified": integrity_verified,
        "scan_range_proven": range_proven,
        "safety_bound_reached": bound_reached,
        "page_size": scan.get("page_size"),
        "max_signatures": scan.get("max_signatures"),
        "rpc_visible_mint_history_complete": full,
        "asset_wide_activity_verified": False,
        "asset_lifetime_start_verified": False,
        "full_asset_lifetime_verified": False,
        "continuous_coverage_verified": False,
        "archival_completeness_verified": False,
        "newest_verified_signature": scan.get("newest_signature"),
        "newest_verified_slot": scan.get("newest_slot"),
        "newest_verified_time_utc": scan.get("newest_block_time_utc"),
        "oldest_verified_signature": scan.get("oldest_signature"),
        "oldest_verified_slot": scan.get("oldest_slot"),
        "oldest_verified_time_utc": scan.get("oldest_block_time_utc"),
        "limitations": [
            "mint_address_history_is_not_asset_wide_transfer_history",
            "token_account_activity_can_exist_without_mint_address_membership",
            "rpc_block_boundary_does_not_prove_signature_index_archival_completeness",
            "asset_creation_or_first_trade_time_not_proven_by_this_coverage",
            "continuous_asset_activity_coverage_not_verified",
        ],
    }
    if boundary_error:
        result["rpc_block_boundary_error"] = boundary_error
    return result


__all__ = [
    "CHAIN",
    "COVERAGE_SCOPE",
    "build_rpc_visible_mint_history_coverage",
]
