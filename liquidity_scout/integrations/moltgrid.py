"""MoltGrid entrypoint wired to the reusable Liquidity Scout market core.

This is a migration seam for the current v0.12 listener. It keeps the legacy
MoltGrid transport, formatting, AI routing, and conversation state intact while
replacing the listener's market catalog and asset-resolution globals at runtime.

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


def wire_market_core(listener_module):
    """Replace the legacy listener's market globals with core implementations."""
    listener_module.XDEXCatalog = MoltGridXDEXCatalog
    listener_module.resolve_asset = resolve_asset
    listener_module.resolve_multiple_assets = resolve_multiple_assets
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
