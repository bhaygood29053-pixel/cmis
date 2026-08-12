"""
Create a local FOREST preview card from live XDEX data.
No MoltGrid post is created.
"""

from pathlib import Path

import moltgrid_signal_v12_ollama as scout
from liquidity_scout_graphics import render_asset_card


def main():
    catalog = scout.XDEXCatalog()
    catalog.refresh()

    term, matches = scout.resolve_asset("Tell me about FOREST", catalog.pools)
    if not matches:
        raise SystemExit("FOREST was not found in the current XDEX catalog.")

    snap = scout.compact_asset_snapshot(term, matches, catalog)

    out = (
        Path(__file__).resolve().parent
        / "data"
        / "graphics"
        / "FOREST_preview.png"
    )

    render_asset_card(
        snap,
        out,
        subtitle="XDEX ASSET SNAPSHOT",
    )

    print("Graphics test: PASS")
    print(f"Created: {out}")


if __name__ == "__main__":
    main()
