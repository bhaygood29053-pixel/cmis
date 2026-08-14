def s(value):
    return str(value or "").strip()


def n(value, default=0.0):
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def get_num(obj, *keys):
    for key in keys:
        if key in obj and obj.get(key) is not None:
            return n(obj.get(key))
    return 0.0


def pool_id(pool):
    return (
        s(pool.get("address"))
        or s(pool.get("poolAddress"))
        or s(pool.get("id"))
        or repr(pool)
    )


def token_identity(token):
    symbol = s(token.get("symbol")).upper()
    name = s(token.get("name"))
    mint = s(
        token.get("mint")
        or token.get("address")
    )
    return symbol, name, mint


def aggregate_assets(pools):
    """
    Aggregate X1.Ninja/XDEX pool data into one record per token.
    Liquidity and volume are summed across that token's pools.
    """
    assets = {}

    for pool in pools:
        pid = pool_id(pool)

        for side in ("baseToken", "quoteToken"):
            token = pool.get(side) or {}

            symbol, name, mint = token_identity(token)

            if not symbol or not mint:
                continue

            asset = assets.setdefault(
                mint,
                {
                    "symbol": symbol,
                    "name": name,
                    "mint": mint,
                    "pools": {},
                },
            )

            asset["pools"][pid] = pool

    results = []

    for asset in assets.values():
        token_pools = list(asset["pools"].values())

        if not token_pools:
            continue

        primary = max(
            token_pools,
            key=lambda p: get_num(
                p,
                "liquidity",
            ),
        )

        volume24 = sum(
            get_num(p, "volume24h")
            for p in token_pools
        )

        volume1h = sum(
            get_num(p, "volume1h")
            for p in token_pools
        )

        liquidity = sum(
            get_num(p, "liquidity")
            for p in token_pools
        )

        txns1h = sum(
            get_num(
                p,
                "txns1h",
                "transactions1h",
            )
            for p in token_pools
        )

        txns24h = sum(
            get_num(
                p,
                "txns24h",
                "transactions24h",
            )
            for p in token_pools
        )

        holders = max(
            (
                get_num(p, "holders")
                for p in token_pools
            ),
            default=0.0,
        )

        results.append(
            {
                "symbol": asset["symbol"],
                "name": asset["name"],
                "mint": asset["mint"],
                "pool_count": len(token_pools),

                # Aggregated metrics
                "volume24": volume24,
                "volume1h": volume1h,
                "liquidity": liquidity,
                "txns1h": txns1h,
                "txns24h": txns24h,
                "holders": holders,

                # Primary/deepest pool metrics
                "price": get_num(
                    primary,
                    "priceUsd",
                ),
                "change24": get_num(
                    primary,
                    "priceChange24h",
                ),
                "change1h": get_num(
                    primary,
                    "priceChange1h",
                ),
                "safety_score": get_num(
                    primary,
                    "safetyScore",
                ),
                "safety_grade": s(
                    primary.get("safetyGrade")
                ),
            }
        )

    return results


def ranking_value(asset, metric, use_txns_for_trending=True):
    if metric == "volume":
        return asset["volume24"]

    if metric == "liquidity":
        return asset["liquidity"]

    if metric == "holders":
        return asset["holders"]

    if metric == "safety":
        return asset["safety_score"]

    if metric == "gainers":
        return asset["change24"]

    if metric == "losers":
        return asset["change24"]

    if metric == "trending":
        if use_txns_for_trending:
            return asset["txns1h"]
        return asset["volume1h"]

    raise ValueError(
        f"Unsupported ranking metric: {metric}"
    )


def rank_assets(pools, metric="volume", limit=50):
    assets = aggregate_assets(pools)

    # X1.Ninja catalogs can differ in whether txns1h is exposed.
    # If there is no 1h transaction count at all, use 1h volume
    # as the deterministic trending fallback.
    use_txns_for_trending = any(
        a["txns1h"] > 0
        for a in assets
    )

    reverse = metric != "losers"

    ranked = sorted(
        assets,
        key=lambda a: (
            ranking_value(
                a,
                metric,
                use_txns_for_trending,
            ),
            a["liquidity"],
        ),
        reverse=reverse,
    )

    # Avoid zero-value junk at the bottom of requested rankings.
    if metric == "volume":
        ranked = [
            a for a in ranked
            if a["volume24"] > 0
        ]

    elif metric == "liquidity":
        ranked = [
            a for a in ranked
            if a["liquidity"] > 0
        ]

    elif metric == "holders":
        ranked = [
            a for a in ranked
            if a["holders"] > 0
        ]

    elif metric == "safety":
        ranked = [
            a for a in ranked
            if a["safety_score"] > 0
        ]

    elif metric == "trending":
        key = (
            "txns1h"
            if use_txns_for_trending
            else "volume1h"
        )

        ranked = [
            a for a in ranked
            if a[key] > 0
        ]

    for index, asset in enumerate(ranked, 1):
        asset["rank"] = index

    return ranked[:limit], {
        "trending_basis": (
            "1h transactions"
            if use_txns_for_trending
            else "1h volume"
        )
    }


