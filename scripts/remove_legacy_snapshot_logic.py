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


def _snapshot_function(source: str) -> ast.FunctionDef | None:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "compact_asset_snapshot":
            return node
    return None


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    if (
        "bridge_compact_asset_snapshot" in source
        and "Legacy-compatible adapter to the structured market-report snapshot" in source
    ):
        print("Legacy compact snapshot cleanup already applied.")
        return

    snapshot = _snapshot_function(source)
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

    # Validate the rewritten function itself instead of scanning the entire
    # legacy listener for generic statements that may legitimately occur in
    # unrelated functions.
    rewritten_snapshot = _snapshot_function(updated)
    if rewritten_snapshot is None:
        raise RuntimeError("rewritten compact_asset_snapshot function not found")

    rewritten_text = ast.get_source_segment(updated, rewritten_snapshot) or ""
    required = (
        "bridge_compact_asset_snapshot(",
        "sys.modules[__name__]",
    )
    missing = [marker for marker in required if marker not in rewritten_text]
    if missing:
        raise RuntimeError(f"legacy snapshot wrapper incomplete: {missing}")

    forbidden = (
        'price_usd = n(pool.get("priceUsd"))',
        'primary_liquidity = n(pool.get("liquidity"))',
        "Public asset liquidity = total across all matching XDEX pools.",
        'market_cap = n(pool.get("marketCap"))',
    )
    remaining = [marker for marker in forbidden if marker in rewritten_text]
    if remaining:
        raise RuntimeError(
            f"legacy compact snapshot implementation remains in wrapper: {remaining}"
        )

    ast.parse(updated)

    old_lines = len(source.splitlines())
    new_lines = len(updated.splitlines())
    TARGET.write_text(updated, encoding="utf-8")
    print(
        "Removed duplicated legacy compact snapshot logic: "
        f"{old_lines - new_lines} net lines removed."
    )


if __name__ == "__main__":
    main()
