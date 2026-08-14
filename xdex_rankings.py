from liquidity_scout.market.aggregation import aggregate_assets


def s(value):
    return str(value or "").strip()


def ranking_value(asset, metric, use_txns_for_trending=True):
    if metric == "volume":
        return asset["volume24"]
    if metric == "liquidity":
        return asset["liquidity"]
    if metric == "holders":
        return asset["holders"]
    if metric == "safety":
        return asset["safety_score"]
    if metric in ("gainers", "losers"):
        return asset["change24"]
    if metric == "trending":
        return asset["txns1h"] if use_txns_for_trending else asset["volume1h"]
    raise ValueError(f"Unsupported ranking metric: {metric}")


def rank_assets(pools, metric="volume", limit=50):
    assets = aggregate_assets(pools)

    use_txns_for_trending = any(
        asset["txns1h"] > 0
        for asset in assets
    )

    reverse = metric != "losers"
    ranked = sorted(
        assets,
        key=lambda asset: (
            ranking_value(asset, metric, use_txns_for_trending),
            asset["liquidity"],
        ),
        reverse=reverse,
    )

    if metric == "volume":
        ranked = [asset for asset in ranked if asset["volume24"] > 0]
    elif metric == "liquidity":
        ranked = [asset for asset in ranked if asset["liquidity"] > 0]
    elif metric == "holders":
        ranked = [asset for asset in ranked if asset["holders"] > 0]
    elif metric == "safety":
        ranked = [asset for asset in ranked if asset["safety_score"] > 0]
    elif metric == "trending":
        key = "txns1h" if use_txns_for_trending else "volume1h"
        ranked = [asset for asset in ranked if asset[key] > 0]

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
        return f"{grade} ({asset['safety_score']:.0f}/100)"
    if metric in ("gainers", "losers"):
        return f"{asset['change24']:+.2f}%"
    if metric == "trending":
        basis = (meta or {}).get("trending_basis")
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
    value = metric_text(asset, metric, meta)
    rank_text = f"#{asset['rank']}"
    symbol = display_asset(asset["symbol"], 12)
    lp_count = str(asset["pool_count"])

    if metric == "liquidity":
        return (
            f"{rank_text:<4} | "
            f"{symbol:<12} | "
            f"{value:>14} | "
            f"{lp_count:>5}"
        )

    liquidity_text = f"${asset['liquidity']:,.2f}"

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
        lines.append(ranking_row(asset, metric, meta))

    return "\n".join(lines)
