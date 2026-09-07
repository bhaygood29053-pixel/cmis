import json
import unittest

from liquidity_scout.providers.web_discovery import (
    DISCOVERED,
    FORTIBLOX_NETWORK_OBSERVATION_CONTRACT,
    classify_fortiblox_network_route,
    list_fortiblox_network_observations,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


APP_PAGE = "https://app.fortiblox.com/"
TOKENS_URL = "https://app.fortiblox.com/api/tokens"
QUOTE_URL = "https://app.fortiblox.com/api/quote"
BUILD_URL = "https://app.fortiblox.com/api/tx/build"


def har_entry(
    *,
    url=TOKENS_URL,
    method="GET",
    request_payload=None,
    referer=APP_PAGE,
    status=200,
    response_body=None,
    response_mime="application/json",
):
    headers = [
        {"name": "Referer", "value": referer},
        {"name": "Authorization", "value": "must-not-survive"},
        {"name": "PAYMENT-SIGNATURE", "value": "must-not-survive"},
    ]
    request = {
        "method": method,
        "url": url,
        "headers": headers,
        "cookies": [{"name": "session", "value": "secret"}],
    }
    if method == "POST":
        payload = request_payload or {
            "inputMint": "A",
            "outputMint": "B",
            "amount": "1000",
        }
        request["postData"] = {
            "mimeType": "application/json",
            "text": json.dumps(payload),
        }

    payload = {"ok": True, "marker": "raw-response-must-not-survive"}
    if response_body is not None:
        payload = response_body
    serialized = (
        payload if isinstance(payload, str) else json.dumps(payload)
    )

    return {
        "request": request,
        "response": {
            "status": status,
            "headers": [
                {"name": "Content-Type", "value": response_mime},
                {"name": "Set-Cookie", "value": "secret=1"},
                {"name": "PAYMENT-REQUIRED", "value": "secret-payment-metadata"},
            ],
            "content": {
                "mimeType": response_mime,
                "size": len(serialized.encode("utf-8")),
                "text": serialized,
            },
        },
    }


def har(*entries):
    return {"log": {"version": "1.2", "entries": list(entries)}}


class FortiBloxNetworkObservationTests(unittest.TestCase):
    def test_known_read_only_get_is_sanitized(self):
        observations = list_fortiblox_network_observations(har(har_entry()))

        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertEqual(item["contract"], FORTIBLOX_NETWORK_OBSERVATION_CONTRACT)
        self.assertEqual(item["route"]["qualification"], "allowed_read_only")
        self.assertEqual(item["route"]["route_template"], "/api/tokens")
        self.assertTrue(item["response_json_parse_verified"])
        self.assertIsNotNone(item["response_sha256"])
        self.assertFalse(item["request_headers_retained"])
        self.assertFalse(item["request_cookies_retained"])
        self.assertFalse(item["response_headers_retained"])
        self.assertFalse(item["payment_headers_retained"])
        self.assertFalse(item["payment_signature_retained"])
        self.assertEqual(item["truth_state"]["discovery_state"], DISCOVERED)
        self.assertFalse(item["truth_state"]["cmis_verified"])
        self.assertFalse(item["execution_authorized"])

        serialized = json.dumps(item)
        self.assertNotIn("must-not-survive", serialized)
        self.assertNotIn("raw-response-must-not-survive", serialized)
        self.assertNotIn("secret-payment-metadata", serialized)

    def test_payment_required_is_metadata_not_payment_authority(self):
        observations = list_fortiblox_network_observations(
            har(
                har_entry(
                    status=402,
                    response_body={
                        "code": "PAYMENT_REQUIRED",
                        "message": "payment required",
                    },
                )
            )
        )

        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertTrue(item["payment_required_observed"])
        self.assertFalse(item["payment_authorized"])
        self.assertFalse(item["payment_headers_retained"])
        self.assertFalse(item["execution_authorized"])

    def test_quote_post_can_be_observed_without_retaining_body(self):
        observations = list_fortiblox_network_observations(
            har(
                har_entry(
                    url=QUOTE_URL,
                    method="POST",
                    request_payload={
                        "inputMint": "mint-a",
                        "outputMint": "mint-b",
                        "amount": "12345",
                    },
                )
            )
        )

        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertEqual(item["route"]["qualification"], "allowed_read_only")
        self.assertEqual(item["route"]["route_template"], "/api/quote")
        self.assertIsNotNone(item["request_body_sha256"])
        self.assertGreater(item["request_body_bytes"], 0)
        self.assertFalse(item["request_body_retained"])
        self.assertNotIn("mint-a", json.dumps(item))
        self.assertFalse(item["request_replay_authorized"])
        self.assertFalse(item["execution_authorized"])

    def test_execution_route_is_dropped(self):
        classification = classify_fortiblox_network_route("POST", BUILD_URL)
        self.assertFalse(classification["observable"])
        self.assertEqual(classification["qualification"], "blocked_execution")

        observations = list_fortiblox_network_observations(
            har(
                har_entry(
                    url=BUILD_URL,
                    method="POST",
                    request_payload={"signedTransaction": "do-not-retain"},
                )
            )
        )
        self.assertEqual(observations, [])

    def test_unknown_same_host_get_json_is_discovery_candidate_only(self):
        url = "https://app.fortiblox.com/api/new-read-surface?limit=10"
        observations = list_fortiblox_network_observations(
            har(har_entry(url=url))
        )

        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertEqual(
            item["route"]["qualification"],
            "unqualified_get_candidate",
        )
        self.assertFalse(item["truth_state"]["route_semantics_verified"])
        self.assertFalse(item["cmis_promotable"])

    def test_public_discovery_route_is_recognized(self):
        observations = list_fortiblox_network_observations(
            har(
                har_entry(
                    url="https://app.fortiblox.com/api/x402/discovery?limit=25&offset=0",
                )
            )
        )
        self.assertEqual(len(observations), 1)
        self.assertEqual(
            observations[0]["route"]["qualification"],
            "public_discovery",
        )

    def test_foreign_or_secret_bearing_url_is_rejected(self):
        self.assertEqual(
            list_fortiblox_network_observations(
                har(har_entry(url="https://example.com/api/tokens"))
            ),
            [],
        )
        self.assertEqual(
            list_fortiblox_network_observations(
                har(har_entry(url=TOKENS_URL + "?api_key=secret"))
            ),
            [],
        )

    def test_sensitive_post_body_is_rejected(self):
        observations = list_fortiblox_network_observations(
            har(
                har_entry(
                    url=QUOTE_URL,
                    method="POST",
                    request_payload={
                        "inputMint": "a",
                        "private_key": "never",
                    },
                )
            )
        )
        self.assertEqual(observations, [])

    def test_service_wrapper_preserves_internal_boundary(self):
        service = CMISWebDiscoveryService()
        result = service.observe_fortiblox_network(har(har_entry()))

        self.assertEqual(result["source_id"], "fortiblox_app")
        self.assertEqual(result["observation_count"], 1)
        self.assertFalse(result["request_replay_authorized"])
        self.assertFalse(result["payment_authorized"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
