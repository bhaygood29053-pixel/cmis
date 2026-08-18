from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from liquidity_scout.integrations import moltgrid_roberta
from liquidity_scout.integrations.roberta_bridge import RobertaBridgeError


class _Catalog:
    def __init__(self):
        self.pools = []
        self.refresh_calls = 0

    def refresh_if_needed(self):
        self.refresh_calls += 1


def _listener(
    question,
    *,
    message_type="standalone-implicit-general",
    reply_to=None,
    returned_reply_to=None,
):
    post = {
        "id": "signal-1",
        "content": question,
        "name": "Bryant",
        "wallet": "owner-wallet",
        "replyTo": reply_to,
    }
    posted = []
    saved = []
    old_process = Mock(return_value="legacy-process-result")

    def post_visible_reply(target, content):
        posted.append((target, content))
        confirmed_target = target if returned_reply_to is None else returned_reply_to
        return {
            "post": {
                "id": "reply-1",
                "replyTo": confirmed_target,
            }
        }

    listener = SimpleNamespace(
        process_cycle=old_process,
        fetch_signal_posts=lambda: [post],
        ensure_thread_reply_mode_start=lambda: "thread-start",
        find_unanswered_messages=lambda *args: [
            (post, message_type, None, None)
        ],
        load_answered=lambda: set(),
        save_answered=lambda answered: saved.append(set(answered)),
        post_visible_reply=post_visible_reply,
        s=lambda value: str(value or "").strip(),
        # Emergency legacy-router surface. Success and bridge-failure tests ensure
        # these are never used automatically in Roberta-first production mode.
        wants_global_xdex_ranking=lambda value: False,
        looks_like_agent_identity_question=lambda value: False,
        explicitly_requests_multiple_assets=lambda value: False,
        resolve_multiple_assets=lambda value, pools: [],
        resolve_asset=lambda value, pools: (None, []),
        wants_asset_analysis=lambda value: False,
        requested_asset_fields=lambda value: [],
        format_global_xdex_ranking_answer=lambda value, catalog: "legacy rank",
        format_hxmp_identity_answer=lambda value: "legacy identity",
        format_multi_asset_answer=lambda value, multi, catalog: "legacy multi",
        format_asset_analysis_answer=lambda value, term, matches, catalog: "legacy analysis",
        format_pool_answer=lambda value, term, matches, catalog: "legacy pool",
        format_general_answer=lambda value: "Liquidity Scout reply:\nlegacy general",
        xdex_ranking_metric=lambda value: "volume",
    )
    return listener, posted, saved, old_process


