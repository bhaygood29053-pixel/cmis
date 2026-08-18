from __future__ import annotations

import json
import os
import unittest
from unittest.mock import Mock, patch

from liquidity_scout.integrations.roberta_bridge import (
    MOLTGRID_SCOPE_LIMITATION_MESSAGE,
    ask_roberta,
    moltgrid_question_supported,
    moltgrid_simple_only_enabled,
)


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


class MoltGridSimpleScopeTests(unittest.TestCase):
    def test_simple_only_mode_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(moltgrid_simple_only_enabled())

    def test_simple_only_mode_accepts_explicit_enable(self):
        with patch.dict(
            os.environ,
            {"ROBERTA_MOLTGRID_SIMPLE_ONLY_ENABLED": "1"},
            clear=True,
        ):
            self.assertTrue(moltgrid_simple_only_enabled())

    def test_concise_question_types_remain_supported(self):
        supported = [
            "Who are you?",
            "What is impermanent loss?",
            "What is the price of AGI?",
            "How much liquidity does AGI have?",
            "How many holders does AGI have?",
            "Tell me about X1.",
            "What does mint authority mean?",
        ]
        for question in supported:
            with self.subTest(question=question):
                self.assertTrue(moltgrid_question_supported(question))

    def test_advanced_question_types_are_declined(self):
        declined = [
            "Compare AGI and X1X liquidity.",
            "AGI vs X1X",
            "Show me the top 10 tokens on XDEX by volume.",
            "How has AGI liquidity changed over the last week?",
            "Is it OK to buy $500 of AGI?",
            "Give me a detailed risk analysis of AGI.",
            "Show the raw CMIS verification evidence.",
            "Give me a technical diagnostic report.",
            "Write Python code to analyze this token.",
        ]
        for question in declined:
            with self.subTest(question=question):
                self.assertFalse(moltgrid_question_supported(question))

    def test_overlong_prompt_is_declined(self):
        self.assertFalse(moltgrid_question_supported("Explain X1 " + ("please " * 80)))

    def test_declined_question_returns_professional_message_without_calling_roberta(self):
        urlopen = Mock()
        with (
            patch.dict(
                os.environ,
                {"ROBERTA_MOLTGRID_SIMPLE_ONLY_ENABLED": "1"},
                clear=True,
            ),
            patch("urllib.request.urlopen", urlopen),
        ):
            reply = ask_roberta("Compare AGI and X1X liquidity.")

        self.assertEqual(reply, MOLTGRID_SCOPE_LIMITATION_MESSAGE)
        urlopen.assert_not_called()

    def test_supported_question_still_reaches_roberta(self):
        urlopen = Mock(
            return_value=_FakeResponse(
                {
                    "service": "roberta_bridge",
                    "status": "ok",
                    "reply": "AGI is currently $0.000064.",
                }
            )
        )
        with (
            patch.dict(
                os.environ,
                {"ROBERTA_MOLTGRID_SIMPLE_ONLY_ENABLED": "1"},
                clear=True,
            ),
            patch("urllib.request.urlopen", urlopen),
        ):
            reply = ask_roberta(
                "What is the price of AGI?",
                base_url="http://127.0.0.1:8766",
                timeout_seconds=5,
            )

        self.assertEqual(reply, "AGI is currently $0.000064.")
        urlopen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
