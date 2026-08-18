#!/usr/bin/env python3
"""Read-only CMIS v1.5.3 X1 mint-filtered program-state discovery probe."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping

from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.market.resolver import (
    find_matches_for_term,
    pair_name,
    pool_address,
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


def _text(value):
    text = str(value or "").strip()
    return text or None


def _number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _mint(token):
    token = token if isinstance(token, Mapping) else {}
    return _text(token.get("mint") or token.get("address"))


def _select_layout_samples(catalog_pools, inventory_index, max_pools):
    raw_pools = [pool for pool in catalog_pools if isinstance(pool, Mapping)]
    raw_pools.sort(
        key=lambda pool: (
            _number(pool.get("liquidity")),
            _number(pool.get("volume24h")),
            pool_address(pool),
        ),
        reverse=True,
    )

    selected = []
    seen_addresses = set()
    seen_pairs = set()
    for pool in raw_pools:
        address = pool_address(pool)
        if not address or address in seen_addresses:
            continue
        seen_addresses.add(address)

        inventory_row = inventory_index.get(address)
        if not inventory_row or inventory_row.get("owner_matches_program") is not True:
            continue

        base_mint = _mint(pool.get("baseToken"))
        quote_mint = _mint(pool.get("quoteToken"))
        if not base_mint or not quote_mint or base_mint == quote_mint:
            continue

        pair_key = tuple(sorted((base_mint, quote_mint)))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

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


def _resolve_asset_and_catalog_pools(gateway, asset, catalog_pools):
    market = gateway._market_report(asset)
    if market.get("status") not in {"ok", "partial"}:
        raise RuntimeError("asset resolution failed: " + json.dumps(market))

    resolved = market.get("asset")
    resolved = resolved if isinstance(resolved, Mapping) else {}
    mint = _text(resolved.get("mint"))
    if not mint:
        raise RuntimeError("resolved asset has no mint")

    matches = [
        match
        for match in find_matches_for_term(mint, catalog_pools)
        if match[3] >= 90
    ]
    pools = []
    seen = set()
    for match in matches:
        pool = match[0]
        address = pool_address(pool)
        if not address or address in seen:
            continue
        seen.add(address)
        pools.append(
            {
                "pool_address": address,
                "pair": pair_name(pool),
            }
        )
    return dict(resolved), mint, pools


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Re-verify the cross-pool mint layout, then use X1 RPC dataSize+memcmp "
            "filters to enumerate matching XDEX program-state accounts for one asset."
        )
    )
    parser.add_argument("asset")
    parser.add_argument("--layout-sample-pools", type=int, default=8)
    parser.add_argument("--min-layout-pools", type=int, default=3)
    args = parser.parse_args()

    if args.layout_sample_pools < 3 or args.layout_sample_pools > 20:
        raise SystemExit("--layout-sample-pools must be between 3 and 20")
    if args.min_layout_pools < 3 or args.min_layout_pools > args.layout_sample_pools:
        raise SystemExit("--min-layout-pools must be between 3 and --layout-sample-pools")

    gateway = TradeAwareCMISGateway()
    catalog, failure = gateway._collect_x1_catalog("verified_asset_activity")
    if failure is not None:
        raise RuntimeError("pool catalog failed: " + json.dumps(failure))
    catalog_pools = [
        pool for pool in catalog.get("pools", []) if isinstance(pool, Mapping)
    ]

    inventory = inventory_recognized_amm_programs(
        rpc_url=gateway.x1_trade_rpc_url,
        data_slice_length=0,
    )
    inventory_index = {}
    for program in inventory.get("programs") or []:
        if not isinstance(program, Mapping):
            continue
        program_id = _text(program.get("program_id"))
        for account in program.get("accounts") or []:
            if not isinstance(account, Mapping):
                continue
            pubkey = _text(account.get("pubkey"))
            if pubkey:
                inventory_index[pubkey] = {
                    "program_id": program_id,
                    "space": account.get("space"),
                    "owner_matches_program": account.get("owner_matches_program") is True,
                }

    layout_samples = _select_layout_samples(
        catalog_pools,
        inventory_index,
        args.layout_sample_pools,
    )
    layout = verify_cross_pool_mint_layout(
        layout_samples,
        rpc_url=gateway.x1_trade_rpc_url,
        min_verification_pools=args.min_layout_pools,
    )
    verified_families = layout.get("summary", {}).get("verified_families") or []

    resolved, mint, catalog_asset_pools = _resolve_asset_and_catalog_pools(
        gateway,
        args.asset,
        catalog_pools,
    )

    discovery = None
    errors = []
    if len(verified_families) == 1:
        family = verified_families[0]
        discovery = discover_program_state_accounts_for_mint(
            mint=mint,
            program_id=family["program_id"],
            account_space=int(family["space"]),
            mint_offsets=family["stable_mint_offsets"],
            rpc_url=gateway.x1_trade_rpc_url,
        )
    else:
        errors.append(
            {
                "stage": "layout_verification",
                "error": (
                    "Expected exactly one verified mint-layout family before filtered "
                    f"discovery; observed {len(verified_families)}."
                ),
            }
        )

    discovered_accounts = (
        discovery.get("accounts", []) if isinstance(discovery, Mapping) else []
    )
    discovered_addresses = {
        _text(row.get("pubkey"))
        for row in discovered_accounts
        if isinstance(row, Mapping) and _text(row.get("pubkey"))
    }
    catalog_addresses = {
        row["pool_address"] for row in catalog_asset_pools if row.get("pool_address")
    }

    overlap = sorted(discovered_addresses & catalog_addresses)
    discovered_not_in_catalog = sorted(discovered_addresses - catalog_addresses)
    catalog_not_discovered = sorted(catalog_addresses - discovered_addresses)

    discovery_summary = (
        discovery.get("summary", {}) if isinstance(discovery, Mapping) else {}
    )
    layout_verified = layout.get("summary", {}).get(
        "pool_mint_pair_layout_verified"
    ) is True
    filters_observed = discovery_summary.get(
        "targeted_program_family_mint_filter_observed"
    ) is True

    result = {
        "service": "mint_filtered_pool_discovery_probe",
        "version": "1.5.3",
        "chain": "x1",
        "asset": resolved,
        "status": (
            "candidate_unlisted_program_state_observed"
            if layout_verified and filters_observed and discovered_not_in_catalog
            else "targeted_mint_filter_observed"
            if layout_verified and filters_observed
            else "partial"
        ),
        "layout_verification": layout,
        "discovery": discovery,
        "catalog_comparison": {
            "catalog_asset_pool_count": len(catalog_addresses),
            "matching_program_state_account_count": len(discovered_addresses),
            "catalog_pool_recovered_count": len(overlap),
            "catalog_pool_not_recovered_count": len(catalog_not_discovered),
            "matching_program_state_not_in_catalog_count": len(discovered_not_in_catalog),
            "catalog_pool_addresses_recovered": overlap,
            "catalog_pool_addresses_not_recovered": catalog_not_discovered,
            "matching_program_state_addresses_not_in_catalog": discovered_not_in_catalog,
            "all_catalog_asset_pools_recovered": bool(catalog_addresses) and not catalog_not_discovered,
        },
        "promotion": {
            "pool_mint_pair_layout_verified": layout_verified,
            "targeted_program_family_mint_filter_observed": filters_observed,
            "every_matching_account_is_pool_verified": False,
            "recognized_program_registry_globally_exhaustive": False,
            "global_onchain_pool_discovery_proven": False,
            "asset_window_complete_promotable": False,
        },
        "errors": errors + (
            discovery.get("errors", []) if isinstance(discovery, Mapping) else []
        ),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