def find_asset_rank(pools, query, metric="volume"):
    query = s(query).upper()

    ranked, meta = rank_assets(
        pools,
        metric=metric,
        limit=100000,
    )

    for asset in ranked:
        if (
            asset["symbol"].upper() == query
            or asset["mint"].upper() == query
            or asset["name"].upper() == query
        ):
            return asset, len(ranked), meta

    return None, len(ranked), meta


def metric_text(asset, metric, meta=None):
    if metric == "volume":
        return f"${asset['volume24']:,.2f}"

    if metric == "liquidity":
        return f"${asset['liquidity']:,.2f}"

    if metric == "holders":
        return f"{asset['holders']:,.0f}"

    if metric == "safety":
        grade = asset["safety_grade"] or "N/A"
        return (
            f"{grade} "
            f"({asset['safety_score']:.0f}/100)"
        )

    if metric in ("gainers", "losers"):
        return f"{asset['change24']:+.2f}%"

    if metric == "trending":
        basis = (
            (meta or {}).get("trending_basis")
        )

        if basis == "1h transactions":
            return f"{asset['txns1h']:,.0f} txns"

        return f"${asset['volume1h']:,.2f}"

    return ""


def ranking_style(metric, meta=None):
    styles = {
        "volume": {
            "icon": "📊",
            "label": "24H VOLUME",
            "column": "24H VOLUME",
        },
        "liquidity": {
            "icon": "💧",
            "label": "LIQUIDITY",
            "column": "LIQUIDITY",
        },
        "holders": {
            "icon": "👥",
            "label": "HOLDERS",
            "column": "HOLDERS",
        },
        "safety": {
            "icon": "🛡️",
            "label": "TOKENOMICS SAFETY",
            "column": "SAFETY",
        },
        "gainers": {
            "icon": "🚀",
            "label": "24H GAINERS",
            "column": "24H CHANGE",
        },
        "losers": {
            "icon": "📉",
            "label": "24H LOSERS",
            "column": "24H CHANGE",
        },
        "trending": {
            "icon": "🔥",
            "label": "1H TRENDING",
            "column": (
                "1H TXNS"
                if (meta or {}).get("trending_basis") == "1h transactions"
                else "1H VOLUME"
            ),
        },
    }

    return styles.get(
        metric,
        {
            "icon": "📊",
            "label": metric.upper(),
            "column": metric.upper(),
        },
    )


def display_asset(symbol, width=12):
    """Keep asset symbols inside the table width."""
    symbol = str(symbol or "")

    if len(symbol) <= width:
        return symbol

    return symbol[:width]


def ranking_header(metric, meta=None):
    style = ranking_style(metric, meta)

    if metric == "liquidity":
        return (
            f"{'RANK':<4} | "
            f"{'ASSET':<12} | "
            f"{style['column']:>14} | "
            f"{'#LPs':>5}"
        )

    return (
        f"{'RANK':<4} | "
        f"{'ASSET':<12} | "
        f"{style['column']:>14} | "
        f"{'LIQUIDITY':>14} | "
        f"{'#LPs':>5}"
    )


def ranking_separator(metric):
    if metric == "liquidity":
        return (
            "-----+--------------+"
            "----------------+------"
        )

    return (
        "-----+--------------+"
        "----------------+"
        "----------------+------"
    )


def ranking_row(asset, metric, meta=None):
    value = metric_text(
        asset,
        metric,
        meta,
    )

    rank_text = f"#{asset['rank']}"
    symbol = display_asset(
        asset["symbol"],
        12,
    )

    lp_count = str(
        asset["pool_count"]
    )

    if metric == "liquidity":
        return (
            f"{rank_text:<4} | "
            f"{symbol:<12} | "
            f"{value:>14} | "
            f"{lp_count:>5}"
        )

    liquidity_text = (
        f"${asset['liquidity']:,.2f}"
    )

    return (
        f"{rank_text:<4} | "
        f"{symbol:<12} | "
        f"{value:>14} | "
        f"{liquidity_text:>14} | "
        f"{lp_count:>5}"
    )


def format_top(pools, metric="volume", limit=10):
    ranked, meta = rank_assets(
        pools,
        metric=metric,
        limit=limit,
    )

    style = ranking_style(metric, meta)

    lines = [
        f"{style['icon']} X1.NINJA / XDEX TOP {len(ranked)}",
        style["label"],
    ]

    if metric == "trending":
        basis = meta.get("trending_basis")

        if basis:
            lines[1] += (
                " • Ranked by transactions"
                if basis == "1h transactions"
                else " • Ranked by volume"
            )

    lines.extend([
        "",
        ranking_header(metric, meta),
        ranking_separator(metric),
    ])

    for asset in ranked:
        lines.append(
            ranking_row(
                asset,
                metric,
                meta,
            )
        )

    return "\n".join(lines)
