"""
XDEX Catalog Probe

Read-only diagnostic for the X1.Ninja /v1/pools endpoint.
It NEVER prints your API key.
"""

import json
import requests
from config import SETTINGS

URL = "https://api.x1.ninja/v1/pools"


def compact_token(token):
    if not isinstance(token, dict):
        return token
    return {
        "symbol": token.get("symbol"),
        "name": token.get("name"),
        "mint": token.get("mint") or token.get("address"),
    }


def main():
    if not SETTINGS.api_key:
        raise SystemExit("ERROR: X1_NINJA_API_KEY is missing from .env")

    r = requests.get(
        URL,
        params={"limit": 5},
        headers={"Authorization": f"Bearer {SETTINGS.api_key}"},
        timeout=20,
    )

    print("HTTP status:", r.status_code)
    print("Rate-limit remaining:", r.headers.get("X-RateLimit-Remaining"))
    r.raise_for_status()

    body = r.json()

    print("\nTop-level response keys:")
    if isinstance(body, dict):
        print(sorted(body.keys()))
    else:
        print(type(body).__name__)

    # Print pagination-like metadata without dumping entire records.
    if isinstance(body, dict):
        print("\nPossible pagination metadata:")
        pagination_keys = [
            "total", "count", "limit", "offset", "page", "pages",
            "next", "nextCursor", "next_cursor", "cursor",
            "hasMore", "has_more"
        ]
        found = False
        for key in pagination_keys:
            if key in body:
                print(f"{key}: {body.get(key)}")
                found = True
        if not found:
            print("(none of the common pagination keys were present)")

        pools = body.get("pools", [])
    else:
        pools = []

    print(f"\nPools returned in this request: {len(pools)}")

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
