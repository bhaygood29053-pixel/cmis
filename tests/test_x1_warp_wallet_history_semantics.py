import copy
import json
import pathlib
import unittest

from liquidity_scout.providers.x1.bridge_source_provenance import (
    BridgeSourceProof,
    evaluate_bridge_source_provenance,
)
from liquidity_scout.providers.x1.warp_config_semantics import (
    WARP_CONFIG_SOURCE_URL,
    build_warp_config_route_observation,
)
from liquidity_scout.providers.x1.warp_wallet_history_semantics import (
    CONTRACT,
    DESTINATION_SETTLEMENT_CONTRACT,
    EXACT_RESPONSE_CANONICAL_SHA256,
    SANITIZED_FIXTURE_CANONICAL_SHA256,
    WarpWalletHistorySemanticError,
    analyze_warp_wallet_history_response,
    build_verified_settled_flow_event,
    canonical_sha256,
)
from liquidity_scout.services.cmis_bridge_flow_intelligence import (
    build_bridge_flow_intelligence,
)
from liquidity_scout.services.cmis_bridge_route_evidence import (
    qualify_warp_bridge_route,
)
from liquidity_scout.services.cmis_cross_chain_provenance import (
    build_cross_chain_asset_provenance,
)


USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_X = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
ROUTE_ID = "warp-solana-x1-usdc"
CONFIG_FIXTURE = (
    pathlib.Path(__file__).parent / "fixtures" / "warp_bridge_config_20260903.json"
)
HISTORY_FIXTURE = (
    pathlib.Path(__file__).parent
    / "fixtures"
    / "warp_wallet_history_20260903_sanitized.json"
)
DUMMY_WALLET = "11111111111111111111111111111111"


def endpoint(chain, mint):
    return {"chain": chain, "asset_id": mint, "asset_id_kind": "mint"}


def config_response():
    return json.loads(CONFIG_FIXTURE.read_text(encoding="utf-8"))


def history_response():
    data = json.loads(HISTORY_FIXTURE.read_text(encoding="utf-8"))
    data["wallet"] = DUMMY_WALLET
    for tx in data["transactions"]:
        tx["sender"] = DUMMY_WALLET
        tx["recipient"] = DUMMY_WALLET
    return data


def qualification():
    provenance = build_cross_chain_asset_provenance(
        canonical_asset_id="usdc",
        origin=endpoint("solana", USDC),
        current=endpoint("x1", USDC_X),
        hops=[
            {
                "source": endpoint("solana", USDC),
                "destination": endpoint("x1", USDC_X),
                "bridge": "Warp Bridge",
                "representation_type": "bridge_representation",
                "custody_model": "unknown",
                "bridge_route_id": ROUTE_ID,
            }
        ],
    )
    observation = build_warp_config_route_observation(
        config_response=config_response(),
        route_id=ROUTE_ID,
        source=endpoint("solana", USDC),
        destination=endpoint("x1", USDC_X),
    )
    source = evaluate_bridge_source_provenance(
        url=WARP_CONFIG_SOURCE_URL,
        proofs=[
            BridgeSourceProof(
                proof_type="official_app_network_observation",
                reference="accepted official config response",
                exact_url=WARP_CONFIG_SOURCE_URL,
            )
        ],
    )
    return qualify_warp_bridge_route(
        provenance=provenance,
        hop_index=0,
        source_provenance=source,
        observation=observation,
        evaluated_at=1788436232.329,
    )


def semantics():
    return analyze_warp_wallet_history_response(
        response=history_response(),
        route_qualification=qualification(),
        config_response=config_response(),
    )


def rpc_evidence(**overrides):
    base = {
        "contract": DESTINATION_SETTLEMENT_CONTRACT,
        "transaction_signature": (
            "4PMmzc8Hy1qq7i5AQ2FGRgEi32ZS1DcZS9y7b86xfqaX7wNiFC2t5FWBddj8SsE5cMGW5zfkRRaTFmMgy5ChiuqG"
        ),
        "slot": 68029675,
        "transaction_found": True,
        "transaction_succeeded": True,
        "finalized": True,
        "block_time_verified": True,
        "block_time": 1785414808,
    }
    base.update(overrides)
    return base


