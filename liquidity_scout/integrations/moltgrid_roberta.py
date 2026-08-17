"""MoltGrid launcher with an opt-in Roberta pre-trade conversation bridge.

The existing ``liquidity_scout.integrations.moltgrid`` module remains the
transport/source of truth for Signal/MoltGrid behavior. This wrapper loads that
listener, then replaces only the explicit pre-trade presentation seam so the
user's exact question can be answered by Roberta -> X1 Scout -> CMIS.

Run with::

    ROBERTA_MOLTGRID_PRETRADE_ENABLED=1 \
    python -m liquidity_scout.integrations.moltgrid_roberta
"""

from __future__ import annotations

from liquidity_scout.integrations import moltgrid as base_moltgrid
from liquidity_scout.integrations.roberta_bridge import (
    RobertaBridgeError,
    ask_roberta,
    roberta_pretrade_enabled,
)


def wire_roberta_pretrade(listener_module):
    """Wrap only the already-wired MoltGrid explicit pre-trade formatter."""
    existing_formatter = getattr(
        listener_module,
        "_roberta_bridge_fallback_format_asset_analysis_answer",
        listener_module.format_asset_analysis_answer,
    )
    listener_module._roberta_bridge_fallback_format_asset_analysis_answer = existing_formatter

    def routed_format_asset_analysis_answer(question, term, matches, catalog):
        if not base_moltgrid.wants_cmis_pre_trade(question):
            return existing_formatter(question, term, matches, catalog)
        if not roberta_pretrade_enabled():
            return existing_formatter(question, term, matches, catalog)

        print(f"Roberta Bridge: PRE-TRADE | asset: {term}")
        try:
            return ask_roberta(question)
        except RobertaBridgeError as exc:
            print(f"Roberta Bridge unavailable: {type(exc).__name__}")
            fallback = existing_formatter(question, term, matches, catalog)
            return (
                "Roberta is temporarily unavailable; using Liquidity Scout's "
                "deterministic pre-trade fallback.\n\n"
                f"{fallback}"
            )

    listener_module.format_asset_analysis_answer = routed_format_asset_analysis_answer
    return listener_module


def load_listener():
    """Load the existing MoltGrid listener, then add the Roberta handoff."""
    return wire_roberta_pretrade(base_moltgrid.load_listener())


def main():
    listener = load_listener()
    listener.main()


if __name__ == "__main__":
    main()


__all__ = ["load_listener", "main", "wire_roberta_pretrade"]
