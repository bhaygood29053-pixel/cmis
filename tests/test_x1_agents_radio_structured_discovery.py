from __future__ import annotations

import unittest

from liquidity_scout.providers.web_discovery import (
    DISCOVERED,
    SourceBoundaryError,
    X1_AGENTS_RADIO_STRUCTURED_CONTRACT,
    X1AgentsRadioStructuredDiscoveryError,
    normalize_x1_agents_radio_payload,
    parse_x1_agents_radio_url,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


REGISTRY_PROGRAM = "4Ai4Ps8YsrLfshU9xvkf9pobiVhewELdbXEZA7zaZ8E3"
FAUCET_PROGRAM = "9zkypzFPQ2s3D5UqbYuixt3iXo5ig3ZNWLK1TrbNf5eR"
IDENTITY_PROGRAM = "F3ydfNgdM89BK5hDh7amVmt8AAGQSYCX1afb3EWZKGh8"

BOOTSTRAP = "https://x1radio.vercel.app/api/bootstrap"
CATALOG = "https://x1agentsradio.xyz/api/catalog"
DEPLOYMENTS = "https://x1agentsradio.xyz/api/deployments"
HEALTH = "https://x1agentsradio.xyz/api/health"


class X1AgentsRadioStructuredDiscoveryTests(unittest.TestCase):
    def test_endpoint_classification_preserves_internal_boundary(self):
        result = parse_x1_agents_radio_url(BOOTSTRAP)

        self.assertEqual(
            result["contract"],
            "x1_agents_radio_structured_discovery/v1",
        )
        self.assertEqual(
            result["contract"],
            X1_AGENTS_RADIO_STRUCTURED_CONTRACT,
        )
        self.assertEqual(result["endpoint_type"], "bootstrap")
        self.assertEqual(result["transport_method"], "GET")
        self.assertTrue(result["truth_state"]["x1_agents_radio_route_verified"])
        self.assertFalse(result["truth_state"]["program_identity_verified"])
        self.assertFalse(result["truth_state"]["program_semantics_verified"])
        self.assertFalse(result["truth_state"]["cmis_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_subscriber_endpoint_is_rejected(self):
        with self.assertRaises(SourceBoundaryError):
            parse_x1_agents_radio_url(
                "https://x1agentsradio.xyz/api/programs"
            )

    def test_catalog_flexible_nested_envelope_normalizes_candidate_only(self):
        payload = {
            "data": {
                "programs": [
                    {
                        "id": "provider-row-1",
                        "program": {
                            "programId": REGISTRY_PROGRAM,
                            "name": "Agent Registry",
                            "category": "agent_infrastructure",
                            "instructions": [
                                {"name": "subscribe"},
                                {"name": "renew"},
                            ],
                            "provider_extra": "unverified",
                        },
                        "txCount": 1234,
                        "lastActiveSlot": 987654,
                        "mysteryScore": 0.91,
                    }
                ]
            }
        }

        result = normalize_x1_agents_radio_payload(CATALOG, payload)
        self.assertEqual(result["endpoint_type"], "catalog")
        self.assertEqual(result["candidate_record_count"], 1)

        record = result["records"][0]
        self.assertEqual(record["record_type"], "program_candidate")
        self.assertEqual(record["program_id"], REGISTRY_PROGRAM)
        self.assertEqual(record["program_id_source_field"], "program.programId")
        self.assertEqual(record["program_id_decoded_bytes"], 32)
        self.assertTrue(record["program_id_syntax_valid"])
        self.assertEqual(record["provider_name"], "Agent Registry")
        self.assertEqual(record["provider_category"], "agent_infrastructure")
        self.assertEqual(record["provider_instructions"], ["subscribe", "renew"])
        self.assertEqual(record["provider_activity"]["transaction_count"], 1234)
        self.assertEqual(record["provider_activity"]["last_active_slot"], 987654)
        self.assertIn("mysteryScore", record["unmapped_provider_fields"])
        self.assertIn("id", record["unmapped_provider_fields"])
        self.assertIn(
            "provider_extra",
            record["unmapped_nested_program_fields"],
        )
        self.assertTrue(
            any(
                handoff["target"] == "X1 RPC getAccountInfo"
                for handoff in record["verification_handoff"]
            )
        )
        self.assertEqual(
            record["truth_state"]["discovery_state"],
            DISCOVERED,
        )
        self.assertFalse(record["truth_state"]["activity_verified"])
        self.assertFalse(record["truth_state"]["cmis_verified"])
        self.assertFalse(record["execution_authorized"])

    def test_mapping_key_program_id_is_supported_without_schema_guess(self):
        payload = {
            "catalog": {
                FAUCET_PROGRAM: {
                    "name": "Agent Faucet",
                    "category": "faucet",
                    "methods": ["drip"],
                }
            }
        }

        result = normalize_x1_agents_radio_payload(CATALOG, payload)
        self.assertEqual(result["candidate_record_count"], 1)
        record = result["records"][0]
        self.assertEqual(record["program_id"], FAUCET_PROGRAM)
        self.assertEqual(
            record["program_id_source_field"],
            "__container_key_program_id",
        )
        self.assertTrue(record["program_id_syntax_valid"])
        self.assertEqual(record["provider_instructions"], ["drip"])

    def test_invalid_explicit_program_id_remains_visible_but_unverified(self):
        payload = {
            "programs": [
                {
                    "program_id": "not-a-valid-x1-program-id",
                    "name": "Bad Candidate",
                    "category": "unknown",
                }
            ]
        }

        result = normalize_x1_agents_radio_payload(BOOTSTRAP, payload)
        self.assertEqual(result["candidate_record_count"], 1)
        record = result["records"][0]
        self.assertEqual(record["program_id"], "not-a-valid-x1-program-id")
        self.assertFalse(record["program_id_syntax_valid"])
        self.assertEqual(record["verification_handoff"], [])
        self.assertFalse(record["truth_state"]["program_identity_verified"])

    def test_deployment_candidate_emits_transaction_verification_handoff(self):
        signature = "5" * 88
        payload = {
            "deployments": [
                {
                    "programId": IDENTITY_PROGRAM,
                    "name": "Identity Program",
                    "eventType": "upgrade",
                    "upgradeSlot": 123456,
                    "txSignature": signature,
                    "confidence": "provider_reported",
                }
            ]
        }

        result = normalize_x1_agents_radio_payload(DEPLOYMENTS, payload)
        record = result["records"][0]
        self.assertEqual(record["record_type"], "deployment_candidate")
        self.assertEqual(record["provider_deployment"]["event_type"], "upgrade")
        self.assertEqual(record["provider_deployment"]["upgrade_slot"], 123456)
        self.assertEqual(
            record["provider_deployment"]["transaction_signature"],
            signature,
        )
        self.assertIn("confidence", record["unmapped_provider_fields"])
        self.assertTrue(
            any(
                handoff["target"] == "X1 RPC getTransaction"
                for handoff in record["verification_handoff"]
            )
        )
        self.assertFalse(record["truth_state"]["deployment_verified"])
        self.assertFalse(record["truth_state"]["upgrade_verified"])

    def test_health_normalization_never_becomes_chain_truth(self):
        payload = {
            "status": "ok",
            "healthy": True,
            "latestSlot": 999,
            "programCount": 536,
            "version": "radio-1",
            "queueDepth": 4,
        }

        result = normalize_x1_agents_radio_payload(HEALTH, payload)
        self.assertEqual(result["candidate_record_count"], 1)
        record = result["records"][0]
        self.assertEqual(record["record_type"], "health_candidate")
        self.assertEqual(record["provider_health"]["status"], "ok")
        self.assertTrue(record["provider_health"]["healthy"])
        self.assertEqual(record["provider_health"]["latest_slot"], 999)
        self.assertEqual(record["provider_health"]["indexed_program_count"], 536)
        self.assertIn("queueDepth", record["unmapped_provider_fields"])
        self.assertFalse(record["truth_state"]["freshness_verified"])
        self.assertFalse(record["truth_state"]["cmis_verified"])
        self.assertFalse(record["execution_authorized"])

    def test_record_limit_is_enforced_and_truncation_is_visible(self):
        payload = [
            {"program_id": REGISTRY_PROGRAM, "name": "One"},
            {"program_id": FAUCET_PROGRAM, "name": "Two"},
        ]

        result = normalize_x1_agents_radio_payload(
            CATALOG,
            payload,
            max_records=1,
        )

        self.assertEqual(result["candidate_record_count"], 1)
        self.assertEqual(result["record_limit"], 1)
        self.assertTrue(result["records_truncated"])

        with self.assertRaises(X1AgentsRadioStructuredDiscoveryError):
            normalize_x1_agents_radio_payload(CATALOG, payload, max_records=0)

        with self.assertRaises(X1AgentsRadioStructuredDiscoveryError):
            normalize_x1_agents_radio_payload(CATALOG, payload, max_records=101)

    def test_non_json_shape_fails_closed(self):
        with self.assertRaises(X1AgentsRadioStructuredDiscoveryError):
            normalize_x1_agents_radio_payload(CATALOG, "not-json-object")

        with self.assertRaises(X1AgentsRadioStructuredDiscoveryError):
            normalize_x1_agents_radio_payload(HEALTH, ["not", "an", "object"])

    def test_internal_service_wrapper_preserves_authority(self):
        payload = {
            "programs": [
                {
                    "program_id": REGISTRY_PROGRAM,
                    "name": "Agent Registry",
                }
            ]
        }
        service = CMISWebDiscoveryService()

        result = service.discover_x1_agents_radio_structured(
            CATALOG,
            payload=payload,
            max_records=10,
        )

        self.assertEqual(result["source_id"], "x1_agents_radio")
        self.assertEqual(
            result["structured_endpoint"]["endpoint_type"],
            "catalog",
        )
        self.assertEqual(
            result["structured_payload"]["candidate_record_count"],
            1,
        )
        self.assertTrue(result["read_only"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
