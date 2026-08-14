"""One-time codemod to remove duplicated legacy multi-asset comparison policy.

Run from repository root:
    .venv/bin/python scripts/remove_legacy_market_comparison.py

PR #11 moved deterministic comparison policy into
``liquidity_scout.services.market_comparison`` and wired the canonical MoltGrid
entrypoint to it. This cleanup keeps direct imports of the legacy listener
working through a thin adapter while deleting the second comparison engine.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "moltgrid_signal_v12_ollama.py"

WRAPPER = '''def format_multi_asset_answer(question, resolved_assets, catalog):
    """Legacy-compatible adapter to reusable multi-asset comparison policy."""
    snapshots = [
        compact_asset_snapshot(term, matches, catalog)
        for term, matches in resolved_assets
    ]
    fields = requested_asset_fields(question)

    return core_format_market_comparison(
        question,
        snapshots,
        fields=fields,
        format_usd=format_usd,
        format_field_line=format_field_line,
        include_token_addresses=wants_token_address(question),
    )
'''


def _replace_lines(lines: list[str], start: int, end: int, replacement: str) -> None:
    lines[start - 1 : end] = replacement.splitlines(keepends=True)


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "".join(lines[node.lineno - 1 : node.end_lineno])
    raise RuntimeError(f"function not found after rewrite: {name}")


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    if (
        "Legacy-compatible adapter to reusable multi-asset comparison policy" in source
        and "core_format_market_comparison(" in source
    ):
        print("Legacy multi-asset comparison cleanup already applied.")
        return

    tree = ast.parse(source)
    target = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "format_multi_asset_answer":
            target = node
            break

    if target is None:
        raise RuntimeError("legacy format_multi_asset_answer function not found")

    lines = source.splitlines(keepends=True)
    _replace_lines(lines, target.lineno, target.end_lineno, WRAPPER)
    updated = "".join(lines)

    service_anchor = "from liquidity_scout.services import (\n"
    if service_anchor not in updated:
        raise RuntimeError("services import anchor not found")

    import_line = "    format_market_comparison as core_format_market_comparison,\n"
    if import_line not in updated:
        updated = updated.replace(service_anchor, service_anchor + import_line, 1)

    ast.parse(updated)

    wrapper_source = _function_source(updated, "format_multi_asset_answer")
    required = (
        "core_format_market_comparison(",
        "compact_asset_snapshot(term, matches, catalog)",
        "requested_asset_fields(question)",
        "include_token_addresses=wants_token_address(question)",
    )
    missing = [marker for marker in required if marker not in wrapper_source]
    if missing:
        raise RuntimeError(f"legacy comparison adapter incomplete: {missing}")

    forbidden = (
        "Analyst comparison:",
        "more available liquidity",
        "more 24h volume",
        "Largest absolute 24h price move",
        "Best 24h return",
        "reduce slippage and price-impact pressure",
    )
    remaining = [marker for marker in forbidden if marker in wrapper_source]
    if remaining:
        raise RuntimeError(f"legacy comparison policy remains in adapter: {remaining}")

    old_lines = len(source.splitlines())
    new_lines = len(updated.splitlines())
    TARGET.write_text(updated, encoding="utf-8")
    print(
        "Removed duplicated legacy multi-asset comparison policy: "
        f"{old_lines - new_lines} net lines removed."
    )


if __name__ == "__main__":
    main()
