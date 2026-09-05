"""Bounded X1.Ninja catalog watch-set selection for #461 live evidence.

This module selects candidate wrapped-XNT pool addresses from an already-fetched
X1.Ninja catalog. Selection is discovery only. Exact XDEX pool structure and
mint position must still be verified from X1 RPC before a selected candidate may
contribute semantic evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


DEFAULT_MAX_WATCH_POOLS = 150


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _pool_address(row: Mapping[str, Any]) -> str | None:
    return _text(
        row.get("address")
        or row.get("poolAddress")
        or row.get("pool_address")
        or row.get("id")
    )


def _token_candidates(row: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for side_name in ("baseToken", "quoteToken"):
        side = row.get(side_name)
        if not isinstance(side, Mapping):
            continue
        for key in (
            "mint",
            "address",
            "tokenAddress",
            "token_address",
            "mintAddress",
            "mint_address",
        ):
            value = _text(side.get(key))
            if value:
                values.add(value)

    for key in (
        "token1_mint",
        "token1Mint",
        "token1_address",
        "token1Address",
        "token2_mint",
        "token2Mint",
        "token2_address",
        "token2Address",
    ):
        value = _text(row.get(key))
        if value:
            values.add(value)
    return values


def _positive_liquidity_candidate(row: Mapping[str, Any]) -> bool:
    try:
        value = Decimal(str(row.get("liquidity")))
    except (InvalidOperation, TypeError, ValueError):
        return False
    return bool(value.is_finite() and value > 0)


def select_wrapped_xnt_watch_candidates(
    pools: Sequence[Mapping[str, Any]],
    *,
    wrapped_xnt_mint: str,
    max_pools: int = DEFAULT_MAX_WATCH_POOLS,
    priority_addresses: Sequence[str] = (),
    excluded_addresses: Sequence[str] = (),
) -> dict[str, Any]:
    """Select a bounded catalog watch set without making semantic claims.

    Provider catalog order and optional priority addresses are collection
    heuristics only. The result does not verify pool identity, token side
    semantics, liquidity units, activity, freshness, or provider completeness.
    """

    mint = _text(wrapped_xnt_mint)
    if mint is None:
        raise ValueError("wrapped_xnt_mint is required")
    if isinstance(max_pools, bool) or not isinstance(max_pools, int):
        raise ValueError("max_pools must be an integer")
    if max_pools < 5 or max_pools > 500:
        raise ValueError("max_pools must be between 5 and 500")
    if not isinstance(pools, Sequence) or isinstance(
        pools, (str, bytes, bytearray)
    ):
        raise TypeError("pools must be a sequence")

    excluded = {
        value
        for raw in excluded_addresses
        if (value := _text(raw)) is not None
    }

    eligible_in_catalog_order: list[str] = []
    seen: set[str] = set()
    rejected_rows = 0

    for raw in pools:
        if not isinstance(raw, Mapping):
            rejected_rows += 1
            continue
        address = _pool_address(raw)
        if (
            address is None
            or address in seen
            or address in excluded
            or mint not in _token_candidates(raw)
            or not _positive_liquidity_candidate(raw)
        ):
            continue
        seen.add(address)
        eligible_in_catalog_order.append(address)

    eligible_set = set(eligible_in_catalog_order)
    selected: list[str] = []
    selected_set: set[str] = set()

    for raw in priority_addresses:
        address = _text(raw)
        if (
            address is not None
            and address in eligible_set
            and address not in selected_set
            and len(selected) < max_pools
        ):
            selected.append(address)
            selected_set.add(address)

    for address in eligible_in_catalog_order:
        if len(selected) >= max_pools:
            break
        if address in selected_set:
            continue
        selected.append(address)
        selected_set.add(address)

    return {
        "wrapped_xnt_mint": mint,
        "catalog_row_count": len(pools),
        "eligible_catalog_candidate_count": len(eligible_in_catalog_order),
        "selected_candidate_count": len(selected),
        "selected_candidate_addresses": selected,
        "max_watch_pools": max_pools,
        "priority_candidate_count": sum(
            1 for address in selected if address in set(priority_addresses)
        ),
        "selection_truncated": len(eligible_in_catalog_order) > len(selected),
        "excluded_addresses": sorted(excluded),
        "non_mapping_row_count": rejected_rows,
        "pool_identity_verified": False,
        "wrapped_xnt_position_verified": False,
        "liquidity_semantics_verified": False,
        "activity_semantics_verified": False,
        "provider_catalog_complete_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "DEFAULT_MAX_WATCH_POOLS",
    "select_wrapped_xnt_watch_candidates",
]
