"""One-time codemod to wire the reusable market-comparison service.

Run from repository root:
    .venv/bin/python scripts/wire_market_comparison.py

This slice does not delete the legacy ``format_multi_asset_answer`` function.
It makes the canonical MoltGrid module entrypoint replace that function at
runtime with an adapter backed by ``services.market_comparison``. Physical
legacy cleanup belongs to the next slice after this seam is validated.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICES_INIT = ROOT / "liquidity_scout" / "services" / "__init__.py"
MOLTGRID = ROOT / "liquidity_scout" / "integrations" / "moltgrid.py"


BRIDGE_FUNCTION = '''\n\ndef format_multi_asset_answer(listener_module, question, resolved_assets, catalog):
    """Format a multi-asset comparison through the reusable comparison service."""
    snapshots = [
        compact_asset_snapshot(listener_module, term, matches, catalog)
        for term, matches in resolved_assets
    ]
    fields = requested_asset_fields(listener_module, question)

    return format_market_comparison(
        question,
        snapshots,
        fields=fields,
        format_usd=listener_module.format_usd,
        format_field_line=lambda field, snap: format_field_line(
            listener_module,
            field,
            snap,
        ),
        include_token_addresses=core_wants_token_address(question),
    )
'''

ADAPTER_FUNCTION = '''\n\ndef _multi_asset_adapter(listener_module):
    def adapter(question, resolved_assets, catalog):
        return format_multi_asset_answer(
            listener_module,
            question,
            resolved_assets,
            catalog,
        )

    return adapter
'''


def update_services_init() -> None:
    source = SERVICES_INIT.read_text(encoding="utf-8")

    if "from .market_comparison import format_market_comparison" not in source:
        anchor = '"""Structured Liquidity Scout service capabilities."""\n\n'
        if anchor not in source:
            raise RuntimeError("services __init__ header anchor not found")
        source = source.replace(
            anchor,
            anchor + "from .market_comparison import format_market_comparison\n",
            1,
        )

    if '    "format_market_comparison",\n' not in source:
        anchor = '    "format_field_line",\n'
        if anchor not in source:
            raise RuntimeError("services __all__ anchor not found")
        source = source.replace(
            anchor,
            anchor + '    "format_market_comparison",\n',
            1,
        )

    ast.parse(source)
    SERVICES_INIT.write_text(source, encoding="utf-8")


def update_moltgrid() -> None:
    source = MOLTGRID.read_text(encoding="utf-8")

    if "    format_market_comparison,\n" not in source:
        anchor = "    format_field_line as core_format_field_line,\n"
        if anchor not in source:
            raise RuntimeError("MoltGrid services import anchor not found")
        source = source.replace(
            anchor,
            anchor + "    format_market_comparison,\n",
            1,
        )

    if "def format_multi_asset_answer(listener_module, question, resolved_assets, catalog):" not in source:
        anchor = "\ndef requested_asset_fields(listener_module, question):\n"
        if anchor not in source:
            raise RuntimeError("requested_asset_fields anchor not found")
        source = source.replace(anchor, BRIDGE_FUNCTION + anchor, 1)

    if "def _multi_asset_adapter(listener_module):" not in source:
        anchor = "\ndef _snapshot_adapter(listener_module):\n"
        if anchor not in source:
            raise RuntimeError("snapshot adapter anchor not found")
        source = source.replace(anchor, ADAPTER_FUNCTION + anchor, 1)

    wire_line = "    listener_module.compact_asset_snapshot = _snapshot_adapter(listener_module)\n"
    assignment = (
        "    listener_module.format_multi_asset_answer = "
        "_multi_asset_adapter(listener_module)\n"
    )
    if assignment not in source:
        if wire_line not in source:
            raise RuntimeError("wire_market_core snapshot assignment anchor not found")
        source = source.replace(wire_line, wire_line + assignment, 1)

    ast.parse(source)
    MOLTGRID.write_text(source, encoding="utf-8")


def main() -> None:
    update_services_init()
    update_moltgrid()
    print("Wired reusable market comparison service into MoltGrid runtime.")


if __name__ == "__main__":
    main()
