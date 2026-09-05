import json
import unittest

from liquidity_scout.providers.web_discovery import (
    DISCOVERED,
    X1_EXPLORER_NETWORK_OBSERVATION_CONTRACT,
    X1_EXPLORER_READ_ONLY_RPC_METHODS,
    list_x1_explorer_network_observations,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


ADDRESS = "1" * 32
SIGNATURE = "1" * 64
RPC_URL = "https://rpc.mainnet.x1.xyz"
EXPLORER_PAGE = f"https://explorer.mainnet.x1.xyz/address/{ADDRESS}"


def rpc_request(method, params=None, *, request_id=1):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": [] if params is None else params,
    }


def har_entry(
    *,
    url=RPC_URL,
    method="POST",
    request_payload=None,
    referer=EXPLORER_PAGE,
    origin=None,
    status=200,
    response_body=None,
    response_mime="application/json",
    request_mime="application/json",
    include_response_body=True,
):
    request_headers = [{"name": "Cookie", "value": "must-not-be-retained"}]
    if referer is not None:
        request_headers.append({"name": "Referer", "value": referer})
    if origin is not None:
        request_headers.append({"name": "Origin", "value": origin})

    request = {
        "method": method,
        "url": url,
        "headers": request_headers,
        "cookies": [{"name": "session", "value": "secret"}],
    }
    if method == "POST":
        payload = (
            rpc_request("getEpochInfo")
            if request_payload is None
            else request_payload
        )
        request["postData"] = {
            "mimeType": request_mime,
            "text": json.dumps(payload),
        }

    response_payload = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
    if response_body is not None:
        response_payload = response_body
    serialized = json.dumps(response_payload)
    response_content = {
        "mimeType": response_mime,
        "size": len(serialized.encode("utf-8")),
    }
    if include_response_body:
        response_content["text"] = serialized

    return {
        "request": request,
        "response": {
            "status": status,
            "headers": [
                {"name": "Content-Type", "value": response_mime},
                {"name": "Set-Cookie", "value": "secret=1"},
            ],
            "content": response_content,
        },
    }


def har(*entries):
    return {"log": {"version": "1.2", "entries": list(entries)}}


