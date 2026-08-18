from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from liquidity_scout.integrations import moltgrid_roberta
from liquidity_scout.integrations.roberta_bridge import RobertaBridgeError


def _listener(
    asset_fallback="legacy asset reply",
    general_fallback="Liquidity Scout reply:\nlegacy general reply",
    identity_fallback="legacy identity reply",
):
    def asset(question, term, matches, catalog):
        return asset_fallback

    def general(question):
        return general_fallback

    def identity(question):
        return identity_fallback

    return SimpleNamespace(
        format_asset_analysis_answer=asset,
        format_general_answer=general,
        format_hxmp_identity_answer=identity,
    )


class MoltGridRobertaBridgeTests(unittest.TestCase):
    def test_non_pretrade_asset_question_keeps_existing_listener_route(self):
        listener = _listener()
        ask = Mock(side_effect=AssertionError("should not call Roberta"))
        with (
            patch.object(
                moltgrid_roberta.base_moltgrid,
                "wants_cmis_pre_trade",
                return_value=False,
            ),
            patch.object(
                moltgrid_roberta,
                "roberta_pretrade_enabled",
                return_value=True,
            ),
            patch.object(
                moltgrid_roberta,
                "roberta_conversation_enabled",
                return_value=True,
            ),
            patch.object(moltgrid_roberta, "ask_roberta", ask),
        ):
            wired = moltgrid_roberta.wire_roberta_pretrade(listener)
            answer = wired.format_asset_analysis_answer(
                "What is AGI price?",
                "AGI",
                [],
                None,
            )

        self.assertEqual(answer, "legacy asset reply")
        ask.assert_not_called()

    def test_pretrade_question_keeps_existing_route_when_bridge_disabled(self):
        listener = _listener()
        ask = Mock(side_effect=AssertionError("should not call Roberta"))
        with (
            patch.object(
                moltgrid_roberta.base_moltgrid,
                "wants_cmis_pre_trade",
                return_value=True,
            ),
            patch.object(
                moltgrid_roberta,
                "roberta_pretrade_enabled",
                return_value=False,
            ),
            patch.object(moltgrid_roberta, "ask_roberta", ask),
        ):
            wired = moltgrid_roberta.wire_roberta_pretrade(listener)
            answer = wired.format_asset_analysis_answer(
                "Buy $500 AGI",
                "AGI",
                [],
                None,
            )

        self.assertEqual(answer, "legacy asset reply")
        ask.assert_not_called()

    def test_enabled_pretrade_routes_exact_question_to_roberta(self):
        listener = _listener()
        ask = Mock(return_value="Roberta conversational answer")
        question = "Is it ok to purchase $500 of AGI?"
        with (
            patch.object(
                moltgrid_roberta.base_moltgrid,
                "wants_cmis_pre_trade",
                return_value=True,
            ),
            patch.object(
                moltgrid_roberta,
                "roberta_pretrade_enabled",
                return_value=True,
            ),
            patch.object(moltgrid_roberta, "ask_roberta", ask),
        ):
            wired = moltgrid_roberta.wire_roberta_pretrade(listener)
            answer = wired.format_asset_analysis_answer(question, "AGI", [], None)

        self.assertEqual(answer, "Roberta conversational answer")
        self.assertNotIn("Liquidity Scout reply:", answer)
        ask.assert_called_once_with(question)

    def test_pretrade_bridge_failure_returns_roberta_availability_message_only(self):
        listener = _listener(
            asset_fallback="Liquidity Scout reply:\nCMIS pre-trade analysis — AGI"
        )
        ask = Mock(side_effect=RobertaBridgeError("unavailable"))
        with (
            patch.object(
                moltgrid_roberta.base_moltgrid,
                "wants_cmis_pre_trade",
                return_value=True,
            ),
            patch.object(
                moltgrid_roberta,
                "roberta_pretrade_enabled",
                return_value=True,
            ),
            patch.object(moltgrid_roberta, "ask_roberta", ask),
        ):
            wired = moltgrid_roberta.wire_roberta_pretrade(listener)
            answer = wired.format_asset_analysis_answer(
                "Buy $500 AGI",
                "AGI",
                [],
                None,
            )

        self.assertEqual(answer, moltgrid_roberta.ROBERTA_UNAVAILABLE_MESSAGE)
        self.assertNotIn("Liquidity Scout reply:", answer)
        self.assertNotIn("CMIS", answer)
        ask.assert_called_once_with("Buy $500 AGI")

    def test_general_question_routes_exact_question_to_roberta(self):
        listener = _listener()
        ask = Mock(return_value="Roberta general answer")
        question = "What is impermanent loss?"
        with (
            patch.object(
                moltgrid_roberta,
                "roberta_conversation_enabled",
                return_value=True,
            ),
            patch.object(moltgrid_roberta, "ask_roberta", ask),
        ):
            wired = moltgrid_roberta.wire_roberta_pretrade(listener)
            answer = wired.format_general_answer(question)

        self.assertEqual(answer, "Roberta general answer")
        self.assertNotIn("Liquidity Scout reply:", answer)
        ask.assert_called_once_with(question)

    def test_general_question_keeps_existing_route_when_conversation_disabled(self):
        listener = _listener()
        ask = Mock(side_effect=AssertionError("should not call Roberta"))
        with (
            patch.object(
                moltgrid_roberta,
                "roberta_conversation_enabled",
                return_value=False,
            ),
            patch.object(moltgrid_roberta, "ask_roberta", ask),
        ):
            wired = moltgrid_roberta.wire_roberta_pretrade(listener)
            answer = wired.format_general_answer("What is impermanent loss?")

        self.assertEqual(answer, "Liquidity Scout reply:\nlegacy general reply")
        ask.assert_not_called()

    def test_identity_question_routes_exact_question_to_roberta(self):
        listener = _listener()
        ask = Mock(return_value="I am Roberta.")
        question = "Who are you?"
        with (
            patch.object(
                moltgrid_roberta,
                "roberta_conversation_enabled",
                return_value=True,
            ),
            patch.object(moltgrid_roberta, "ask_roberta", ask),
        ):
            wired = moltgrid_roberta.wire_roberta_pretrade(listener)
            answer = wired.format_hxmp_identity_answer(question)

        self.assertEqual(answer, "I am Roberta.")
        ask.assert_called_once_with(question)

    def test_general_bridge_failure_returns_roberta_availability_message_only(self):
        listener = _listener()
        ask = Mock(side_effect=RobertaBridgeError("unavailable"))
        with (
            patch.object(
                moltgrid_roberta,
                "roberta_conversation_enabled",
                return_value=True,
            ),
            patch.object(moltgrid_roberta, "ask_roberta", ask),
        ):
            wired = moltgrid_roberta.wire_roberta_pretrade(listener)
            answer = wired.format_general_answer("Tell me about yourself")

        self.assertEqual(answer, moltgrid_roberta.ROBERTA_UNAVAILABLE_MESSAGE)
        self.assertNotIn("legacy general reply", answer)
        self.assertNotIn("Liquidity Scout reply:", answer)
        ask.assert_called_once_with("Tell me about yourself")

    def test_wiring_is_idempotent_and_does_not_stack_wrappers(self):
        asset_calls = []
        general_calls = []
        identity_calls = []

        def asset(question, term, matches, catalog):
            asset_calls.append(question)
            return "legacy asset reply"

        def general(question):
            general_calls.append(question)
            return "legacy general reply"

        def identity(question):
            identity_calls.append(question)
            return "legacy identity reply"

        listener = SimpleNamespace(
            format_asset_analysis_answer=asset,
            format_general_answer=general,
            format_hxmp_identity_answer=identity,
        )
        with (
            patch.object(
                moltgrid_roberta.base_moltgrid,
                "wants_cmis_pre_trade",
                return_value=False,
            ),
            patch.object(
                moltgrid_roberta,
                "roberta_conversation_enabled",
                return_value=False,
            ),
        ):
            moltgrid_roberta.wire_roberta_pretrade(listener)
            moltgrid_roberta.wire_roberta_pretrade(listener)
            asset_answer = listener.format_asset_analysis_answer(
                "What is AGI price?",
                "AGI",
                [],
                None,
            )
            general_answer = listener.format_general_answer("What is DeFi?")
            identity_answer = listener.format_hxmp_identity_answer("Who are you?")

        self.assertEqual(asset_answer, "legacy asset reply")
        self.assertEqual(general_answer, "legacy general reply")
        self.assertEqual(identity_answer, "legacy identity reply")
        self.assertEqual(asset_calls, ["What is AGI price?"])
        self.assertEqual(general_calls, ["What is DeFi?"])
        self.assertEqual(identity_calls, ["Who are you?"])


if __name__ == "__main__":
    unittest.main()
