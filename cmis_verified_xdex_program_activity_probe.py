#!/usr/bin/env python3
"""Read-only CMIS v1.5.5 verified-XDEX-program activity coverage probe."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping

from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.providers.x1.verified_program_pool_set import (
    verify_recognized_program_asset_pool_set,
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


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Resolve the structurally verified target-mint pool set for the "
            "verified XDEX program, then prove one exact chain window across "
            "every pool in that program-scoped set."
        )
    )
    parser.add_argument("asset")
    parser.add_argument("--window", default="1h")
    parser.add_argument("--layout-sample-pools", type=int, default=8)
    parser.add_argument("--min-layout-pools", type=int, default=3)
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-signatures-per-pool", type=int, default=1000)
    args = parser.parse_args()

    window_seconds = parse_activity_window_seconds(args.window)
    if args.layout_sample_pools < 3 or args.layout_sample_pools > 20:
        raise SystemExit("--layout-sample-pools must be between 3 and 20")
    if args.min_layout_pools < 3 or args.min_layout_pools > args.layout_sample_pools:
        raise SystemExit("--min-layout-pools must be between 3 and --layout-sample-pools")
    if args.page_size < 1 or args.page_size > 1000:
        raise SystemExit("--page-size must be between 1 and 1000")
    if args.max_signatures_per_pool < 1 or args.max_signatures_per_pool > 5000:
        raise SystemExit("--max-signatures-per-pool must be between 1 and 5000")

    gateway = TradeAwareCMISGateway()
    market = gateway._market_report(args.asset)
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
    catalog_pools = [
        pool for pool in catalog.get("pools", []) if isinstance(pool, Mapping)
    ]

    pool_set = verify_recognized_program_asset_pool_set(
        asset_mint=mint,
        catalog_pools=catalog_pools,
        rpc_url=gateway.x1_trade_rpc_url,
        layout_sample_pools=args.layout_sample_pools,
        min_layout_pools=args.min_layout_pools,
    )

    pool_set_verified = pool_set.get("summary", {}).get(
        "recognized_program_asset_pool_set_structurally_verified"
    ) is True
    pools = pool_set.get("pools") or []

    chain_activity = None
    errors = list(pool_set.get("errors") or [])
    end_epoch = time.time()
    if pool_set_verified:
        try:
            chain_activity = enumerate_chain_window_dex_activity(
                asset_mint=mint,
                pools=pools,
                start_epoch=end_epoch - window_seconds,
                end_epoch=end_epoch,
                rpc_url=gateway.x1_trade_rpc_url,
                page_size=args.page_size,
                max_signatures_per_pool=args.max_signatures_per_pool,
            )
        except Exception as exc:
            errors.append(
                {
                    "stage": "chain_window",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    chain_summary = (
        chain_activity.get("summary", {})
        if isinstance(chain_activity, Mapping)
        else {}
    )
    all_verified_program_pool_ranges_complete = chain_summary.get(
        "selected_pool_chain_window_complete"
    ) is True
    xdex_program_asset_window_complete = bool(
        pool_set_verified and all_verified_program_pool_ranges_complete
    )

    result = {
        "service": "verified_xdex_program_activity_probe",
        "version": "1.5.5",
        "chain": "x1",
        "asset": dict(resolved),
        "requested_window": args.window,
        "status": (
            "verified_xdex_program_window_complete"
            if xdex_program_asset_window_complete
            else "partial"
        ),
        "verified_program_pool_set": pool_set,
        "chain_window_activity": chain_activity,
        "summary": {
            "verified_program_id": pool_set.get("program_id"),
            "verified_program_pool_count": len(pools),
            "recognized_program_asset_pool_set_structurally_verified": (
                pool_set_verified
            ),
            "all_verified_program_pool_ranges_complete": (
                all_verified_program_pool_ranges_complete
            ),
            "xdex_program_asset_window_complete": (
                xdex_program_asset_window_complete
            ),
            "xdex_program_coverage_basis": (
                "VERIFIED_PROGRAM_POOL_SET_PLUS_X1_RPC_ADDRESS_HISTORY"
            ),
            "x1_all_dex_asset_window_complete": False,
            "recognized_program_registry_globally_exhaustive": False,
            "global_onchain_pool_discovery_proven": False,
            "effective_coverage_scope": (
                "verified_xdex_program"
                if xdex_program_asset_window_complete
                else "partial"
            ),
            "interpretation": (
                "A complete result proves the requested time window across every "
                "structurally verified target-mint pool state in the verified XDEX "
                "program. It does not prove that no other AMM program on X1 can "
                "trade the asset."
            ),
        },
        "errors": errors,
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
