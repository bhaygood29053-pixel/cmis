"""
XDEX Asset Lookup v0.1 compatibility utility.

Market collection is delegated to the X1 Provider. This script only performs
read-only legacy lookup/presentation over the returned catalog.
"""

import argparse
from typing import Any, Dict, List

from liquidity_scout.providers.x1.market import (
    MARKET_SOURCE,
    fetch_all_pools as provider_fetch_all_pools,
)


def n(value, default=0.0):
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def s(value):
    return str(value or "").strip()


def token_matches(token: Dict[str, Any], query: str) -> bool:
    if not isinstance(token, dict):
        return False

    q = query.lower().strip()
    fields = [
        s(token.get("symbol")),
        s(token.get("name")),
        s(token.get("mint")),
        s(token.get("address")),
    ]
    return any(q == field.lower() for field in fields if field) or any(
        q in field.lower() for field in fields if field
    )


def fetch_all_pools():
    """Compatibility collection wrapper over the X1 market provider."""
    return provider_fetch_all_pools()


def pair_name(pool):
    base = pool.get("baseToken") or {}
    quote = pool.get("quoteToken") or {}
    return f"{s(base.get('symbol'))}/{s(quote.get('symbol'))}"


def find_asset(query: str, pools: List[Dict[str, Any]]):
    q = query.lower().strip()
    results = []

    for pool in pools:
        base = pool.get("baseToken") or {}
        quote = pool.get("quoteToken") or {}

        base_match = token_matches(base, q)
        quote_match = token_matches(quote, q)

        if base_match or quote_match:
            results.append({
                "pool": pool,
                "asset_side": "base" if base_match else "quote",
                "asset": base if base_match else quote,
                "other": quote if base_match else base,
            })

    results.sort(
        key=lambda item: (
            n(item["pool"].get("liquidity")),
            n(item["pool"].get("volume24h")),
        ),
        reverse=True,
    )
    return results


def print_pool_result(item, rank):
    pool = item["pool"]
    asset = item["asset"]
    other = item["other"]

    print("=" * 72)
    print(f"MATCH {rank}")
    print(f"Asset: {s(asset.get('symbol'))} — {s(asset.get('name'))}")
    print(f"Mint:  {s(asset.get('mint') or asset.get('address'))}")
    print(f"Pair:  {pair_name(pool)}")
    print(f"Pool:  {s(pool.get('address'))}")
    print(f"Price USD:      ${n(pool.get('priceUsd')):,.12g}")
    print(f"Price native:   {n(pool.get('priceNative')):,.12g}")
    print(f"Liquidity:      ${n(pool.get('liquidity')):,.2f}")
    print(f"24h volume:     ${n(pool.get('volume24h')):,.2f}")
    print(f"1h volume:      ${n(pool.get('volume1h')):,.2f}")
    print(f"24h change:     {n(pool.get('priceChange24h')):+.2f}%")
    print(f"Market cap:     ${n(pool.get('marketCap')):,.2f}")
    print(f"FDV:            ${n(pool.get('fdv')):,.2f}")
    print(f"Holders:        {int(n(pool.get('holders'))):,}")
    print(f"24h txns:       {int(n(pool.get('txns24h'))):,}")
    print(
        f"Safety:         {s(pool.get('safetyGrade')) or 'N/A'} "
        f"({n(pool.get('safetyScore')):g})"
    )
    print(f"Other token:    {s(other.get('symbol'))} — {s(other.get('name'))}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Search all XDEX assets")
    parser.add_argument(
        "asset",
        help="Token symbol, name, mint, or pool-related asset text (example: XNT)",
    )
    args = parser.parse_args()

    pools, xnt_price_usd = fetch_all_pools()

    print(f"Source: {MARKET_SOURCE}")
    print(f"XDEX pools loaded: {len(pools)}")
    if xnt_price_usd is not None:
        print(f"XNT reference price: ${n(xnt_price_usd):,.8f}")
    print()

    query = args.asset.strip()
    if query.lower() in {"xnt", "wrapped xnt"} and xnt_price_usd is not None:
        print(f"XNT USD price: ${n(xnt_price_usd):,.8f}")
        print()

    matches = find_asset(query, pools)
    if not matches:
        print(f"No XDEX asset/pool match found for: {query}")
        print("Try the exact token symbol, token name, mint address, or pool address.")
        return

    print(f"Matches found: {len(matches)}")
    print("Showing up to 5 strongest pools by liquidity/volume.")
    print()

    for rank, item in enumerate(matches[:5], 1):
        print_pool_result(item, rank)

    print("=" * 72)
    print("LOOKUP COMPLETE — read only; no trade or MoltGrid post was made.")


if __name__ == "__main__":
    main()
