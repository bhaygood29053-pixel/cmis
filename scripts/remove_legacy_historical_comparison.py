"""Replace duplicate legacy historical-comparison policy with a thin adapter.

Run from repository root:
    .venv/bin/python scripts/remove_legacy_historical_comparison.py

The script edits only ``moltgrid_signal_v12_ollama.py``. It uses Python AST
source spans so it does not depend on fragile exact-text matching.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "moltgrid_signal_v12_ollama.py"
FUNCTION_NAME = "format_historical_comparison_answer"

REPLACEMENT = '''def format_historical_comparison_answer(
    question,
    term,
    matches,
    catalog,
):
    """Legacy-compatible adapter to reusable historical comparison policy."""
    from liquidity_scout.services import format_historical_comparison

    snap = compact_asset_snapshot(term, matches, catalog)
    return format_historical_comparison(
        question,
        snap,
        history_backend=history,
        get_total_supply=get_token_total_supply,
    )
'''


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    tree = ast.parse(source)

    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == FUNCTION_NAME
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one {FUNCTION_NAME} definition; found {len(matches)}"
        )

    node = matches[0]
    lines = source.splitlines(keepends=True)
    start = node.lineno - 1
    end = node.end_lineno

    replacement = REPLACEMENT
    if end < len(lines) and lines[end].strip():
        replacement += "\n"
    else:
        replacement += "\n"

    updated = "".join(lines[:start]) + replacement + "".join(lines[end:])

    compile(updated, str(TARGET), "exec")

    forbidden = (
        "Historical burn percentage comparisons are not yet enabled in the live listener",
        "Always store the current observation",
        "Current {metric}: {current_text}",
        "history.threshold_result(\n            change,",
    )
    leftovers = [text for text in forbidden if text in updated]
    if leftovers:
        raise RuntimeError(f"legacy historical policy still present: {leftovers}")

    TARGET.write_text(updated, encoding="utf-8")
    print("Replaced legacy historical comparison policy with thin service adapter.")


if __name__ == "__main__":
    main()
