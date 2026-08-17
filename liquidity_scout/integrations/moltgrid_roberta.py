"""MoltGrid launcher with opt-in Roberta conversational routes.

The existing ``liquidity_scout.integrations.moltgrid`` module remains the
transport/source of truth for Signal/MoltGrid behavior. This wrapper preserves
the existing router and deterministic market routes while handing selected
conversation routes to Roberta.

Routes:
- explicit pre-trade questions -> Roberta -> X1 Scout -> CMIS
- general conversational questions -> Roberta
- agent identity questions -> Roberta
- deterministic market-data/ranking routes -> existing Liquidity Scout router

Run with::

    ROBERTA_MOLTGRID_PRETRADE_ENABLED=1 \
    ROBERTA_MOLTGRID_CONVERSATION_ENABLED=1 \
    python -m liquidity_scout.integrations.moltgrid_roberta
"""

from __future__ import annotations

from liquidity_scout.integrations import moltgrid as base_moltgrid
from liquidity_scout.integrations.roberta_bridge import (
    RobertaBridgeError,
    ask_roberta,
    roberta_conversation_enabled,
    roberta_pretrade_enabled,
)


def _conversation_fallback(label, fallback_text):
    text = str(fallback_text or "").strip()
    if not text:
        return "Roberta is temporarily unavailable."
    return (
        "Roberta is temporarily unavailable; using Liquidity Scout's "
        f"{label} fallback.\n\n{text}"
    )


def wire_roberta_pretrade(listener_module):
    """Preserve the MoltGrid router while adding selected Roberta handoffs.

    The public function name is retained for compatibility with the first
    bridge release, but it now wires pre-trade plus general/identity routes.
    """
    existing_asset_formatter = getattr(
        listener_module,
        "_roberta_bridge_fallback_format_asset_analysis_answer",
        listener_module.format_asset_analysis_answer,
    )
    listener_module._roberta_bridge_fallback_format_asset_analysis_answer = (
        existing_asset_formatter
    )

    existing_general_formatter = getattr(
        listener_module,
        "_roberta_bridge_fallback_format_general_answer",
        getattr(listener_module, "format_general_answer", None),
    )
    if callable(existing_general_formatter):
        listener_module._roberta_bridge_fallback_format_general_answer = (
            existing_general_formatter
        )

    existing_identity_formatter = getattr(
        listener_module,
        "_roberta_bridge_fallback_format_hxmp_identity_answer",
        getattr(listener_module, "format_hxmp_identity_answer", None),
    )
    if callable(existing_identity_formatter):
        listener_module._roberta_bridge_fallback_format_hxmp_identity_answer = (
            existing_identity_formatter
        )

    def routed_format_asset_analysis_answer(question, term, matches, catalog):
        if not base_moltgrid.wants_cmis_pre_trade(question):
            return existing_asset_formatter(question, term, matches, catalog)
        if not roberta_pretrade_enabled():
            return existing_asset_formatter(question, term, matches, catalog)

        print(f"Roberta Bridge: PRE-TRADE | asset: {term}")
        try:
            return ask_roberta(question)
        except RobertaBridgeError as exc:
            print(f"Roberta Bridge unavailable: {type(exc).__name__}")
            fallback = existing_asset_formatter(question, term, matches, catalog)
            return (
                "Roberta is temporarily unavailable; using Liquidity Scout's "
                "deterministic pre-trade fallback.\n\n"
                f"{fallback}"
            )

    listener_module.format_asset_analysis_answer = routed_format_asset_analysis_answer

    if callable(existing_general_formatter):
        def routed_format_general_answer(question):
            if not roberta_conversation_enabled():
                return existing_general_formatter(question)

            print("Roberta Bridge: GENERAL CONVERSATION")
            try:
                return ask_roberta(question)
            except RobertaBridgeError as exc:
                print(f"Roberta Bridge unavailable: {type(exc).__name__}")
                return _conversation_fallback(
                    "conversational",
                    existing_general_formatter(question),
                )

        listener_module.format_general_answer = routed_format_general_answer

    if callable(existing_identity_formatter):
        def routed_format_hxmp_identity_answer(question):
            if not roberta_conversation_enabled():
                return existing_identity_formatter(question)

            print("Roberta Bridge: AGENT IDENTITY")
            try:
                return ask_roberta(question)
            except RobertaBridgeError as exc:
                print(f"Roberta Bridge unavailable: {type(exc).__name__}")
                return _conversation_fallback(
                    "identity",
                    existing_identity_formatter(question),
                )

        listener_module.format_hxmp_identity_answer = (
            routed_format_hxmp_identity_answer
        )

    return listener_module


def load_listener():
    """Load the existing MoltGrid listener, then add the Roberta handoffs."""
    return wire_roberta_pretrade(base_moltgrid.load_listener())


def main():
    listener = load_listener()
    listener.main()


if __name__ == "__main__":
    main()


__all__ = ["load_listener", "main", "wire_roberta_pretrade"]
