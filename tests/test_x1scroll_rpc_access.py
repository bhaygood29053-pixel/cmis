import unittest

from liquidity_scout.providers.x1.x1scroll_rpc_access import (
    X1SCROLL_RPC_REDACTED_ENDPOINT,
    X1ScrollRpcAccessError,
    probe_x1scroll_rpc_access,
)


TEST_API_KEY = "unit-test-key_123"


class Response:
    def __init__(self, status_code=200, body=None, json_error=None):
        self.status_code = status_code
        self.body = body
        self.json_error = json_error
        self.closed = False
        self.json_called = False

    def json(self):
        self.json_called = True
        if self.json_error is not None:
            raise self.json_error
        return self.body

    def close(self):
        self.closed = True


class Session:
    def __init__(self, response=None, error=None, *, ambient_credentials=False):
        self.response = response
        self.error = error
        self.calls = []
        self.closed = False
        self.trust_env = True
        self.auth = ("ambient-user", "ambient-password") if ambient_credentials else None
        self.headers = (
            {
                "Authorization": "Bearer ambient-secret",
                "Proxy-Authorization": "Basic proxy-secret",
                "X-Test": "preserve",
            }
            if ambient_credentials
            else {"X-Test": "preserve"}
        )
        self.cookies = {"session": "ambient-cookie"} if ambient_credentials else {}
        self.proxies = {"https": "https://proxy.invalid"} if ambient_credentials else {}

    def post(self, endpoint, *, json, timeout, allow_redirects, headers):
        self.calls.append(
            {
                "endpoint": endpoint,
                "json": json,
                "timeout": timeout,
                "allow_redirects": allow_redirects,
                "headers": headers,
                "trust_env": self.trust_env,
                "auth": self.auth,
                "session_headers": dict(self.headers),
                "cookies": dict(self.cookies),
                "proxies": dict(self.proxies),
            }
        )
        if self.error is not None:
            raise self.error
        return self.response

    def close(self):
        self.closed = True


def _factory(session):
    return lambda: session


