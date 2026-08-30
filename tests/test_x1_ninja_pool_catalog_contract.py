import unittest

from liquidity_scout.providers.x1.ninja_pool_catalog import (
    BASE_URL,
    POOLS_PATH,
    X1NinjaCatalogError,
    fetch_pool_catalog_raw,
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
        "X-RateLimit-Reset": "1788100000",
    }
    headers.update(extra)
    return headers


class X1NinjaPoolCatalogContractTests(unittest.TestCase):
    def test_requires_positive_integer_limit_before_transport(self):
        session = FakeSession(FakeResponse())
        for bad in (0, -1, True, 1.5, "10"):
            with self.assertRaises(ValueError):
                fetch_pool_catalog_raw(
                    limit=bad,
                    api_key="secret",
                    session=session,
                )
        self.assertEqual(session.calls, [])

    def test_requires_api_key_without_transport(self):
        session = FakeSession(FakeResponse())
        with self.assertRaises(RuntimeError):
            fetch_pool_catalog_raw(api_key="", session=session)
        self.assertEqual(session.calls, [])

    def test_uses_exact_documented_endpoint_and_bearer_auth(self):
        body = {
            "pools": [
                {
                    "address": "POOL1",
                    "priceUsd": "1.23",
                    "liquidityUsd": "456",
                    "unknownProviderField": "preserve",
                }
            ],
            "total": 100,
            "xntPriceUsd": "0.50",
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

        result = fetch_pool_catalog_raw(
            limit=7,
            api_key="secret",
            session=session,
            timeout=9,
            observed_at_fn=lambda: 123.5,
        )

        self.assertEqual(len(session.calls), 1)
        url, kwargs = session.calls[0]
        self.assertEqual(url, f"{BASE_URL}{POOLS_PATH}")
        self.assertEqual(kwargs["params"], {"limit": 7})
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer secret"})
        self.assertEqual(kwargs["timeout"], 9)

        self.assertEqual(result["chain"], "x1")
        self.assertEqual(result["source"], "X1.Ninja Developer API")
        self.assertEqual(result["endpoint"], POOLS_PATH)
        self.assertEqual(result["requested_limit"], 7)
        self.assertEqual(result["observed_at"], 123.5)
        self.assertEqual(result["raw_response"], body)

        self.assertEqual(result["rate_limit"]["limit"], "60")
        self.assertEqual(result["rate_limit"]["remaining"], "59")
        self.assertEqual(result["rate_limit"]["reset"], "1788100000")
        self.assertEqual(result["rate_limit"]["window"], "60")
        self.assertEqual(result["rate_limit"]["service"], "public-api")

        contract = result["contract"]
        self.assertTrue(contract["request_contract_verified"])
        self.assertTrue(contract["response_json_verified"])
        self.assertTrue(contract["pool_array_verified"])
        self.assertTrue(contract["pool_row_object_shape_verified"])
        self.assertEqual(contract["returned_pool_count"], 1)
        self.assertIn("unknownProviderField", contract["pool_row_keys"])
        self.assertEqual(
            contract["pagination_candidate_values_raw"],
            {"total": 100},
        )

        self.assertFalse(result["identity"]["pool_identity_verified"])
        self.assertFalse(result["identity"]["token_side_identity_verified"])
        self.assertTrue(all(value is False for value in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_empty_pool_array_is_valid_without_fabrication(self):
        result = fetch_pool_catalog_raw(
            api_key="secret",
            session=FakeSession(
                FakeResponse(
                    body={"pools": [], "total": 0},
                    headers=success_headers(),
                )
            ),
        )
        self.assertEqual(result["raw_response"]["pools"], [])
        self.assertEqual(result["contract"]["returned_pool_count"], 0)
        self.assertFalse(result["cmis_promotable"])

    def test_missing_pools_array_fails_closed(self):
        with self.assertRaisesRegex(X1NinjaCatalogError, "pools"):
            fetch_pool_catalog_raw(
                api_key="secret",
                session=FakeSession(
                    FakeResponse(
                        body={"total": 1},
                        headers=success_headers(),
                    )
                ),
            )

    def test_non_object_pool_row_fails_closed(self):
        with self.assertRaisesRegex(X1NinjaCatalogError, "row 0"):
            fetch_pool_catalog_raw(
                api_key="secret",
                session=FakeSession(
                    FakeResponse(
                        body={"pools": ["not-an-object"]},
                        headers=success_headers(),
                    )
                ),
            )

    def test_missing_documented_rate_limit_header_fails_closed(self):
        headers = success_headers()
        del headers["X-RateLimit-Reset"]
        with self.assertRaisesRegex(X1NinjaCatalogError, "X-RateLimit-Reset"):
            fetch_pool_catalog_raw(
                api_key="secret",
                session=FakeSession(
                    FakeResponse(body={"pools": []}, headers=headers)
                ),
            )

    def test_invalid_json_preserves_bounded_context_without_api_key(self):
        with self.assertRaisesRegex(X1NinjaCatalogError, "not valid JSON") as raised:
            fetch_pool_catalog_raw(
                api_key="super-secret-key",
                session=FakeSession(
                    FakeResponse(
                        headers=success_headers(),
                        text="not-json",
                        json_error=ValueError("bad json"),
                    )
                ),
            )
        self.assertIn("not-json", str(raised.exception))
        self.assertNotIn("super-secret-key", str(raised.exception))

    def test_http_error_preserves_status_retry_after_and_bounded_body(self):
        with self.assertRaises(X1NinjaCatalogError) as raised:
            fetch_pool_catalog_raw(
                api_key="super-secret-key",
                session=FakeSession(
                    FakeResponse(
                        status_code=503,
                        headers={"Retry-After": "60"},
                        text='{"error":"upstream unavailable"}',
                        http_error=RuntimeError("503 Server Error"),
                    )
                ),
            )

        message = str(raised.exception)
        self.assertIn("HTTP 503", message)
        self.assertIn("Retry-After=60", message)
        self.assertIn("upstream unavailable", message)
        self.assertNotIn("super-secret-key", message)


if __name__ == "__main__":
    unittest.main()
