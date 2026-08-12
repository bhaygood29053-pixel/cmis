"""
Liquidity Scout graphics test v2.

Fetches live FOREST data from XDEX and saves the generated card to:
    graphics/generated/FOREST_snapshot.png

No MoltGrid post is created.
"""

from pathlib import Path

import moltgrid_signal_v12_ollama as scout
from liquidity_scout_graphics import render_asset_card


def main():
    project_root = Path(__file__).resolve().parent
    output_dir = project_root / "graphics" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    catalog = scout.XDEXCatalog()
    catalog.refresh()

    term, matches = scout.resolve_asset(
        "Tell me about FOREST",
        catalog.pools,
    )

    if not matches:
        raise SystemExit("FOREST was not found in the current XDEX catalog.")

    snap = scout.compact_asset_snapshot(term, matches, catalog)

    output_path = output_dir / "FOREST_snapshot.png"

    render_asset_card(
        snap,
        output_path,
        subtitle="XDEX ASSET SNAPSHOT",
    )

    print("Graphics test: PASS")
    print(f"Asset: {snap['symbol']}")
    print(f"Token: {snap['token_address']}")
    print(f"Pool: {snap['pool']}")
    print(f"Pool address: {snap['pool_address']}")
    print(f"Created: {output_path}")


if __name__ == "__main__":
    main()
