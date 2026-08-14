"""Legacy compatibility shim for Liquidity Scout ranking services."""

from liquidity_scout.services.market_rankings import (
    display_asset,
    find_asset_rank,
    format_top,
    metric_text,
    rank_assets,
    ranking_header,
    ranking_row,
    ranking_separator,
    ranking_style,
    ranking_value,
)

__all__ = [
    "display_asset",
    "find_asset_rank",
    "format_top",
    "metric_text",
    "rank_assets",
    "ranking_header",
    "ranking_row",
    "ranking_separator",
    "ranking_style",
    "ranking_value",
]
