"""Read-only diagnostic over the X1 Provider's X1.Ninja/XDEX catalog."""

import json

from liquidity_scout.providers.x1.market import (
    MARKET_SOURCE,
    POOLS_URL,
    X1Provider,
)


def compact_token(token):
    if not isinstance(token, dict):
        return token
    return {
        "symbol": token.get("symbol"),
        "name": token.get("name"),
        "mint": token.get("mint") or token.get("address"),
    }


def main():
    provider = X1Provider()
    provider.refresh()
    catalog = provider.market_catalog()
    pools = catalog["pools"]

    print("Source:", MARKET_SOURCE)
    print("Endpoint:", POOLS_URL)
    print("Observed at:", catalog.get("observed_at"))
    print("Pools loaded:", len(pools))
    print("XNT reference price:", catalog.get("xnt_price_usd"))
    print(
        "Rate-limit remaining: unavailable through the provider contract "
        "(raw HTTP headers are intentionally not exposed)"
    )

    for i, pool in enumerate(pools[:5], 1):
        print("\n" + "=" * 72)
        print(f"POOL {i}")
        print("Pool record keys:", sorted(pool.keys()) if isinstance(pool, dict) else "N/A")
        if isinstance(pool, dict):
            print("Address:", pool.get("address") or pool.get("poolAddress") or pool.get("id"))
            print("Base token:", json.dumps(compact_token(pool.get("baseToken")), indent=2))
            print("Quote token:", json.dumps(compact_token(pool.get("quoteToken")), indent=2))
            print("priceUsd:", pool.get("priceUsd"))
            print("liquidityUsd:", pool.get("liquidityUsd"))
            print("volume24h:", pool.get("volume24h"))

    print("\n" + "=" * 72)
    print("PROBE COMPLETE — read only, no trades or MoltGrid posts were made.")


if __name__ == "__main__":
    main()
