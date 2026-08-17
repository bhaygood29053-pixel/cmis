#!/usr/bin/env python3
"""Read-only CMIS v1.5.1 known-pool binary-state fingerprint probe."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping

from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.market.resolver import (
    find_matches_for_term,
    pair_name,
    pool_address,
)
from liquidity_scout.providers.x1.pool_state_fingerprint import (
    fingerprint_known_pool_state,
)
from liquidity_scout.providers.x1.program_accounts import (
    inventory_recognized_amm_programs,
)


def _text(value):
    text = str(value or "").strip()
    return text or None


def _parse_extra_identity(value):
    text = _text(value)
    if not text or "=" not in text:
        raise argparse.ArgumentTypeError("--identity must be NAME=PUBKEY")
    name, pubkey = text.split("=", 1)
    name = _text(name)
    pubkey = _text(pubkey)
    if not name or not pubkey:
        raise argparse.ArgumentTypeError("--identity must be NAME=PUBKEY")
    return name, pubkey


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

    return resolved, pools


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Fetch complete binary state only for already-known catalog pools, "
            "then locate deterministic public-key byte occurrences."
        )
    )
    parser.add_argument("asset")
    parser.add_argument(
        "--identity",
        action="append",
        type=_parse_extra_identity,
        default=[],
        help=(
            "Optional extra public-key identity to locate as NAME=PUBKEY. "
            "May be supplied more than once."
        ),
    )
    args = parser.parse_args()

    gateway = TradeAwareCMISGateway()
    resolved, catalog_pools = _resolve_catalog_pools(gateway, args.asset)
    mint = _text(resolved.get("mint"))
    extra_identities = dict(args.identity)

    inventory = inventory_recognized_amm_programs(
        rpc_url=gateway.x1_trade_rpc_url,
        data_slice_length=0,
    )

    account_index = {}
    family_counts = {}
    for program in inventory.get("programs") or []:
        if not isinstance(program, Mapping):
            continue
        program_id = _text(program.get("program_id"))
        size_counts = program.get("account_size_counts")
        size_counts = size_counts if isinstance(size_counts, Mapping) else {}
        for raw_space, count in size_counts.items():
            try:
                space = int(raw_space)
                family_counts[(program_id, space)] = int(count)
            except (TypeError, ValueError):
                continue
        for account in program.get("accounts") or []:
            if not isinstance(account, Mapping):
                continue
            pubkey = _text(account.get("pubkey"))
            if pubkey:
                account_index[pubkey] = {
                    "program_id": program_id,
                    "space": account.get("space"),
                    "owner_matches_program": (
                        account.get("owner_matches_program") is True
                    ),
                }

    pool_reports = []
    family_catalog_counts = Counter()
    for pool in catalog_pools:
        address = pool["pool_address"]
        inventory_row = account_index.get(address) or {}
        fingerprint = fingerprint_known_pool_state(
            pool_address=address,
            asset_mint=mint,
            rpc_url=gateway.x1_trade_rpc_url,
            extra_identities=extra_identities,
        )

        program_id = _text(inventory_row.get("program_id"))
        space = inventory_row.get("space")
        if program_id and isinstance(space, int):
            family_catalog_counts[(program_id, space)] += 1

        pool_reports.append(
            {
                "pool_address": address,
                "pair": pool.get("pair"),
                "present_in_recognized_program_inventory": bool(inventory_row),
                "inventory_program_id": program_id,
                "inventory_space": space,
                "inventory_owner_matches_program": (
                    inventory_row.get("owner_matches_program") is True
                ),
                "program_inventory_size_family_account_count": (
                    family_counts.get((program_id, space))
                    if program_id and isinstance(space, int)
                    else None
                ),
                "fingerprint": fingerprint,
            }
        )

    size_families = []
    for (program_id, space), catalog_count in sorted(
        family_catalog_counts.items(),
        key=lambda item: (item[0][0] or "", item[0][1]),
    ):
        size_families.append(
            {
                "program_id": program_id,
                "space": space,
                "catalog_pool_count": catalog_count,
                "program_inventory_account_count": family_counts.get(
                    (program_id, space)
                ),
                "pool_state_layout_verified": False,
            }
        )

    all_catalog_pools_in_inventory = bool(pool_reports) and all(
        item.get("present_in_recognized_program_inventory") is True
        for item in pool_reports
    )
    all_pool_states_integrity_verified = bool(pool_reports) and all(
        (
            (item.get("fingerprint") or {}).get("summary") or {}
        ).get("response_integrity_verified")
        is True
        for item in pool_reports
    )
    any_identity_coupling = any(
        (
            (item.get("fingerprint") or {}).get("summary") or {}
        ).get("pool_state_identity_coupling_observed")
        is True
        for item in pool_reports
    )

    result = {
        "service": "known_pool_state_fingerprint_probe",
        "version": "1.5.1",
        "chain": "x1",
        "asset": dict(resolved),
        "status": (
            "candidate_layout_observed"
            if all_pool_states_integrity_verified and any_identity_coupling
            else "observed_no_identity_coupling"
            if all_pool_states_integrity_verified
            else "partial"
        ),
        "program_inventory_summary": inventory.get("summary"),
        "catalog_pool_count": len(catalog_pools),
        "known_pools": pool_reports,
        "known_pool_size_families": size_families,
        "summary": {
            "all_catalog_pools_in_recognized_program_inventory": (
                all_catalog_pools_in_inventory
            ),
            "all_known_pool_states_integrity_verified": (
                all_pool_states_integrity_verified
            ),
            "any_pool_state_identity_coupling_observed": (
                any_identity_coupling
            ),
            "known_pool_size_family_count": len(size_families),
            "pool_state_layout_verified": False,
            "global_onchain_pool_discovery_proven": False,
            "interpretation": (
                "Known catalog pools are sampled in full to identify their "
                "program-owned account-size family and exact embedded public-key "
                "offsets. This is layout-fingerprint evidence only. Layout "
                "verification requires stable repeated fields across independent "
                "known pools; global discovery additionally requires a complete "
                "recognized-program registry."
            ),
        },
        "promotion": {
            "pool_state_layout_verified": False,
            "recognized_program_registry_globally_exhaustive": False,
            "global_onchain_pool_discovery_proven": False,
            "asset_window_complete_promotable": False,
        },
        "errors": [],
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
