"""Deterministic XDEX asset ranking and public ranking presentation.

Exact ranks are assigned only when the requested metric is complete. Missing or
partial XDEX observations remain unavailable/incomplete rather than becoming
fabricated zeroes, and holder disagreement remains unverified.
"""

from liquidity_scout.market.aggregation import aggregate_assets


def _s(value):
    return str(value or "").strip()


def _metric_field(metric, use_txns_for_trending=True):
    if metric == "volume":
        return "volume24", "volume24"
    if metric == "liquidity":
        return "liquidity", "liquidity"
    if metric == "holders":
        return "holders", "holders"
    if metric == "safety":
        return "safety_score", "safety"
    if metric in ("gainers", "losers"):
        return "change24", "change24"
    if metric == "trending":
        return (
            ("txns1h", "txns1h")
            if use_txns_for_trending
            else ("volume1h", "volume1h")
        )
    raise ValueError(f"Unsupported ranking metric: {metric}")


def ranking_value(asset, metric, use_txns_for_trending=True):
    field, _complete_key = _metric_field(metric, use_txns_for_trending)
    return asset.get(field)


def ranking_complete(asset, metric, use_txns_for_trending=True):
    _field, complete_key = _metric_field(metric, use_txns_for_trending)
    return bool((asset.get("completeness") or {}).get(complete_key))


def _positive_value_required(metric):
    return metric in {
        "volume",
        "liquidity",
        "holders",
        "safety",
        "trending",
    }


def _summary(asset, metric, use_txns_for_trending, reason):
    return {
        "symbol": asset.get("symbol"),
        "name": asset.get("name"),
        "mint": asset.get("mint"),
        "value": ranking_value(asset, metric, use_txns_for_trending),
        "reason": reason,
    }


def _matches_query(asset, query):
    return (
        _s(asset.get("symbol")).upper() == query
        or _s(asset.get("mint")).upper() == query
        or _s(asset.get("name")).upper() == query
    )


def rank_assets(pools, metric="volume", limit=50):
    assets = aggregate_assets(pools)

    # Preserve the established trending preference: use transaction activity
    # when at least one exact positive 1h transaction observation exists.
    use_txns_for_trending = any(
        ranking_complete(asset, "trending", True)
        and (asset.get("txns1h") or 0) > 0
        for asset in assets
    )

    rankable = []
    incomplete = []
    excluded_zero = []

    for asset in assets:
        value = ranking_value(asset, metric, use_txns_for_trending)
        complete = ranking_complete(asset, metric, use_txns_for_trending)

        if not complete or value is None:
            incomplete.append(
                _summary(
                    asset,
                    metric,
                    use_txns_for_trending,
                    "requested_metric_incomplete",
                )
            )
            continue

        if _positive_value_required(metric) and value <= 0:
            excluded_zero.append(
                _summary(
                    asset,
                    metric,
                    use_txns_for_trending,
                    "verified_non_positive_value",
                )
            )
            continue

        rankable.append(asset)

    # Stable deterministic tie order independent of catalog row ordering.
    rankable.sort(key=lambda asset: _s(asset.get("mint")))
    ranked = sorted(
        rankable,
        key=lambda asset: ranking_value(
            asset,
            metric,
            use_txns_for_trending,
        ),
        reverse=(metric != "losers"),
    )

    for index, asset in enumerate(ranked, 1):
        asset["rank"] = index

    meta = {
        "trending_basis": (
            "1h transactions" if use_txns_for_trending else "1h volume"
        ),
        "ranked_count": len(ranked),
        "incomplete_count": len(incomplete),
        "unranked_incomplete": incomplete,
        "unranked_zero": excluded_zero,
    }

    return ranked[:limit], meta


def find_asset_rank(pools, query, metric="volume"):
    query = _s(query).upper()

    ranked, meta = rank_assets(
        pools,
        metric=metric,
        limit=100000,
    )

    result_meta = dict(meta)

    for asset in ranked:
        if _matches_query(asset, query):
            result_meta["query_status"] = "ranked"
            return asset, meta["ranked_count"], result_meta

    for asset in meta.get("unranked_incomplete", []):
        if _matches_query(asset, query):
            result_meta["query_status"] = "incomplete"
            result_meta["query_asset"] = asset
            return None, meta["ranked_count"], result_meta

    for asset in meta.get("unranked_zero", []):
        if _matches_query(asset, query):
            result_meta["query_status"] = "verified_non_positive"
            result_meta["query_asset"] = asset
            return None, meta["ranked_count"], result_meta

    result_meta["query_status"] = "not_found"
    return None, meta["ranked_count"], result_meta


def metric_text(asset, metric, meta=None):
    if metric == "volume":
        value = asset.get("volume24")
        return "unavailable" if value is None else f"${value:,.2f}"
    if metric == "liquidity":
        value = asset.get("liquidity")
        return "unavailable" if value is None else f"${value:,.2f}"
    if metric == "holders":
        value = asset.get("holders")
        return "unavailable" if value is None else f"{value:,.0f}"
    if metric == "safety":
        value = asset.get("safety_score")
        if value is None:
            return "unavailable"
        grade = asset["safety_grade"] or "N/A"
        return f"{grade} ({value:.0f}/100)"
    if metric in ("gainers", "losers"):
        value = asset.get("change24")
        return "unavailable" if value is None else f"{value:+.2f}%"
    if metric == "trending":
        basis = (meta or {}).get("trending_basis")
        if basis == "1h transactions":
            value = asset.get("txns1h")
            return "unavailable" if value is None else f"{value:,.0f} txns"
        value = asset.get("volume1h")
        return "unavailable" if value is None else f"${value:,.2f}"
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
        return "-----+--------------+----------------+------"

    return "-----+--------------+----------------+----------------+------"


def _liquidity_text(asset):
    value = asset.get("liquidity")
    if value is None:
        return "unavailable"
    if (asset.get("completeness") or {}).get("liquidity"):
        return f"${value:,.2f}"
    return f">=${value:,.2f}"


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

    liquidity_text = _liquidity_text(asset)

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

    if meta.get("incomplete_count"):
        lines.extend([
            "",
            (
                "Data note: "
                f"{meta['incomplete_count']} asset"
                f"{'s' if meta['incomplete_count'] != 1 else ''} excluded "
                "from the exact ranking because the requested metric is incomplete."
            ),
        ])

    return "\n".join(lines)


__all__ = [
    "display_asset",
    "find_asset_rank",
    "format_top",
    "metric_text",
    "rank_assets",
    "ranking_complete",
    "ranking_header",
    "ranking_row",
    "ranking_separator",
    "ranking_style",
    "ranking_value",
]
