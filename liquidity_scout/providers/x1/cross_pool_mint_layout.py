"""Read-only cross-pool X1 mint-layout verification for CMIS v1.5.2.

This module compares complete binary state for already-known catalog pool
accounts and asks one deliberately narrow question: do the two catalog token
mints recur exactly once at the same byte offsets across multiple independent
program-owned pool accounts in the same owner/size family?

A stable repeated mint-pair layout is strong evidence for targeted on-chain
pool discovery, but it is not sufficient to claim that every account in the
family is a liquidity pool or that the recognized AMM program registry is
complete. Those promotion boundaries remain fail-closed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.pool_state_fingerprint import (
    fetch_account_state,
    find_pubkey_offsets,
)
from liquidity_scout.providers.x1.program_accounts import RECOGNIZED_AMM_PROGRAM_IDS
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, rpc_request

VERSION = "1.5.2"
DEFAULT_MIN_VERIFICATION_POOLS = 3


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _pool_descriptor(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    address = _text(raw.get("pool_address"))
    base_mint = _text(raw.get("base_mint"))
    quote_mint = _text(raw.get("quote_mint"))
    if not address or not base_mint or not quote_mint or base_mint == quote_mint:
        return None
    return {
        "pool_address": address,
        "pair": _text(raw.get("pair")),
        "base_mint": base_mint,
        "quote_mint": quote_mint,
    }


def verify_cross_pool_mint_layout(
    pools: Sequence[Mapping[str, Any]],
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    min_verification_pools: int = DEFAULT_MIN_VERIFICATION_POOLS,
    recognized_program_ids: Sequence[str] = RECOGNIZED_AMM_PROGRAM_IDS,
    requester: Callable[..., Any] = rpc_request,
) -> dict[str, Any]:
    """Compare exact mint byte offsets across known program-owned pool states.

    Verification is family-specific. A program-owner/account-space family is
    promoted only when at least ``min_verification_pools`` independently known
    pools are sampled, every sample has verified account-data integrity and a
    recognized program owner, each catalog mint occurs exactly once, and every
    sample has the same unordered pair of mint offsets.
    """

    if isinstance(min_verification_pools, bool) or not isinstance(
        min_verification_pools, int
    ):
        raise ValueError("min_verification_pools must be an integer >= 3")
    if min_verification_pools < 3 or min_verification_pools > 25:
        raise ValueError("min_verification_pools must be an integer between 3 and 25")

    recognized = {
        program_id
        for program_id in (_text(item) for item in recognized_program_ids)
        if program_id
    }

    descriptors: list[dict[str, Any]] = []
    seen = set()
    for raw in pools:
        if not isinstance(raw, Mapping):
            continue
        descriptor = _pool_descriptor(raw)
        if descriptor is None:
            continue
        address = descriptor["pool_address"]
        if address in seen:
            continue
        seen.add(address)
        descriptors.append(descriptor)

    observations: list[dict[str, Any]] = []
    family_members: dict[tuple[str | None, int | None], list[dict[str, Any]]] = defaultdict(list)

    for pool in descriptors:
        address = pool["pool_address"]
        try:
            account = fetch_account_state(
                address,
                rpc_url=rpc_url,
                requester=requester,
            )
            data = account.pop("data", None)
            data = data if isinstance(data, bytes) else None

            owner = _text(account.get("owner"))
            space = account.get("space") if isinstance(account.get("space"), int) else None
            integrity = account.get("response_integrity_verified") is True
            recognized_owner = owner in recognized

            base_offsets: list[int] = []
            quote_offsets: list[int] = []
            offset_error = None
            if data is not None:
                try:
                    base_offsets = find_pubkey_offsets(data, pool["base_mint"])
                    quote_offsets = find_pubkey_offsets(data, pool["quote_mint"])
                except ValueError as exc:
                    offset_error = str(exc)

            exactly_one_each = len(base_offsets) == 1 and len(quote_offsets) == 1
            distinct_offsets = bool(
                exactly_one_each and base_offsets[0] != quote_offsets[0]
            )
            mint_offset_set = (
                sorted([base_offsets[0], quote_offsets[0]])
                if distinct_offsets
                else []
            )
            valid_sample = bool(
                integrity
                and recognized_owner
                and distinct_offsets
                and offset_error is None
            )

            row = {
                **pool,
                "owner": owner,
                "space": space,
                "response_integrity_verified": integrity,
                "recognized_program_owner": recognized_owner,
                "base_mint_offsets": base_offsets,
                "quote_mint_offsets": quote_offsets,
                "each_mint_occurs_exactly_once": exactly_one_each,
                "mint_offsets_distinct": distinct_offsets,
                "mint_offset_set": mint_offset_set,
                "valid_layout_sample": valid_sample,
                "data_sha256": account.get("data_sha256"),
            }
            if offset_error:
                row["offset_error"] = offset_error
        except Exception as exc:
            row = {
                **pool,
                "owner": None,
                "space": None,
                "response_integrity_verified": False,
                "recognized_program_owner": False,
                "base_mint_offsets": [],
                "quote_mint_offsets": [],
                "each_mint_occurs_exactly_once": False,
                "mint_offsets_distinct": False,
                "mint_offset_set": [],
                "valid_layout_sample": False,
                "data_sha256": None,
                "error": f"{type(exc).__name__}: {exc}",
            }

        observations.append(row)
        family_members[(row.get("owner"), row.get("space"))].append(row)

    families = []
    verified_families = []

    for (owner, space), rows in sorted(
        family_members.items(),
        key=lambda item: ((item[0][0] or ""), item[0][1] if item[0][1] is not None else -1),
    ):
        valid_rows = [row for row in rows if row.get("valid_layout_sample") is True]
        offset_sets = {
            tuple(row.get("mint_offset_set") or [])
            for row in valid_rows
            if len(row.get("mint_offset_set") or []) == 2
        }
        enough_samples = len(rows) >= min_verification_pools
        all_samples_valid = bool(rows) and len(valid_rows) == len(rows)
        stable_offsets = len(offset_sets) == 1
        verified = bool(enough_samples and all_samples_valid and stable_offsets)
        stable_mint_offsets = list(next(iter(offset_sets))) if stable_offsets else None

        family = {
            "program_id": owner,
            "space": space,
            "sample_count": len(rows),
            "valid_sample_count": len(valid_rows),
            "minimum_verification_pool_count": min_verification_pools,
            "enough_independent_pool_samples": enough_samples,
            "all_samples_valid": all_samples_valid,
            "observed_mint_offset_sets": [list(item) for item in sorted(offset_sets)],
            "stable_mint_offsets": stable_mint_offsets,
            "mint_pair_layout_verified": verified,
            "pool_state_layout_verified": False,
        }
        families.append(family)
        if verified:
            verified_families.append(family)

    return {
        "service": "cross_pool_mint_layout_verification",
        "version": VERSION,
        "chain": "x1",
        "requested_pool_count": len(descriptors),
        "observations": observations,
        "families": families,
        "summary": {
            "minimum_verification_pool_count": min_verification_pools,
            "verified_mint_pair_layout_family_count": len(verified_families),
            "pool_mint_pair_layout_verified": bool(verified_families),
            "verified_families": [
                {
                    "program_id": item["program_id"],
                    "space": item["space"],
                    "stable_mint_offsets": item["stable_mint_offsets"],
                    "sample_count": item["sample_count"],
                }
                for item in verified_families
            ],
            "pool_state_layout_verified": False,
            "every_family_account_is_pool_verified": False,
            "recognized_program_registry_globally_exhaustive": False,
            "global_onchain_pool_discovery_proven": False,
            "interpretation": (
                "Stable repeated mint offsets across multiple independently known "
                "program-owned pool accounts verify only the mint-pair field layout "
                "for that owner/size family. They do not prove that every account in "
                "the family is a pool or that all AMM programs are known."
            ),
        },
        "errors": [],
    }


__all__ = [
    "DEFAULT_MIN_VERIFICATION_POOLS",
    "VERSION",
    "verify_cross_pool_mint_layout",
]
