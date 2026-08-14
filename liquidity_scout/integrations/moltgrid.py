"""MoltGrid entrypoint wired to reusable Liquidity Scout services.

This is a migration seam for the current v0.12 listener. It keeps the legacy
MoltGrid transport, formatting, AI routing, and conversation state intact while
replacing market catalog/resolution and deterministic snapshot construction at
runtime.

Run with:
    python -m liquidity_scout.integrations.moltgrid
"""

from importlib import import_module

from liquidity_scout.market import (
    AmbiguousAssetError,
    XDEXCatalog as CoreXDEXCatalog,
    resolve_asset as core_resolve_asset,
    resolve_multiple_assets as core_resolve_multiple_assets,
)
from liquidity_scout.services import build_market_report


class MoltGridXDEXCatalog(CoreXDEXCatalog):
    """Core XDEX catalog with the legacy listener's refresh status output."""

    def refresh(self):
        super().refresh()
        print(self.status_text())
        return self


def resolve_asset(question, pools):
    """Legacy-compatible adapter over the mint-aware core resolver.

    Ambiguous human-facing identifiers fail closed instead of crashing the
    listener loop or silently choosing one mint.
    """
    try:
        return core_resolve_asset(question, pools)
    except AmbiguousAssetError:
        return None, []


def resolve_multiple_assets(question, pools, max_assets=4):
    """Legacy-compatible multi-asset adapter that fails closed on ambiguity."""
    try:
        return core_resolve_multiple_assets(
            question,
            pools,
            max_assets=max_assets,
        )
    except AmbiguousAssetError:
        return []


def _value_or_zero(value):
    """Preserve the v0.12 presentation contract at the integration boundary."""
    return 0 if value is None else value


def compact_asset_snapshot(listener_module, term, matches, catalog):
    """Adapt the structured market report to the legacy v0.12 snapshot shape."""
    report = build_market_report(term, matches, catalog)

    symbol = report["symbol"]
    name = report.get("name") or ""
    if symbol.upper() == "XNT":
        title = "XNT"
    else:
        title = symbol
        if name and name.upper() != symbol.upper():
            title += f" ({name})"

    safety_text = report.get("safety_grade") or "N/A"
    safety_score = report.get("safety_score")
    if safety_score is not None and safety_score > 0:
        safety_text += f" ({safety_score:g}/100)"

    # The structured service preserves holder disagreement as uncertainty.
    # The legacy listener expects an integer, so keep its historical max-pool
    # compatibility behavior here until presentation is migrated separately.
    holders = report.get("holders")
    if holders is None:
        holders = report.get("holders_observed_max")

    primary_pool = report["primary_pool"]

    return {
        "title": title,
        "symbol": symbol,
        "token_address": report.get("mint") or "",
        "price": listener_module.format_usd(
            _value_or_zero(report.get("price_usd"))
        ),
        "price_usd_value": _value_or_zero(report.get("price_usd")),
        "age": listener_module.format_age(report.get("created_at")),
        "holders": int(_value_or_zero(holders)),
        "txns24": int(_value_or_zero(report.get("transactions_24h"))),
        "vol24": _value_or_zero(report.get("volume_24h_usd")),
        "change1": _value_or_zero(report.get("price_change_1h_pct")),
        "change24": _value_or_zero(report.get("price_change_24h_pct")),
        "liquidity": _value_or_zero(report.get("liquidity_usd")),
        "primary_liquidity": _value_or_zero(primary_pool.get("liquidity_usd")),
        "pool_count": report.get("lp_count", 0),
        "market_cap": _value_or_zero(report.get("market_cap_usd_reported")),
        "fdv": _value_or_zero(report.get("fdv_usd_reported")),
        "safety": safety_text,
        "pool": primary_pool.get("pair") or "",
        "pool_address": primary_pool.get("address") or "",
    }


def _snapshot_adapter(listener_module):
    def adapter(term, matches, catalog):
        return compact_asset_snapshot(listener_module, term, matches, catalog)

    return adapter


def wire_market_core(listener_module):
    """Replace legacy market globals with reusable core/service implementations."""
    listener_module.XDEXCatalog = MoltGridXDEXCatalog
    listener_module.resolve_asset = resolve_asset
    listener_module.resolve_multiple_assets = resolve_multiple_assets
    listener_module.compact_asset_snapshot = _snapshot_adapter(listener_module)
    return listener_module


def load_listener():
    """Import the legacy listener and wire it to Liquidity Scout Core."""
    listener = import_module("moltgrid_signal_v12_ollama")
    return wire_market_core(listener)


def main():
    listener = load_listener()
    listener.main()


if __name__ == "__main__":
    main()