class WarpWalletHistorySemanticsTests(unittest.TestCase):
    def test_sanitized_fixture_hash_is_pinned_without_wallet_identifier(self):
        fixture = json.loads(HISTORY_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(
            canonical_sha256(fixture),
            SANITIZED_FIXTURE_CANONICAL_SHA256,
        )
        self.assertEqual(
            EXACT_RESPONSE_CANONICAL_SHA256,
            "e309a68509b631002c46526e772ac0b40d2381a21ff2bef46c7c56cbaa4dcca5",
        )
        self.assertNotIn(DUMMY_WALLET, json.dumps(fixture))

    def test_exact_usdc_route_semantics_are_bounded(self):
        result = semantics()
        self.assertEqual(result["contract"], CONTRACT)
        self.assertEqual(result["route_id"], ROUTE_ID)
        self.assertEqual(result["source"]["asset_id"], USDC)
        self.assertEqual(result["destination"]["asset_id"], USDC_X)
        self.assertEqual(result["source_token_symbol"], "USDC")
        self.assertEqual(result["destination_token_symbol"], "USDC.X")
        self.assertEqual(result["decimals"], 6)
        self.assertEqual(result["provider_storage_label"], "sqlite")
        self.assertEqual(result["response_count"], 2)
        self.assertTrue(result["response_count_matches_list"])
        self.assertFalse(result["wallet_identifier_retained"])
        self.assertFalse(result["route_wide_coverage_verified"])
        self.assertFalse(result["pagination_coverage_verified"])
        self.assertFalse(result["live_flow_normalization_authorized"])
        self.assertFalse(result["execution_authorized"])

    def test_executed_record_is_destination_settlement_candidate_not_flow_event(self):
        executed = semantics()["transactions"][0]
        self.assertEqual(executed["provider_status"], "executed")
        self.assertEqual(executed["amount_raw"], 24007049)
        self.assertEqual(executed["decimals"], 6)
        self.assertEqual(executed["provider_timestamp_ms"], 1785414802165)
        self.assertEqual(executed["provider_timestamp"], 1785414802.165)
        self.assertEqual(
            executed["provider_timestamp_role"],
            "transaction_timestamp_not_destination_settlement_time",
        )
        self.assertTrue(executed["source_reference_consistent"])
        self.assertTrue(executed["guardian_quorum_reached"])
        self.assertTrue(executed["tx_signature_match"])
        self.assertTrue(executed["slot_match"])
        self.assertTrue(executed["provider_execution_evidence_present"])
        self.assertFalse(executed["settlement_verified"])
        self.assertFalse(executed["pairing_verified"])
        self.assertIsNone(executed["settled_at"])
        self.assertFalse(executed["flow_event_eligible"])

    def test_signing_record_remains_unsettled_and_excluded(self):
        signing = semantics()["transactions"][1]
        self.assertEqual(signing["provider_status"], "signing")
        self.assertFalse(signing["source_reference_consistent"])
        self.assertFalse(signing["guardian_quorum_reached"])
        self.assertFalse(signing["provider_execution_evidence_present"])
        self.assertFalse(signing["settlement_verified"])
        self.assertFalse(signing["pairing_verified"])
        self.assertFalse(signing["flow_event_eligible"])

    def test_wallet_identity_is_not_retained_in_semantic_output(self):
        result = semantics()
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(DUMMY_WALLET, serialized)

    def test_wrong_token_label_cannot_bind_to_exact_route(self):
        response = history_response()
        response["transactions"][0]["token"] = "wSOL"
        with self.assertRaisesRegex(
            WarpWalletHistorySemanticError,
            "token label does not match exact source mint",
        ):
            analyze_warp_wallet_history_response(
                response=response,
                route_qualification=qualification(),
                config_response=config_response(),
            )

    def test_only_verified_destination_rpc_can_create_settled_flow_event(self):
        executed = semantics()["transactions"][0]
        event = build_verified_settled_flow_event(
            transaction_semantics=executed,
            destination_rpc_evidence=rpc_evidence(),
        )
        self.assertEqual(event["route_id"], ROUTE_ID)
        self.assertEqual(event["direction"], "inflow")
        self.assertEqual(event["amount_raw"], 24007049)
        self.assertEqual(event["decimals"], 6)
        self.assertEqual(event["settled_at"], 1785414808.0)
        self.assertEqual(event["lifecycle_state"], "settled")
        self.assertTrue(event["settlement_verified"])
        self.assertTrue(event["pairing_verified"])
        self.assertEqual(event["settlement_source"], "canonical_x1_rpc")
        self.assertFalse(event["execution_authorized"])

    def test_signing_record_cannot_be_promoted_by_rpc_evidence(self):
        signing = semantics()["transactions"][1]
        with self.assertRaisesRegex(
            WarpWalletHistorySemanticError,
            "only provider executed",
        ):
            build_verified_settled_flow_event(
                transaction_semantics=signing,
                destination_rpc_evidence=rpc_evidence(),
            )

    def test_destination_signature_and_slot_must_match(self):
        executed = semantics()["transactions"][0]
        with self.assertRaisesRegex(
            WarpWalletHistorySemanticError,
            "signature does not match",
        ):
            build_verified_settled_flow_event(
                transaction_semantics=executed,
                destination_rpc_evidence=rpc_evidence(
                    transaction_signature="wrong"
                ),
            )
        with self.assertRaisesRegex(
            WarpWalletHistorySemanticError,
            "slot does not match",
        ):
            build_verified_settled_flow_event(
                transaction_semantics=executed,
                destination_rpc_evidence=rpc_evidence(slot=1),
            )

    def test_flow_engine_accepts_verified_event_but_keeps_wallet_history_coverage_unknown(self):
        executed = semantics()["transactions"][0]
        event = build_verified_settled_flow_event(
            transaction_semantics=executed,
            destination_rpc_evidence=rpc_evidence(),
        )
        result = build_bridge_flow_intelligence(
            route_qualification=qualification(),
            events=[event],
            as_of=1788440000,
            coverage_start=1783000000,
            coverage_end=1788440000,
            coverage_verified=False,
        )
        self.assertEqual(
            result["event_accounting"]["accepted_settled_event_count"],
            1,
        )
        self.assertFalse(result["coverage"]["coverage_verified"])
        self.assertIsNone(result["windows"]["24h"]["current"]["inflow_raw"])
        self.assertIsNone(result["windows"]["30d"]["prior"]["net_flow_raw"])
        self.assertEqual(result["status"], "partial")


if __name__ == "__main__":
    unittest.main()
