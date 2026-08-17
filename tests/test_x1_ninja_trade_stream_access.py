import unittest

from liquidity_scout.providers.x1.ninja_trade_stream import (
    STREAM_PATH,
    X1NinjaTradeStreamError,
    probe_trade_stream_access,
)


class Response:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.closed = False

    def close(self):
        self.closed = True

    def json(self):
        raise AssertionError("access probe must not parse a JSON/event body")

    def iter_lines(self):
        raise AssertionError("access probe must not consume SSE event lines")


class Session:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, *, headers, stream, timeout):
        self.calls.append((url, headers, stream, timeout))
        if self.error is not None:
            raise self.error
        return self.response


class X1NinjaTradeStreamAccessTests(unittest.TestCase):
    def test_200_event_stream_verifies_handshake_only(self):
        response = Response(
            200,
            {
                "Content-Type": "text/event-stream; charset=utf-8",
                "X-RateLimit-Limit": "10",
                "X-RateLimit-Remaining": "9",
            },
        )
        session = Session(response=response)

        result = probe_trade_stream_access(
            api_key="test-key",
            session=session,
            connect_timeout=3,
            read_timeout=4,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["access"], "available_sse_handshake")
        self.assertTrue(result["sse_handshake_verified"])
        self.assertFalse(result["event_body_consumed"])
        self.assertFalse(result["event_schema_verified"])
        self.assertFalse(result["event_ordering_verified"])
        self.assertFalse(result["event_finality_verified"])
        self.assertFalse(result["reconnect_semantics_verified"])
        self.assertFalse(result["backfill_semantics_verified"])
        self.assertFalse(result["stream_freshness_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertTrue(response.closed)

        url, headers, stream, timeout = session.calls[0]
        self.assertTrue(url.endswith(STREAM_PATH))
        self.assertEqual(headers["Authorization"], "Bearer test-key")
        self.assertEqual(headers["Accept"], "text/event-stream")
        self.assertTrue(stream)
        self.assertEqual(timeout, (3, 4))
        self.assertNotIn("test-key", str(result))

    def test_403_is_structured_unavailable_not_exception(self):
        response = Response(403, {"Content-Type": "application/json"})
        result = probe_trade_stream_access(
            api_key="test-key",
            session=Session(response=response),
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["access"], "access_denied")
        self.assertFalse(result["sse_handshake_verified"])
        self.assertIn(
            "current_credentials_do_not_establish_stream_access",
            result["warnings"],
        )
        self.assertFalse(result["cmis_promotable"])
        self.assertTrue(response.closed)

    def test_401_is_access_denied(self):
        result = probe_trade_stream_access(
            api_key="test-key",
            session=Session(response=Response(401)),
        )
        self.assertEqual(result["access"], "access_denied")
        self.assertEqual(result["status"], "unavailable")

    def test_404_is_endpoint_not_found(self):
        result = probe_trade_stream_access(
            api_key="test-key",
            session=Session(response=Response(404)),
        )
        self.assertEqual(result["access"], "endpoint_not_found")
        self.assertIn("stream_access_not_verified", result["warnings"])

    def test_429_is_rate_limited(self):
        result = probe_trade_stream_access(
            api_key="test-key",
            session=Session(
                response=Response(
                    429,
                    {
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": "1234",
                    },
                )
            ),
        )
        self.assertEqual(result["access"], "rate_limited")
        self.assertEqual(result["rate_limit"]["remaining"], "0")
        self.assertIn("stream_access_probe_rate_limited", result["warnings"])

    def test_provider_5xx_is_unavailable(self):
        result = probe_trade_stream_access(
            api_key="test-key",
            session=Session(response=Response(503)),
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["access"], "provider_error")
        self.assertFalse(result["cmis_promotable"])

    def test_http_200_wrong_content_type_is_partial(self):
        result = probe_trade_stream_access(
            api_key="test-key",
            session=Session(
                response=Response(200, {"Content-Type": "application/json"})
            ),
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["access"], "unexpected_success_content_type")
        self.assertFalse(result["sse_handshake_verified"])
        self.assertIn(
            "http_200_without_text_event_stream_content_type",
            result["warnings"],
        )

    def test_unexpected_status_is_partial(self):
        result = probe_trade_stream_access(
            api_key="test-key",
            session=Session(response=Response(302)),
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["access"], "unexpected_http_status")

    def test_request_failure_is_sanitized_exception(self):
        with self.assertRaisesRegex(
            X1NinjaTradeStreamError,
            "access probe request failed",
        ) as caught:
            probe_trade_stream_access(
                api_key="test-key",
                session=Session(error=RuntimeError("secret upstream detail")),
            )
        self.assertNotIn("secret upstream detail", str(caught.exception))
        self.assertNotIn("test-key", str(caught.exception))

    def test_missing_api_key_fails_before_transport(self):
        with self.assertRaisesRegex(RuntimeError, "X1_NINJA_API_KEY"):
            probe_trade_stream_access(api_key="", session=Session(response=Response(200)))

    def test_invalid_response_status_fails_closed_and_closes_response(self):
        response = Response(None)
        with self.assertRaisesRegex(
            X1NinjaTradeStreamError,
            "status is missing or invalid",
        ):
            probe_trade_stream_access(
                api_key="test-key",
                session=Session(response=response),
            )
        self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()
