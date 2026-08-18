"""MoltGrid launcher with Roberta-first conversational routing.

The existing ``liquidity_scout.integrations.moltgrid`` module remains the
Signal/MoltGrid transport and admission boundary. Roberta can be enabled in two
modes:

- selected-route compatibility mode: pre-trade and/or conversation handoffs;
- all-questions mode: every admitted Signal question goes to Roberta first.

In all-questions mode, the legacy Liquidity Scout router is retained in the
codebase for rollback and operator diagnostics, but it is never used as an
automatic user-facing fallback. If the Roberta bridge is unavailable, MoltGrid
receives one concise service-unavailable message instead of raw router/CMIS
output.

Recommended mode::

    ROBERTA_MOLTGRID_ALL_QUESTIONS_ENABLED=1 \
    python -m liquidity_scout.integrations.moltgrid_roberta
"""

from __future__ import annotations

from liquidity_scout.integrations import moltgrid as base_moltgrid
from liquidity_scout.integrations.roberta_bridge import (
    RobertaBridgeError,
    ask_roberta,
    roberta_all_questions_enabled,
    roberta_conversation_enabled,
    roberta_pretrade_enabled,
)


ROBERTA_UNAVAILABLE_MESSAGE = (
    "Roberta is temporarily unavailable. Please try your request again shortly."
)


def _legacy_route_answer(
    listener_module,
    catalog,
    question,
    pre_term=None,
    pre_matches=None,
):
    """Run the legacy router explicitly for rollback/operator diagnostics.

    Production Roberta-first MoltGrid routing never calls this helper
    automatically after a Roberta bridge failure. It remains available so an
    operator can deliberately restore or exercise the former router behavior.
    """
    if listener_module.wants_global_xdex_ranking(question):
        metric = listener_module.xdex_ranking_metric(question)
        print(
            "Fallback route: GLOBAL XDEX RANKING | "
            f"metric: {metric}"
        )
        return listener_module.format_global_xdex_ranking_answer(
            question,
            catalog,
        )

    if listener_module.looks_like_agent_identity_question(question):
        print("Fallback route: AGENT IDENTITY / HXMP QUESTION")
        return listener_module.format_hxmp_identity_answer(question)

    if listener_module.explicitly_requests_multiple_assets(question):
        multi = listener_module.resolve_multiple_assets(
            question,
            catalog.pools,
        )
    else:
        multi = []

    if len(multi) >= 2:
        names = ", ".join(term for term, _ in multi)
        print(f"Fallback route: MULTI-ASSET DATA | detected: {names}")
        return listener_module.format_multi_asset_answer(
            question,
            multi,
            catalog,
        )

    if pre_matches:
        term, matches = pre_term, pre_matches
    elif multi:
        term, matches = multi[0]
    else:
        term, matches = listener_module.resolve_asset(
            question,
            catalog.pools,
        )

    if matches:
        if listener_module.wants_asset_analysis(question):
            print(f"Fallback route: ASSET ANALYSIS | asset: {term}")
            return listener_module.format_asset_analysis_answer(
                question,
                term,
                matches,
                catalog,
            )

        fields = listener_module.requested_asset_fields(question)
        if fields:
            print(
                "Fallback route: SPECIFIC ASSET DATA | "
                f"asset: {term} | fields: {', '.join(fields)}"
            )
        else:
            print(f"Fallback route: FULL ASSET REPORT | asset: {term}")
        return listener_module.format_pool_answer(
            question,
            term,
            matches,
            catalog,
        )

    print("Fallback route: GENERAL CRYPTO/X1/DEFI QUESTION")
    return listener_module.format_general_answer(question)


def wire_roberta_all_questions(listener_module):
    """Make Roberta the first responder for every admitted Signal question."""
    if getattr(listener_module, "_roberta_all_questions_wired", False):
        return listener_module

    existing_process_cycle = getattr(
        listener_module,
        "_roberta_all_questions_fallback_process_cycle",
        listener_module.process_cycle,
    )
    listener_module._roberta_all_questions_fallback_process_cycle = (
        existing_process_cycle
    )
    listener_module._roberta_all_questions_wired = True

    def routed_process_cycle(catalog, implicit_mode_started_at):
        if not roberta_all_questions_enabled():
            return existing_process_cycle(catalog, implicit_mode_started_at)

        catalog.refresh_if_needed()

        posts = listener_module.fetch_signal_posts()
        thread_reply_mode_started_at = (
            listener_module.ensure_thread_reply_mode_start()
        )
        pending = listener_module.find_unanswered_messages(
            posts,
            catalog,
            implicit_mode_started_at,
            thread_reply_mode_started_at,
        )

        if not pending:
            return

        answered = listener_module.load_answered()

        for post, message_type, pre_term, pre_matches in pending[:5]:
            post_id = str(post["id"])
            question = listener_module.s(post.get("content"))
            sender = post.get("name") or post.get("wallet")

            if message_type.startswith("standalone"):
                reply_target_id = post_id
            else:
                reply_target_id = str(post.get("replyTo"))

            print()
            print("=" * 72)
            print(f"New {message_type} message from: {sender}")
            print(f"Message: {question}")
            print("Route: ROBERTA FIRST | all admitted questions")

            try:
                answer = ask_roberta(question)
            except RobertaBridgeError as exc:
                print(
                    "Roberta Bridge unavailable: "
                    f"{type(exc).__name__}"
                )
                print("User-facing legacy router fallback: DISABLED")
                answer = ROBERTA_UNAVAILABLE_MESSAGE

            result = listener_module.post_visible_reply(
                reply_target_id,
                answer,
            )
            created = (
                result.get("post", {})
                if isinstance(result, dict)
                else {}
            )
            returned_reply_to = str(created.get("replyTo") or "")

            if returned_reply_to == reply_target_id:
                answered.add(post_id)
                listener_module.save_answered(answered)
                print(
                    "Answered successfully on Signal. Post ID: "
                    f"{created.get('id')}"
                )
            else:
                print("WARNING: reply linkage was not confirmed.")
                print("Stopping this cycle to avoid duplicate replies.")
                break

    listener_module.process_cycle = routed_process_cycle
    return listener_module


def wire_roberta_pretrade(listener_module):
    """Preserve selected-route compatibility handoffs.

    The public function name is retained for compatibility with the first
    bridge release. It wires explicit pre-trade plus general/identity routes.
    When a route has been handed to Roberta, a bridge failure never exposes a
    second conversational voice or raw legacy formatter output.
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
            print("User-facing legacy pre-trade fallback: DISABLED")
            return ROBERTA_UNAVAILABLE_MESSAGE

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
                print("User-facing legacy conversational fallback: DISABLED")
                return ROBERTA_UNAVAILABLE_MESSAGE

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
                print("User-facing legacy identity fallback: DISABLED")
                return ROBERTA_UNAVAILABLE_MESSAGE

        listener_module.format_hxmp_identity_answer = (
            routed_format_hxmp_identity_answer
        )

    return listener_module


def load_listener():
    """Load MoltGrid and apply the configured Roberta ownership mode."""
    listener = base_moltgrid.load_listener()
    if roberta_all_questions_enabled():
        return wire_roberta_all_questions(listener)
    return wire_roberta_pretrade(listener)


def main():
    listener = load_listener()
    listener.main()


if __name__ == "__main__":
    main()


__all__ = [
    "ROBERTA_UNAVAILABLE_MESSAGE",
    "load_listener",
    "main",
    "wire_roberta_all_questions",
    "wire_roberta_pretrade",
]
