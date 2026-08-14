"""One-time codemod to remove duplicated market-context policy from the legacy listener.

Run from repository root:
    .venv/bin/python scripts/remove_legacy_market_context.py

The canonical MoltGrid runtime already wires deterministic classifications and
verified market context through ``liquidity_scout.integrations.moltgrid`` and
``liquidity_scout.services``. This migration keeps direct imports of the legacy
module working while removing its second implementation of that policy.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "moltgrid_signal_v12_ollama.py"

REMOVE_FUNCTIONS = {
    "liquidity_depth_label",
    "volume_activity_label",
    "price_movement_label",
}

CONTEXT_WRAPPER = '''def verified_snapshot_context(snap, fields):
    """Legacy-compatible adapter to reusable verified market context."""
    return bridge_verified_snapshot_context(
        sys.modules[__name__],
        snap,
        fields,
    )
'''


def _replace_lines(lines: list[str], start: int, end: int, replacement: str = "") -> None:
    lines[start - 1 : end] = replacement.splitlines(keepends=True)


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    if (
        "bridge_verified_snapshot_context" in source
        and "def liquidity_depth_label(" not in source
    ):
        print("Legacy market-context cleanup already applied.")
        return

    tree = ast.parse(source)
    edits: list[tuple[int, int, str]] = []
    found = set()
    context_found = False

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in REMOVE_FUNCTIONS:
            found.add(node.name)
            edits.append((node.lineno, node.end_lineno, ""))
        elif isinstance(node, ast.FunctionDef) and node.name == "verified_snapshot_context":
            context_found = True
            edits.append((node.lineno, node.end_lineno, CONTEXT_WRAPPER))

    missing = REMOVE_FUNCTIONS - found
    if missing:
        raise RuntimeError(f"legacy classification functions not found: {sorted(missing)}")
    if not context_found:
        raise RuntimeError("legacy verified_snapshot_context function not found")

    lines = source.splitlines(keepends=True)
    for start, end, replacement in sorted(edits, reverse=True):
        _replace_lines(lines, start, end, replacement)

    updated = "".join(lines)

    if "import sys\n" not in updated:
        anchor = "import re\n"
        if anchor not in updated:
            raise RuntimeError("import anchor not found")
        updated = updated.replace(anchor, anchor + "import sys\n", 1)

    bridge_anchor = "    resolve_multiple_assets,\n)\n"
    if bridge_anchor not in updated:
        raise RuntimeError("MoltGrid bridge import anchor not found")
    updated = updated.replace(
        bridge_anchor,
        "    resolve_multiple_assets,\n"
        "    verified_snapshot_context as bridge_verified_snapshot_context,\n"
        ")\n",
        1,
    )

    service_anchor = "    full_snapshot_lines as core_full_snapshot_lines,\n"
    if service_anchor not in updated:
        raise RuntimeError("services import anchor not found")
    updated = updated.replace(
        service_anchor,
        service_anchor
        + "    liquidity_depth_label,\n"
        + "    price_movement_label,\n"
        + "    volume_activity_label,\n",
        1,
    )

    ast.parse(updated)

    forbidden = (
        "def liquidity_depth_label(",
        "def volume_activity_label(",
        "def price_movement_label(",
        "Serialize only the verified XDEX values approved for this answer.",
    )
    remaining = [marker for marker in forbidden if marker in updated]
    if remaining:
        raise RuntimeError(f"legacy market-context implementation remains: {remaining}")

    if "sys.modules[__name__]" not in updated:
        raise RuntimeError("legacy context wrapper was not installed")

    old_lines = len(source.splitlines())
    new_lines = len(updated.splitlines())
    TARGET.write_text(updated, encoding="utf-8")
    print(
        "Removed duplicated legacy market-context logic: "
        f"{old_lines - new_lines} net lines removed."
    )


if __name__ == "__main__":
    main()
