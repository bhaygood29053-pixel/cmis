"""Remove dead duplicate legacy volume-ranking implementation.

Run from repository root:
    .venv/bin/python scripts/remove_legacy_volume_ranking.py

The script edits only ``moltgrid_signal_v12_ollama.py``. It removes the obsolete
volume-only ranking chain now superseded by ``format_asset_rank_answer`` and the
packaged ``xdex_rankings`` / Liquidity Scout ranking service.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "moltgrid_signal_v12_ollama.py"
REMOVE_FUNCTIONS = {
    "aggregate_asset_activity",
    "get_asset_rank",
    "format_volume_rank_answer",
}


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in REMOVE_FUNCTIONS
    ]
    found = {node.name for node in nodes}
    missing = REMOVE_FUNCTIONS - found
    if missing:
        raise RuntimeError(f"legacy ranking functions missing before cleanup: {sorted(missing)}")

    # Delete bottom-up so AST source spans remain valid.
    for node in sorted(nodes, key=lambda item: item.lineno, reverse=True):
        start = node.lineno - 1
        end = node.end_lineno
        while end < len(lines) and not lines[end].strip():
            end += 1
        del lines[start:end]

    updated = "".join(lines)
    updated = updated.replace("    asset_key,\n", "", 1)

    compile(updated, str(TARGET), "exec")

    parsed = ast.parse(updated)
    remaining = {
        node.name
        for node in parsed.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in REMOVE_FUNCTIONS
    }
    if remaining:
        raise RuntimeError(f"legacy ranking functions still present: {sorted(remaining)}")

    if "rankings.find_asset_rank(" not in updated:
        raise RuntimeError("packaged asset-rank delegation is missing")
    if "def wants_volume_rank(" not in updated:
        raise RuntimeError("field-selection volume-rank predicate was removed unexpectedly")

    TARGET.write_text(updated, encoding="utf-8")
    print("Removed dead duplicate legacy volume-ranking implementation.")


if __name__ == "__main__":
    main()
