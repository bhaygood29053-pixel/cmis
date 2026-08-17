#!/usr/bin/env python3
"""Read-only CMIS v1.5 X1 AMM program-account inventory probe."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping

from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.market.resolver import find_matches_for_term, pool_address
from liquidity_scout.providers.x1.program_accounts import (
    inventory_recognized_amm_programs,
)


def _text(value):
    text = str(value or "").strip()
    return text or None


def _resolve_catalog_pools(gateway, asset):
    market = gateway._market_report(asset)
    if market.get("status") not in {"ok", "partial"}:
        raise RuntimeError("asset resolution failed: " + json.dumps(market))

    resolved = market.get("asset")
    resolved = resolved if isinstance(resolved, Mapping) else {}
    mint = _text(resolved.get("mint"))
    if not mint:
        raise RuntimeError("resolved asset has no mint")

    catalog, failure = gateway._collect_x1_catalog("verified_asset_activity")
    if failure is not None:
        raise RuntimeError("pool catalog failed: " + json.dumps(failure))

    matches = [
        match
        for match in find_matches_for_term(mint, catalog["pools"])
        if match[3] >= 90
    ]
    addresses = []
    seen = set()
    for match in matches:
        address = pool_address(match[0])
        if address and address not in seen:
            seen.add(address)
            addresses.append(address)

    return resolved, addresses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("asset")
    parser.add_argument(
        "--data-slice-length",
        type=int,
        default=0,
        help="Bytes of each program-owned account to request (0..256).",
    )
    args = parser.parse_args()

    gateway = TradeAwareCMISGateway()
    resolved, catalog_pool_addresses = _resolve_catalog_pools(
        gateway,
        args.asset,
    )

    inventory = inventory_recognized_amm_programs(
        rpc_url=gateway.x1_trade_rpc_url,
        data_slice_length=args.data_slice_length,
    )
    inventory_pubkeys = set(inventory.get("account_pubkeys") or [])

    catalog_comparison = []
    for address in catalog_pool_addresses:
        catalog_comparison.append(
            {
                "pool_address": address,
                "present_in_recognized_program_owned_account_inventory": (
                    address in inventory_pubkeys
                ),
            }
        )

    matched = sum(
        1
        for item in catalog_comparison
        if item[
            "present_in_recognized_program_owned_account_inventory"
        ]
    )

    result = {
        "service": "program_account_inventory_probe",
        "version": "1.5.0",
        "chain": "x1",
        "asset": dict(resolved),
        "status": "observed",
        "program_inventory": inventory,
        "catalog_comparison": {
            "catalog_asset_pool_count": len(catalog_pool_addresses),
            "catalog_asset_pool_present_in_program_inventory_count": matched,
            "catalog_asset_pool_missing_from_program_inventory_count": (
                len(catalog_pool_addresses) - matched
            ),
            "pools": catalog_comparison,
        },
        "promotion": {
            "recognized_program_account_inventory_observed": (
                inventory.get("summary", {}).get(
                    "recognized_program_account_inventory_observed"
                )
                is True
            ),
            "recognized_program_registry_globally_exhaustive": False,
            "pool_state_layout_verified": False,
            "global_onchain_pool_discovery_proven": False,
            "asset_window_complete_promotable": False,
            "reason": (
                "This phase independently inventories accounts owned by the "
                "configured recognized AMM programs and compares known catalog "
                "pool addresses against that set. Binary pool-state layout and "
                "global AMM program-registry exhaustiveness remain unproven."
            ),
        },
        "errors": [],
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
