"""Verified X1 XDEX-program asset pool-set resolution for CMIS v1.5.5.

This module composes the independently established evidence chain:

1. enumerate accounts owned by the recognized XDEX/XenDEX programs;
2. verify the recurring mint-pair layout across independent catalog pools;
3. verify the vault-slot layout across those known pools;
4. use dataSize+memcmp filters to enumerate every matching account for a target
   mint inside the verified program/size family; and
5. require every matching account to satisfy the structural pool-role proof.

The resulting set may be complete for the one verified XDEX program family. It
must NOT be promoted to all-X1 DEX completeness because the AMM-program registry
is still not independently proven globally exhaustive.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.market.resolver import find_matches_for_term, pair_name, pool_address
from liquidity_scout.providers.x1.candidate_pool_role import (
    DEFAULT_VAULT_OFFSETS,
    verify_candidate_pool_role,
)
from liquidity_scout.providers.x1.cross_pool_mint_layout import (
    verify_cross_pool_mint_layout,
)
from liquidity_scout.providers.x1.mint_filtered_pool_discovery import (
    discover_program_state_accounts_for_mint,
)
from liquidity_scout.providers.x1.program_accounts import (
    inventory_recognized_amm_programs,
)
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL

VERSION = "1.5.5"
DEFAULT_LAYOUT_SAMPLE_POOLS = 8
DEFAULT_MIN_LAYOUT_POOLS = 3


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _mint(token: Any) -> str | None:
    token = token if isinstance(token, Mapping) else {}
    return _text(token.get("mint") or token.get("address"))


def _inventory_index(inventory: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for program in inventory.get("programs") or []:
        if not isinstance(program, Mapping):
            continue
        program_id = _text(program.get("program_id"))
        for account in program.get("accounts") or []:
            if not isinstance(account, Mapping):
                continue
            pubkey = _text(account.get("pubkey"))
            if pubkey:
                index[pubkey] = {
                    "program_id": program_id,
                    "space": account.get("space"),
                    "owner_matches_program": (
                        account.get("owner_matches_program") is True
                    ),
                }
    return index


def _select_layout_samples(
    catalog_pools: Sequence[Mapping[str, Any]],
    inventory_index: Mapping[str, Mapping[str, Any]],
    *,
    max_pools: int,
) -> list[dict[str, Any]]:
    pools = [dict(pool) for pool in catalog_pools if isinstance(pool, Mapping)]
    pools.sort(
        key=lambda pool: (
            _number(pool.get("liquidity")),
            _number(pool.get("volume24h")),
            pool_address(pool),
        ),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    seen_addresses: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for pool in pools:
        address = pool_address(pool)
        if not address or address in seen_addresses:
            continue
        seen_addresses.add(address)

        inventory_row = inventory_index.get(address)
        if not isinstance(inventory_row, Mapping) or (
            inventory_row.get("owner_matches_program") is not True
        ):
            continue

        base_mint = _mint(pool.get("baseToken"))
        quote_mint = _mint(pool.get("quoteToken"))
        if not base_mint or not quote_mint or base_mint == quote_mint:
            continue

        mint_pair = tuple(sorted((base_mint, quote_mint)))
        if mint_pair in seen_pairs:
            continue
        seen_pairs.add(mint_pair)

        selected.append(
            {
                "pool_address": address,
                "pair": pair_name(pool),
                "base_mint": base_mint,
                "quote_mint": quote_mint,
            }
        )
        if len(selected) >= max_pools:
            break
    return selected


def _catalog_asset_pool_addresses(
    asset_mint: str,
    catalog_pools: Sequence[Mapping[str, Any]],
) -> set[str]:
    addresses: set[str] = set()
    for match in find_matches_for_term(asset_mint, catalog_pools):
        if match[3] < 90:
            continue
        address = pool_address(match[0])
        if address:
            addresses.add(address)
    return addresses


def verify_recognized_program_asset_pool_set(
    *,
    asset_mint: str,
    catalog_pools: Sequence[Mapping[str, Any]],
    rpc_url: str = DEFAULT_X1_RPC_URL,
    layout_sample_pools: int = DEFAULT_LAYOUT_SAMPLE_POOLS,
    min_layout_pools: int = DEFAULT_MIN_LAYOUT_POOLS,
    allow_verified_zero_set: bool = False,
    inventory_provider: Callable[..., Mapping[str, Any]] = (
        inventory_recognized_amm_programs
    ),
    layout_verifier: Callable[..., Mapping[str, Any]] = (
        verify_cross_pool_mint_layout
    ),
    discovery_provider: Callable[..., Mapping[str, Any]] = (
        discover_program_state_accounts_for_mint
    ),
    role_verifier: Callable[..., Mapping[str, Any]] = verify_candidate_pool_role,
) -> dict[str, Any]:
    """Resolve the structurally verified target-mint pool set for one XDEX family.

    Empty mint-filtered results remain unverified by default. A caller may
    explicitly opt into allow_verified_zero_set only when a verified empty
    program-family set is itself the required fact. This never widens the
    result beyond the one verified program/account family and never proves an
    all-X1 DEX zero.
    """

    asset_mint = _text(asset_mint)
    rpc_url = _text(rpc_url)
    if not asset_mint:
        raise ValueError("asset_mint is required")
    if not rpc_url:
        raise ValueError("rpc_url is required")
    if isinstance(layout_sample_pools, bool) or not isinstance(layout_sample_pools, int):
        raise ValueError("layout_sample_pools must be an integer between 3 and 20")
    if layout_sample_pools < 3 or layout_sample_pools > 20:
        raise ValueError("layout_sample_pools must be an integer between 3 and 20")
    if isinstance(min_layout_pools, bool) or not isinstance(min_layout_pools, int):
        raise ValueError("min_layout_pools must be an integer >= 3")
    if min_layout_pools < 3 or min_layout_pools > layout_sample_pools:
        raise ValueError("min_layout_pools must be between 3 and layout_sample_pools")
    if not isinstance(allow_verified_zero_set, bool):
        raise ValueError("allow_verified_zero_set must be boolean")

    clean_catalog = [
        dict(pool) for pool in catalog_pools if isinstance(pool, Mapping)
    ]
    errors: list[dict[str, Any]] = []

    inventory = inventory_provider(
        rpc_url=rpc_url,
        data_slice_length=0,
    )
    inventory_index = _inventory_index(inventory)
    layout_samples = _select_layout_samples(
        clean_catalog,
        inventory_index,
        max_pools=layout_sample_pools,
    )

    mint_layout = layout_verifier(
        layout_samples,
        rpc_url=rpc_url,
        min_verification_pools=min_layout_pools,
    )
    verified_families = (
        mint_layout.get("summary", {}).get("verified_families") or []
    )

    family = verified_families[0] if len(verified_families) == 1 else None
    if family is None:
        return {
            "service": "verified_program_asset_pool_set",
            "version": VERSION,
            "chain": "x1",
            "asset_mint": asset_mint,
            "status": "layout_not_verified",
            "program_id": None,
            "account_space": None,
            "mint_offsets": [],
            "vault_offsets": list(DEFAULT_VAULT_OFFSETS),
            "pools": [],
            "summary": {
                "recognized_program_asset_pool_set_structurally_verified": False,
                "verified_program_pool_count": 0,
                "recognized_program_registry_globally_exhaustive": False,
                "global_onchain_pool_discovery_proven": False,
            },
            "evidence": {
                "mint_layout": mint_layout,
                "vault_layout_verified": False,
                "discovery": None,
            },
            "errors": [
                {
                    "stage": "mint_layout",
                    "error": (
                        "Expected exactly one verified mint-layout family; observed "
                        f"{len(verified_families)}."
                    ),
                }
            ],
        }

    program_id = _text(family.get("program_id"))
    account_space = family.get("space")
    mint_offsets = family.get("stable_mint_offsets") or []
    if not program_id or not isinstance(account_space, int) or len(mint_offsets) != 2:
        raise ValueError("verified mint-layout family is malformed")

    known_reports: list[dict[str, Any]] = []
    for sample in layout_samples:
        try:
            report = role_verifier(
                account=sample["pool_address"],
                target_mint=sample["base_mint"],
                program_id=program_id,
                account_space=account_space,
                mint_offsets=mint_offsets,
                vault_offsets=DEFAULT_VAULT_OFFSETS,
                rpc_url=rpc_url,
                signature_limit=1,
            )
        except Exception as exc:
            report = {
                "account": sample["pool_address"],
                "summary": {"pool_state_structural_role_verified": False},
                "errors": [
                    {
                        "stage": "known_pool_structure",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                ],
            }
        known_reports.append(report)

    known_valid_count = sum(
        1
        for report in known_reports
        if report.get("summary", {}).get("pool_state_structural_role_verified") is True
    )
    vault_layout_verified = bool(
        len(known_reports) >= min_layout_pools
        and known_valid_count == len(known_reports)
    )

    discovery = None
    candidate_reports: list[dict[str, Any]] = []
    if vault_layout_verified:
        discovery = discovery_provider(
            mint=asset_mint,
            program_id=program_id,
            account_space=account_space,
            mint_offsets=mint_offsets,
            rpc_url=rpc_url,
        )
        for row in discovery.get("accounts") or []:
            if not isinstance(row, Mapping):
                continue
            address = _text(row.get("pubkey"))
            if not address:
                continue
            try:
                report = role_verifier(
                    account=address,
                    target_mint=asset_mint,
                    program_id=program_id,
                    account_space=account_space,
                    mint_offsets=mint_offsets,
                    vault_offsets=DEFAULT_VAULT_OFFSETS,
                    rpc_url=rpc_url,
                    signature_limit=1,
                )
            except Exception as exc:
                report = {
                    "account": address,
                    "summary": {
                        "pool_state_structural_role_verified": False,
                        "recent_recognized_instruction_coupling_observed": False,
                    },
                    "errors": [
                        {
                            "stage": "candidate_structure",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    ],
                }
            candidate_reports.append(report)
    else:
        errors.append(
            {
                "stage": "vault_layout",
                "error": (
                    "The vault-slot layout did not verify across all independent "
                    "known-pool samples."
                ),
            }
        )

    discovered_addresses = {
        _text(row.get("pubkey"))
        for row in (discovery or {}).get("accounts", [])
        if isinstance(row, Mapping) and _text(row.get("pubkey"))
    }
    verified_reports = [
        report
        for report in candidate_reports
        if report.get("summary", {}).get("pool_state_structural_role_verified") is True
    ]
    verified_addresses = {
        _text(report.get("account"))
        for report in verified_reports
        if _text(report.get("account"))
    }
    catalog_addresses = _catalog_asset_pool_addresses(asset_mint, clean_catalog)

    filters_verified = (discovery or {}).get("summary", {}).get(
        "targeted_program_family_mint_filter_observed"
    ) is True
    zero_matching_program_state = not discovered_addresses
    verified_zero_set = bool(
        allow_verified_zero_set
        and zero_matching_program_state
        and filters_verified
        and not catalog_addresses
    )
    all_matching_verified = bool(
        verified_addresses == discovered_addresses
        and (bool(discovered_addresses) or verified_zero_set)
    )
    catalog_recovered = catalog_addresses.issubset(discovered_addresses)
    pool_set_verified = bool(
        vault_layout_verified
        and filters_verified
        and all_matching_verified
        and catalog_recovered
    )

    pools: list[dict[str, Any]] = []
    for report in verified_reports:
        address = _text(report.get("account"))
        decoded = report.get("decoded_state")
        decoded = decoded if isinstance(decoded, Mapping) else {}
        mint_0 = _text(decoded.get("mint_0"))
        mint_1 = _text(decoded.get("mint_1"))
        pools.append(
            {
                "pool_address": address,
                "pair": (
                    f"{mint_0}/{mint_1}" if mint_0 and mint_1 else None
                ),
                "mint_0": mint_0,
                "mint_1": mint_1,
                "catalog_listed": address in catalog_addresses,
                "recent_recognized_instruction_coupling_observed": (
                    report.get("summary", {}).get(
                        "recent_recognized_instruction_coupling_observed"
                    )
                    is True
                ),
                "pool_state_structural_role_verified": True,
            }
        )
    pools.sort(key=lambda row: row.get("pool_address") or "")

    return {
        "service": "verified_program_asset_pool_set",
        "version": VERSION,
        "chain": "x1",
        "asset_mint": asset_mint,
        "status": (
            "recognized_program_asset_pool_set_structurally_verified"
            if pool_set_verified
            else "partial"
        ),
        "program_id": program_id,
        "account_space": account_space,
        "mint_offsets": list(mint_offsets),
        "vault_offsets": list(DEFAULT_VAULT_OFFSETS),
        "pools": pools,
        "summary": {
            "layout_sample_count": len(layout_samples),
            "vault_layout_verified": vault_layout_verified,
            "targeted_program_family_mint_filter_observed": filters_verified,
            "matching_program_state_account_count": len(discovered_addresses),
            "verified_program_pool_count": len(verified_addresses),
            "allow_verified_zero_set": allow_verified_zero_set,
            "zero_matching_program_state_observed": zero_matching_program_state,
            "verified_zero_set": verified_zero_set,
            "all_matching_accounts_structurally_verified": all_matching_verified,
            "catalog_asset_pool_count": len(catalog_addresses),
            "all_catalog_asset_pools_recovered": catalog_recovered,
            "noncatalog_verified_program_pool_count": len(
                verified_addresses - catalog_addresses
            ),
            "recognized_program_asset_pool_set_structurally_verified": (
                pool_set_verified
            ),
            "recognized_program_registry_globally_exhaustive": False,
            "global_onchain_pool_discovery_proven": False,
            "interpretation": (
                "The target-mint pool-state set is structurally verified for one "
                "recognized XDEX program/account family. This is sufficient for a "
                "program-scoped chain-window claim, not an all-X1 DEX claim."
            ),
        },
        "evidence": {
            "mint_layout": mint_layout,
            "known_pool_structural_reports": known_reports,
            "discovery": discovery,
            "candidate_structural_reports": candidate_reports,
        },
        "errors": errors,
    }


__all__ = [
    "DEFAULT_LAYOUT_SAMPLE_POOLS",
    "DEFAULT_MIN_LAYOUT_POOLS",
    "VERSION",
    "verify_recognized_program_asset_pool_set",
]
