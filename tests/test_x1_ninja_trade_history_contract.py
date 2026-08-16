import unittest

from liquidity_scout.providers.x1.ninja_history import (
    TRADE_HISTORY_PATH,
    X1_NINJA_API_BASE_URL,
    X1NinjaAPIError,
    fetch_pool_trades_raw,
)


class FakeResponse:
    def __init__(
        self,
        *,
        body=None,
        headers=None,
        status_code=200,
        text="",
        json_error=None,
        http_error=None,
    ):
        self._body = body
        self.headers = dict(headers or {})
        self.status_code = status_code
        self.text = text
        self._json_error = json_error
        self._http_error = http_error

    def raise_for_status(self):
        if self._http_error is not None:
            raise self._http_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._body


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def success_headers(**extra):
    headers = {
        "X-RateLimit-Limit": "60",
        "X-RateLimit-Remaining": "59",
        "X-RateLimit-Reset": "1786819999",
    }
    headers.update(extra)
    return headers


class X1NinjaTradeHistoryContractTests(unittest.TestCase):
    def test_requires_pool_address(self):
        with self.assertRaises(ValueError):
            fetch_pool_trades_raw("", api_key="secret")

    def test_requires_api_key_without_making_request(self):
        session = FakeSession(FakeResponse())
        with self.assertRaises(RuntimeError):
            fetch_pool_trades_raw("POOL1", api_key="", session=session)
        self.assertEqual(session.calls, [])

    def test_uses_documented_path_bearer_auth_and_preserves_raw_object(self):
        body = {
            "trades": [
                {"unknown_provider_field": "preserve-me"},
            ],
            "provider_meta": {"anything": True},
        }
        session = FakeSession(
            FakeResponse(
                body=body,
                headers=success_headers(
                    **{
                        "X-RateLimit-Window": "60",
                        "X-API-Service": "public-api",
                    }
                ),
            )
        )

        result = fetch_pool_trades_raw(
            "POOL1",
            api_key="secret",
            session=session,
            timeout=7,
            observed_at_fn=lambda: 123.5,
        )

        self.assertEqual(len(session.calls), 1)
        url, kwargs = session.calls[0]
        self.assertEqual(
            url,
            f"{X1_NINJA_API_BASE_URL}{TRADE_HISTORY_PATH.format(address='POOL1')}",
        )
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer secret"})
        self.assertEqual(kwargs["timeout"], 7)
        self.assertEqual(result["chain"], "x1")
        self.assertEqual(result["pool_address"], "POOL1")
        self.assertEqual(result["observed_at"], 123.5)
        self.assertEqual(result["response_shape"], "object")
        self.assertEqual(result["raw_response"], body)
        self.assertEqual(result["rate_limit"]["limit"], "60")
        self.assertEqual(result["rate_limit"]["remaining"], "59")
        self.assertEqual(result["rate_limit"]["reset"], "1786819999")
        self.assertEqual(result["rate_limit"]["window"], "60")
        self.assertEqual(result["rate_limit"]["service"], "public-api")
        self.assertFalse(result["cmis_promotable"])
        self.assertTrue(all(value is False for value in result["semantics"].values()))

    def test_preserves_raw_array_without_inventing_trade_schema(self):
        body = [
            {"opaque": 1},
            {"opaque": 2},
        ]
        result = fetch_pool_trades_raw(
            "POOL2",
            api_key="secret",
            session=FakeSession(FakeResponse(body=body, headers=success_headers())),
            observed_at_fn=lambda: 1.0,
        )

        self.assertEqual(result["response_shape"], "array")
        self.assertEqual(result["raw_response"], body)
        self.assertNotIn("trades", result)

    def test_success_fails_closed_when_documented_rate_limit_header_missing(self):
        headers = success_headers()
        del headers["X-RateLimit-Reset"]
        session = FakeSession(FakeResponse(body={"anything": []}, headers=headers))

        with self.assertRaisesRegex(X1NinjaAPIError, "X-RateLimit-Reset"):
            fetch_pool_trades_raw("POOL3", api_key="secret", session=session)

    def test_invalid_json_fails_closed_and_preserves_bounded_response_context(self):
        session = FakeSession(
            FakeResponse(
                headers=success_headers(),
                text="not-json",
                json_error=ValueError("bad json"),
            )
        )

        with self.assertRaisesRegex(X1NinjaAPIError, "not valid JSON") as raised:
            fetch_pool_trades_raw("POOL4", api_key="secret", session=session)
        self.assertIn("not-json", str(raised.exception))

    def test_documented_http_failure_preserves_status_and_retry_after(self):
        session = FakeSession(
            FakeResponse(
                headers={"Retry-After": "60"},
                status_code=503,
                text='{"error":"upstream unavailable"}',
                http_error=RuntimeError("503 Server Error"),
            )
        )

        with self.assertRaises(X1NinjaAPIError) as raised:
            fetch_pool_trades_raw("POOL5", api_key="secret", session=session)

        message = str(raised.exception)
        self.assertIn("HTTP 503", message)
        self.assertIn("Retry-After=60", message)
        self.assertIn("upstream unavailable", message)
        self.assertNotIn("secret", message)


if __name__ == "__main__":
    unittest.main()
