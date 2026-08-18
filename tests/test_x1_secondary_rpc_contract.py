import unittest

from liquidity_scout.providers.x1.secondary_rpc_contract import (
    classify_secondary_rpc_response,
)


class SecondaryRpcContractTests(unittest.TestCase):
    def test_health_success_is_structural_only(self):
        obs = classify_secondary_rpc_response(
            source="secondary-x1-rpc",
            method="getHealth",
            payload={"jsonrpc": "2.0", "id": 1, "result": "ok"},
        )
        self.assertTrue(obs.transport_ok)
        self.assertTrue(obs.result_shape_verified)
        self.assertFalse(obs.archival_completeness_verified)
        self.assertFalse(obs.retention_verified)
        self.assertFalse(obs.finality_semantics_verified)
        self.assertFalse(obs.cmis_promotable)

    def test_slot_preserves_observed_slot(self):
        obs = classify_secondary_rpc_response(
            source="secondary-x1-rpc",
            method="getSlot",
            payload={"jsonrpc": "2.0", "id": 2, "result": 12345},
        )
        self.assertEqual(obs.observed_slot, 12345)
        self.assertTrue(obs.result_shape_verified)

    def test_block_object_proves_only_requested_block_shape(self):
        obs = classify_secondary_rpc_response(
            source="secondary-x1-rpc",
            method="getBlock",
            payload={"jsonrpc": "2.0", "id": 3, "result": {"parentSlot": 99, "transactions": []}},
        )
        self.assertTrue(obs.result_shape_verified)
        self.assertEqual(obs.observed_slot, 100)
        self.assertFalse(obs.archival_completeness_verified)

    def test_null_block_is_not_retrievability_proof(self):
        obs = classify_secondary_rpc_response(
            source="secondary-x1-rpc",
            method="getBlock",
            payload={"jsonrpc": "2.0", "id": 3, "result": None},
        )
        self.assertTrue(obs.transport_ok)
        self.assertFalse(obs.result_shape_verified)

    def test_rpc_error_is_preserved_without_promotion(self):
        obs = classify_secondary_rpc_response(
            source="secondary-x1-rpc",
            method="getBlock",
            payload={"jsonrpc": "2.0", "id": 4, "error": {"code": -32004, "message": "unavailable"}},
        )
        self.assertFalse(obs.transport_ok)
        self.assertEqual(obs.error_code, -32004)
        self.assertFalse(obs.cmis_promotable)

    def test_bad_envelope_fails_closed(self):
        obs = classify_secondary_rpc_response(
            source="secondary-x1-rpc",
            method="getSlot",
            payload={"result": 1},
        )
        self.assertFalse(obs.jsonrpc_envelope_verified)
        self.assertFalse(obs.transport_ok)

    def test_rejects_unsupported_method(self):
        with self.assertRaises(ValueError):
            classify_secondary_rpc_response(
                source="secondary-x1-rpc",
                method="sendTransaction",
                payload={"jsonrpc": "2.0", "id": 1, "result": "x"},
            )

    def test_rejects_empty_source(self):
        with self.assertRaises(ValueError):
            classify_secondary_rpc_response(
                source=" ", method="getHealth", payload={"jsonrpc": "2.0", "id": 1, "result": "ok"}
            )


if __name__ == "__main__":
    unittest.main()
