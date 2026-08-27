import unittest
from datetime import datetime, timezone

from liquidity_scout.providers.x1.self_hosted_readonly_node import (
    FINALIZED,
    REQUIRED_READ_ONLY_FLAGS,
    classify_block_pubsub_session,
    collect_self_hosted_rpc_evidence,
    compare_historical_rpc_sample,
    evaluate_block_pubsub_reconnect,
    evaluate_rpc_identity,
    evaluate_startup_configuration,
)


def tx(signature, slot=100, block_time=1700000000, err=None):
    return {
        "slot": slot,
        "blockTime": block_time,
        "transaction": {"signatures": [signature]},
        "meta": {"err": err},
    }


class SelfHostedReadonlyNodeContractTests(unittest.TestCase):
    def test_startup_configuration_requires_all_flags_and_provenance(self):
        command = "tachyon-validator " + " ".join(REQUIRED_READ_ONLY_FLAGS)
        evidence = evaluate_startup_configuration(
            command,
            provenance="operator-captured startup command",
        )
        self.assertTrue(evidence.startup_configuration_verified)
        self.assertFalse(evidence.running_process_configuration_verified)
        self.assertEqual(evidence.missing_required_flags, ())

    def test_startup_configuration_missing_flag_fails_closed(self):
        command = "tachyon-validator --full-rpc-api --enable-rpc-transaction-history"
        evidence = evaluate_startup_configuration(
            command,
            provenance="operator-captured startup command",
        )
        self.assertFalse(evidence.startup_configuration_verified)
        self.assertIn(
            "--rpc-pubsub-enable-block-subscription",
            evidence.missing_required_flags,
        )

    def test_startup_configuration_without_provenance_fails_closed(self):
        command = "tachyon-validator " + " ".join(REQUIRED_READ_ONLY_FLAGS)
        evidence = evaluate_startup_configuration(command, provenance=None)
        self.assertFalse(evidence.startup_configuration_verified)

    def test_rpc_identity_requires_genesis_match_and_version_shape(self):
        evidence = evaluate_rpc_identity(
            candidate_genesis_hash="GenesisA",
            canonical_genesis_hash="GenesisA",
            candidate_version={"solana-core": "2.1.0", "feature-set": 1},
        )
        self.assertTrue(evidence.network_identity_verified)
        self.assertTrue(evidence.version_shape_verified)
        self.assertTrue(evidence.endpoint_url_redacted)

    def test_rpc_identity_mismatch_fails_closed(self):
        evidence = evaluate_rpc_identity(
            candidate_genesis_hash="GenesisA",
            canonical_genesis_hash="GenesisB",
            candidate_version={"solana-core": "2.1.0"},
        )
        self.assertFalse(evidence.network_identity_verified)

    def test_historical_agreement_is_infrastructure_only(self):
        history = [
            {
                "signature": "SigA",
                "slot": 100,
                "err": None,
                "blockTime": 1700000000,
                "confirmationStatus": "finalized",
            }
        ]
        comparison = compare_historical_rpc_sample(
            candidate_history=history,
            candidate_transaction=tx("SigA"),
            candidate_block_time=1700000000,
            canonical_transaction=tx("SigA"),
            canonical_block_time=1700000000,
        )
        self.assertEqual(comparison.status, "AGREEMENT")
        self.assertTrue(comparison.same_fact_identity_verified)
        self.assertTrue(comparison.infrastructure_agreement_verified)
        self.assertFalse(comparison.market_source_independence_verified)
        self.assertFalse(comparison.archival_completeness_verified)
        self.assertFalse(comparison.retention_verified)

    def test_historical_conflict_is_preserved(self):
        history = [
            {
                "signature": "SigA",
                "slot": 100,
                "err": None,
                "blockTime": 1700000000,
                "confirmationStatus": "finalized",
            }
        ]
        comparison = compare_historical_rpc_sample(
            candidate_history=history,
            candidate_transaction=tx("SigA", slot=100),
            candidate_block_time=1700000000,
            canonical_transaction=tx("SigA", slot=101),
            canonical_block_time=1700000000,
        )
        self.assertEqual(comparison.status, "CONFLICT")
        self.assertIn("slot", comparison.conflicts)
        self.assertFalse(comparison.infrastructure_agreement_verified)

    def test_non_finalized_history_is_insufficient(self):
        history = [
            {
                "signature": "SigA",
                "slot": 100,
                "err": None,
                "blockTime": 1700000000,
                "confirmationStatus": "confirmed",
            }
        ]
        comparison = compare_historical_rpc_sample(
            candidate_history=history,
            candidate_transaction=tx("SigA"),
            candidate_block_time=1700000000,
            canonical_transaction=tx("SigA"),
            canonical_block_time=1700000000,
        )
        self.assertEqual(comparison.status, "INSUFFICIENT_EVIDENCE")
        self.assertFalse(comparison.same_fact_identity_verified)

    def test_pubsub_session_tracks_duplicates_without_calling_them_drops(self):
        messages = [
            {"jsonrpc": "2.0", "id": 7, "result": 44},
            {
                "jsonrpc": "2.0",
                "method": "blockNotification",
                "params": {
                    "subscription": 44,
                    "result": {"context": {"slot": 10}, "value": {}},
                },
            },
            {
                "jsonrpc": "2.0",
                "method": "blockNotification",
                "params": {
                    "subscription": 44,
                    "result": {"context": {"slot": 10}, "value": {}},
                },
            },
            {
                "jsonrpc": "2.0",
                "method": "blockNotification",
                "params": {
                    "subscription": 44,
                    "result": {"context": {"slot": 12}, "value": {}},
                },
            },
        ]
        session = classify_block_pubsub_session(
            messages,
            request_id=7,
            commitment=FINALIZED,
        )
        self.assertTrue(session.stream_contract_verified)
        self.assertEqual(session.duplicate_slots, (10,))
        self.assertFalse(session.out_of_order)

    def test_pubsub_out_of_order_fails_contract(self):
        messages = [
            {"jsonrpc": "2.0", "id": 7, "result": 44},
            {
                "jsonrpc": "2.0",
                "method": "blockNotification",
                "params": {
                    "subscription": 44,
                    "result": {"context": {"slot": 12}, "value": {}},
                },
            },
            {
                "jsonrpc": "2.0",
                "method": "blockNotification",
                "params": {
                    "subscription": 44,
                    "result": {"context": {"slot": 11}, "value": {}},
                },
            },
        ]
        session = classify_block_pubsub_session(messages, request_id=7)
        self.assertTrue(session.acknowledgement_verified)
        self.assertTrue(session.out_of_order)
        self.assertFalse(session.stream_contract_verified)

    def test_reconnect_uses_canonical_backfill_to_distinguish_skipped_slot(self):
        first = classify_block_pubsub_session(
            [
                {"jsonrpc": "2.0", "id": 1, "result": 11},
                {
                    "jsonrpc": "2.0",
                    "method": "blockNotification",
                    "params": {
                        "subscription": 11,
                        "result": {"context": {"slot": 100}, "value": {}},
                    },
                },
            ],
            request_id=1,
        )
        second = classify_block_pubsub_session(
            [
                {"jsonrpc": "2.0", "id": 2, "result": 12},
                {
                    "jsonrpc": "2.0",
                    "method": "blockNotification",
                    "params": {
                        "subscription": 12,
                        "result": {"context": {"slot": 102}, "value": {}},
                    },
                },
            ],
            request_id=2,
        )
        evaluation = evaluate_block_pubsub_reconnect(
            first,
            second,
            canonical_block_presence={101: False},
        )
        self.assertEqual(evaluation.status, "AGREEMENT")
        self.assertTrue(evaluation.canonical_backfill_complete)
        self.assertEqual(evaluation.missing_block_notifications, ())
        self.assertTrue(evaluation.dropped_event_detection_verified)
        self.assertFalse(evaluation.market_source_independence_verified)

    def test_reconnect_flags_missing_notification_when_canonical_block_exists(self):
        first = classify_block_pubsub_session(
            [
                {"jsonrpc": "2.0", "id": 1, "result": 11},
                {
                    "jsonrpc": "2.0",
                    "method": "blockNotification",
                    "params": {
                        "subscription": 11,
                        "result": {"context": {"slot": 100}, "value": {}},
                    },
                },
            ],
            request_id=1,
        )
        second = classify_block_pubsub_session(
            [
                {"jsonrpc": "2.0", "id": 2, "result": 12},
                {
                    "jsonrpc": "2.0",
                    "method": "blockNotification",
                    "params": {
                        "subscription": 12,
                        "result": {"context": {"slot": 102}, "value": {}},
                    },
                },
            ],
            request_id=2,
        )
        evaluation = evaluate_block_pubsub_reconnect(
            first,
            second,
            canonical_block_presence={101: True},
        )
        self.assertEqual(evaluation.status, "CONFLICT")
        self.assertEqual(evaluation.missing_block_notifications, (101,))
        self.assertTrue(evaluation.dropped_event_detection_verified)

    def test_reconnect_unknown_backfill_is_insufficient(self):
        first = classify_block_pubsub_session(
            [
                {"jsonrpc": "2.0", "id": 1, "result": 11},
                {
                    "jsonrpc": "2.0",
                    "method": "blockNotification",
                    "params": {
                        "subscription": 11,
                        "result": {"context": {"slot": 100}, "value": {}},
                    },
                },
            ],
            request_id=1,
        )
        second = classify_block_pubsub_session(
            [
                {"jsonrpc": "2.0", "id": 2, "result": 12},
                {
                    "jsonrpc": "2.0",
                    "method": "blockNotification",
                    "params": {
                        "subscription": 12,
                        "result": {"context": {"slot": 102}, "value": {}},
                    },
                },
            ],
            request_id=2,
        )
        evaluation = evaluate_block_pubsub_reconnect(
            first,
            second,
            canonical_block_presence={},
        )
        self.assertEqual(evaluation.status, "INSUFFICIENT_EVIDENCE")
        self.assertFalse(evaluation.canonical_backfill_complete)
        self.assertFalse(evaluation.dropped_event_detection_verified)

    def test_collect_rpc_evidence_is_sanitized_and_non_promotional(self):
        candidate = "http://private-node:8899"
        canonical = "https://rpc.mainnet.x1.xyz"
        calls = []

        def rpc_call(method, params, *, rpc_url):
            calls.append((rpc_url, method, params))
            if method == "getGenesisHash":
                return "GenesisA"
            if method == "getVersion":
                return {"solana-core": "2.1.0", "feature-set": 7}
            if method == "getHealth":
                return "ok"
            if method == "getSlot":
                return 1234
            if method == "getSignaturesForAddress":
                return [
                    {
                        "signature": "SigA",
                        "slot": 100,
                        "err": None,
                        "blockTime": 1700000000,
                        "confirmationStatus": "finalized",
                    }
                ]
            if method == "getTransaction":
                return tx("SigA")
            if method == "getBlockTime":
                return 1700000000
            raise AssertionError(method)

        result = collect_self_hosted_rpc_evidence(
            rpc_url=candidate,
            canonical_rpc_url=canonical,
            probe_address="AddressA",
            rpc_call=rpc_call,
            observed_at=datetime(2026, 8, 27, 20, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["identity"]["network_identity_verified"])
        self.assertTrue(result["rpc"]["rpc_contract_verified"])
        self.assertTrue(result["scope"]["history_sample_verified"])
        self.assertFalse(result["scope"]["archival_completeness_verified"])
        self.assertFalse(result["scope"]["retention_verified"])
        self.assertFalse(result["scope"]["streaming_verified"])
        self.assertFalse(result["scope"]["market_source_independence_verified"])
        self.assertFalse(result["scope"]["cmis_provider_promoted"])
        self.assertFalse(result["scope"]["execution_authorized"])
        self.assertNotIn(candidate, repr(result))
        self.assertTrue(any(call[1] == "getGenesisHash" for call in calls))

    def test_collect_requires_explicit_endpoints_and_probe_address(self):
        with self.assertRaises(ValueError):
            collect_self_hosted_rpc_evidence(
                rpc_url="",
                canonical_rpc_url="https://rpc.mainnet.x1.xyz",
                probe_address="AddressA",
            )
        with self.assertRaises(ValueError):
            collect_self_hosted_rpc_evidence(
                rpc_url="http://node",
                canonical_rpc_url="",
                probe_address="AddressA",
            )
        with self.assertRaises(ValueError):
            collect_self_hosted_rpc_evidence(
                rpc_url="http://node",
                canonical_rpc_url="https://rpc.mainnet.x1.xyz",
                probe_address="",
            )


if __name__ == "__main__":
    unittest.main()
