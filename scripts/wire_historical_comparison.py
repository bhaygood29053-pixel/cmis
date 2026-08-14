"""One-time codemod to wire the reusable historical comparison service.

Run from repository root:
    .venv/bin/python scripts/wire_historical_comparison.py

The script edits only ``liquidity_scout/integrations/moltgrid.py`` and is removed
from the branch after the permanent wiring is committed and validated.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "liquidity_scout" / "integrations" / "moltgrid.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"wiring anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    source = replace_once(
        source,
        "    build_verified_market_context,\n",
        "    build_verified_market_context,\n"
        "    format_historical_comparison as core_format_historical_comparison,\n",
        "service import",
    )

    multi_anchor = '''def format_multi_asset_answer(listener_module, question, resolved_assets, catalog):
    """Format a multi-asset comparison through the reusable comparison service."""
'''
    historical_block = '''def format_historical_comparison_answer(
    listener_module,
    question,
    term,
    matches,
    catalog,
):
    """Format historical comparison through verified reusable service policy."""
    snapshot = compact_asset_snapshot(listener_module, term, matches, catalog)
    return core_format_historical_comparison(
        question,
        snapshot,
        history_backend=listener_module.history,
        get_total_supply=listener_module.get_token_total_supply,
    )


'''
    source = replace_once(
        source,
        multi_anchor,
        historical_block + multi_anchor,
        "historical bridge",
    )

    snapshot_adapter_anchor = '''def _snapshot_adapter(listener_module):
    def adapter(term, matches, catalog):
        return compact_asset_snapshot(listener_module, term, matches, catalog)

    return adapter
'''
    historical_adapter = '''def _historical_comparison_adapter(listener_module):
    def adapter(question, term, matches, catalog):
        return format_historical_comparison_answer(
            listener_module,
            question,
            term,
            matches,
            catalog,
        )

    return adapter


'''
    source = replace_once(
        source,
        snapshot_adapter_anchor,
        historical_adapter + snapshot_adapter_anchor,
        "historical adapter",
    )

    wire_anchor = (
        "    listener_module.format_multi_asset_answer = "
        "_multi_asset_adapter(listener_module)\n"
    )
    wire_replacement = (
        wire_anchor
        + "    listener_module.format_historical_comparison_answer = "
        "_historical_comparison_adapter(listener_module)\n"
    )
    source = replace_once(
        source,
        wire_anchor,
        wire_replacement,
        "runtime wiring",
    )

    required = (
        "format_historical_comparison as core_format_historical_comparison",
        "def format_historical_comparison_answer(",
        "history_backend=listener_module.history",
        "def _historical_comparison_adapter(",
        "listener_module.format_historical_comparison_answer =",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(f"historical wiring incomplete: {missing}")

    compile(source, str(TARGET), "exec")
    TARGET.write_text(source, encoding="utf-8")
    print("Wired reusable historical comparison service into MoltGrid runtime.")


if __name__ == "__main__":
    main()
