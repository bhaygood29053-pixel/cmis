from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from liquidity_scout.services.cmis_wallet_relationship_intelligence import (
    CONTRACT_VERSION,
    SERVICE,
    WalletRelationshipIntelligenceContractError,
    build_wallet_relationship_intelligence_response,
    validate_wallet_relationship_materialization,
)


def _cid(prefix, material):
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return prefix + "_" + hashlib.sha256(encoded).hexdigest()


def _materialization():
    observation = {
        "schema_version": 1,
        "schema": "cmis_wallet_activity_observation.v1",
        "chain": "x1",
        "wallet": "wallet-a",
        "activity_type": "TRANSFER_OUT",
        "transaction_signature": "sig-1",
        "observed_at": "2026-09-09T18:00:00Z",
        "source": "X1 RPC",
        "verification_method": "x1_rpc_jsonparsed_spl_transfer_v1",
        "evidence_scope": "exact_finalized_x1_transaction",
        "asset_id": "mint-1",
        "block_slot": 123,
        "asset_amount": "1000",
        "asset_unit": "raw-token-units",
        "quote_value": None,
        "quote_unit": None,
        "counterparty": "wallet-b",
        "deployer_id": None,
        "token_account": "source-token-account",
        "balance_before": None,
        "balance_after": None,
        "verification": {
            "wallet_identity_verified": True,
            "asset_identity_verified": True,
            "transaction_identity_verified": True,
            "amount_verified": True,
            "transfer_direction_verified": True,
            "trade_direction_verified": False,
            "lp_action_verified": False,
            "deployer_identity_verified": False,
            "token_account_ownership_verified": True,
            "quote_value_verified": False,
            "counterparty_verified": True,
        },
        "limitations": [
            "behavior_intent_and_risk_not_inferred",
            "exact_transaction_scope_only",
            "fungible_spl_token_program_only",
            "native_xnt_not_supported",
            "ownership_not_inferred",
            "single_unambiguous_matching_transfer_required",
            "token_2022_not_supported",
        ],
        "behavioral_interpretation_added": False,
        "ownership_interpretation_added": False,
        "intent_interpretation_added": False,
        "risk_interpretation": None,
        "execution_authorized": False,
    }
    obs_material = deepcopy(observation)
    observation["observation_id"] = _cid("wa", obs_material)

    relationship = {
        "schema_version": 1,
        "schema": "cmis_wallet_relationship_evidence.v1",
        "relationship_kind": "observed_direct_interaction",
        "interaction_type": "verified_token_transfer",
        "chain": "x1",
        "asset_id": "mint-1",
        "sender": "wallet-a",
        "recipient": "wallet-b",
        "transaction_signature": "sig-1",
        "observed_at": "2026-09-09T18:00:00Z",
        "block_slot": 123,
        "asset_amount": "1000",
        "asset_unit": "raw-token-units",
        "source": "X1 RPC",
        "verification_method": "x1_rpc_jsonparsed_spl_transfer_v1",
        "evidence_scope": "exact_finalized_x1_transaction",
        "evidence": {
            "wallet_activity_observation_id": observation["observation_id"],
            "wallet_activity_revalidated": True,
            "wallet_identity_verified": True,
            "counterparty_verified": True,
            "asset_identity_verified": True,
            "transaction_identity_verified": True,
            "transfer_direction_verified": True,
            "evidence_receipt_binding_available": False,
            "evidence_receipt_ids": [],
            "proof_score_binding_available": False,
            "proof_score_records": [],
        },
        "limitations": [
            "behavior_intent_and_risk_not_inferred",
            "beneficial_ownership_not_inferred",
            "complete_relationship_graph_not_proven",
            "complete_wallet_history_not_proven",
            "exact_transaction_scope_only",
            "fungible_spl_token_program_only",
            "missing_amounts_are_not_zero_filled",
            "native_xnt_not_supported",
            "observed_direct_interaction_only",
            "ownership_not_inferred",
            "single_unambiguous_matching_transfer_required",
            "token_2022_not_supported",
            "wallet_activity_source_does_not_embed_evidence_receipt_or_proof_score",
        ],
        "ownership_inference_added": False,
        "beneficial_ownership_inference_added": False,
        "behavioral_interpretation_added": False,
        "intent_interpretation_added": False,
        "risk_interpretation": None,
        "proof_strength_separate_from_risk": True,
        "complete_history_claimed": False,
        "complete_graph_coverage_claimed": False,
        "provider_assertion_promoted": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }
    relationship["relationship_evidence_id"] = _cid(
        "wr", deepcopy(relationship)
    )

    return {
        "contract_version": "x1_direct_wallet_transfer_materialization/v1",
        "chain": "x1",
        "transaction_signature": "sig-1",
        "asset_mint": "mint-1",
        "sender_wallet": "wallet-a",
        "recipient_wallet": "wallet-b",
        "instruction_type": "transferChecked",
        "source_token_account": "source-token-account",
        "destination_token_account": "destination-token-account",
        "amount_raw": "1000",
        "decimals": 6,
        "observed_at": "2026-09-09T18:00:00Z",
        "block_slot": 123,
        "wallet_activity_observation": observation,
        "relationship_evidence": relationship,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "ownership_inference_added": False,
        "beneficial_ownership_inference_added": False,
        "behavioral_interpretation_added": False,
        "intent_interpretation_added": False,
        "risk_interpretation": None,
        "execution_authorized": False,
    }


