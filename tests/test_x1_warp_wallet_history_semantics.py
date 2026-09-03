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
    CANONICAL_SETTLEMENT_SOURCE_CONTRACT,
    CONTRACT,
    EXACT_RESPONSE_CANONICAL_SHA256,
    SANITIZED_FIXTURE_CANONICAL_SHA256,
    WarpWalletHistorySemanticError,
    analyze_warp_wallet_history_response,
    canonical_sha256,
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
CONFIG_FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "warp_bridge_config_20260903.json"
HISTORY_FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "warp_wallet_history_20260903_sanitized.json"
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


class WarpWalletHistorySemanticsTests(unittest.TestCase):
    def test_sanitized_fixture_hash_is_pinned_without_wallet_identifier(self):
        fixture = json.loads(HISTORY_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(canonical_sha256(fixture), SANITIZED_FIXTURE_CANONICAL_SHA256)
        self.assertEqual(
            EXACT_RESPONSE_CANONICAL_SHA256,
            "e309a68509b631002c46526e772ac0b40d2381a21ff2bef46c7c56cbaa4dcca5",
        )
        self.assertNotIn(DUMMY_WALLET, json.dumps(fixture))

    def test_response_is_contextualized_against_exact_usdc_route(self):
        result = analyze_warp_wallet_history_response(
            response=history_response(),
            route_qualification=qualification(),
            config_response=config_response(),
        )
        self.assertEqual(result["contract"], CONTRACT)
        self.assertEqual(result["route_context_id"], ROUTE_ID)
        self.assertEqual(result["source"]["asset_id"], USDC)
        self.assertEqual(result["destination"]["asset_id"], USDC_X)
        self.assertEqual(result["source_token_symbol"], "USDC")
        self.assertEqual(result["destination_token_symbol"], "USDC.X")
        self.assertEqual(result["route_decimals_context"], 6)
        self.assertEqual(result["provider_storage_label"], "sqlite")
        self.assertEqual(result["response_count"], 2)
        self.assertTrue(result["response_count_matches_list"])
        self.assertTrue(result["corroboration_only"])
        self.assertEqual(
            result["canonical_settlement_source_contract"],
            CANONICAL_SETTLEMENT_SOURCE_CONTRACT,
        )
        self.assertFalse(result["wallet_identifier_retained"])
        self.assertFalse(result["route_wide_coverage_verified"])
        self.assertFalse(result["pagination_coverage_verified"])
        self.assertFalse(result["flow_event_normalization_authorized"])
        self.assertFalse(result["execution_authorized"])

    def test_executed_row_is_observed_but_not_promoted_to_settlement(self):
        result = analyze_warp_wallet_history_response(
            response=history_response(),
            route_qualification=qualification(),
            config_response=config_response(),
        )
        executed = result["transactions"][0]
        self.assertEqual(executed["provider_status"], "executed")
        self.assertEqual(executed["provider_amount_integer"], 24007049)
        self.assertEqual(executed["route_decimals_context"], 6)
        self.assertFalse(executed["provider_amount_unit_semantics_verified"])
        self.assertEqual(executed["provider_timestamp_ms"], 1785414802165)
        self.assertEqual(executed["provider_timestamp"], 1785414802.165)
        self.assertFalse(executed["provider_timestamp_is_settlement_time"])
        self.assertTrue(executed["source_reference_consistent"])
        self.assertTrue(executed["guardian_quorum_reached"])
        self.assertTrue(executed["destination_reference_complete"])
        self.assertFalse(executed["provider_status_is_settlement_authority"])
        self.assertFalse(executed["row_exact_mint_identity_verified"])
        self.assertFalse(executed["flow_event_normalization_authorized"])

    def test_signing_row_remains_non_settlement_corroboration(self):
        result = analyze_warp_wallet_history_response(
            response=history_response(),
            route_qualification=qualification(),
            config_response=config_response(),
        )
        signing = result["transactions"][1]
        self.assertEqual(signing["provider_status"], "signing")
        self.assertFalse(signing["source_reference_consistent"])
        self.assertFalse(signing["guardian_quorum_reached"])
        self.assertFalse(signing["destination_reference_complete"])
        self.assertFalse(signing["flow_event_normalization_authorized"])

    def test_wallet_identity_is_not_retained(self):
        result = analyze_warp_wallet_history_response(
            response=history_response(),
            route_qualification=qualification(),
            config_response=config_response(),
        )
        self.assertNotIn(DUMMY_WALLET, json.dumps(result, sort_keys=True))

    def test_wrong_token_label_cannot_be_contextualized_to_route(self):
        response = history_response()
        response["transactions"][0]["token"] = "wSOL"
        with self.assertRaisesRegex(
            WarpWalletHistorySemanticError,
            "token label does not match",
        ):
            analyze_warp_wallet_history_response(
                response=response,
                route_qualification=qualification(),
                config_response=config_response(),
            )


if __name__ == "__main__":
    unittest.main()
