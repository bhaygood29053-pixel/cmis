import historical_metrics as history
from liquidity_scout.market import XDEXCatalog, aggregate_assets


def build_snapshot_rows(pools, xnt_price_usd=None):
    """Build one historical snapshot row per mint from XDEX pool data."""
    rows = []

    for asset in aggregate_assets(pools):
        price = asset["price"]

        if asset["symbol"] == "XNT" and xnt_price_usd is not None:
            try:
                price = float(xnt_price_usd)
            except (TypeError, ValueError):
                price = asset["price"]

        rows.append(
            {
                "mint": asset["mint"],
                "symbol": asset["symbol"],
                "price": price,
                "liquidity": asset["liquidity"],
                "volume24": asset["volume24"],
                "holders": asset["holders"],
                "pool_count": asset["pool_count"],
            }
        )

    return rows


def record_catalog_snapshot(catalog):
    """Persist the current catalog snapshot and return the asset count."""
    rows = build_snapshot_rows(
        catalog.pools,
        xnt_price_usd=catalog.xnt_price_usd,
    )

    for row in rows:
        history.record_snapshot(**row)

    return len(rows)


def main():
    catalog = XDEXCatalog()
    catalog.refresh()

    recorded = record_catalog_snapshot(catalog)

    print(
        f"Historical snapshot complete: "
        f"{recorded:,} XDEX assets recorded"
    )


if __name__ == "__main__":
    main()