class X1ExplorerNetworkObservationTests(unittest.TestCase):
    def test_read_only_rpc_allowlist_excludes_execution_methods(self):
        self.assertIn("getTransaction", X1_EXPLORER_READ_ONLY_RPC_METHODS)
        self.assertIn("getSignaturesForAddress", X1_EXPLORER_READ_ONLY_RPC_METHODS)
        self.assertNotIn("sendTransaction", X1_EXPLORER_READ_ONLY_RPC_METHODS)
        self.assertNotIn("simulateTransaction", X1_EXPLORER_READ_ONLY_RPC_METHODS)

    def test_transaction_rpc_observation_extracts_safe_identifier(self):
        observations = list_x1_explorer_network_observations(
            har(
                har_entry(
                    request_payload=rpc_request(
                        "getTransaction",
                        [SIGNATURE, {"maxSupportedTransactionVersion": 0}],
                    )
                )
            )
        )

        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertEqual(
            item["contract"],
            X1_EXPLORER_NETWORK_OBSERVATION_CONTRACT,
        )
        self.assertEqual(item["transport_method"], "POST")
        self.assertTrue(item["rpc_read_method_recognized"])
        self.assertEqual(item["rpc"]["rpc_methods"], ["getTransaction"])
        self.assertEqual(
            item["rpc"]["safe_identifiers"],
            [
                {
                    "role": "transaction_signature",
                    "entity_type": "transaction",
                    "identifier": SIGNATURE,
                    "explorer_route": f"/tx/{SIGNATURE}",
                    "entity_identity_verified": False,
                }
            ],
        )
        self.assertFalse(item["request_body_retained"])
        self.assertFalse(item["request_headers_retained"])
        self.assertFalse(item["request_cookies_retained"])
        self.assertFalse(item["response_body_retained"])
        self.assertFalse(item["response_headers_retained"])
        self.assertTrue(item["response_json_parse_verified"])
        self.assertIsNotNone(item["request_body_sha256"])
        self.assertIsNotNone(item["response_sha256"])
        self.assertEqual(
            item["truth_state"]["discovery_state"],
            DISCOVERED,
        )
        self.assertFalse(item["truth_state"]["entity_identity_verified"])
        self.assertFalse(item["cmis_promotable"])
        self.assertFalse(item["execution_authorized"])

    def test_address_history_rpc_observation_extracts_address(self):
        observations = list_x1_explorer_network_observations(
            har(
                har_entry(
                    request_payload=rpc_request(
                        "getSignaturesForAddress",
                        [ADDRESS, {"limit": 25}],
                    )
                )
            )
        )
        self.assertEqual(len(observations), 1)
        identifier = observations[0]["rpc"]["safe_identifiers"][0]
        self.assertEqual(identifier["entity_type"], "address")
        self.assertEqual(identifier["identifier"], ADDRESS)
        self.assertEqual(identifier["explorer_route"], f"/address/{ADDRESS}")

    def test_batch_read_only_rpc_is_allowed_and_bounded(self):
        payload = [
            rpc_request("getEpochInfo", request_id=1),
            rpc_request("getBlock", [42], request_id=2),
            rpc_request("getBlockTime", [42], request_id=3),
        ]
        observations = list_x1_explorer_network_observations(
            har(har_entry(request_payload=payload))
        )
        self.assertEqual(len(observations), 1)
        rpc = observations[0]["rpc"]
        self.assertEqual(rpc["rpc_call_count"], 3)
        self.assertEqual(
            rpc["rpc_methods"],
            ["getEpochInfo", "getBlock", "getBlockTime"],
        )
        self.assertEqual(len(rpc["safe_identifiers"]), 1)

    def test_send_transaction_and_unknown_rpc_methods_fail_closed(self):
        observations = list_x1_explorer_network_observations(
            har(
                har_entry(
                    request_payload=rpc_request(
                        "sendTransaction",
                        ["signed-payload"],
                    )
                ),
                har_entry(
                    request_payload=rpc_request(
                        "getMysteryThing",
                        [],
                    )
                ),
            )
        )
        self.assertEqual(observations, [])

    def test_foreign_referrer_or_target_host_is_rejected(self):
        observations = list_x1_explorer_network_observations(
            har(
                har_entry(referer="https://example.com/"),
                har_entry(url="https://rpc.example.com"),
            )
        )
        self.assertEqual(observations, [])

    def test_official_origin_can_qualify_when_referer_is_missing(self):
        observations = list_x1_explorer_network_observations(
            har(
                har_entry(
                    referer=None,
                    origin="https://explorer.mainnet.x1.xyz",
                )
            )
        )
        self.assertEqual(len(observations), 1)
        self.assertTrue(
            observations[0]["official_explorer_network_observation"]
        )

    def test_sensitive_query_and_request_body_are_rejected(self):
        observations = list_x1_explorer_network_observations(
            har(
                har_entry(
                    url="https://rpc.mainnet.x1.xyz?api_key=secret"
                ),
                har_entry(
                    request_payload={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getEpochInfo",
                        "params": [],
                        "access_token": "secret",
                    }
                ),
            )
        )
        self.assertEqual(observations, [])

    def test_get_json_api_observation_is_metadata_only_not_rpc(self):
        observations = list_x1_explorer_network_observations(
            har(
                har_entry(
                    url="https://explorer.mainnet.x1.xyz/api/metadata/example",
                    method="GET",
                )
            )
        )
        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertEqual(item["transport_method"], "GET")
        self.assertFalse(item["rpc_read_method_recognized"])
        self.assertIsNone(item["rpc"])
        self.assertTrue(item["response_json_parse_verified"])
        self.assertFalse(item["truth_state"]["cmis_verified"])

    def test_non_json_get_response_is_rejected(self):
        observations = list_x1_explorer_network_observations(
            har(
                har_entry(
                    url="https://explorer.mainnet.x1.xyz/api/example",
                    method="GET",
                    response_mime="text/html",
                )
            )
        )
        self.assertEqual(observations, [])

    def test_response_without_body_preserves_metadata_without_json_promotion(self):
        observations = list_x1_explorer_network_observations(
            har(
                har_entry(
                    request_payload=rpc_request("getEpochSchedule"),
                    include_response_body=False,
                )
            )
        )
        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertFalse(item["response_body_present"])
        self.assertFalse(item["response_json_parse_verified"])
        self.assertIsNone(item["response_sha256"])
        self.assertFalse(item["truth_state"]["cmis_verified"])

    def test_service_wrapper_preserves_replay_and_execution_boundary(self):
        service = CMISWebDiscoveryService()
        result = service.observe_x1_explorer_network(
            har(
                har_entry(
                    request_payload=rpc_request("getBlock", [76529110])
                )
            )
        )

        self.assertEqual(result["observation_count"], 1)
        self.assertFalse(result["request_replay_authorized"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
