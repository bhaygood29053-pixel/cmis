import historical_metrics as history
import moltgrid_signal_v12_ollama as scout


def main():
    catalog = scout.XDEXCatalog()
    catalog.refresh()

    assets = {}

    for pool in catalog.pools:
        for side_name in ("baseToken", "quoteToken"):
            token = pool.get(side_name) or {}

            symbol = scout.s(token.get("symbol")).upper()
            mint = scout.s(
                token.get("mint")
                or token.get("address")
            )

            if not symbol or not mint:
                continue

            key = mint

            if key not in assets:
                assets[key] = {
                    "symbol": symbol,
                    "mint": mint,
                    "pools": [],
                }

            assets[key]["pools"].append(pool)

    recorded = 0

    for item in assets.values():
        symbol = item["symbol"]
        mint = item["mint"]
        pools = item["pools"]

        # Remove duplicate pool objects for this asset.
        unique_pools = []
        seen = set()

        for pool in pools:
            pool_key = (
                scout.s(pool.get("address"))
                or scout.s(pool.get("poolAddress"))
                or scout.s(pool.get("id"))
                or str(id(pool))
            )

            if pool_key in seen:
                continue

            seen.add(pool_key)
            unique_pools.append(pool)

        if not unique_pools:
            continue

        # Use the deepest pool as the representative price source.
        primary = max(
            unique_pools,
            key=lambda p: scout.n(p.get("liquidity")),
        )

        if symbol == "XNT" and catalog.xnt_price_usd is not None:
            price = scout.n(catalog.xnt_price_usd)
        else:
            price = scout.n(primary.get("priceUsd"))

        liquidity = sum(
            scout.n(p.get("liquidity"))
            for p in unique_pools
        )

        volume24 = sum(
            scout.n(p.get("volume24h"))
            for p in unique_pools
        )

        holders = max(
            (
                scout.n(p.get("holders"))
                for p in unique_pools
            ),
            default=0,
        )

        history.record_snapshot(
            mint=mint,
            symbol=symbol,
            price=price,
            liquidity=liquidity,
            volume24=volume24,
            holders=holders,
            pool_count=len(unique_pools),
        )

        recorded += 1

    print(
        f"Historical snapshot complete: "
        f"{recorded:,} XDEX assets recorded"
    )


if __name__ == "__main__":
    main()
