import json
import unittest

from liquidity_scout.providers.x1.warp_har_capture import (
    HAR_OBSERVATION_CONTRACT,
    HAR_METADATA_OBSERVATION_CONTRACT,
    capture_warp_machine_contract_from_har,
    list_warp_har_candidates,
    list_warp_har_observations,
)


CANDIDATE_URL = "https://bridge-api.example.invalid/v1/config"


def field_map():
    return {
        "route_id": "route.id",
        "source_asset_id": "route.sourceMint",
        "destination_asset_id": "route.destinationMint",
        "route_status": "route.status",
        "backing_model": "route.backingModel",
        "custody_dependency": "route.custodyDependency",
        "source_timestamp": "observedAt",
    }


def response():
    return {
        "route": {
            "id": "warp-solana-x1-wsol",
            "sourceMint": "So11111111111111111111111111111111111111112",
            "destinationMint": "JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8",
            "status": "active",
            "backingModel": "lock_mint",
            "custodyDependency": "guardian_multisig",
        },
        "observedAt": 1788420000,
    }


def har_entry(
    *,
    url=CANDIDATE_URL,
    method="GET",
    status=200,
    mime_type="application/json",
    body=None,
    referer="https://app.bridge.x1.xyz/info",
    encoding=None,
    include_body=True,
    content_size=None,
):
    headers = []
    if referer is not None:
        headers.append({"name": "Referer", "value": referer})
    headers.append({"name": "Cookie", "value": "must-not-be-retained"})

    serialized = json.dumps(response() if body is None else body)
    content = {
        "mimeType": mime_type,
        "size": len(serialized.encode("utf-8")) if content_size is None else content_size,
    }
    if include_body:
        content["text"] = serialized
    if encoding is not None:
        content["encoding"] = encoding

    return {
        "request": {
            "method": method,
            "url": url,
            "headers": headers,
            "cookies": [{"name": "session", "value": "secret"}],
        },
        "response": {
            "status": status,
            "headers": [
                {"name": "Content-Type", "value": mime_type},
                {"name": "Set-Cookie", "value": "secret=1"},
            ],
            "content": content,
        },
    }


def har(*entries):
    return {"log": {"version": "1.2", "entries": list(entries)}}


class WarpHarCaptureTests(unittest.TestCase):
    def test_metadata_only_observation_preserves_endpoint_without_semantic_promotion(self):
        observations = list_warp_har_observations(
            har(
                har_entry(
                    url="https://app.bridge.x1.xyz/api/bridge/config",
                    include_body=False,
                    content_size=7746,
                )
            )
        )

        self.assertEqual(len(observations), 1)
        observation = observations[0]
        self.assertEqual(
            observation["contract"],
            HAR_METADATA_OBSERVATION_CONTRACT,
        )
        self.assertEqual(
            observation["source_url"],
            "https://app.bridge.x1.xyz/api/bridge/config",
        )
        self.assertEqual(observation["response_size_bytes"], 7746)
        self.assertFalse(observation["response_body_present"])
        self.assertFalse(observation["json_parse_verified"])
        self.assertIsNone(observation["response_sha256"])
        self.assertFalse(observation["semantic_capture_eligible"])
        self.assertTrue(observation["official_app_network_observation"])
        self.assertFalse(observation["execution_authorized"])

    def test_metadata_only_observation_is_not_a_semantic_capture_candidate(self):
        document = har(
            har_entry(
                url="https://app.bridge.x1.xyz/api/bridge/config",
                include_body=False,
                content_size=7746,
            )
        )
        self.assertEqual(list_warp_har_candidates(document), [])

        with self.assertRaisesRegex(
            ValueError,
            "not an official-app GET\\+200\\+JSON observation",
        ):
            capture_warp_machine_contract_from_har(
                har_document=document,
                entry_index=0,
                field_map=field_map(),
                timestamp_unit="seconds",
                collected_at=1788420010,
            )
    def test_lists_only_sanitized_official_app_get_json_candidates(self):
        candidates = list_warp_har_candidates(har(har_entry()))

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["contract"], HAR_OBSERVATION_CONTRACT)
        self.assertEqual(candidate["entry_index"], 0)
        self.assertEqual(candidate["source_url"], CANDIDATE_URL)
        self.assertTrue(candidate["official_app_network_observation"])
        self.assertFalse(candidate["request_headers_retained"])
        self.assertFalse(candidate["response_body_retained"])
        self.assertNotIn("response_text", candidate)
        self.assertNotIn("headers", candidate)
        self.assertNotIn("cookies", candidate)
        self.assertFalse(candidate["execution_authorized"])

    def test_post_html_and_nonofficial_referrer_are_not_candidates(self):
        candidates = list_warp_har_candidates(
            har(
                har_entry(method="POST"),
                har_entry(mime_type="text/html"),
                har_entry(referer="https://example.com/"),
            )
        )
        self.assertEqual(candidates, [])

    def test_base64_response_is_not_accepted_as_capture_evidence(self):
        candidates = list_warp_har_candidates(
            har(har_entry(encoding="base64"))
        )
        self.assertEqual(candidates, [])

    def test_multiple_candidates_remain_explicit_and_ordered(self):
        candidates = list_warp_har_candidates(
            har(
                har_entry(url="https://bridge-api.example.invalid/v1/config"),
                har_entry(method="POST"),
                har_entry(url="https://bridge-api.example.invalid/v1/health"),
            )
        )
        self.assertEqual(
            [candidate["entry_index"] for candidate in candidates],
            [0, 2],
        )

    def test_selected_candidate_flows_into_existing_capture_gate(self):
        result = capture_warp_machine_contract_from_har(
            har_document=har(har_entry()),
            entry_index=0,
            field_map=field_map(),
            timestamp_unit="seconds",
            collected_at=1788420010,
        )

        self.assertTrue(result["source_provenance_verified"])
        self.assertTrue(result["semantic_review_ready"])
        self.assertTrue(result["official_app_network_observation"])
        self.assertEqual(result["har_entry_index"], 0)
        self.assertFalse(result["semantic_contract_accepted"])
        self.assertFalse(result["accepted_registry_mutation_authorized"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_sensitive_response_body_is_rejected_by_capture_gate(self):
        payload = response()
        payload["access_token"] = "do-not-store"

        with self.assertRaisesRegex(ValueError, "credential-like"):
            capture_warp_machine_contract_from_har(
                har_document=har(har_entry(body=payload)),
                entry_index=0,
                field_map=field_map(),
                timestamp_unit="seconds",
                collected_at=1788420010,
            )

    def test_sensitive_query_parameter_is_not_a_candidate(self):
        candidates = list_warp_har_candidates(
            har(
                har_entry(
                    url="https://bridge-api.example.invalid/v1/config?token=secret"
                )
            )
        )
        self.assertEqual(candidates, [])

    def test_selected_non_candidate_fails_closed(self):
        with self.assertRaisesRegex(
            ValueError,
            "not an official-app GET\\+200\\+JSON observation",
        ):
            capture_warp_machine_contract_from_har(
                har_document=har(har_entry(referer="https://example.com/")),
                entry_index=0,
                field_map=field_map(),
                timestamp_unit="seconds",
                collected_at=1788420010,
            )


if __name__ == "__main__":
    unittest.main()