class X1ScrollRpcAccessTests(unittest.TestCase):
    def test_health_success_uses_isolated_authenticated_transport(self):
        response = Response(200, {"jsonrpc": "2.0", "id": 1, "result": "ok"})
        session = Session(response=response, ambient_credentials=True)
        result = probe_x1scroll_rpc_access(
            api_key=TEST_API_KEY,
            session_factory=_factory(session),
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["access"], "available_authenticated")
        self.assertEqual(result["endpoint"], X1SCROLL_RPC_REDACTED_ENDPOINT)
        self.assertEqual(result["authentication"], "api_key_path_segment")
        self.assertEqual(result["request_id"], 1)
        self.assertTrue(result["response_id_verified"])
        self.assertTrue(result["jsonrpc_envelope_verified"])
        self.assertTrue(result["result_shape_verified"])
        self.assertFalse(result["redirects_followed"])
        self.assertTrue(result["transport_environment_auth_disabled"])
        self.assertTrue(result["credentials_supplied"])
        self.assertFalse(result["credentials_retained"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["archival_completeness_verified"])
        self.assertFalse(result["retention_verified"])
        self.assertFalse(result["finality_semantics_verified"])
        self.assertFalse(result["historical_method_coverage_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertNotIn(TEST_API_KEY, str(result))
        self.assertTrue(response.closed)
        self.assertTrue(session.closed)

        call = session.calls[0]
        self.assertEqual(
            call["endpoint"],
            f"https://rpc.x1scroll.io/v1/{TEST_API_KEY}",
        )
        self.assertEqual(call["json"]["method"], "getHealth")
        self.assertEqual(call["json"]["params"], [])
        self.assertEqual(call["timeout"], 10)
        self.assertFalse(call["allow_redirects"])
        self.assertFalse(call["trust_env"])
        self.assertIsNone(call["auth"])
        self.assertNotIn("Authorization", call["session_headers"])
        self.assertNotIn("Proxy-Authorization", call["session_headers"])
        self.assertEqual(call["cookies"], {})
        self.assertEqual(call["proxies"], {})
        self.assertNotIn("Authorization", call["headers"])
        self.assertNotIn("X-API-Key", call["headers"])

    def test_slot_success_preserves_observed_slot_without_archival_claim(self):
        response = Response(200, {"jsonrpc": "2.0", "id": 1, "result": 123456})
        result = probe_x1scroll_rpc_access(
            api_key=TEST_API_KEY,
            method="getSlot",
            session_factory=_factory(Session(response=response)),
        )
        self.assertEqual(result["access"], "available_authenticated")
        self.assertEqual(result["observed_slot"], 123456)
        self.assertTrue(result["response_id_verified"])
        self.assertFalse(result["archival_completeness_verified"])
        self.assertFalse(result["historical_method_coverage_verified"])

    def test_redirect_is_not_followed_or_accepted_as_rpc_evidence(self):
        response = Response(
            307,
            json_error=AssertionError("redirect response body must not be parsed"),
        )
        session = Session(response=response)
        result = probe_x1scroll_rpc_access(
            api_key=TEST_API_KEY,
            session_factory=_factory(session),
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["access"], "unexpected_http_status")
        self.assertFalse(result["redirects_followed"])
        self.assertFalse(result["response_id_verified"])
        self.assertFalse(response.json_called)
        self.assertFalse(session.calls[0]["allow_redirects"])

    def test_response_id_mismatch_is_partial_and_never_accessible(self):
        response = Response(200, {"jsonrpc": "2.0", "id": 999, "result": "ok"})
        result = probe_x1scroll_rpc_access(
            api_key=TEST_API_KEY,
            session_factory=_factory(Session(response=response)),
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["access"], "jsonrpc_id_mismatch")
        self.assertFalse(result["response_id_verified"])
        self.assertFalse(result["jsonrpc_envelope_verified"])
        self.assertFalse(result["result_shape_verified"])

    def test_boolean_response_id_does_not_equal_integer_request_id(self):
        response = Response(200, {"jsonrpc": "2.0", "id": True, "result": "ok"})
        result = probe_x1scroll_rpc_access(
            api_key=TEST_API_KEY,
            session_factory=_factory(Session(response=response)),
        )
        self.assertEqual(result["access"], "jsonrpc_id_mismatch")
        self.assertFalse(result["response_id_verified"])

    def test_access_denied_is_structured_and_does_not_parse_body(self):
        response = Response(401, json_error=AssertionError("body must not be parsed"))
        result = probe_x1scroll_rpc_access(
            api_key=TEST_API_KEY,
            session_factory=_factory(Session(response=response)),
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["access"], "access_denied")
        self.assertFalse(result["jsonrpc_envelope_verified"])
        self.assertNotIn(TEST_API_KEY, str(result))
        self.assertFalse(response.json_called)
        self.assertTrue(response.closed)

    def test_rate_limit_is_structured_unavailable(self):
        result = probe_x1scroll_rpc_access(
            api_key=TEST_API_KEY,
            session_factory=_factory(Session(response=Response(429, {"secret": "not parsed"}))),
        )
        self.assertEqual(result["access"], "rate_limited")
        self.assertFalse(result["cmis_promotable"])

    def test_jsonrpc_error_preserves_only_numeric_error_code(self):
        response = Response(
            200,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32001, "message": "API key required"},
            },
        )
        result = probe_x1scroll_rpc_access(
            api_key=TEST_API_KEY,
            session_factory=_factory(Session(response=response)),
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["access"], "jsonrpc_error")
        self.assertEqual(result["rpc_error_code"], -32001)
        self.assertTrue(result["response_id_verified"])
        self.assertNotIn("API key required", str(result))
        self.assertNotIn(TEST_API_KEY, str(result))

    def test_invalid_json_response_is_partial(self):
        result = probe_x1scroll_rpc_access(
            api_key=TEST_API_KEY,
            session_factory=_factory(
                Session(response=Response(200, json_error=ValueError("bad")))
            ),
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["access"], "invalid_json_response")

    def test_transport_exception_is_sanitized_without_chained_cause(self):
        session = Session(
            error=RuntimeError(
                f"private upstream detail https://rpc.x1scroll.io/v1/{TEST_API_KEY}"
            )
        )
        with self.assertRaisesRegex(
            X1ScrollRpcAccessError,
            "read-only RPC access probe failed",
        ) as caught:
            probe_x1scroll_rpc_access(
                api_key=TEST_API_KEY,
                session_factory=_factory(session),
            )
        self.assertNotIn("private upstream detail", str(caught.exception))
        self.assertNotIn(TEST_API_KEY, str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(session.closed)

    def test_session_factory_exception_is_sanitized(self):
        def broken_factory():
            raise RuntimeError("private factory detail")

        with self.assertRaisesRegex(
            X1ScrollRpcAccessError,
            "read-only RPC access probe failed",
        ) as caught:
            probe_x1scroll_rpc_access(
                api_key=TEST_API_KEY,
                session_factory=broken_factory,
            )
        self.assertNotIn("private factory detail", str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)

    def test_empty_api_key_is_rejected_before_factory(self):
        calls = []

        def factory():
            calls.append(True)
            return Session(response=Response(200, {}))

        with self.assertRaisesRegex(ValueError, "non-empty string"):
            probe_x1scroll_rpc_access(api_key="", session_factory=factory)
        self.assertEqual(calls, [])

    def test_url_delimiter_and_whitespace_keys_are_rejected_before_factory(self):
        for invalid in (
            "key/child",
            "key?query",
            "key#fragment",
            "key with space",
            " key",
            "key\n",
        ):
            with self.subTest(invalid=invalid):
                calls = []

                def factory():
                    calls.append(True)
                    return Session(response=Response(200, {}))

                with self.assertRaisesRegex(ValueError, "unsupported characters"):
                    probe_x1scroll_rpc_access(
                        api_key=invalid,
                        session_factory=factory,
                    )
                self.assertEqual(calls, [])

    def test_write_method_is_rejected_before_factory(self):
        calls = []

        def factory():
            calls.append(True)
            return Session(response=Response(200, {}))

        with self.assertRaisesRegex(ValueError, "getHealth or getSlot"):
            probe_x1scroll_rpc_access(
                api_key=TEST_API_KEY,
                method="sendTransaction",
                session_factory=factory,
            )
        self.assertEqual(calls, [])

    def test_boolean_http_status_is_rejected_and_transport_closed(self):
        response = Response(True, {})
        session = Session(response=response)
        with self.assertRaisesRegex(X1ScrollRpcAccessError, "HTTP status"):
            probe_x1scroll_rpc_access(
                api_key=TEST_API_KEY,
                session_factory=_factory(session),
            )
        self.assertTrue(response.closed)
        self.assertTrue(session.closed)


if __name__ == "__main__":
    unittest.main()
