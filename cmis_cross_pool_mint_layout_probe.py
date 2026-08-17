#!/usr/bin/env python3
"""Read-only CMIS v1.5.2 cross-pool XDEX mint-layout probe."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping

from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.market.resolver import pair_name, pool_address
from liquidity_scout.providers.x1.cross_pool_mint_layout import (
    verify_cross_pool_mint_layout,
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


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Sample independent known XDEX catalog pools and verify whether their "
            "two catalog mints recur at stable byte offsets inside program-owned "
            "binary pool state."
        )
    )
    parser.add_argument("--max-pools", type=int, default=8)
    parser.add_argument("--min-verification-pools", type=int, default=3)
    args = parser.parse_args()

    if args.max_pools < 3 or args.max_pools > 20:
        raise SystemExit("--max-pools must be between 3 and 20")
    if args.min_verification_pools < 3 or args.min_verification_pools > args.max_pools:
        raise SystemExit(
            "--min-verification-pools must be between 3 and --max-pools"
        )

    gateway = TradeAwareCMISGateway()
    catalog, failure = gateway._collect_x1_catalog("verified_asset_activity")
    if failure is not None:
        raise RuntimeError("pool catalog failed: " + json.dumps(failure))

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

    raw_pools = [
        pool
        for pool in catalog.get("pools", [])
        if isinstance(pool, Mapping)
    ]
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
    skipped = {
        "not_in_recognized_program_inventory": 0,
        "invalid_or_same_mints": 0,
        "duplicate_pool_address": 0,
        "duplicate_mint_pair": 0,
    }

    for pool in raw_pools:
        address = pool_address(pool)
        if not address or address in seen_addresses:
            skipped["duplicate_pool_address"] += 1
            continue
        seen_addresses.add(address)

        inventory_row = inventory_index.get(address)
        if not inventory_row or inventory_row.get("owner_matches_program") is not True:
            skipped["not_in_recognized_program_inventory"] += 1
            continue

        base = pool.get("baseToken") or {}
        quote = pool.get("quoteToken") or {}
        base_mint = _mint(base)
        quote_mint = _mint(quote)
        if not base_mint or not quote_mint or base_mint == quote_mint:
            skipped["invalid_or_same_mints"] += 1
            continue

        pair_key = tuple(sorted((base_mint, quote_mint)))
        if pair_key in seen_pairs:
            skipped["duplicate_mint_pair"] += 1
            continue
        seen_pairs.add(pair_key)

        selected.append(
            {
                "pool_address": address,
                "pair": pair_name(pool),
                "base_mint": base_mint,
                "quote_mint": quote_mint,
                "catalog_liquidity": pool.get("liquidity"),
                "catalog_volume24h": pool.get("volume24h"),
                "inventory_program_id": inventory_row.get("program_id"),
                "inventory_space": inventory_row.get("space"),
            }
        )
        if len(selected) >= args.max_pools:
            break

    verification = verify_cross_pool_mint_layout(
        selected,
        rpc_url=gateway.x1_trade_rpc_url,
        min_verification_pools=args.min_verification_pools,
    )

    result = {
        "service": "cross_pool_mint_layout_probe",
        "version": "1.5.2",
        "chain": "x1",
        "status": (
            "mint_pair_layout_verified"
            if verification.get("summary", {}).get(
                "pool_mint_pair_layout_verified"
            )
            is True
            else "observed_not_verified"
        ),
        "catalog_pool_count": len(raw_pools),
        "recognized_program_inventory_summary": inventory.get("summary"),
        "selected_pool_count": len(selected),
        "selected_pools": selected,
        "selection_skips": skipped,
        "verification": verification,
        "promotion": {
            "pool_mint_pair_layout_verified": verification.get("summary", {}).get(
                "pool_mint_pair_layout_verified"
            )
            is True,
            "pool_state_layout_verified": False,
            "every_family_account_is_pool_verified": False,
            "recognized_program_registry_globally_exhaustive": False,
            "global_onchain_pool_discovery_proven": False,
            "asset_window_complete_promotable": False,
        },
        "errors": [],
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
