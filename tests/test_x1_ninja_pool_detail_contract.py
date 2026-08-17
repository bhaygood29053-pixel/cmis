import unittest

from liquidity_scout.providers.x1.ninja_pool_detail import (
    X1NinjaPoolDetailError,
    fetch_pool_detail_raw,
)


class FakeResponse:
    def __init__(self, body, *, headers=None, error=None):
        self._body = body
        self.headers = headers or {
            "X-RateLimit-Limit": "60",
            "X-RateLimit-Remaining": "59",
            "X-RateLimit-Reset": "1234567890",
        }
        self._error = error

    def raise_for_status(self):
        if self._error is not None:
            raise self._error

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class X1NinjaPoolDetailContractTests(unittest.TestCase):
    def test_preserves_raw_response_and_never_promotes_reserve_semantics(self):
        body = {
            "address": "pool-1",
            "baseToken": {"symbol": "AAA", "reserveRaw": "100"},
            "quoteToken": {"symbol": "XNT"},
            "baseReserve": "100",
            "quoteReserve": "200",
            "holders": [],
        }
        session = FakeSession(FakeResponse(body))

        result = fetch_pool_detail_raw(
            "pool-1",
            api_key="secret",
            session=session,
            timeout=7,
        )

        self.assertEqual(result["raw_response"], body)
        self.assertEqual(result["pool_address_requested"], "pool-1")
        self.assertFalse(result["identity"]["pool_identity_verified"])
        self.assertFalse(result["semantics"]["reserve_field_roles_verified"])
        self.assertFalse(result["semantics"]["reserve_units_verified"])
        self.assertFalse(result["semantics"]["token_decimals_verified"])
        self.assertFalse(result["cmis_promotable"])

        self.assertEqual(
            result["contract"]["lexical_reserve_field_paths"],
            ["baseReserve", "baseToken.reserveRaw", "quoteReserve"],
        )
        self.assertEqual(
            result["identity"]["raw_identifier_candidates"],
            {"address": "pool-1"},
        )

        self.assertEqual(len(session.calls), 1)
        url, kwargs = session.calls[0]
        self.assertEqual(url, "https://api.x1.ninja/v1/pools/pool-1")
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer secret"})
        self.assertEqual(kwargs["timeout"], 7)

    def test_lexical_reserve_detection_is_not_value_interpretation(self):
        body = {
            "poolAddress": "pool-1",
            "metadata": {
                "reserveLabel": None,
                "nested": [{"reserveMystery": {"amount": "not-a-number"}}],
            },
        }
        session = FakeSession(FakeResponse(body))

        result = fetch_pool_detail_raw(
            "pool-1",
            api_key="secret",
            session=session,
        )

        self.assertEqual(
            result["contract"]["lexical_reserve_field_paths"],
            [
                "metadata.nested[].reserveMystery",
                "metadata.reserveLabel",
            ],
        )
        self.assertFalse(result["cmis_promotable"])

    def test_rejects_non_object_json(self):
        session = FakeSession(FakeResponse([]))

        with self.assertRaisesRegex(
            X1NinjaPoolDetailError,
            "must be a JSON object",
        ):
            fetch_pool_detail_raw(
                "pool-1",
                api_key="secret",
                session=session,
            )

    def test_rejects_missing_documented_rate_limit_headers(self):
        session = FakeSession(
            FakeResponse(
                {"address": "pool-1"},
                headers={"X-RateLimit-Limit": "60"},
            )
        )

        with self.assertRaisesRegex(
            X1NinjaPoolDetailError,
            "missing documented rate-limit header",
        ):
            fetch_pool_detail_raw(
                "pool-1",
                api_key="secret",
                session=session,
            )

    def test_rejects_invalid_json(self):
        session = FakeSession(FakeResponse(ValueError("bad json")))

        with self.assertRaisesRegex(
            X1NinjaPoolDetailError,
            "was not valid JSON",
        ):
            fetch_pool_detail_raw(
                "pool-1",
                api_key="secret",
                session=session,
            )

    def test_rejects_http_failure(self):
        session = FakeSession(
            FakeResponse({}, error=RuntimeError("HTTP 503"))
        )

        with self.assertRaisesRegex(
            X1NinjaPoolDetailError,
            "request failed",
        ):
            fetch_pool_detail_raw(
                "pool-1",
                api_key="secret",
                session=session,
            )

    def test_rejects_empty_address(self):
        session = FakeSession(FakeResponse({}))

        with self.assertRaisesRegex(ValueError, "address must not be empty"):
            fetch_pool_detail_raw(
                "  ",
                api_key="secret",
                session=session,
            )

    def test_requires_api_key(self):
        session = FakeSession(FakeResponse({}))

        with self.assertRaisesRegex(RuntimeError, "X1_NINJA_API_KEY"):
            fetch_pool_detail_raw(
                "pool-1",
                api_key="",
                session=session,
            )


if __name__ == "__main__":
    unittest.main()
