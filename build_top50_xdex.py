import csv
import json
from datetime import datetime, timezone

import moltgrid_signal_v12_ollama as scout


TOP_N = 50
JSON_FILE = "top50_xdex_assets.json"
CSV_FILE = "top50_xdex_assets.csv"


def token_identity(token):
    symbol = scout.s(token.get("symbol")).upper()
    name = scout.s(token.get("name"))

    mint = scout.s(
        token.get("mint")
        or token.get("address")
    )

    return symbol, name, mint


def pool_id(pool):
    return (
        scout.s(pool.get("address"))
        or scout.s(pool.get("poolAddress"))
        or scout.s(pool.get("id"))
        or repr(pool)
    )


def main():
    catalog = scout.XDEXCatalog()
    catalog.refresh()

    assets = {}

    for pool in catalog.pools:
        pid = pool_id(pool)

        volume24 = scout.n(pool.get("volume24h"))
        liquidity = scout.n(pool.get("liquidity"))

        for side in ("baseToken", "quoteToken"):
            token = pool.get(side) or {}

            symbol, name, mint = token_identity(token)

            if not symbol or not mint:
                continue

            if mint not in assets:
                assets[mint] = {
                    "symbol": symbol,
                    "name": name,
                    "mint": mint,
                    "pools": {},
                }

            # Dedupe the same pool for this token.
            assets[mint]["pools"][pid] = {
                "volume24": volume24,
                "liquidity": liquidity,
            }

    ranked = []

    for asset in assets.values():
        pools = list(asset["pools"].values())

        total_volume24 = sum(
            p["volume24"] for p in pools
        )

        total_liquidity = sum(
            p["liquidity"] for p in pools
        )

        ranked.append(
            {
                "symbol": asset["symbol"],
                "name": asset["name"],
                "mint": asset["mint"],
                "volume24": total_volume24,
                "liquidity": total_liquidity,
                "pool_count": len(pools),
            }
        )

    # Primary rank = 24h volume.
    # Liquidity acts as deterministic tie-breaker.
    ranked.sort(
        key=lambda x: (
            x["volume24"],
            x["liquidity"],
        ),
        reverse=True,
    )

    top50 = ranked[:TOP_N]

    generated_at = datetime.now(
        timezone.utc
    ).isoformat()

    output = {
        "generated_at": generated_at,
        "ranking_method": (
            "sum of XDEX 24h volume across all pools; "
            "liquidity used as secondary tie-breaker"
        ),
        "total_assets_seen": len(ranked),
        "top_n": TOP_N,
        "assets": [],
    }

    for rank, asset in enumerate(top50, 1):
        row = {
            "rank": rank,
            **asset,
        }

        output["assets"].append(row)

    with open(JSON_FILE, "w") as f:
        json.dump(
            output,
            f,
            indent=2,
        )

    with open(
        CSV_FILE,
        "w",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rank",
                "symbol",
                "name",
                "mint",
                "volume24",
                "liquidity",
                "pool_count",
            ],
        )

        writer.writeheader()

        for row in output["assets"]:
            writer.writerow(row)

    print()
    print(
        f"XDEX assets found: {len(ranked)}"
    )
    print(
        f"Top {TOP_N} saved to:"
    )
    print(f"  {JSON_FILE}")
    print(f"  {CSV_FILE}")
    print()

    print(
        f"{'Rank':<6}"
        f"{'Symbol':<16}"
        f"{'24h Volume':>16}"
        f"{'Liquidity':>16}"
        f"{'Pools':>8}"
    )

    print("-" * 62)

    for row in top50:
        print(
            f"{row['rank']:<6}"
            f"{row['symbol']:<16}"
            f"${row['volume24']:>14,.2f}"
            f"${row['liquidity']:>14,.2f}"
            f"{row['pool_count']:>8}"
        )


if __name__ == "__main__":
    main()
