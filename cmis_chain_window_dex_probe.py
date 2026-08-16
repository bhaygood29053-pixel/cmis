#!/usr/bin/env python3
"""Read-only CMIS v1.4 chain-window DEX enumeration probe."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping
from datetime import datetime, timezone

from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.market.resolver import (
    find_matches_for_term,
    pair_name,
    pool_address,
)
from liquidity_scout.services.cmis_activity_window import (
    parse_activity_window_seconds,
)
from liquidity_scout.services.cmis_chain_window_dex import (
    enumerate_chain_window_dex_activity,
)


def _text(value):
    text = str(value or "").strip()
    return text or None


def _iso(value):
    return datetime.fromtimestamp(
        float(value), tz=timezone.utc
    ).isoformat()


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
    parser.add_argument(
        "--page-size",
        type=int,
        default=1000,
    )
    args = parser.parse_args()

    if args.max_pools <= 0 or args.max_pools > 10:
        raise SystemExit("--max-pools must be 1..10")

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
    activity = enumerate_chain_window_dex_activity(
        asset_mint=mint,
        pools=pools,
        start_epoch=start_epoch,
        end_epoch=end_epoch,
        rpc_url=gateway.x1_trade_rpc_url,
        page_size=args.page_size,
        max_signatures_per_pool=args.max_signatures_per_pool,
    )

    selected_pool_count = len(pools)
    pool_selection_complete = (
        selected_pool_count == matched_pool_count
    )

    result = {
        "service": "chain_window_dex_probe",
        "version": "1.4",
        "chain": "x1",
        "asset": dict(resolved),
        "status": (
            "selected_pool_chain_window_enumerated"
            if activity["summary"][
                "selected_pool_chain_window_complete"
            ]
            else "partial"
        ),
        "requested_window": {
            "label": args.window,
            "duration_seconds": seconds,
            "start_epoch": start_epoch,
            "start_utc": _iso(start_epoch),
            "end_epoch": end_epoch,
            "end_utc": _iso(end_epoch),
            "membership_basis": "X1_RPC_BLOCK_TIME",
        },
        "market_snapshot_status": market.get("status"),
        "pool_discovery": {
            "matched_pool_count": matched_pool_count,
            "selected_pool_count": selected_pool_count,
            "selection_complete_within_current_catalog": (
                pool_selection_complete
            ),
            "global_onchain_pool_discovery_proven": False,
        },
        "activity": activity,
        "summary": {
            **activity["summary"],
            "selection_complete_within_current_catalog": (
                pool_selection_complete
            ),
            "global_onchain_pool_discovery_proven": False,
            "cmis_asset_window_completion_promoted": False,
            "interpretation": (
                "v1.4 enumerates exact-window X1 transactions for every "
                "selected asset pool, deduplicates multi-pool signatures, and "
                "reuses deterministic transaction semantics for transaction-"
                "level BUY/SELL classification. It does not yet prove global "
                "on-chain pool discovery exhaustiveness or exact chain-native "
                "pool-leg amounts."
            ),
        },
        "errors": [],
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
