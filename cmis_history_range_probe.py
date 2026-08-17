#!/usr/bin/env python3
"""Read-only CMIS v1.3.1 history-range proof probe."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.market.resolver import (
    find_matches_for_term,
    pair_name,
    pool_address,
)
from liquidity_scout.providers.x1.history_range import (
    compare_provider_rows_to_chain,
    scan_address_history_range,
    summarize_entries_for_window,
)
from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw
from liquidity_scout.services.cmis_activity_window import (
    parse_activity_window_seconds,
)
from liquidity_scout.services.cmis_history_range_artifact import (
    sanitize_history_range_probe_result,
)


def _text(value):
    text = str(value or "").strip()
    return text or None


def _parse_provider_epoch(value):
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).timestamp()


def _iso_epoch(value):
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
        pools.append(pool)

    return market, resolved, pools[:max_pools], len(pools)


def build_history_range_probe_result(
    asset,
    *,
    window="1h",
    max_pools=5,
    max_signatures_per_pool=5000,
    page_size=1000,
    end_epoch=None,
):
    """Build one bounded history-range observation before artifact sanitization."""
    if max_pools <= 0 or max_pools > 10:
        raise ValueError("max_pools must be 1..10")

    seconds = parse_activity_window_seconds(window)
    end_epoch = time.time() if end_epoch is None else float(end_epoch)
    requested_start = end_epoch - seconds

    gateway = TradeAwareCMISGateway()
    market, resolved, pools, matched_pool_count = _resolve_asset_pools(
        gateway, asset, max_pools
    )

    reports = []

    for pool in pools:
        address = pool_address(pool)
        provider = fetch_pool_trades_raw(address)
        raw = (
            provider.get("raw_response")
            if isinstance(provider, Mapping)
            else None
        )
        rows = raw.get("trades") if isinstance(raw, Mapping) else []
        rows = rows if isinstance(rows, list) else []

        provider_epochs = [
            _parse_provider_epoch(row.get("timestamp"))
            for row in rows
            if isinstance(row, Mapping)
        ]
        provider_epochs = [
            value for value in provider_epochs if value is not None
        ]

        # Scan at least as far back as the requested window. When possible,
        # extend to the oldest returned provider row so sampled provider rows
        # can be linked to chain signatures without assuming provider ordering.
        scan_start = requested_start
        if provider_epochs:
            scan_start = min(scan_start, min(provider_epochs))

        chain = scan_address_history_range(
            address,
            start_epoch=scan_start,
            end_epoch=end_epoch,
            rpc_url=gateway.x1_trade_rpc_url,
            page_size=page_size,
            max_signatures=max_signatures_per_pool,
        )

        entries = chain.pop("entries", [])
        requested_window_chain = summarize_entries_for_window(
            entries,
            start_epoch=requested_start,
            end_epoch=end_epoch,
        )
        comparison = compare_provider_rows_to_chain(rows, entries)

        contract = provider.get("contract")
        contract = contract if isinstance(contract, Mapping) else {}

        reports.append({
            "pool_address": address,
            "pair": pair_name(pool),
            "provider_history": {
                "returned_row_count": len(rows),
                "provider_total_raw": contract.get("provider_total_raw"),
                "provider_last_updated_raw": contract.get(
                    "provider_last_updated_raw"
                ),
                "transport_pagination_or_range_verified": bool(
                    (
                        provider.get("semantics")
                        if isinstance(provider.get("semantics"), Mapping)
                        else {}
                    ).get("pagination_or_range_verified")
                    is True
                ),
            },
            "requested_window_chain": requested_window_chain,
            "proof_scan": chain,
            "provider_chain_comparison": comparison,
        })

    all_chain_ranges = bool(reports) and all(
        item["proof_scan"]["range_proven"] for item in reports
    )
    all_ordering_observed = bool(reports) and all(
        item["provider_chain_comparison"][
            "provider_ordering_observed_consistent"
        ]
        for item in reports
    )
    all_overlap_identity = bool(reports) and all(
        item["provider_chain_comparison"]["overlapping_identity_verified"]
        for item in reports
    )

    return {
        "service": "history_range_probe",
        "version": "1.3.1",
        "chain": "x1",
        "asset": dict(resolved),
        "status": (
            "observed_chain_range_proven" if all_chain_ranges else "partial"
        ),
        "requested_window": {
            "label": window,
            "duration_seconds": seconds,
            "start_epoch": requested_start,
            "start_utc": _iso_epoch(requested_start),
            "end_epoch": end_epoch,
            "end_utc": _iso_epoch(end_epoch),
            "membership_basis": "X1_RPC_BLOCK_TIME",
        },
        "market_snapshot_status": market.get("status"),
        "matched_pool_count": matched_pool_count,
        "selected_pool_count": len(pools),
        "pools": reports,
        "summary": {
            "all_selected_pool_proof_ranges_proven": all_chain_ranges,
            # Backward-compatible alias for the v1.3 probe summary.
            "all_selected_pool_chain_ranges_proven": all_chain_ranges,
            "all_provider_ordering_observed_consistent": all_ordering_observed,
            "all_overlapping_provider_chain_identity_verified": (
                all_overlap_identity
            ),
            "provider_range_contract_verified": False,
            "cmis_window_completion_promoted": False,
            "interpretation": (
                "requested_window reports the literal user-requested time "
                "interval. proof_scan may extend farther backward so provider "
                "sample rows can be linked to X1 RPC without assuming provider "
                "ordering. A proven proof_scan still does not establish "
                "provider index exhaustiveness, so CMIS window completeness "
                "remains gated."
            ),
        },
        "errors": [],
    }


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
    parser.add_argument(
        "--output",
        default=os.getenv("X1_HISTORY_RANGE_OUTPUT"),
        help="optional path for the sanitized retained artifact",
    )
    args = parser.parse_args()

    try:
        result = build_history_range_probe_result(
            args.asset,
            window=args.window,
            max_pools=args.max_pools,
            max_signatures_per_pool=args.max_signatures_per_pool,
            page_size=args.page_size,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    artifact = sanitize_history_range_probe_result(result)
    encoded = json.dumps(artifact, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(encoded + "\n", encoding="utf-8")

    # Console output is the same sanitized retained contract. Raw signatures,
    # raw provider payloads, and credentials are never printed here.
    print(encoded)


if __name__ == "__main__":
    main()


__all__ = ["build_history_range_probe_result"]
