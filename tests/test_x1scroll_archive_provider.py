import unittest

from liquidity_scout.providers.x1.x1scroll_archive import (
    DEFAULT_X1SCROLL_BASE_URL,
    DOCUMENTED_METHODS,
    X1SCROLL_PROVIDER_ID,
    X1SCROLL_SOURCE,
    X1ScrollArchiveError,
    X1ScrollArchiveProvider,
    build_x1scroll_rpc_url,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class X1ScrollArchiveProviderTests(unittest.TestCase):
    def test_build_rpc_url_keeps_credential_in_one_encoded_path_segment(self):
        self.assertEqual(
            build_x1scroll_rpc_url("a/b c"),
            DEFAULT_X1SCROLL_BASE_URL + "/a%2Fb%20c",
        )

    def test_provider_requires_api_key_unless_complete_rpc_url_is_injected(self):
        with self.assertRaises(ValueError):
            X1ScrollArchiveProvider()

        provider = X1ScrollArchiveProvider(
            rpc_url="https://rpc.example/v1/test-key",
            retries=1,
            post=lambda *_args, **_kwargs: None,
        )
        self.assertEqual(provider.chain, "x1")
        self.assertEqual(provider.provider_id, X1SCROLL_PROVIDER_ID)
        self.assertEqual(provider.source, X1SCROLL_SOURCE)
        self.assertEqual(provider.documented_methods, DOCUMENTED_METHODS)

    def test_get_transaction_uses_exact_documented_default_parameter_shape(self):
        calls = []

        def post(url, json, timeout):
            calls.append((url, json, timeout))
            return FakeResponse({
                "result": {
                    "slot": 99,
                    "blockTime": 1700000000,
                    "meta": {"err": None},
                    "transaction": {"signatures": ["SigA"]},
                }
            })

        provider = X1ScrollArchiveProvider(
            rpc_url="https://rpc.example/v1/test-key",
            retries=1,
            timeout=7,
            post=post,
            sleep=lambda _seconds: None,
        )

        result = provider.get_transaction("SigA")

        self.assertEqual(calls[0][1]["method"], "getTransaction")
        self.assertEqual(calls[0][1]["params"], ["SigA"])
        self.assertEqual(calls[0][2], 7)
        self.assertTrue(result["transaction_available"])
        self.assertEqual(result["signature"], "SigA")
        self.assertEqual(result["provider"], "x1scroll")
        self.assertTrue(result["known_signature_lookup"])
        self.assertFalse(result["address_history_discovery_verified"])
        self.assertFalse(result["archive_completeness_verified"])
        self.assertFalse(result["source_independence_verified"])

    def test_get_transaction_preserves_explicit_qualified_config(self):
        calls = []

        def post(_url, json, timeout):
            calls.append((json, timeout))
            return FakeResponse({"result": None})

        provider = X1ScrollArchiveProvider(
            rpc_url="https://rpc.example/v1/test-key",
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        result = provider.get_transaction(
            "SigA",
            config={"encoding": "jsonParsed"},
        )

        self.assertEqual(
            calls[0][0]["params"],
            ["SigA", {"encoding": "jsonParsed"}],
        )
        self.assertFalse(result["transaction_available"])
        self.assertIsNone(result["transaction"])

    def test_undocumented_methods_fail_closed_by_default(self):
        provider = X1ScrollArchiveProvider(
            rpc_url="https://rpc.example/v1/test-key",
            retries=1,
            post=lambda *_args, **_kwargs: None,
        )

        with self.assertRaises(ValueError):
            provider.request("getSignaturesForAddress", ["MintA"])

    def test_malformed_transaction_result_fails_closed(self):
        def post(_url, json, timeout):
            return FakeResponse({"result": ["not", "a", "transaction"]})

        provider = X1ScrollArchiveProvider(
            rpc_url="https://rpc.example/v1/test-key",
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        with self.assertRaises(X1ScrollArchiveError):
            provider.get_transaction("SigA")

    def test_final_error_does_not_echo_secret_bearing_rpc_url(self):
        secret = "super-secret-key"

        def post(_url, json, timeout):
            return FakeResponse(
                {"error": {"code": -32000, "message": "provider failure"}}
            )

        provider = X1ScrollArchiveProvider(
            api_key=secret,
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        with self.assertRaises(X1ScrollArchiveError) as ctx:
            provider.get_transaction("SigA")

        self.assertNotIn(secret, str(ctx.exception))
        self.assertNotIn(provider.rpc_url, str(ctx.exception))


    def test_rate_limit_retries_are_bounded_and_sanitized(self):
        secret = "rate-limit-secret"
        calls = []

        class RateLimitedResponse:
            status_code = 429

            def raise_for_status(self):
                return None

            def json(self):
                return {"error": {"code": 429, "message": "rate limited"}}

        def post(url, json, timeout):
            calls.append((url, json, timeout))
            return RateLimitedResponse()

        provider = X1ScrollArchiveProvider(
            api_key=secret,
            retries=2,
            post=post,
            sleep=lambda _seconds: None,
        )

        with self.assertRaises(X1ScrollArchiveError) as ctx:
            provider.get_transaction("SigA")

        self.assertEqual(len(calls), 2)
        self.assertNotIn(secret, str(ctx.exception))
        self.assertNotIn(provider.rpc_url, str(ctx.exception))
        self.assertIn("X1ScrollArchiveError", str(ctx.exception))


    def test_transport_exception_cannot_echo_secret_bearing_rpc_url(self):
        secret = "transport-secret-key"

        def post(url, json, timeout):
            raise RuntimeError(f"connection failed for {url}")

        provider = X1ScrollArchiveProvider(
            api_key=secret,
            retries=1,
            post=post,
            sleep=lambda _seconds: None,
        )

        with self.assertRaises(X1ScrollArchiveError) as ctx:
            provider.get_transaction("SigA")

        self.assertNotIn(secret, str(ctx.exception))
        self.assertNotIn(provider.rpc_url, str(ctx.exception))
        self.assertIn("RuntimeError", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
