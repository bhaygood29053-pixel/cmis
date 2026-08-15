import unittest

from liquidity_scout.providers.x1 import (
    CLUSTER_HISTORY_URL,
    HEALTH_URL,
    NETWORK_HISTORY_SOURCE,
    X1HealthAPIError,
    X1HealthProvider,
    X1NetworkAPIError,
    X1NetworkHistoryAPIError,
    X1NetworkHistoryProvider,
    X1NetworkProvider,
    fetch_cluster_history,
    fetch_health,
    fetch_network_snapshot,
    parse_cluster_history,
    parse_health,
    parse_network_snapshot,
)


class FakeJSONResponse:
    def __init__(self, payload, *, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error

    def json(self):
        return self.payload


class RecordingGet:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.responses.pop(0)


class X1NetworkHistoryProviderTests(unittest.TestCase):
    def test_history_uses_exact_official_request_contract(self):
        payload = {
            "labels": [343, 344],
            "datasets": [
                {
                    "name": "currentValidators",
                    "label": "Current Validators",
                    "data": [585, 583],
                },
                {
                    "name": "activatedStake",
                    "label": "Activated Stake",
                    "data": ["998053617680395500", "997282437609329500"],
                },
                {
                    "name": "totalSupply",
                    "label": "Total Supply",
                    "data": ["1066878133201983900", "1067069620907072600"],
                },
            ],
        }
        get = RecordingGet([FakeJSONResponse(payload)])

        result = fetch_cluster_history(get=get)

        call = get.calls[0]
        self.assertEqual(call["url"], CLUSTER_HISTORY_URL)
        self.assertEqual(call["headers"], {"accept": "application/json"})
        self.assertEqual(
            call["params"],
            {
                "network": "mainnet",
                "groupBy": "epoch",
                "chartFormat": "false",
                "order": "asc",
                "filterProperties": "currentValidators,activatedStake,totalSupply",
            },
        )
        self.assertEqual(result["chain"], "x1")
        self.assertEqual(result["network"], "mainnet")
        self.assertEqual(result["source"], NETWORK_HISTORY_SOURCE)
        self.assertIsNone(result["observed_at"])
        self.assertEqual(result["labels"], [343, 344])
        self.assertEqual(
            result["datasets"][2]["data"][1],
            "1067069620907072600",
        )

    def test_history_provider_allows_filtered_properties(self):
        payload = {
            "labels": [344],
            "datasets": [
                {"name": "currentValidators", "label": "Current Validators", "data": [583]},
            ],
        }
        get = RecordingGet([FakeJSONResponse(payload)])
        provider = X1NetworkHistoryProvider(get=get)

        result = provider.get_history(properties=["currentValidators"])

        self.assertEqual(result["properties"], ["currentValidators"])
        self.assertEqual(
            get.calls[0]["params"]["filterProperties"],
            "currentValidators",
        )

    def test_history_dataset_alignment_fails_closed(self):
        payload = {
            "labels": [343, 344],
            "datasets": [
                {"name": "totalSupply", "label": "Total Supply", "data": ["1"]},
            ],
        }
        with self.assertRaises(X1NetworkHistoryAPIError):
            parse_cluster_history(payload)

    def test_history_duplicate_dataset_fails_closed(self):
        payload = {
            "labels": [344],
            "datasets": [
                {"name": "totalSupply", "label": "Total Supply", "data": ["1"]},
                {"name": "totalSupply", "label": "Total Supply", "data": ["1"]},
            ],
        }
        with self.assertRaises(X1NetworkHistoryAPIError):
            parse_cluster_history(payload)

    def test_history_http_failure_fails_closed(self):
        get = RecordingGet([
            FakeJSONResponse({}, error=RuntimeError("service unavailable")),
        ])
        with self.assertRaises(X1NetworkHistoryAPIError):
            fetch_cluster_history(get=get)


class X1HealthProviderTests(unittest.TestCase):
    def test_health_is_provider_infrastructure_not_chain_health(self):
        payload = {
            "status": "ok",
            "info": {"redis": {"status": "up"}},
            "error": {},
            "details": {"redis": {"status": "up"}},
        }
        get = RecordingGet([FakeJSONResponse(payload)])

        result = fetch_health(get=get)

        self.assertEqual(get.calls[0]["url"], HEALTH_URL)
        self.assertEqual(get.calls[0]["headers"], {"accept": "application/json"})
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["operational"])
        self.assertEqual(result["scope"], "provider_infrastructure")
        self.assertEqual(result["details"]["redis"]["status"], "up")
        self.assertIsNone(result["observed_at"])

    def test_health_non_ok_status_is_preserved_without_chain_inference(self):
        parsed = parse_health({"status": "error", "info": {}, "error": {}, "details": {}})
        self.assertEqual(parsed["status"], "error")
        self.assertFalse(parsed["operational"])

    def test_health_missing_status_fails_closed(self):
        with self.assertRaises(X1HealthAPIError):
            parse_health({"info": {}, "error": {}, "details": {}})

    def test_health_provider_delegates_configured_transport(self):
        get = RecordingGet([
            FakeJSONResponse({"status": "ok", "info": {}, "error": {}, "details": {}}),
        ])
        provider = X1HealthProvider(get=get)
        result = provider.get_health()
        self.assertTrue(result["operational"])
        self.assertEqual(len(get.calls), 1)


class X1CurrentNetworkProviderTests(unittest.TestCase):
    def test_snapshot_parser_preserves_provider_representations(self):
        payload = {
            "network": "mainnet",
            "currentValidators": 583,
            "activatedStake": "997282437609329500",
            "totalSupply": "1067069620907791200",
            "circulatingSupply": "13810245516622384",
            "transactionPerSecond": 1618,
            "createdAt": "2026-08-15T09:38:28.295Z",
        }

        parsed = parse_network_snapshot(payload)

        self.assertEqual(parsed["currentValidators"], 583)
        self.assertEqual(parsed["totalSupply"], "1067069620907791200")
        self.assertEqual(parsed["circulatingSupply"], "13810245516622384")
        self.assertEqual(parsed["transactionPerSecond"], 1618)

    def test_snapshot_fetch_requires_explicit_verified_route(self):
        with self.assertRaises(ValueError):
            fetch_network_snapshot(url="")
        with self.assertRaises(ValueError):
            X1NetworkProvider(url="")

    def test_snapshot_fetch_preserves_provider_timestamp_and_marks_units_unverified(self):
        payload = {
            "network": "mainnet",
            "totalSupply": "1067069620907791200",
            "createdAt": "2026-08-15T09:38:28.295Z",
        }
        get = RecordingGet([FakeJSONResponse(payload)])

        result = fetch_network_snapshot(
            url="https://api.x1.xyz/example-explicit-route",
            get=get,
        )

        self.assertEqual(
            get.calls[0]["params"],
            {"network": "mainnet"},
        )
        self.assertEqual(
            result["observed_at"],
            "2026-08-15T09:38:28.295Z",
        )
        self.assertFalse(result["units_verified"])
        self.assertEqual(result["data"]["totalSupply"], "1067069620907791200")

    def test_snapshot_network_mismatch_fails_closed(self):
        get = RecordingGet([FakeJSONResponse({"network": "testnet"})])
        with self.assertRaises(X1NetworkAPIError):
            fetch_network_snapshot(
                url="https://api.x1.xyz/example-explicit-route",
                network="mainnet",
                get=get,
            )


if __name__ == "__main__":
    unittest.main()
