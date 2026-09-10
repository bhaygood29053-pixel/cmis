from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


SERVICE = "wallet_relationship_intelligence"
CONTRACT_VERSION = "wallet_relationship_intelligence/v1"
REQUEST_CONTRACT_VERSION = "wallet_relationship_intelligence_request/v1"
MATERIALIZATION_CONTRACT_VERSION = "x1_direct_wallet_transfer_materialization/v1"
CAPABILITIES_PATH = Path("liquidity_scout/cmis/capabilities.py")
PUBLIC_INIT_PATH = Path("liquidity_scout/cmis/__init__.py")


def _source() -> str:
    return CAPABILITIES_PATH.read_text(encoding="utf-8")


def _assignment(name: str):
    tree = ast.parse(_source())
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"assignment {name} not found")


def _helper():
    tree = ast.parse(_source())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_wallet_relationship_capability"
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "Any": Any,
        "WALLET_RELATIONSHIP_CONTRACT_VERSION": CONTRACT_VERSION,
        "WALLET_RELATIONSHIP_REQUEST_CONTRACT_VERSION": REQUEST_CONTRACT_VERSION,
    }
    exec(compile(module, str(CAPABILITIES_PATH), "exec"), namespace)
    return namespace["_wallet_relationship_capability"]


def test_promotion_bumps_contract_and_public_service_surface():
    assert _assignment("CMIS_CONTRACT_VERSION") == "1.28.0"
    services = _assignment("PUBLIC_RUNTIME_SERVICES")
    assert services[-1] == SERVICE
    assert services.count(SERVICE) == 1
    public_init = PUBLIC_INIT_PATH.read_text(encoding="utf-8")
    assert f'"{SERVICE}"' in public_init


def test_x1_wallet_relationship_is_bounded_read_only_and_promoted():
    x1 = _helper()(available=True)
    assert x1["state"] == "bounded"
    assert x1["callable"] is True
    assert x1["read_only"] is True
    assert x1["public_service_promoted"] is True
    assert x1["scout_reliance_promoted"] is True
    assert x1["service_contract_version"] == CONTRACT_VERSION
    assert x1["request_contract_version"] == REQUEST_CONTRACT_VERSION
    assert x1["materialization_contract_version"] == MATERIALIZATION_CONTRACT_VERSION
    assert x1["observed_relationships_only"] is True
    assert x1["proof_score_separate_from_risk"] is True
    assert x1["evidence_receipt_binding_available"] is False
    assert x1["proof_score_binding_available"] is False
    assert x1["execution_authorized"] is False


def test_x1_wallet_relationship_requires_verified_transaction_evidence():
    x1 = _helper()(available=True)
    for requirement in (
        "exact_x1_transaction_signature",
        "exact_x1_asset_mint_identity",
        "exact_sender_wallet_identity",
        "exact_recipient_wallet_identity",
        "cmis_owned_finalized_x1_transaction_resolution",
        "verified_direct_spl_token_transfer",
        "exact_token_account_owner_binding",
        "exact_transfer_direction",
        "exact_raw_amount_and_decimals",
        "canonical_transaction_fact_time",
        "content_addressed_wallet_activity_observation",
        "content_addressed_direct_relationship_evidence",
        "caller_fact_evidence_provider_injection_rejected",
    ):
        assert requirement in x1["requirements"]


def test_x1_wallet_relationship_preserves_investigation_truth_boundaries():
    x1 = _helper()(available=True)
    assert x1["ownership_inference_authorized"] is False
    assert x1["beneficial_ownership_inference_authorized"] is False
    assert x1["behavior_or_intent_inference_authorized"] is False
    assert x1["risk_inference_authorized"] is False
    assert x1["complete_history_claim_authorized"] is False
    assert x1["complete_graph_coverage_claim_authorized"] is False
    for limitation in (
        "observed_direct_interaction_only",
        "relationship_is_transaction_scoped_not_complete_history",
        "transfer_does_not_prove_common_ownership",
        "transfer_does_not_prove_beneficial_ownership",
        "wallet_address_is_not_real_world_identity",
        "transfer_does_not_prove_insider_whale_bot_or_market_maker",
        "behavior_or_intent_not_inferred",
        "coordination_manipulation_or_fraud_not_inferred",
        "sequence_or_transfer_does_not_establish_causality",
        "risk_severity_not_inferred",
        "complete_wallet_history_not_proven",
        "complete_relationship_graph_not_proven",
        "missing_evidence_is_unknown_not_zero",
        "no_execution_authorization",
        "x1_only_initial_scope",
    ):
        assert limitation in x1["limitations"]


def test_solana_wallet_relationship_is_explicitly_unavailable():
    solana = _helper()(available=False)
    assert solana["state"] == "unavailable"
    assert solana["callable"] is False
    assert solana["read_only"] is True
    assert solana["public_service_promoted"] is False
    assert solana["scout_reliance_promoted"] is False
    assert solana["service_contract_version"] == CONTRACT_VERSION
    assert solana["request_contract_version"] == REQUEST_CONTRACT_VERSION
    assert solana["proof_score_separate_from_risk"] is True
    assert solana["execution_authorized"] is False


def test_capability_is_wired_for_x1_and_solana_without_private_imports():
    source = _source()
    assert (
        "WALLET_RELATIONSHIP_SERVICE: _wallet_relationship_capability(available=True)"
        in source
    )
    assert (
        "WALLET_RELATIONSHIP_SERVICE: _wallet_relationship_capability(available=False)"
        in source
    )
