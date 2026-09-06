"""Bounded fact-time evidence for X1.Ninja priceNative.

Collect repeated snapshots of the same exact X1 pools while preserving:
- CMIS collection time;
- X1 RPC slot/block-time brackets;
- X1.Ninja global lastUpdated raw value;
- X1.Ninja row lastSyncedAt raw value;
- provider priceNative / pooledBase / pooledQuote;
- provider liquidity / rolling 24h volume / rolling 24h transaction candidates;
- independently read X1 RPC gross vault reserves and their exact ratio.

This module intentionally does not assign timestamp units or source semantics.
It is an evidence collector for #345, not a price or liquidity promotion path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
import time
from typing import Any, Callable

from liquidity_scout.providers.x1.candidate_pool_role import extract_pubkey_at
from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_pool_catalog import fetch_pool_catalog_raw
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.program_accounts import RECOGNIZED_AMM_PROGRAM_IDS
from liquidity_scout.providers.x1.rpc import (
    DEFAULT_X1_RPC_URL,
    get_block_time,
    get_token_account_info,
    rpc_request,
)


VERSION = "1.0"
POOL_STATE_LENGTH = 637
MINT_OFFSETS = (168, 200)
VAULT_OFFSETS = (72, 104)


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _decimal(value: Any, *, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be finite")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be finite")
    return parsed


def _scaled(raw_amount: Any, decimals: Any) -> Decimal:
    raw = _text(raw_amount)
    if raw is None or not raw.isdigit():
        raise ValueError("vault raw amount must be a non-negative integer string")
    if isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0:
        raise ValueError("vault decimals must be a non-negative integer")
    return Decimal(raw) / (Decimal(10) ** decimals)


def _slot_record(
    *,
    requester: Callable[..., Any],
    block_time_fetcher: Callable[..., Mapping[str, Any]],
    rpc_url: str,
) -> dict[str, Any]:
    slot = requester(
        "getSlot",
        [{"commitment": "confirmed"}],
        rpc_url=rpc_url,
    )
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise ValueError("X1 RPC getSlot returned a malformed result")
    block = block_time_fetcher(slot, rpc_url=rpc_url)
    return {
        "slot": slot,
        "block_time": block.get("block_time") if isinstance(block, Mapping) else None,
        "block_time_verified": (
            isinstance(block, Mapping)
            and block.get("block_time_verified") is True
        ),
    }


def _row_address(row: Mapping[str, Any]) -> str | None:
    return _text(
        row.get("address")
        or row.get("poolAddress")
        or row.get("pool_address")
        or row.get("id")
    )


def _rpc_pool_reserve_ratio(
    pool_address: str,
    *,
    account_state_fetcher: Callable[..., Mapping[str, Any]],
    token_account_fetcher: Callable[..., Mapping[str, Any]],
    rpc_url: str,
) -> dict[str, Any]:
    state = account_state_fetcher(pool_address, rpc_url=rpc_url)
    data = state.get("data") if isinstance(state, Mapping) else None
    owner = _text(state.get("owner")) if isinstance(state, Mapping) else None
    if not isinstance(data, bytes) or len(data) != POOL_STATE_LENGTH:
        raise ValueError("pool does not match accepted 637-byte XDEX state")
    if owner not in set(RECOGNIZED_AMM_PROGRAM_IDS):
        raise ValueError("pool owner is not an accepted XDEX program")

    mint_0 = extract_pubkey_at(data, MINT_OFFSETS[0])
    mint_1 = extract_pubkey_at(data, MINT_OFFSETS[1])
    vault_0 = extract_pubkey_at(data, VAULT_OFFSETS[0])
    vault_1 = extract_pubkey_at(data, VAULT_OFFSETS[1])

    v0 = token_account_fetcher(vault_0, rpc_url=rpc_url)
    v1 = token_account_fetcher(vault_1, rpc_url=rpc_url)
    if not isinstance(v0, Mapping) or not isinstance(v1, Mapping):
        raise ValueError("vault token-account evidence unavailable")
    if v0.get("identity_verified") is not True or v1.get("identity_verified") is not True:
        raise ValueError("vault token-account identity unverified")
    if _text(v0.get("mint")) != mint_0 or _text(v1.get("mint")) != mint_1:
        raise ValueError("vault mint does not match decoded pool state")

    reserve_0 = _scaled(v0.get("raw_amount"), v0.get("decimals"))
    reserve_1 = _scaled(v1.get("raw_amount"), v1.get("decimals"))
    if reserve_0 <= 0 or reserve_1 <= 0:
        raise ValueError("gross vault reserves must be positive")

    return {
        "mint_0": mint_0,
        "mint_1": mint_1,
        "vault_0": vault_0,
        "vault_1": vault_1,
        "gross_reserve_0": format(reserve_0, "f"),
        "gross_reserve_1": format(reserve_1, "f"),
        "gross_quote_per_base_ratio": format(reserve_0 / reserve_1, "f"),
        "rpc_reserve_ratio_verified": True,
    }


def collect_ninja_price_fact_time_snapshot(
    *,
    pool_addresses: Sequence[str],
    rpc_url: str = DEFAULT_X1_RPC_URL,
    pool_fetcher: Callable[..., Any] = fetch_all_pools,
    catalog_probe: Callable[..., Mapping[str, Any]] = fetch_pool_catalog_raw,
    account_state_fetcher: Callable[..., Mapping[str, Any]] = fetch_account_state,
    token_account_fetcher: Callable[..., Mapping[str, Any]] = get_token_account_info,
    requester: Callable[..., Any] = rpc_request,
    block_time_fetcher: Callable[..., Mapping[str, Any]] = get_block_time,
    clock: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Collect one slot-bracketed snapshot for exact current pool addresses."""

    addresses = []
    seen = set()
    for raw in pool_addresses:
        address = _text(raw)
        if address and address not in seen:
            seen.add(address)
            addresses.append(address)
    if not addresses:
        raise ValueError("at least one pool address is required")

    before = _slot_record(
        requester=requester,
        block_time_fetcher=block_time_fetcher,
        rpc_url=rpc_url,
    )
    observed_at_start = clock()

    pools, provider_xnt_price_usd = pool_fetcher(sleep_seconds=0)
    by_address = {
        _row_address(row): row
        for row in pools
        if isinstance(row, Mapping) and _row_address(row)
    }

    catalog = catalog_probe(limit=1)
    raw_response = catalog.get("raw_response") if isinstance(catalog, Mapping) else {}
    global_last_updated = (
        raw_response.get("lastUpdated")
        if isinstance(raw_response, Mapping) and "lastUpdated" in raw_response
        else None
    )

    observations = []
    for address in addresses:
        row = by_address.get(address)
        if not isinstance(row, Mapping):
            observations.append(
                {
                    "pool_address": address,
                    "status": "unavailable",
                    "error": "pool_missing_from_current_ninja_catalog",
                }
            )
            continue
        try:
            rpc = _rpc_pool_reserve_ratio(
                address,
                account_state_fetcher=account_state_fetcher,
                token_account_fetcher=token_account_fetcher,
                rpc_url=rpc_url,
            )
            provider_price = _decimal(row.get("priceNative"), name="priceNative")
            ratio = _decimal(
                rpc.get("gross_quote_per_base_ratio"),
                name="rpc reserve ratio",
            )
            absolute_error = abs(provider_price - ratio)
            relative_error = absolute_error / abs(ratio) if ratio != 0 else None
            observations.append(
                {
                    "pool_address": address,
                    "status": "ok",
                    "provider": {
                        "priceNative": row.get("priceNative"),
                        "pooledBase": row.get("pooledBase"),
                        "pooledQuote": row.get("pooledQuote"),
                        "liquidity": row.get("liquidity"),
                        "volume24h": row.get("volume24h"),
                        "txns24h": row.get("txns24h"),
                        "transactions24h": row.get("transactions24h"),
                        "lastSyncedAt_raw": row.get("lastSyncedAt"),
                        "createdAt_raw": row.get("createdAt"),
                    },
                    "rpc": rpc,
                    "price_vs_rpc_ratio": {
                        "absolute_error": format(absolute_error, "f"),
                        "relative_error": (
                            format(relative_error, "e")
                            if relative_error is not None
                            else None
                        ),
                    },
                }
            )
        except Exception as exc:
            observations.append(
                {
                    "pool_address": address,
                    "status": "unavailable",
                    "error": f"{type(exc).__name__}: {exc}",
                    "provider": {
                        "priceNative": row.get("priceNative"),
                        "pooledBase": row.get("pooledBase"),
                        "pooledQuote": row.get("pooledQuote"),
                        "liquidity": row.get("liquidity"),
                        "volume24h": row.get("volume24h"),
                        "txns24h": row.get("txns24h"),
                        "transactions24h": row.get("transactions24h"),
                        "lastSyncedAt_raw": row.get("lastSyncedAt"),
                        "createdAt_raw": row.get("createdAt"),
                    },
                }
            )

    observed_at_end = clock()
    after = _slot_record(
        requester=requester,
        block_time_fetcher=block_time_fetcher,
        rpc_url=rpc_url,
    )

    return {
        "service": "x1_ninja_price_fact_time_snapshot",
        "version": VERSION,
        "chain": "x1",
        "status": "ok" if all(row.get("status") == "ok" for row in observations) else "partial",
        "observed_at_start": observed_at_start,
        "observed_at_end": observed_at_end,
        "rpc_slot_bracket": {
            "before": before,
            "after": after,
        },
        "provider_xnt_price_usd": provider_xnt_price_usd,
        "provider_timestamp_candidates": {
            "global_lastUpdated_raw": global_last_updated,
            "global_lastUpdated_semantics_verified": False,
            "row_lastSyncedAt_semantics_verified": False,
            "timestamp_units_verified": False,
        },
        "pools": observations,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "same_fact_temporal_alignment_verified": False,
        "price_native_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def classify_ninja_price_fact_time_series(
    snapshots: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Describe repeated observations without inventing timestamp semantics."""

    usable = [
        dict(row)
        for row in snapshots
        if isinstance(row, Mapping)
    ]
    if len(usable) < 3:
        raise ValueError("at least three snapshots are required")

    addresses = []
    seen = set()
    for snap in usable:
        for row in snap.get("pools") or []:
            if not isinstance(row, Mapping):
                continue
            address = _text(row.get("pool_address"))
            if address and address not in seen:
                seen.add(address)
                addresses.append(address)

    pool_series = []
    for address in addresses:
        rows = []
        for index, snap in enumerate(usable):
            match = None
            for raw in snap.get("pools") or []:
                if isinstance(raw, Mapping) and _text(raw.get("pool_address")) == address:
                    match = raw
                    break
            if not isinstance(match, Mapping):
                continue
            provider = match.get("provider") if isinstance(match.get("provider"), Mapping) else {}
            rows.append(
                {
                    "snapshot_index": index,
                    "status": match.get("status"),
                    "priceNative": provider.get("priceNative"),
                    "pooledBase": provider.get("pooledBase"),
                    "pooledQuote": provider.get("pooledQuote"),
                    "lastSyncedAt_raw": provider.get("lastSyncedAt_raw"),
                    "relative_error": (
                        match.get("price_vs_rpc_ratio", {}).get("relative_error")
                        if isinstance(match.get("price_vs_rpc_ratio"), Mapping)
                        else None
                    ),
                }
            )

        prices = [str(r.get("priceNative")) for r in rows if r.get("priceNative") is not None]
        syncs = [str(r.get("lastSyncedAt_raw")) for r in rows if r.get("lastSyncedAt_raw") is not None]
        reserves = [
            (str(r.get("pooledBase")), str(r.get("pooledQuote")))
            for r in rows
            if r.get("pooledBase") is not None and r.get("pooledQuote") is not None
        ]
        pool_series.append(
            {
                "pool_address": address,
                "observations": rows,
                "price_changed": len(set(prices)) > 1,
                "row_sync_candidate_changed": len(set(syncs)) > 1,
                "pooled_reserves_changed": len(set(reserves)) > 1,
                "price_changed_without_row_sync_candidate_change": (
                    len(set(prices)) > 1 and len(set(syncs)) <= 1
                ),
            }
        )

    global_values = [
        snap.get("provider_timestamp_candidates", {}).get("global_lastUpdated_raw")
        for snap in usable
        if isinstance(snap.get("provider_timestamp_candidates"), Mapping)
    ]

    return {
        "service": "x1_ninja_price_fact_time_series",
        "version": VERSION,
        "chain": "x1",
        "status": "partial",
        "snapshot_count": len(usable),
        "global_lastUpdated_changed": len({str(v) for v in global_values}) > 1,
        "pool_series": pool_series,
        "separate_price_update_behavior_observed": any(
            row.get("price_changed_without_row_sync_candidate_change") is True
            for row in pool_series
        ),
        "provider_timestamp_units_verified": False,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "same_fact_temporal_alignment_verified": False,
        "price_native_semantics_verified": False,
        "warnings": [
            "timestamp_field_names_do_not_prove_fact_time_semantics",
            "different_update_behavior_does_not_identify_the_upstream_price_source",
            "no_tolerance_widening_authorized",
        ],
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def classify_ninja_current_market_fact_time_series(
    snapshots: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Classify candidate update coupling for all current-market fields.

    This is evidence collection only. It never treats lastSyncedAt/lastUpdated
    as verified fact time and never promotes freshness from correlation alone.
    """

    usable = [dict(row) for row in snapshots if isinstance(row, Mapping)]
    if len(usable) < 3:
        raise ValueError("at least three snapshots are required")

    metric_names = (
        "priceNative",
        "liquidity",
        "volume24h",
        "transactions24h",
    )

    addresses: list[str] = []
    seen: set[str] = set()
    for snap in usable:
        for raw in snap.get("pools") or []:
            if not isinstance(raw, Mapping):
                continue
            address = _text(raw.get("pool_address"))
            if address and address not in seen:
                seen.add(address)
                addresses.append(address)

    pool_series: list[dict[str, Any]] = []
    aggregate_changes = {name: 0 for name in metric_names}
    aggregate_changes_with_row_sync = {name: 0 for name in metric_names}
    aggregate_changes_without_row_sync = {name: 0 for name in metric_names}

    for address in addresses:
        observations: list[dict[str, Any]] = []
        for index, snap in enumerate(usable):
            match = None
            for raw in snap.get("pools") or []:
                if (
                    isinstance(raw, Mapping)
                    and _text(raw.get("pool_address")) == address
                ):
                    match = raw
                    break
            if not isinstance(match, Mapping):
                continue

            provider = (
                match.get("provider")
                if isinstance(match.get("provider"), Mapping)
                else {}
            )
            tx24 = provider.get("transactions24h")
            if tx24 is None:
                tx24 = provider.get("txns24h")

            observations.append(
                {
                    "snapshot_index": index,
                    "status": match.get("status"),
                    "priceNative": provider.get("priceNative"),
                    "liquidity": provider.get("liquidity"),
                    "volume24h": provider.get("volume24h"),
                    "transactions24h": tx24,
                    "lastSyncedAt_raw": provider.get("lastSyncedAt_raw"),
                }
            )

        transitions: list[dict[str, Any]] = []
        for before, after in zip(observations, observations[1:]):
            row_sync_changed = (
                str(before.get("lastSyncedAt_raw"))
                != str(after.get("lastSyncedAt_raw"))
            )
            changed: dict[str, bool] = {}
            for name in metric_names:
                field_changed = str(before.get(name)) != str(after.get(name))
                changed[name] = field_changed
                if field_changed:
                    aggregate_changes[name] += 1
                    if row_sync_changed:
                        aggregate_changes_with_row_sync[name] += 1
                    else:
                        aggregate_changes_without_row_sync[name] += 1

            transitions.append(
                {
                    "before_snapshot_index": before.get("snapshot_index"),
                    "after_snapshot_index": after.get("snapshot_index"),
                    "row_sync_candidate_changed": row_sync_changed,
                    "changed_fields": changed,
                }
            )

        pool_series.append(
            {
                "pool_address": address,
                "observations": observations,
                "transitions": transitions,
            }
        )

    global_values = [
        snap.get("provider_timestamp_candidates", {}).get(
            "global_lastUpdated_raw"
        )
        for snap in usable
        if isinstance(snap.get("provider_timestamp_candidates"), Mapping)
    ]

    field_summary = {}
    for name in metric_names:
        field_summary[name] = {
            "change_events": aggregate_changes[name],
            "changes_with_row_sync_candidate_change": (
                aggregate_changes_with_row_sync[name]
            ),
            "changes_without_row_sync_candidate_change": (
                aggregate_changes_without_row_sync[name]
            ),
            "row_sync_candidate_covers_all_observed_changes": (
                aggregate_changes[name] > 0
                and aggregate_changes_without_row_sync[name] == 0
            ),
            "provider_fact_time_verified": False,
            "freshness_verified": False,
        }

    return {
        "service": "x1_ninja_current_market_fact_time_series",
        "version": VERSION,
        "chain": "x1",
        "status": "partial",
        "snapshot_count": len(usable),
        "global_lastUpdated_changed": (
            len({str(value) for value in global_values}) > 1
        ),
        "field_summary": field_summary,
        "pool_series": pool_series,
        "provider_timestamp_units_verified": False,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "current_market_freshness_verified": False,
        "warnings": [
            "timestamp_field_names_do_not_prove_fact_time_semantics",
            "update_correlation_does_not_prove_field_fact_time",
            "collection_time_is_not_provider_fact_time",
        ],
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "VERSION",
    "classify_ninja_current_market_fact_time_series",
    "classify_ninja_price_fact_time_series",
    "collect_ninja_price_fact_time_snapshot",
]
