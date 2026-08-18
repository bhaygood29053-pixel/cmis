#!/usr/bin/env python3
"""Read-only CMIS v1.5.4 X1 candidate pool-role verification probe."""

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


def _inventory_index(inventory):
    index = {}
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


def _select_layout_samples(catalog_pools, inventory_index, max_pools):
    pools = [pool for pool in catalog_pools if isinstance(pool, Mapping)]
    pools.sort(
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
    for pool in pools:
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


def _resolve_asset(gateway, asset, catalog_pools):
    market = gateway._market_report(asset)
    if market.get("status") not in {"ok", "partial"}:
        raise RuntimeError("asset resolution failed: " + json.dumps(market))
    resolved = market.get("asset")
    resolved = resolved if isinstance(resolved, Mapping) else {}
    mint = _text(resolved.get("mint"))
    if not mint:
        raise RuntimeError("resolved asset has no mint")

    catalog_addresses = []
    seen = set()
    for match in find_matches_for_term(mint, catalog_pools):
        if match[3] < 90:
            continue
        address = pool_address(match[0])
        if address and address not in seen:
            seen.add(address)
            catalog_addresses.append(address)
    return dict(resolved), mint, catalog_addresses


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Re-verify mint layout and vault layout on independent known pools, "
            "then structurally verify every mint-filtered XDEX candidate."
        )
    )
    parser.add_argument("asset")
    parser.add_argument("--layout-sample-pools", type=int, default=8)
    parser.add_argument("--min-layout-pools", type=int, default=3)
    parser.add_argument("--signature-limit", type=int, default=20)
    args = parser.parse_args()

    if args.layout_sample_pools < 3 or args.layout_sample_pools > 20:
        raise SystemExit("--layout-sample-pools must be between 3 and 20")
    if args.min_layout_pools < 3 or args.min_layout_pools > args.layout_sample_pools:
        raise SystemExit("--min-layout-pools must be between 3 and --layout-sample-pools")
    if args.signature_limit < 1 or args.signature_limit > 100:
        raise SystemExit("--signature-limit must be between 1 and 100")

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
    inventory_index = _inventory_index(inventory)

    layout_samples = _select_layout_samples(
        catalog_pools,
        inventory_index,
        args.layout_sample_pools,
    )
    mint_layout = verify_cross_pool_mint_layout(
        layout_samples,
        rpc_url=gateway.x1_trade_rpc_url,
        min_verification_pools=args.min_layout_pools,
    )
    verified_families = mint_layout.get("summary", {}).get("verified_families") or []

    resolved, target_mint, catalog_asset_addresses = _resolve_asset(
        gateway,
        args.asset,
        catalog_pools,
    )

    errors = []
    discovery = None
    known_pool_structure = []
    candidate_structure = []
    family = verified_families[0] if len(verified_families) == 1 else None

    if family is None:
        errors.append(
            {
                "stage": "mint_layout",
                "error": (
                    "Expected exactly one verified mint-layout family; observed "
                    f"{len(verified_families)}."
                ),
            }
        )
    else:
        program_id = family["program_id"]
        account_space = int(family["space"])
        mint_offsets = family["stable_mint_offsets"]

        # Verify the proposed 72/104 vault-slot mapping on independent catalog pools
        # before applying it to mint-filtered candidates.
        for sample in layout_samples:
            try:
                report = verify_candidate_pool_role(
                    account=sample["pool_address"],
                    target_mint=sample["base_mint"],
                    program_id=program_id,
                    account_space=account_space,
                    mint_offsets=mint_offsets,
                    vault_offsets=DEFAULT_VAULT_OFFSETS,
                    rpc_url=gateway.x1_trade_rpc_url,
                    signature_limit=1,
                )
            except Exception as exc:
                report = {
                    "account": sample["pool_address"],
                    "summary": {
                        "pool_state_structural_role_verified": False,
                    },
                    "errors": [
                        {
                            "stage": "known_pool_structure",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    ],
                }
            known_pool_structure.append(
                {
                    "pair": sample.get("pair"),
                    "base_mint": sample.get("base_mint"),
                    "quote_mint": sample.get("quote_mint"),
                    "report": report,
                }
            )

        known_structural_valid_count = sum(
            1
            for item in known_pool_structure
            if (item.get("report") or {}).get("summary", {}).get(
                "pool_state_structural_role_verified"
            )
            is True
        )
        vault_layout_verified = bool(
            len(known_pool_structure) >= args.min_layout_pools
            and known_structural_valid_count == len(known_pool_structure)
        )

        if vault_layout_verified:
            discovery = discover_program_state_accounts_for_mint(
                mint=target_mint,
                program_id=program_id,
                account_space=account_space,
                mint_offsets=mint_offsets,
                rpc_url=gateway.x1_trade_rpc_url,
            )
            for row in discovery.get("accounts") or []:
                address = _text(row.get("pubkey"))
                if not address:
                    continue
                try:
                    report = verify_candidate_pool_role(
                        account=address,
                        target_mint=target_mint,
                        program_id=program_id,
                        account_space=account_space,
                        mint_offsets=mint_offsets,
                        vault_offsets=DEFAULT_VAULT_OFFSETS,
                        rpc_url=gateway.x1_trade_rpc_url,
                        signature_limit=args.signature_limit,
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
                candidate_structure.append(report)
        else:
            errors.append(
                {
                    "stage": "vault_layout",
                    "error": (
                        "The 72/104 vault-slot hypothesis did not verify across all "
                        "independent known-pool samples; candidate structural role "
                        "promotion was not attempted."
                    ),
                }
            )

    known_valid_count = sum(
        1
        for item in known_pool_structure
        if (item.get("report") or {}).get("summary", {}).get(
            "pool_state_structural_role_verified"
        )
        is True
    )
    vault_layout_verified = bool(
        len(known_pool_structure) >= args.min_layout_pools
        and known_valid_count == len(known_pool_structure)
    )

    candidate_verified = [
        report
        for report in candidate_structure
        if report.get("summary", {}).get("pool_state_structural_role_verified") is True
    ]
    coupled = [
        report
        for report in candidate_structure
        if report.get("summary", {}).get(
            "recent_recognized_instruction_coupling_observed"
        )
        is True
    ]

    discovered_addresses = {
        _text(row.get("pubkey"))
        for row in (discovery or {}).get("accounts", [])
        if isinstance(row, Mapping) and _text(row.get("pubkey"))
    }
    structurally_verified_addresses = {
        _text(report.get("account"))
        for report in candidate_verified
        if _text(report.get("account"))
    }
    catalog_set = set(catalog_asset_addresses)
    noncatalog_structurally_verified = sorted(
        structurally_verified_addresses - catalog_set
    )

    filters_verified = (discovery or {}).get("summary", {}).get(
        "targeted_program_family_mint_filter_observed"
    ) is True
    all_matching_structurally_verified = bool(discovered_addresses) and (
        structurally_verified_addresses == discovered_addresses
    )
    catalog_recovered = bool(catalog_set) and catalog_set.issubset(discovered_addresses)

    recognized_program_asset_pool_set_structurally_verified = bool(
        vault_layout_verified
        and filters_verified
        and all_matching_structurally_verified
        and catalog_recovered
    )

    result = {
        "service": "candidate_pool_role_probe",
        "version": "1.5.4",
        "chain": "x1",
        "asset": resolved,
        "status": (
            "recognized_program_asset_pool_set_structurally_verified"
            if recognized_program_asset_pool_set_structurally_verified
            else "candidate_pool_roles_partially_verified"
            if candidate_verified
            else "observed_not_verified"
        ),
        "mint_layout_verification": mint_layout,
        "vault_layout_verification": {
            "sample_count": len(known_pool_structure),
            "structurally_verified_sample_count": known_valid_count,
            "minimum_required_samples": args.min_layout_pools,
            "vault_offsets": list(DEFAULT_VAULT_OFFSETS),
            "vault_layout_verified": vault_layout_verified,
            "samples": known_pool_structure,
        },
        "discovery": discovery,
        "candidate_role_reports": candidate_structure,
        "summary": {
            "matching_program_state_account_count": len(discovered_addresses),
            "structurally_verified_pool_state_count": len(candidate_verified),
            "recent_instruction_coupled_count": len(coupled),
            "all_matching_accounts_structurally_verified": (
                all_matching_structurally_verified
            ),
            "catalog_asset_pool_count": len(catalog_set),
            "all_catalog_asset_pools_recovered": catalog_recovered,
            "noncatalog_structurally_verified_count": len(
                noncatalog_structurally_verified
            ),
            "noncatalog_structurally_verified_addresses": (
                noncatalog_structurally_verified
            ),
            "recognized_program_asset_pool_set_structurally_verified": (
                recognized_program_asset_pool_set_structurally_verified
            ),
            "recognized_program_registry_globally_exhaustive": False,
            "global_onchain_pool_discovery_proven": False,
            "asset_window_complete_promotable": False,
            "interpretation": (
                "The result can structurally verify the complete target-mint pool-state "
                "set for the one verified XDEX program/637-byte family. It does not "
                "prove that the recognized AMM program registry is globally exhaustive, "
                "so asset-wide discovery and asset_window_complete remain gated."
            ),
        },
        "errors": errors,
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
