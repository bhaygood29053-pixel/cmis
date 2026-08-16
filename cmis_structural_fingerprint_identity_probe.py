#!/usr/bin/env python3
"""Read-only CMIS v1.4.5 structural fingerprint identity probe."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping

from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.market.resolver import (
    find_matches_for_term,
    pair_name,
    pool_address,
)
from liquidity_scout.providers.x1.structural_fingerprint_identity import (
    evaluate_structural_fingerprint_identity,
)
from liquidity_scout.services.cmis_activity_window import (
    parse_activity_window_seconds,
)


def _text(value):
    text = str(value or "").strip()
    return text or None


def _resolve_asset_pools(gateway, asset, max_pools):
    market = gateway._market_report(asset)
    if market.get("status") not in {"ok", "partial"}:
        raise RuntimeError(
            "asset resolution failed: " + json.dumps(market)
        )

    resolved = market.get("asset")
    resolved = resolved if isinstance(resolved, Mapping) else {}
    mint = _text(resolved.get("mint"))
    if not mint:
        raise RuntimeError("resolved asset has no mint")

    catalog, failure = gateway._collect_x1_catalog(
        "verified_asset_activity"
    )
    if failure is not None:
        raise RuntimeError(
            "pool catalog failed: " + json.dumps(failure)
        )

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

    return market, resolved, pools[:max_pools], len(pools)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("asset")
    parser.add_argument(
        "--window",
        choices=("1h", "6h", "24h"),
        default="1h",
    )
    parser.add_argument("--max-pools", type=int, default=5)
    parser.add_argument(
        "--max-signatures-per-pool",
        type=int,
        default=5000,
    )
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--min-occurrences", type=int, default=2)
    parser.add_argument(
        "--min-coverage-ratio",
        type=float,
        default=0.50,
    )
    parser.add_argument(
        "--min-opposite-direction-ratio",
        type=float,
        default=0.95,
    )
    parser.add_argument(
        "--min-direction-occurrences",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--min-fingerprint-ratio",
        type=float,
        default=0.95,
    )
    parser.add_argument(
        "--min-dominance-margin",
        type=float,
        default=0.10,
    )
    parser.add_argument(
        "--min-structural-fingerprint-ratio",
        type=float,
        default=0.95,
    )
    args = parser.parse_args()

    seconds = parse_activity_window_seconds(args.window)
    end_epoch = time.time()
    start_epoch = end_epoch - seconds

    gateway = TradeAwareCMISGateway()
    market, resolved, pools, matched_pool_count = _resolve_asset_pools(
        gateway,
        args.asset,
        args.max_pools,
    )
    mint = _text(resolved.get("mint"))

    reports = []
    for pool in pools:
        reports.append(
            evaluate_structural_fingerprint_identity(
                pool_address=pool["pool_address"],
                pair=pool["pair"],
                asset_mint=mint,
                start_epoch=start_epoch,
                end_epoch=end_epoch,
                rpc_url=gateway.x1_trade_rpc_url,
                page_size=args.page_size,
                max_signatures=args.max_signatures_per_pool,
                min_occurrences=args.min_occurrences,
                min_coverage_ratio=args.min_coverage_ratio,
                min_opposite_direction_ratio=(
                    args.min_opposite_direction_ratio
                ),
                min_direction_occurrences=(
                    args.min_direction_occurrences
                ),
                min_fingerprint_ratio=args.min_fingerprint_ratio,
                min_dominance_margin=args.min_dominance_margin,
                min_structural_fingerprint_ratio=(
                    args.min_structural_fingerprint_ratio
                ),
            )
        )

    observed = any(
        (item.get("summary") or {}).get(
            "structural_fingerprint_identity_observed"
        ) is True
        for item in reports
    )
    scope_only = any(
        (item.get("summary") or {}).get(
            "scope_only_variant_observed"
        ) is True
        for item in reports
    )

    result = {
        "service": "structural_fingerprint_identity_probe",
        "version": "1.4.5",
        "chain": "x1",
        "asset": dict(resolved),
        "status": (
            "stable_structural_identity_observed"
            if observed
            else "no_stable_structural_identity_observed"
        ),
        "window": {
            "label": args.window,
            "duration_seconds": seconds,
            "start_epoch": start_epoch,
            "end_epoch": end_epoch,
        },
        "pool_discovery": {
            "matched_pool_count": matched_pool_count,
            "selected_pool_count": len(pools),
            "selection_complete_within_current_catalog": (
                len(pools) == matched_pool_count
            ),
            "global_onchain_pool_discovery_proven": False,
        },
        "pools": reports,
        "summary": {
            "structural_fingerprint_identity_observed": observed,
            "scope_only_variant_observed": scope_only,
            "structural_identity_promoted": False,
            "canonical_vault_mapping_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "interpretation": (
                "v1.4.5 separates structural AMM account layout from "
                "execution scope. outer/inner remains evidence context but "
                "does not by itself create a different structural identity."
            ),
        },
        "errors": [],
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
