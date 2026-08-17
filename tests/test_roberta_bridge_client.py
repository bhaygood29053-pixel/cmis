from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from liquidity_scout.integrations.roberta_bridge import (
    RobertaBridgeError,
    ask_roberta,
    roberta_pretrade_enabled,
)


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


class RobertaBridgeClientTests(unittest.TestCase):
    def test_pretrade_bridge_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(roberta_pretrade_enabled())

    def test_pretrade_bridge_accepts_explicit_enable(self):
        with patch.dict(
            os.environ,
            {"ROBERTA_MOLTGRID_PRETRADE_ENABLED": "1"},
            clear=True,
        ):
            self.assertTrue(roberta_pretrade_enabled())

    def test_ask_roberta_sends_only_exact_user_message(self):
        seen = {}

        def fake_urlopen(request, timeout):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            seen["body"] = json.loads(request.data.decode("utf-8"))
            seen["auth"] = request.headers.get("Authorization")
            return FakeResponse(
                {
                    "service": "roberta_bridge",
                    "status": "ok",
                    "reply": "I would be cautious about buying $500 of AGI.",
                }
            )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            reply = ask_roberta(
                "Is it ok to purchase $500 of AGI?",
                base_url="http://127.0.0.1:8766",
                timeout_seconds=12,
                api_key="bridge-secret",
            )

        self.assertEqual(reply, "I would be cautious about buying $500 of AGI.")
        self.assertEqual(seen["url"], "http://127.0.0.1:8766/v1/roberta")
        self.assertEqual(seen["timeout"], 12)
        self.assertEqual(
            seen["body"],
            {"message": "Is it ok to purchase $500 of AGI?"},
        )
        self.assertEqual(seen["auth"], "Bearer bridge-secret")

    def test_ask_roberta_rejects_invalid_service_envelope(self):
        with patch(
            "urllib.request.urlopen",
            return_value=FakeResponse(
                {
                    "service": "cmis_gateway",
                    "status": "ok",
                    "reply": "wrong boundary",
                }
            ),
        ):
            with self.assertRaisesRegex(RobertaBridgeError, "OK service envelope"):
                ask_roberta(
                    "hello",
                    base_url="http://127.0.0.1:8766",
                    timeout_seconds=1,
                )

    def test_ask_roberta_rejects_missing_reply(self):
        with patch(
            "urllib.request.urlopen",
            return_value=FakeResponse(
                {"service": "roberta_bridge", "status": "ok", "reply": ""}
            ),
        ):
            with self.assertRaisesRegex(RobertaBridgeError, "no assistant reply"):
                ask_roberta(
                    "hello",
                    base_url="http://127.0.0.1:8766",
                    timeout_seconds=1,
                )

    def test_ask_roberta_rejects_empty_message(self):
        with self.assertRaisesRegex(RobertaBridgeError, "non-empty"):
            ask_roberta(
                "   ",
                base_url="http://127.0.0.1:8766",
                timeout_seconds=1,
            )


if __name__ == "__main__":
    unittest.main()
