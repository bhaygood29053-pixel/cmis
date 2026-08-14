"""One-time codemod to remove duplicated compact snapshot logic.

Run from repository root:
    .venv/bin/python scripts/remove_legacy_snapshot_logic.py

The canonical MoltGrid runtime already builds the legacy compatibility snapshot
from ``liquidity_scout.services.build_market_report`` through
``liquidity_scout.integrations.moltgrid``. This migration keeps direct imports
of the legacy listener working while removing its second snapshot engine.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "moltgrid_signal_v12_ollama.py"

SNAPSHOT_WRAPPER = '''def compact_asset_snapshot(term, matches, catalog):
    """Legacy-compatible adapter to the structured market-report snapshot."""
    return bridge_compact_asset_snapshot(
        sys.modules[__name__],
        term,
        matches,
        catalog,
    )
'''


def _replace_lines(lines: list[str], start: int, end: int, replacement: str) -> None:
    lines[start - 1 : end] = replacement.splitlines(keepends=True)


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    if (
        "bridge_compact_asset_snapshot" in source
        and "Legacy-compatible adapter to the structured market-report snapshot" in source
    ):
        print("Legacy compact snapshot cleanup already applied.")
        return

    tree = ast.parse(source)
    snapshot = None

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "compact_asset_snapshot":
            snapshot = node
            break

    if snapshot is None:
        raise RuntimeError("legacy compact_asset_snapshot function not found")

    lines = source.splitlines(keepends=True)
    _replace_lines(lines, snapshot.lineno, snapshot.end_lineno, SNAPSHOT_WRAPPER)
    updated = "".join(lines)

    if "import sys\n" not in updated:
        anchor = "import re\n"
        if anchor not in updated:
            raise RuntimeError("import anchor not found")
        updated = updated.replace(anchor, anchor + "import sys\n", 1)

    bridge_anchor = "from liquidity_scout.integrations.moltgrid import (\n"
    if bridge_anchor not in updated:
        raise RuntimeError("MoltGrid bridge import anchor not found")

    if "compact_asset_snapshot as bridge_compact_asset_snapshot" not in updated:
        updated = updated.replace(
            bridge_anchor,
            bridge_anchor
            + "    compact_asset_snapshot as bridge_compact_asset_snapshot,\n",
            1,
        )

    ast.parse(updated)

    forbidden = (
        'price_usd = n(pool.get("priceUsd"))',
        'primary_liquidity = n(pool.get("liquidity"))',
        "Public asset liquidity = total across all matching XDEX pools.",
        'market_cap = n(pool.get("marketCap"))',
    )
    remaining = [marker for marker in forbidden if marker in updated]
    if remaining:
        raise RuntimeError(f"legacy compact snapshot implementation remains: {remaining}")

    if "sys.modules[__name__]" not in updated:
        raise RuntimeError("legacy snapshot wrapper was not installed")

    old_lines = len(source.splitlines())
    new_lines = len(updated.splitlines())
    TARGET.write_text(updated, encoding="utf-8")
    print(
        "Removed duplicated legacy compact snapshot logic: "
        f"{old_lines - new_lines} net lines removed."
    )


if __name__ == "__main__":
    main()
