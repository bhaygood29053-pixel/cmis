import unittest

from liquidity_scout.providers.x1 import (
    SUPPLY_API_BASE_URL,
    SUPPLY_SOURCE,
    X1SupplyAPIError,
    X1SupplyProvider,
    fetch_supply,
    get_circulating_supply,
    get_x1_network_total_supply,
    parse_supply_text,
)


class FakeResponse:
    def __init__(self, text, *, error=None):
        self.text = text
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error


class RecordingGet:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, params, headers, timeout):
        self.calls.append({
            "url": url,
            "params": params,
            "headers": headers,
            "timeout": timeout,
        })
        return self.responses.pop(0)


class X1SupplyProviderTests(unittest.TestCase):
    def test_circulating_supply_uses_official_public_endpoint(self):
        get = RecordingGet([FakeResponse("13810247")])

        result = get_circulating_supply(get=get)

        self.assertEqual(
            get.calls[0]["url"],
            f"{SUPPLY_API_BASE_URL}/circulating",
        )
        self.assertEqual(get.calls[0]["params"], {"network": "mainnet"})
        self.assertEqual(get.calls[0]["headers"], {"accept": "text/plain"})
        self.assertNotIn("Authorization", get.calls[0]["headers"])
        self.assertEqual(result["chain"], "x1")
        self.assertEqual(result["asset"], "XNT")
        self.assertEqual(result["metric"], "circulating_supply")
        self.assertEqual(result["supply"], "13810247")
        self.assertTrue(result["supply_verified"])
        self.assertEqual(result["representation"], "provider_integer_text")
        self.assertEqual(
            result["source"],
            f"{SUPPLY_SOURCE} /v1/supply/circulating",
        )

    def test_total_supply_uses_official_public_endpoint(self):
        get = RecordingGet([FakeResponse("1067069623")])

        result = get_x1_network_total_supply(get=get)

        self.assertEqual(get.calls[0]["url"], f"{SUPPLY_API_BASE_URL}/total")
        self.assertEqual(get.calls[0]["params"], {"network": "mainnet"})
        self.assertEqual(get.calls[0]["headers"], {"accept": "text/plain"})
        self.assertEqual(result["metric"], "total_supply")
        self.assertEqual(result["supply"], "1067069623")
        self.assertTrue(result["supply_verified"])
        self.assertEqual(
            result["source"],
            f"{SUPPLY_SOURCE} /v1/supply/total",
        )

    def test_provider_fetches_both_supply_metrics_without_reinterpreting_values(self):
        get = RecordingGet([
            FakeResponse("13810247"),
            FakeResponse("1067069623"),
        ])
        provider = X1SupplyProvider(get=get)

        result = provider.get_supply()

        self.assertEqual(provider.chain, "x1")
        self.assertEqual(provider.asset, "XNT")
        self.assertEqual(provider.source, "api.x1.xyz")
        self.assertEqual(result["network"], "mainnet")
        self.assertEqual(result["circulating"]["supply"], "13810247")
        self.assertEqual(result["total"]["supply"], "1067069623")
        self.assertEqual(len(get.calls), 2)

    def test_provider_preserves_exact_integer_without_float_conversion(self):
        very_large = "123456789012345678901234567890"

        self.assertEqual(parse_supply_text(very_large), very_large)

    def test_verified_zero_is_preserved_as_zero(self):
        get = RecordingGet([FakeResponse("0")])

        result = fetch_supply("circulating", get=get)

        self.assertEqual(result["supply"], "0")
        self.assertTrue(result["supply_verified"])

    def test_leading_zeroes_are_normalized_without_changing_integer_value(self):
        self.assertEqual(parse_supply_text("00000123"), "123")
        self.assertEqual(parse_supply_text("0000"), "0")

    def test_malformed_or_empty_supply_fails_closed(self):
        for value in ("", "12.5", "not-a-number", "-1", None):
            with self.subTest(value=value):
                with self.assertRaises(X1SupplyAPIError):
                    parse_supply_text(value)

    def test_http_failure_fails_closed(self):
        get = RecordingGet([
            FakeResponse("", error=RuntimeError("service unavailable")),
        ])

        with self.assertRaises(X1SupplyAPIError) as ctx:
            fetch_supply("total", get=get)

        self.assertIn("total request failed", str(ctx.exception))

    def test_invalid_metric_and_configuration_are_rejected(self):
        with self.assertRaises(ValueError):
            fetch_supply("holders", get=RecordingGet([]))

        with self.assertRaises(ValueError):
            fetch_supply("total", network="   ", get=RecordingGet([]))

        with self.assertRaises(ValueError):
            X1SupplyProvider(network="")

        with self.assertRaises(ValueError):
            X1SupplyProvider(base_url="   ")


if __name__ == "__main__":
    unittest.main()
