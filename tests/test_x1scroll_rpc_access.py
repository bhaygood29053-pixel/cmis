import unittest

from liquidity_scout.providers.x1.x1scroll_rpc_access import (
    X1ScrollRpcAccessError,
    probe_x1scroll_rpc_access,
)


class Response:
    def __init__(self, status_code=200, body=None, json_error=None):
        self.status_code = status_code
        self.body = body
        self.json_error = json_error
        self.closed = False

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.body

    def close(self):
        self.closed = True


class Session:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post(self, endpoint, *, json, timeout, headers):
        self.calls.append((endpoint, json, timeout, headers))
        if self.error is not None:
            raise self.error
        return self.response


class X1ScrollRpcAccessTests(unittest.TestCase):
    def test_health_success_proves_only_unauthenticated_method_access(self):
        response = Response(200, {"jsonrpc": "2.0", "id": 1, "result": "ok"})
        session = Session(response=response)
        result = probe_x1scroll_rpc_access(session=session)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["access"], "available_unauthenticated")
        self.assertTrue(result["jsonrpc_envelope_verified"])
        self.assertTrue(result["result_shape_verified"])
        self.assertFalse(result["credentials_supplied"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["archival_completeness_verified"])
        self.assertFalse(result["retention_verified"])
        self.assertFalse(result["finality_semantics_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertTrue(response.closed)

        endpoint, payload, timeout, headers = session.calls[0]
        self.assertEqual(endpoint, "https://x1scroll.io/rpc")
        self.assertEqual(payload["method"], "getHealth")
        self.assertEqual(payload["params"], [])
        self.assertEqual(timeout, 10)
        self.assertNotIn("Authorization", headers)
        self.assertNotIn("X-API-Key", headers)

    def test_slot_success_preserves_observed_slot_without_archival_claim(self):
        response = Response(200, {"jsonrpc": "2.0", "id": 1, "result": 123456})
        result = probe_x1scroll_rpc_access(
            endpoint="https://rpc.x1scroll.io",
            method="getSlot",
            session=Session(response=response),
        )
        self.assertEqual(result["access"], "available_unauthenticated")
        self.assertEqual(result["observed_slot"], 123456)
        self.assertFalse(result["archival_completeness_verified"])

    def test_access_denied_is_structured_and_does_not_parse_body(self):
        response = Response(401, json_error=AssertionError("body must not be parsed"))
        result = probe_x1scroll_rpc_access(session=Session(response=response))
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["access"], "access_denied")
        self.assertFalse(result["jsonrpc_envelope_verified"])
        self.assertTrue(response.closed)

    def test_rate_limit_is_structured_unavailable(self):
        result = probe_x1scroll_rpc_access(
            session=Session(response=Response(429, {"secret": "not parsed"}))
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
        result = probe_x1scroll_rpc_access(session=Session(response=response))
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["access"], "jsonrpc_error")
        self.assertEqual(result["rpc_error_code"], -32001)
        self.assertNotIn("API key required", str(result))

    def test_invalid_json_response_is_partial(self):
        result = probe_x1scroll_rpc_access(
            session=Session(response=Response(200, json_error=ValueError("bad")))
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["access"], "invalid_json_response")

    def test_transport_exception_is_sanitized(self):
        with self.assertRaisesRegex(
            X1ScrollRpcAccessError,
            "read-only RPC access probe failed",
        ) as caught:
            probe_x1scroll_rpc_access(
                session=Session(error=RuntimeError("private upstream detail"))
            )
        self.assertNotIn("private upstream detail", str(caught.exception))

    def test_arbitrary_endpoint_is_rejected_before_transport(self):
        session = Session(response=Response(200, {}))
        with self.assertRaisesRegex(ValueError, "exact published X1Scroll"):
            probe_x1scroll_rpc_access(
                endpoint="https://example.com/rpc",
                session=session,
            )
        self.assertEqual(session.calls, [])

    def test_write_method_is_rejected_before_transport(self):
        session = Session(response=Response(200, {}))
        with self.assertRaisesRegex(ValueError, "getHealth or getSlot"):
            probe_x1scroll_rpc_access(method="sendTransaction", session=session)
        self.assertEqual(session.calls, [])

    def test_boolean_http_status_is_rejected(self):
        response = Response(True, {})
        with self.assertRaisesRegex(X1ScrollRpcAccessError, "HTTP status"):
            probe_x1scroll_rpc_access(session=Session(response=response))
        self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()
