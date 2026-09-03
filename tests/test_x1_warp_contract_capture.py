import json
import unittest

from liquidity_scout.providers.x1.bridge_source_provenance import BridgeSourceProof
from liquidity_scout.providers.x1.warp_contract_capture import (
    CAPTURE_CONTRACT,
    capture_warp_machine_contract,
)


CANDIDATE_URL = "https://bridge-api.example.invalid/v1/config"


def proof(url=CANDIDATE_URL):
    return BridgeSourceProof(
        proof_type="official_app_network_observation",
        reference="sanitized official-app network observation",
        exact_url=url,
    )


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


class WarpMachineContractCaptureTests(unittest.TestCase):
    def test_complete_exact_get_json_capture_becomes_review_ready_but_not_accepted(self):
        result = capture_warp_machine_contract(
            source_url=CANDIDATE_URL,
            method="GET",
            status_code=200,
            content_type="application/json; charset=utf-8",
            response_text=json.dumps(response(), sort_keys=True),
            proofs=[proof()],
            field_map=field_map(),
            timestamp_unit="seconds",
            collected_at=1788420010,
        )

        self.assertEqual(result["contract"], CAPTURE_CONTRACT)
        self.assertTrue(result["source_provenance_verified"])
        self.assertTrue(result["json_parse_verified"])
        self.assertTrue(result["semantic_review_ready"])
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["semantic_contract_accepted"])
        self.assertFalse(result["accepted_registry_mutation_authorized"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_html_info_page_is_not_a_machine_contract(self):
        result = capture_warp_machine_contract(
            source_url="https://app.bridge.x1.xyz/info",
            method="GET",
            status_code=200,
            content_type="text/html",
            response_text="<html><body>Real-time status and configuration</body></html>",
            proofs=[
                BridgeSourceProof(
                    proof_type="x1_owned_application_artifact",
                    reference="official bridge info page",
                    exact_url="https://app.bridge.x1.xyz/info",
                )
            ],
            field_map=field_map(),
            timestamp_unit="seconds",
            collected_at=1788420010,
        )

        self.assertFalse(result["semantic_review_ready"])
        self.assertIn(
            "machine_json_content_type_not_verified",
            result["blockers"],
        )
        self.assertFalse(result["semantic_contract_accepted"])

    def test_http_200_json_without_exact_provenance_is_not_review_ready(self):
        result = capture_warp_machine_contract(
            source_url=CANDIDATE_URL,
            method="GET",
            status_code=200,
            content_type="application/json",
            response_text=json.dumps(response()),
            proofs=[],
            field_map=field_map(),
            timestamp_unit="seconds",
            collected_at=1788420010,
        )
        self.assertFalse(result["semantic_review_ready"])
        self.assertIn(
            "exact_source_provenance_not_verified",
            result["blockers"],
        )

    def test_missing_required_semantic_field_blocks_review(self):
        payload = response()
        del payload["route"]["custodyDependency"]
        result = capture_warp_machine_contract(
            source_url=CANDIDATE_URL,
            method="GET",
            status_code=200,
            content_type="application/json",
            response_text=json.dumps(payload),
            proofs=[proof()],
            field_map=field_map(),
            timestamp_unit="seconds",
            collected_at=1788420010,
        )
        self.assertFalse(result["semantic_review_ready"])
        self.assertFalse(result["field_presence"]["custody_dependency"])
        self.assertIn(
            "required_semantic_fields_missing",
            result["blockers"],
        )

    def test_non_get_capture_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "GET/read-only"):
            capture_warp_machine_contract(
                source_url=CANDIDATE_URL,
                method="POST",
                status_code=200,
                content_type="application/json",
                response_text=json.dumps(response()),
                proofs=[proof()],
                field_map=field_map(),
                timestamp_unit="seconds",
                collected_at=1788420010,
            )

    def test_credential_like_response_keys_are_rejected(self):
        payload = response()
        payload["access_token"] = "do-not-store"
        with self.assertRaisesRegex(ValueError, "credential-like"):
            capture_warp_machine_contract(
                source_url=CANDIDATE_URL,
                method="GET",
                status_code=200,
                content_type="application/json",
                response_text=json.dumps(payload),
                proofs=[proof()],
                field_map=field_map(),
                timestamp_unit="seconds",
                collected_at=1788420010,
            )

    def test_capture_id_and_response_hash_are_deterministic(self):
        kwargs = dict(
            source_url=CANDIDATE_URL,
            method="GET",
            status_code=200,
            content_type="application/json",
            response_text=json.dumps(response(), sort_keys=True),
            proofs=[proof()],
            field_map=field_map(),
            timestamp_unit="seconds",
            collected_at=1788420010,
        )
        first = capture_warp_machine_contract(**kwargs)
        second = capture_warp_machine_contract(**kwargs)
        self.assertEqual(first["capture_id"], second["capture_id"])
        self.assertEqual(first["response_sha256"], second["response_sha256"])

    def test_unknown_timestamp_unit_blocks_semantic_review(self):
        result = capture_warp_machine_contract(
            source_url=CANDIDATE_URL,
            method="GET",
            status_code=200,
            content_type="application/json",
            response_text=json.dumps(response()),
            proofs=[proof()],
            field_map=field_map(),
            timestamp_unit="provider_magic_time",
            collected_at=1788420010,
        )
        self.assertFalse(result["semantic_review_ready"])
        self.assertIn("timestamp_unit_not_declared", result["blockers"])


if __name__ == "__main__":
    unittest.main()
