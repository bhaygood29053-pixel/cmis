"""Bounded semantic contract for the XDEX CP-Swap pool open-time field.

Scope is deliberately narrow:
- exact X1 XDEX program id
- verified 637-byte pool-state accounts
- Raydium CP-Swap-derived field layout
- offset 373 as the u64 swap-open timestamp
- one-minute XDEX price bars used only to prove that the first provider interval
  covers the verified swap-open instant

This does NOT prove pool-account creation time, first trade time, provider archive
completeness, continuous coverage, or full asset lifetime by itself.
"""

from __future__ import annotations

from collections.abc import Mapping
import struct
from typing import Any


VERSION = "1.0"
PROOF_ID = "cmis.x1.xdex.pool_open_time_semantics.v1"
CHAIN = "x1"
XDEX_PROGRAM_ID = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
POOL_STATE_LEN = 637
OPEN_TIME_OFFSET = 373
RECENT_EPOCH_OFFSET = 381
BAR_INTERVAL_SECONDS = 60

# Accepted source-review evidence for this exact bounded semantic.
# These are review-time provenance references, not runtime network dependencies.
EVIDENCE_REFS = (
    "XDEX-Labs/Audits@7269fbf944b17116251cef6dd45e811f02ff2e23:XDEX_protocol.md",
    "raydium-io/raydium-cp-swap@244e1241f3c8d90eb93f176dfbc35f2605ec5a5c:programs/cp-swap/src/states/pool.rs",
    "raydium-io/raydium-cp-swap@244e1241f3c8d90eb93f176dfbc35f2605ec5a5c:programs/cp-swap/src/instructions/swap_base_input.rs",
    "x1Brains/x1brainsv1@96acdfec107618ebe30916415b425b79fb920553:programs/brains_pairing/src/instructions/match_listing.rs",
)

_SOURCE_GATES = {
    "xdex_audit_raydium_cp_swap_lineage_verified": True,
    "xdex_audit_initialize_open_time_parameter_observed": True,
    "raydium_pool_state_field_order_verified": True,
    "raydium_open_time_swap_gate_semantics_verified": True,
    "independent_xdex_fork_corroboration_verified": True,
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nonnegative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def evaluate_xdex_pool_open_time_semantics(
    account_state: Any,
    structural_report: Any,
    provider_first_bar: Any,
    *,
    asset_mint: Any,
    quote_mint: Any,
) -> dict[str, Any]:
    """Evaluate the exact XDEX pool open-time semantic and first-bar binding."""

    state = _mapping(account_state)
    structural = _mapping(structural_report)
    summary = _mapping(structural.get("summary"))
    decoded = _mapping(structural.get("decoded_state"))
    provider = _mapping(provider_first_bar)

    asset = _text(asset_mint)
    quote = _text(quote_mint)
    data = state.get("data")
    data = data if isinstance(data, bytes) else None

    program_identity_verified = (
        state.get("response_integrity_verified") is True
        and _text(state.get("owner")) == XDEX_PROGRAM_ID
    )
    state_shape_verified = bool(
        program_identity_verified
        and data is not None
        and len(data) == POOL_STATE_LEN
        and state.get("space") in {None, POOL_STATE_LEN}
    )
    structural_role_verified = (
        summary.get("pool_state_structural_role_verified") is True
    )

    mint_0 = _text(decoded.get("mint_0"))
    mint_1 = _text(decoded.get("mint_1"))
    exact_pair_identity_verified = bool(
        asset
        and quote
        and asset != quote
        and {mint_0, mint_1} == {asset, quote}
    )

    open_time = None
    recent_epoch = None
    if state_shape_verified:
        open_time = struct.unpack_from("<Q", data, OPEN_TIME_OFFSET)[0]
        recent_epoch = struct.unpack_from("<Q", data, RECENT_EPOCH_OFFSET)[0]

    timestamp_plausible = bool(
        open_time is not None
        and 1_600_000_000 <= open_time < 2_000_000_000
    )
    source_semantics_verified = all(_SOURCE_GATES.values())

    open_time_semantics_verified = bool(
        state_shape_verified
        and structural_role_verified
        and exact_pair_identity_verified
        and timestamp_plausible
        and source_semantics_verified
    )

    first_bar_start = _nonnegative_int(provider.get("first_observed_at"))
    first_bar_interval_end = (
        first_bar_start + BAR_INTERVAL_SECONDS
        if first_bar_start is not None
        else None
    )
    first_bar_covers_swap_open = bool(
        open_time_semantics_verified
        and first_bar_start is not None
        and first_bar_start <= open_time < first_bar_interval_end
    )

    lifetime_start_anchor_verified = bool(
        open_time_semantics_verified
        and first_bar_covers_swap_open
    )

    anchor = {
        "kind": "first_verified_supported_market_interval",
        "verified": lifetime_start_anchor_verified,
        "observed_at": first_bar_start,
        "interval_seconds": BAR_INTERVAL_SECONDS,
        "market_open_at": open_time,
        "open_time_semantics_verified": open_time_semantics_verified,
    }

    return {
        "proof_id": PROOF_ID,
        "version": VERSION,
        "chain": CHAIN,
        "program_id": XDEX_PROGRAM_ID,
        "program_identity_verified": program_identity_verified,
        "pool_state_length_verified": state_shape_verified,
        "pool_state_structural_role_verified": structural_role_verified,
        "exact_pair_identity_verified": exact_pair_identity_verified,
        "open_time_offset": OPEN_TIME_OFFSET,
        "open_time": open_time,
        "open_time_semantics_verified": open_time_semantics_verified,
        "recent_epoch_offset": RECENT_EPOCH_OFFSET,
        "recent_epoch": recent_epoch,
        "source_semantics_verified": source_semantics_verified,
        "source_gates": dict(_SOURCE_GATES),
        "evidence_refs": list(EVIDENCE_REFS),
        "provider_first_bar_start": first_bar_start,
        "provider_first_bar_interval_seconds": BAR_INTERVAL_SECONDS,
        "provider_first_bar_interval_end": first_bar_interval_end,
        "provider_first_bar_covers_swap_open": first_bar_covers_swap_open,
        "lifetime_start_anchor_verified": lifetime_start_anchor_verified,
        "lifetime_start_anchor": anchor,
        "full_asset_lifetime_verified": False,
        "continuous_coverage_verified": False,
        "limitations": [
            "open_time_is_swap_enable_time_not_pool_account_creation_time",
            "open_time_is_not_first_trade_timestamp",
            "provider_archive_completeness_not_proven_here",
            "continuous_price_coverage_not_proven_here",
        ],
    }


__all__ = [
    "BAR_INTERVAL_SECONDS",
    "EVIDENCE_REFS",
    "OPEN_TIME_OFFSET",
    "POOL_STATE_LEN",
    "PROOF_ID",
    "RECENT_EPOCH_OFFSET",
    "VERSION",
    "XDEX_PROGRAM_ID",
    "evaluate_xdex_pool_open_time_semantics",
]
