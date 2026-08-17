import unittest

from liquidity_scout.providers.x1.ninja_history import (
    OBSERVED_OHLCV_CANDLE_KEYS,
    OBSERVED_OHLCV_TOP_LEVEL_KEYS,
    OHLCV_PATH,
    SUPPORTED_OHLCV_TIMEFRAMES,
    X1_NINJA_API_BASE_URL,
    X1NinjaAPIError,
    fetch_pool_ohlcv_raw,
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


def observed_ohlcv_candle(**overrides):
    row = {
        "time": 1786932000,
        "open": 1.0,
        "high": 2.0,
        "low": 0.5,
        "close": 1.5,
        "volume": 3.0,
    }
    row.update(overrides)
    return row


def observed_ohlcv_body(
    *candles,
    pool_address="POOL1",
    timeframe="1h",
):
    return {
        "ohlcv": list(candles),
        "timeframe": timeframe,
        "mode": "usd",
        "poolAddress": pool_address,
        "currentPrice": 1.5,
        "currentPriceNative": 2.5,
        "currentPriceUsd": 1.5,
        "baseToken": "TOKEN",
        "quoteToken": "XNT",
        "lastUpdated": 1786932000000,
        "candleCount": len(candles),
        "pending": False,
    }


class X1NinjaOHLCVContractTests(unittest.TestCase):
    def test_documented_timeframes_are_explicit(self):
        self.assertEqual(
            SUPPORTED_OHLCV_TIMEFRAMES,
            frozenset({"1m", "5m", "15m", "1h", "4h", "1D"}),
        )

    def test_requires_pool_address(self):
        with self.assertRaises(ValueError):
            fetch_pool_ohlcv_raw("", api_key="secret")

    def test_requires_api_key_without_making_request(self):
        session = FakeSession(FakeResponse())

        with self.assertRaises(RuntimeError):
            fetch_pool_ohlcv_raw(
                "POOL1",
                api_key="",
                session=session,
            )

        self.assertEqual(session.calls, [])

    def test_rejects_undocumented_timeframe_without_request(self):
        session = FakeSession(FakeResponse())

        with self.assertRaises(ValueError):
            fetch_pool_ohlcv_raw(
                "POOL1",
                api_key="secret",
                timeframe="2h",
                session=session,
            )

        self.assertEqual(session.calls, [])

    def test_rejects_limit_above_documented_max_without_request(self):
        session = FakeSession(FakeResponse())

        with self.assertRaises(ValueError):
            fetch_pool_ohlcv_raw(
                "POOL1",
                api_key="secret",
                limit=301,
                session=session,
            )

        self.assertEqual(session.calls, [])

    def test_uses_documented_path_query_and_preserves_raw_json(self):
        body = observed_ohlcv_body(
            observed_ohlcv_candle(
                provider_field="preserve-me"
            ),
            timeframe="5m",
        )
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

        result = fetch_pool_ohlcv_raw(
            "POOL1",
            api_key="secret",
            timeframe="5m",
            limit=300,
            session=session,
            timeout=7,
            observed_at_fn=lambda: 123.5,
        )

        self.assertEqual(len(session.calls), 1)
        url, kwargs = session.calls[0]

        self.assertEqual(
            url,
            (
                f"{X1_NINJA_API_BASE_URL}"
                f"{OHLCV_PATH.format(address='POOL1')}"
            ),
        )
        self.assertEqual(
            kwargs["headers"],
            {"Authorization": "Bearer secret"},
        )
        self.assertEqual(
            kwargs["params"],
            {"tf": "5m", "limit": 300},
        )
        self.assertEqual(kwargs["timeout"], 7)

        self.assertEqual(result["chain"], "x1")
        self.assertEqual(result["pool_address"], "POOL1")
        self.assertEqual(result["timeframe"], "5m")
        self.assertEqual(result["requested_limit"], 300)
        self.assertEqual(result["observed_at"], 123.5)
        self.assertEqual(result["raw_response"], body)

        self.assertEqual(result["rate_limit"]["limit"], "60")
        self.assertEqual(result["rate_limit"]["remaining"], "59")
        self.assertEqual(result["rate_limit"]["reset"], "1786819999")
        self.assertEqual(result["rate_limit"]["window"], "60")
        self.assertEqual(
            result["rate_limit"]["service"],
            "public-api",
        )

        contract = result["contract"]
        self.assertTrue(contract["request_contract_verified"])
        self.assertTrue(contract["response_json_verified"])
        self.assertTrue(contract["candle_schema_verified"])

        for value in result["semantics"].values():
            self.assertFalse(value)

        self.assertFalse(result["cmis_promotable"])

    def test_default_timeframe_is_documented_one_hour(self):
        session = FakeSession(
            FakeResponse(
                body=observed_ohlcv_body(
                    pool_address="POOL2",
                ),
                headers=success_headers(),
            )
        )

        result = fetch_pool_ohlcv_raw(
            "POOL2",
            api_key="secret",
            session=session,
            observed_at_fn=lambda: 1.0,
        )

        _, kwargs = session.calls[0]

        self.assertEqual(kwargs["params"], {"tf": "1h"})
        self.assertEqual(result["timeframe"], "1h")
        self.assertIsNone(result["requested_limit"])
        self.assertEqual(
            result["raw_response"]["ohlcv"],
            [],
        )
        self.assertFalse(result["cmis_promotable"])

    def test_success_fails_closed_when_rate_limit_header_missing(self):
        headers = success_headers()
        del headers["X-RateLimit-Reset"]

        with self.assertRaisesRegex(
            X1NinjaAPIError,
            "X-RateLimit-Reset",
        ):
            fetch_pool_ohlcv_raw(
                "POOL3",
                api_key="secret",
                session=FakeSession(
                    FakeResponse(
                        body=observed_ohlcv_body(
                            pool_address="POOL3",
                        ),
                        headers=headers,
                    )
                ),
            )

    def test_invalid_json_fails_closed_with_response_context(self):
        session = FakeSession(
            FakeResponse(
                headers=success_headers(),
                text="not-json",
                json_error=ValueError("bad json"),
            )
        )

        with self.assertRaisesRegex(
            X1NinjaAPIError,
            "not valid JSON",
        ) as raised:
            fetch_pool_ohlcv_raw(
                "POOL4",
                api_key="secret",
                session=session,
            )

        self.assertIn("not-json", str(raised.exception))

    def test_http_failure_preserves_status_without_leaking_key(self):
        session = FakeSession(
            FakeResponse(
                headers={"Retry-After": "60"},
                status_code=503,
                text='{"error":"upstream unavailable"}',
                http_error=RuntimeError("503 Server Error"),
            )
        )

        with self.assertRaises(X1NinjaAPIError) as raised:
            fetch_pool_ohlcv_raw(
                "POOL5",
                api_key="secret",
                session=session,
            )

        message = str(raised.exception)
        self.assertIn("HTTP 503", message)
        self.assertIn("Retry-After=60", message)
        self.assertIn("upstream unavailable", message)
        self.assertNotIn("secret", message)


class X1NinjaOHLCVObservedShapeTests(unittest.TestCase):
    def _candle(self, **overrides):
        row = {
            "time": 1786932000,
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "volume": 3.0,
        }
        row.update(overrides)
        return row

    def _body(self, *candles):
        return {
            "ohlcv": list(candles),
            "timeframe": "1h",
            "mode": "usd",
            "poolAddress": "POOL1",
            "currentPrice": 1.5,
            "currentPriceNative": 2.5,
            "currentPriceUsd": 1.5,
            "baseToken": "TOKEN",
            "quoteToken": "XNT",
            "lastUpdated": 1786932000000,
            "candleCount": len(candles),
            "pending": False,
        }

    def test_live_observed_response_shape_is_validated(self):
        body = self._body(
            self._candle(extra_provider_field="preserve-me")
        )

        result = fetch_pool_ohlcv_raw(
            "POOL1",
            api_key="secret",
            timeframe="1h",
            limit=5,
            session=FakeSession(
                FakeResponse(
                    body=body,
                    headers=success_headers(),
                )
            ),
            observed_at_fn=lambda: 123.5,
        )

        contract = result["contract"]

        self.assertTrue(
            contract["response_contract_verified"]
        )
        self.assertTrue(
            contract["candle_row_shape_verified"]
        )
        self.assertEqual(
            contract["returned_candle_count"],
            1,
        )
        self.assertTrue(
            OBSERVED_OHLCV_TOP_LEVEL_KEYS.issubset(
                contract["top_level_keys"]
            )
        )
        self.assertTrue(
            OBSERVED_OHLCV_CANDLE_KEYS.issubset(
                contract["candle_row_keys"]
            )
        )

        self.assertEqual(result["raw_response"], body)
        self.assertFalse(result["cmis_promotable"])

    def test_empty_ohlcv_array_is_valid_structure(self):
        result = fetch_pool_ohlcv_raw(
            "POOL1",
            api_key="secret",
            session=FakeSession(
                FakeResponse(
                    body=self._body(),
                    headers=success_headers(),
                )
            ),
        )

        self.assertEqual(
            result["contract"]["returned_candle_count"],
            0,
        )
        self.assertTrue(
            result["contract"]["candle_row_shape_verified"]
        )

    def test_missing_observed_top_level_field_fails_closed(self):
        body = self._body(self._candle())
        del body["lastUpdated"]

        with self.assertRaisesRegex(
            X1NinjaAPIError,
            "lastUpdated",
        ):
            fetch_pool_ohlcv_raw(
                "POOL1",
                api_key="secret",
                session=FakeSession(
                    FakeResponse(
                        body=body,
                        headers=success_headers(),
                    )
                ),
            )

    def test_ohlcv_must_be_array(self):
        body = self._body()
        body["ohlcv"] = {"not": "an array"}

        with self.assertRaisesRegex(
            X1NinjaAPIError,
            "ohlcv",
        ):
            fetch_pool_ohlcv_raw(
                "POOL1",
                api_key="secret",
                session=FakeSession(
                    FakeResponse(
                        body=body,
                        headers=success_headers(),
                    )
                ),
            )

    def test_missing_observed_candle_field_fails_closed(self):
        candle = self._candle()
        del candle["volume"]

        with self.assertRaisesRegex(
            X1NinjaAPIError,
            "volume",
        ):
            fetch_pool_ohlcv_raw(
                "POOL1",
                api_key="secret",
                session=FakeSession(
                    FakeResponse(
                        body=self._body(candle),
                        headers=success_headers(),
                    )
                ),
            )

    def test_provider_pool_address_must_match_requested_pool(self):
        body = self._body(self._candle())
        body["poolAddress"] = "DIFFERENT_POOL"

        with self.assertRaisesRegex(
            X1NinjaAPIError,
            "poolAddress",
        ):
            fetch_pool_ohlcv_raw(
                "POOL1",
                api_key="secret",
                session=FakeSession(
                    FakeResponse(
                        body=body,
                        headers=success_headers(),
                    )
                ),
            )

    def test_provider_timeframe_must_match_requested_timeframe(self):
        body = self._body(self._candle())
        body["timeframe"] = "5m"

        with self.assertRaisesRegex(
            X1NinjaAPIError,
            "timeframe",
        ):
            fetch_pool_ohlcv_raw(
                "POOL1",
                api_key="secret",
                timeframe="1h",
                session=FakeSession(
                    FakeResponse(
                        body=body,
                        headers=success_headers(),
                    )
                ),
            )

    def test_requested_limit_is_not_treated_as_response_cap(self):
        candles = [
            self._candle(time=1000 + index)
            for index in range(6)
        ]

        result = fetch_pool_ohlcv_raw(
            "POOL1",
            api_key="secret",
            limit=5,
            session=FakeSession(
                FakeResponse(
                    body=self._body(*candles),
                    headers=success_headers(),
                )
            ),
        )

        self.assertEqual(result["requested_limit"], 5)
        self.assertEqual(
            result["contract"]["returned_candle_count"],
            6,
        )
        self.assertFalse(
            result["semantics"]["range_coverage_verified"]
        )

if __name__ == "__main__":
    unittest.main()
