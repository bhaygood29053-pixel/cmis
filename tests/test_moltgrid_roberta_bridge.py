from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from liquidity_scout.integrations import moltgrid_roberta
from liquidity_scout.integrations.roberta_bridge import RobertaBridgeError


def _listener(fallback_text="legacy reply"):
    def fallback(question, term, matches, catalog):
        return fallback_text

    return SimpleNamespace(format_asset_analysis_answer=fallback)


class MoltGridRobertaBridgeTests(unittest.TestCase):
    def test_non_pretrade_question_keeps_existing_listener_route(self):
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
            patch.object(moltgrid_roberta, "ask_roberta", ask),
        ):
            wired = moltgrid_roberta.wire_roberta_pretrade(listener)
            answer = wired.format_asset_analysis_answer(
                "What is AGI price?",
                "AGI",
                [],
                None,
            )

        self.assertEqual(answer, "legacy reply")
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

        self.assertEqual(answer, "legacy reply")
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

    def test_bridge_failure_returns_explicit_deterministic_fallback(self):
        listener = _listener("Liquidity Scout reply:\nCMIS pre-trade analysis — AGI")
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

        self.assertTrue(answer.startswith("Roberta is temporarily unavailable"))
        self.assertIn("Liquidity Scout reply:", answer)
        self.assertIn("CMIS pre-trade analysis — AGI", answer)
        ask.assert_called_once_with("Buy $500 AGI")

    def test_wiring_is_idempotent_and_does_not_stack_wrappers(self):
        calls = []

        def fallback(question, term, matches, catalog):
            calls.append(question)
            return "legacy reply"

        listener = SimpleNamespace(format_asset_analysis_answer=fallback)
        with patch.object(
            moltgrid_roberta.base_moltgrid,
            "wants_cmis_pre_trade",
            return_value=False,
        ):
            moltgrid_roberta.wire_roberta_pretrade(listener)
            moltgrid_roberta.wire_roberta_pretrade(listener)
            answer = listener.format_asset_analysis_answer(
                "What is AGI price?",
                "AGI",
                [],
                None,
            )

        self.assertEqual(answer, "legacy reply")
        self.assertEqual(calls, ["What is AGI price?"])


if __name__ == "__main__":
    unittest.main()
