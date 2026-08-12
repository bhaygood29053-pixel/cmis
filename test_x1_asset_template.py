
"""
Generate a live FOREST report using the master X1 asset template.
This does NOT post to MoltGrid.
"""

from pathlib import Path
import moltgrid_signal_v12_ollama as scout
from liquidity_scout_template_renderer import render_report


def main():
    catalog = scout.XDEXCatalog()
    catalog.refresh()

    term, matches = scout.resolve_asset("Tell me about FOREST", catalog.pools)
    if not matches:
        raise SystemExit("FOREST was not found on XDEX.")

    snap = scout.compact_asset_snapshot(term, matches, catalog)

    bottom_line = scout.plain_language_summary(
        snap["change24"],
        snap["liquidity"],
        snap["vol24"],
        snap["safety"].split(" ")[0],
    )

    out = render_report(snap, bottom_line)

    print("X1 asset template test: PASS")
    print(f"Asset: {snap['symbol']}")
    print(f"Created: {out}")


if __name__ == "__main__":
    main()