def test_validates_and_projects_one_direct_interaction():
    material = _materialization()
    assert validate_wallet_relationship_materialization(material) == material

    response = build_wallet_relationship_intelligence_response(material)
    assert response["service"] == SERVICE
    assert response["chain"] == "x1"
    assert response["status"] == "ok"
    assert response["data"]["contract_version"] == CONTRACT_VERSION
    assert response["data"]["relationship_kind"] == "observed_direct_interaction"
    assert response["data"]["interaction_type"] == "verified_token_transfer"
    assert response["data"]["sender_wallet"] == "wallet-a"
    assert response["data"]["recipient_wallet"] == "wallet-b"
    assert response["data"]["amount_raw"] == "1000"
    assert response["data"]["ownership_inference_added"] is False
    assert response["data"]["beneficial_ownership_inference_added"] is False
    assert response["data"]["behavioral_interpretation_added"] is False
    assert response["data"]["intent_interpretation_added"] is False
    assert response["data"]["risk_interpretation"] is None
    assert response["data"]["complete_history_claimed"] is False
    assert response["data"]["complete_graph_coverage_claimed"] is False
    assert response["data"]["execution_authorized"] is False
    assert response["risk"] is None
    assert response["freshness"]["state"] == "NOT_APPLICABLE"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("chain",), "solana"),
        (("sender_wallet",), "wallet-wrong"),
        (("amount_raw",), "01000"),
        (("public_service_promoted",), True),
        (("execution_authorized",), True),
        (("risk_interpretation",), "LOW"),
        (("relationship_evidence", "ownership_inference_added"), True),
        (("relationship_evidence", "risk_interpretation"), "LOW"),
        (
            ("relationship_evidence", "evidence", "proof_score_binding_available"),
            True,
        ),
    ],
)
def test_tampered_or_promoted_material_fails_closed(path, value):
    material = _materialization()
    cursor = material
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value

    with pytest.raises(WalletRelationshipIntelligenceContractError):
        validate_wallet_relationship_materialization(material)


def test_relationship_content_id_tamper_fails_closed():
    material = _materialization()
    material["relationship_evidence"]["transaction_signature"] = "sig-other"
    with pytest.raises(
        WalletRelationshipIntelligenceContractError,
        match="does not bind canonical relationship material",
    ):
        validate_wallet_relationship_materialization(material)


def test_no_runtime_or_scout_promotion_is_implied_by_contract_module():
    response = build_wallet_relationship_intelligence_response(_materialization())
    assert response["data"]["execution_authorized"] is False
    assert "public_service_promoted" not in response["data"]
    assert "scout_reliance_promoted" not in response["data"]
