"""Legacy compatibility shim for Liquidity Scout ranking services.

Outside the canonical MoltGrid listener this module remains a direct compatibility
view over the pure ranking service.  When Liquidity Scout is launched with
``python -m liquidity_scout.integrations.moltgrid``, listener-facing ranking
operations dynamically resolve to CMIS-backed adapters instead.  This keeps
shared calculation code pure while making the live MoltGrid path exercise the
same ``rank`` gateway contract future Scouts consume.
"""

import os
import sys

from liquidity_scout.services.market_rankings import (
    display_asset,
    find_asset_rank as _core_find_asset_rank,
    format_top as _core_format_top,
    metric_text,
    rank_assets,
    ranking_header,
    ranking_row as _core_ranking_row,
    ranking_separator as _core_ranking_separator,
    ranking_style,
    ranking_value,
)


def _cmis_rank_runtime_enabled():
    explicit = os.getenv("LIQUIDITY_SCOUT_CMIS_RANK_ROUTING", "").strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    if explicit in {"0", "false", "no", "off"}:
        return False

    main_module = sys.modules.get("__main__")
    spec = getattr(main_module, "__spec__", None)
    return getattr(spec, "name", None) == "liquidity_scout.integrations.moltgrid"


def _cmis_ranking_separator(_metric):
    """Omit the legacy dashed divider from CMIS-backed rank presentation."""
    return ""


def __getattr__(name):
    if name not in {"find_asset_rank", "format_top", "ranking_row", "ranking_separator"}:
        raise AttributeError(name)

    if _cmis_rank_runtime_enabled():
        if name == "ranking_separator":
            return _cmis_ranking_separator

        from liquidity_scout.integrations import moltgrid_rank_cmis

        return getattr(moltgrid_rank_cmis, name)

    return {
        "find_asset_rank": _core_find_asset_rank,
        "format_top": _core_format_top,
        "ranking_row": _core_ranking_row,
        "ranking_separator": _core_ranking_separator,
    }[name]


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
