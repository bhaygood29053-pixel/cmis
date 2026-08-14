"""One-time codemod to remove duplicated XDEX catalog/resolver logic.

Run from repository root:
    .venv/bin/python scripts/remove_legacy_xdex_core.py

The canonical MoltGrid runtime already uses the reusable XDEX core through
``liquidity_scout.integrations.moltgrid``. This migration keeps direct imports
of the legacy module working by sourcing its public resolver/catalog names from
the reusable core and bridge instead of maintaining a second implementation.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "moltgrid_signal_v12_ollama.py"

IMPORT_BLOCK = """from liquidity_scout.integrations.moltgrid import (\n    MoltGridXDEXCatalog as XDEXCatalog,\n    resolve_asset,\n    resolve_multiple_assets,\n)\nfrom liquidity_scout.market.resolver import (\n    asset_key,\n    candidate_terms,\n    exact_token_match,\n    explicitly_requests_multiple_assets,\n    find_matches_for_term,\n    normalize_text,\n    pair_name,\n    partial_token_match,\n    pool_address,\n    token_fields,\n)\n"""

REMOVE_FUNCTIONS = {
    "token_fields",
    "pool_address",
    "pair_name",
    "normalize_text",
    "candidate_terms",
    "exact_token_match",
    "partial_token_match",
    "find_matches_for_term",
    "asset_key",
    "explicitly_requests_multiple_assets",
    "resolve_multiple_assets",
    "resolve_asset",
}
REMOVE_ASSIGNMENTS = {"STOPWORDS", "POOLS_URL", "PAGE_SIZE"}


def _assignment_name(node: ast.Assign) -> str | None:
    for target in node.targets:
        if isinstance(target, ast.Name):
            return target.id
    return None


def _replace_lines(lines: list[str], start: int, end: int, replacement: str = "") -> None:
    lines[start - 1 : end] = replacement.splitlines(keepends=True)


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    if "MoltGridXDEXCatalog as XDEXCatalog" in source and "class XDEXCatalog:" not in source:
        print("Legacy XDEX core cleanup already applied.")
        return

    tree = ast.parse(source)
    edits: list[tuple[int, int, str]] = []
    found_functions = set()
    found_assignments = set()
    found_catalog = False

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in REMOVE_FUNCTIONS:
            found_functions.add(node.name)
            edits.append((node.lineno, node.end_lineno, ""))
        elif isinstance(node, ast.ClassDef) and node.name == "XDEXCatalog":
            found_catalog = True
            edits.append((node.lineno, node.end_lineno, ""))
        elif isinstance(node, ast.Assign):
            name = _assignment_name(node)
            if name in REMOVE_ASSIGNMENTS:
                found_assignments.add(name)
                edits.append((node.lineno, node.end_lineno, ""))

    missing_functions = REMOVE_FUNCTIONS - found_functions
    missing_assignments = REMOVE_ASSIGNMENTS - found_assignments
    if missing_functions:
        raise RuntimeError(f"legacy functions not found: {sorted(missing_functions)}")
    if missing_assignments:
        raise RuntimeError(f"legacy assignments not found: {sorted(missing_assignments)}")
    if not found_catalog:
        raise RuntimeError("legacy XDEXCatalog class not found")

    lines = source.splitlines(keepends=True)
    for start, end, replacement in sorted(edits, reverse=True):
        _replace_lines(lines, start, end, replacement)

    updated = "".join(lines)
    anchor = "from config import SETTINGS\n"
    if anchor not in updated:
        raise RuntimeError("config import anchor not found")
    updated = updated.replace(anchor, anchor + "\n" + IMPORT_BLOCK, 1)

    ast.parse(updated)

    forbidden = (
        "class XDEXCatalog:",
        "def candidate_terms(",
        "def find_matches_for_term(",
        "def resolve_asset(",
        "def resolve_multiple_assets(",
    )
    remaining = [marker for marker in forbidden if marker in updated]
    if remaining:
        raise RuntimeError(f"legacy XDEX implementation remains: {remaining}")

    old_lines = len(source.splitlines())
    new_lines = len(updated.splitlines())
    TARGET.write_text(updated, encoding="utf-8")
    print(
        "Removed duplicated legacy XDEX catalog/resolver logic: "
        f"{old_lines - new_lines} net lines removed."
    )


if __name__ == "__main__":
    main()