class MoltGridRobertaAllQuestionsTests(unittest.TestCase):
    def test_every_admitted_question_class_goes_to_roberta_before_legacy_router(self):
        questions = [
            "Who are you?",
            "What is impermanent loss?",
            "What is the liquidity of AGI?",
            "Show me the top 10 tokens on XDEX by volume.",
            "How has AGI liquidity changed over the last week?",
            "Is it OK to buy $500 of AGI?",
            "Compare AGI and FOREST liquidity.",
        ]

        for question in questions:
            with self.subTest(question=question):
                listener, posted, saved, old_process = _listener(question)
                ask = Mock(return_value=f"Roberta answer: {question}")
                with (
                    patch.object(
                        moltgrid_roberta,
                        "roberta_all_questions_enabled",
                        return_value=True,
                    ),
                    patch.object(moltgrid_roberta, "ask_roberta", ask),
                ):
                    moltgrid_roberta.wire_roberta_all_questions(listener)
                    catalog = _Catalog()
                    listener.process_cycle(catalog, "implicit-start")

                ask.assert_called_once_with(question)
                self.assertEqual(
                    posted,
                    [("signal-1", f"Roberta answer: {question}")],
                )
                self.assertEqual(saved, [{"signal-1"}])
                self.assertEqual(catalog.refresh_calls, 1)
                old_process.assert_not_called()

    def test_bridge_failure_returns_service_message_without_legacy_router(self):
        listener, posted, saved, old_process = _listener(
            "What is impermanent loss?"
        )
        ask = Mock(side_effect=RobertaBridgeError("offline"))
        legacy = Mock(return_value="legacy general")
        with (
            patch.object(
                moltgrid_roberta,
                "roberta_all_questions_enabled",
                return_value=True,
            ),
            patch.object(moltgrid_roberta, "ask_roberta", ask),
            patch.object(moltgrid_roberta, "_legacy_route_answer", legacy),
        ):
            moltgrid_roberta.wire_roberta_all_questions(listener)
            listener.process_cycle(_Catalog(), "implicit-start")

        ask.assert_called_once_with("What is impermanent loss?")
        legacy.assert_not_called()
        self.assertEqual(
            posted,
            [("signal-1", moltgrid_roberta.ROBERTA_UNAVAILABLE_MESSAGE)],
        )
        self.assertNotIn("legacy", posted[0][1].lower())
        self.assertNotIn("CMIS", posted[0][1])
        self.assertEqual(saved, [{"signal-1"}])
        old_process.assert_not_called()

    def test_reply_message_stays_attached_to_original_signal_root(self):
        listener, posted, saved, _ = _listener(
            "Tell me more",
            message_type="reply",
            reply_to="root-signal",
        )
        with (
            patch.object(
                moltgrid_roberta,
                "roberta_all_questions_enabled",
                return_value=True,
            ),
            patch.object(
                moltgrid_roberta,
                "ask_roberta",
                return_value="Roberta follow-up",
            ),
        ):
            moltgrid_roberta.wire_roberta_all_questions(listener)
            listener.process_cycle(_Catalog(), "implicit-start")

        self.assertEqual(posted, [("root-signal", "Roberta follow-up")])
        self.assertEqual(saved, [{"signal-1"}])

    def test_unconfirmed_reply_linkage_does_not_mark_message_answered(self):
        listener, posted, saved, _ = _listener(
            "Who are you?",
            returned_reply_to="wrong-root",
        )
        with (
            patch.object(
                moltgrid_roberta,
                "roberta_all_questions_enabled",
                return_value=True,
            ),
            patch.object(
                moltgrid_roberta,
                "ask_roberta",
                return_value="I am Roberta.",
            ),
        ):
            moltgrid_roberta.wire_roberta_all_questions(listener)
            listener.process_cycle(_Catalog(), "implicit-start")

        self.assertEqual(posted, [("signal-1", "I am Roberta.")])
        self.assertEqual(saved, [])

    def test_runtime_disable_returns_to_original_process_cycle(self):
        listener, posted, saved, old_process = _listener("Who are you?")
        with patch.object(
            moltgrid_roberta,
            "roberta_all_questions_enabled",
            return_value=False,
        ):
            moltgrid_roberta.wire_roberta_all_questions(listener)
            result = listener.process_cycle(_Catalog(), "implicit-start")

        self.assertEqual(result, "legacy-process-result")
        old_process.assert_called_once()
        self.assertEqual(posted, [])
        self.assertEqual(saved, [])

    def test_all_questions_wiring_is_idempotent(self):
        listener, posted, saved, _ = _listener("Who are you?")
        ask = Mock(return_value="I am Roberta.")
        with (
            patch.object(
                moltgrid_roberta,
                "roberta_all_questions_enabled",
                return_value=True,
            ),
            patch.object(moltgrid_roberta, "ask_roberta", ask),
        ):
            moltgrid_roberta.wire_roberta_all_questions(listener)
            first = listener.process_cycle
            moltgrid_roberta.wire_roberta_all_questions(listener)
            second = listener.process_cycle
            listener.process_cycle(_Catalog(), "implicit-start")

        self.assertIs(first, second)
        ask.assert_called_once_with("Who are you?")
        self.assertEqual(len(posted), 1)
        self.assertEqual(saved, [{"signal-1"}])


if __name__ == "__main__":
    unittest.main()
