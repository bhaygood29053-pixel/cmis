"""One-time codemod to remove duplicated market-presentation logic from the legacy listener.

Run from the repository root:
    .venv/bin/python scripts/remove_legacy_market_presentation.py

The canonical runtime already wires reusable presentation services through
``liquidity_scout.integrations.moltgrid``. This migration keeps direct imports
of the legacy module working by replacing the duplicated implementation with
thin adapters to ``liquidity_scout.services``.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "moltgrid_signal_v12_ollama.py"

SERVICE_IMPORT = """from liquidity_scout.services import (\n    FIELD_ORDER as CORE_FIELD_ORDER,\n    format_field_line as core_format_field_line,\n    full_snapshot_lines as core_full_snapshot_lines,\n    requested_asset_fields as core_requested_asset_fields,\n    wants_token_address,\n)\n"""

ADAPTER_BLOCK = """FIELD_ORDER = CORE_FIELD_ORDER\n\n\ndef requested_asset_fields(question):\n    \"\"\"Legacy-compatible adapter to reusable field-selection policy.\"\"\"\n    return core_requested_asset_fields(\n        question,\n        historical_comparison=bool(\n            history.parse_historical_comparison(question)\n        ),\n        volume_rank=wants_volume_rank(question),\n        historical_liquidity=wants_historical_liquidity(question),\n    )\n\n\ndef format_field_line(field, snap):\n    \"\"\"Legacy-compatible adapter to reusable public field formatting.\"\"\"\n    return core_format_field_line(\n        field,\n        snap,\n        format_usd=format_usd,\n        get_total_supply=get_token_total_supply,\n        get_mint_info=get_token_mint_info,\n    )\n\n\ndef full_snapshot_lines(snap):\n    \"\"\"Legacy-compatible adapter to reusable default snapshot formatting.\"\"\"\n    return core_full_snapshot_lines(\n        snap,\n        format_usd=format_usd,\n        get_total_supply=get_token_total_supply,\n        get_mint_info=get_token_mint_info,\n    )\n\n\n"""


def _top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise RuntimeError(f"top-level function not found: {name}")


def _field_order_assignment(tree: ast.Module) -> ast.Assign:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "FIELD_ORDER":
                return node
    raise RuntimeError("top-level FIELD_ORDER assignment not found")


def _replace_lines(lines: list[str], start: int, end: int, replacement: str) -> None:
    """Replace inclusive 1-based source lines with replacement text."""
    lines[start - 1 : end] = replacement.splitlines(keepends=True)


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    if "Legacy-compatible adapter to reusable field-selection policy" in source:
        print("Legacy presentation cleanup already applied.")
        return

    tree = ast.parse(source)
    field_order = _field_order_assignment(tree)
    requested_fields = _top_level_function(tree, "requested_asset_fields")
    format_line = _top_level_function(tree, "format_field_line")
    full_lines = _top_level_function(tree, "full_snapshot_lines")
    round_amount = _top_level_function(tree, "round_token_amount")
    token_address = _top_level_function(tree, "wants_token_address")

    if not (
        field_order.lineno < requested_fields.lineno
        < format_line.lineno
        < full_lines.lineno
    ):
        raise RuntimeError("legacy presentation block is not in expected order")

    lines = source.splitlines(keepends=True)

    edits = [
        (
            token_address.lineno,
            token_address.end_lineno,
            "",
        ),
        (
            field_order.lineno,
            full_lines.end_lineno,
            ADAPTER_BLOCK,
        ),
        (
            round_amount.lineno,
            round_amount.end_lineno,
            "",
        ),
    ]

    for start, end, replacement in sorted(edits, reverse=True):
        _replace_lines(lines, start, end, replacement)

    updated = "".join(lines)
    updated = updated.replace(
        "from decimal import Decimal, ROUND_HALF_UP\n",
        "from decimal import Decimal\n",
        1,
    )

    anchor = "from config import SETTINGS\n"
    if anchor not in updated:
        raise RuntimeError("config import anchor not found")
    updated = updated.replace(
        anchor,
        anchor + "\n" + SERVICE_IMPORT,
        1,
    )

    # Fail closed if the codemod produced invalid Python or left the duplicate
    # helper implementation behind.
    ast.parse(updated)
    if "ROUND_HALF_UP" in updated:
        raise RuntimeError("legacy ROUND_HALF_UP presentation helper remains")
    if "def wants_token_address(question):" in updated:
        raise RuntimeError("legacy wants_token_address implementation remains")
    if "Round to nearest whole token; .5 and above rounds up." in updated:
        raise RuntimeError("legacy round_token_amount helper remains")

    old_lines = len(source.splitlines())
    new_lines = len(updated.splitlines())
    TARGET.write_text(updated, encoding="utf-8")
    print(
        "Removed duplicated legacy presentation logic: "
        f"{old_lines - new_lines} net lines removed."
    )


if __name__ == "__main__":
    main()
