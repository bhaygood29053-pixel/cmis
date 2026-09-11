from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


SERVICE = "tokenized_equity_intelligence"
CONTRACT_VERSION = "tokenized_equity_intelligence/v1"
REQUEST_CONTRACT_VERSION = "tokenized_equity_intelligence_request/v1"
MATERIALIZATION_CONTRACT_VERSION = "tokenized_equity_intelligence_materialization/v1"
BRIEF_SERVICE = "x1_intelligence_brief_inputs"
WALLET_SERVICE = "wallet_relationship_intelligence"
CAPABILITIES_PATH = Path("liquidity_scout/cmis/capabilities.py")
PUBLIC_INIT_PATH = Path("liquidity_scout/cmis/__init__.py")
SERVICE_PATH = Path("liquidity_scout/services/cmis_tokenized_equity_intelligence.py")


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


def _helper(name: str, namespace: dict[str, Any]):
    tree = ast.parse(_source())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    scope = {"Any": Any, **namespace}
    exec(compile(module, str(CAPABILITIES_PATH), "exec"), scope)
    return scope[name]


def _tokenized_equity_helper():
    return _helper(
        "_tokenized_equity_intelligence_capability",
        {
            "TOKENIZED_EQUITY_INTELLIGENCE_CONTRACT_VERSION": CONTRACT_VERSION,
            "TOKENIZED_EQUITY_INTELLIGENCE_REQUEST_CONTRACT_VERSION": REQUEST_CONTRACT_VERSION,
            "TOKENIZED_EQUITY_INTELLIGENCE_MATERIALIZATION_CONTRACT_VERSION": MATERIALIZATION_CONTRACT_VERSION,
        },
    )


def test_cmis_130_service_order_preserves_brief_and_wallet_facade():
    assert _assignment("CMIS_CONTRACT_VERSION") == "1.30.0"
    services = _assignment("PUBLIC_RUNTIME_SERVICES")
    assert services[-3:] == (BRIEF_SERVICE, SERVICE, WALLET_SERVICE)
    assert len(services) == 23
    assert services.count(SERVICE) == 1
    assert services.count(BRIEF_SERVICE) == 1
    assert services.count(WALLET_SERVICE) == 1
    public_init = PUBLIC_INIT_PATH.read_text(encoding="utf-8")
    assert f'"{SERVICE}"' in public_init
    assert SERVICE_PATH.read_text(encoding="utf-8").count("PROMOTED = True") == 1


def test_x1_tokenized_equity_service_is_bounded_read_only_and_scout_promoted():
    x1 = _tokenized_equity_helper()(available=True)
    assert x1["state"] == "bounded"
    assert x1["callable"] is True
    assert x1["read_only"] is True
    assert x1["public_service_promoted"] is True
    assert x1["scout_reliance_promoted"] is True
    assert x1["service_contract_version"] == CONTRACT_VERSION
    assert x1["request_contract_version"] == REQUEST_CONTRACT_VERSION
    assert x1["materialization_contract_version"] == MATERIALIZATION_CONTRACT_VERSION
    assert x1["live_x1_equity_deployment_verified"] is False
    assert x1["live_robinhood_x1_route_verified"] is False
    assert x1["proof_score_separate_from_risk"] is True
    assert x1["execution_authorized"] is False

    for requirement in (
        "exact_x1_asset_mint_identity",
        "cmis_owned_tokenized_equity_record_resolver",
        "accepted_tokenized_equity_provenance_v1",
        "accepted_cross_chain_equity_provenance_v1",
        "accepted_tokenized_equity_rights_v1",
        "accepted_tokenized_equity_market_activity_v1",
        "accepted_tokenized_equity_evidence_quality_v1",
        "caller_fact_evidence_provider_injection_rejected",
        "protected_evidence_receipt_and_proof_score_attachment",
    ):
        assert requirement in x1["requirements"]

    for limitation in (
        "service_availability_does_not_prove_x1_tokenized_equity_deployment",
        "missing_subject_or_component_is_evidence_required_not_zero",
        "ticker_or_name_is_not_security_or_token_identity",
        "robinhood_chain_to_x1_route_unverified_without_direct_accepted_evidence",
        "rights_evidence_is_not_legal_adjudication",
        "wrapped_representation_is_not_underlying_equity",
        "liquidity_is_not_volume",
        "transfer_is_not_trade",
        "bridge_flow_is_not_adoption",
        "reference_price_is_not_executed_price",
        "proof_score_is_not_risk",
        "no_automatic_legal_compliance_risk_or_investment_conclusion",
        "no_execution_authorization",
    ):
        assert limitation in x1["limitations"]


def test_solana_tokenized_equity_service_remains_explicitly_unavailable():
    solana = _tokenized_equity_helper()(available=False)
    assert solana["state"] == "unavailable"
    assert solana["callable"] is False
    assert solana["read_only"] is True
    assert solana["public_service_promoted"] is False
    assert solana["scout_reliance_promoted"] is False
    assert solana["live_x1_equity_deployment_verified"] is False
    assert solana["live_robinhood_x1_route_verified"] is False
    assert solana["proof_score_separate_from_risk"] is True
    assert solana["execution_authorized"] is False


def test_capability_helper_is_wired_for_x1_and_solana():
    source = _source()
    assert "TOKENIZED_EQUITY_INTELLIGENCE_SERVICE: _tokenized_equity_intelligence_capability(\n            available=True\n        )" in source
    assert "TOKENIZED_EQUITY_INTELLIGENCE_SERVICE: _tokenized_equity_intelligence_capability(\n            available=False\n        )" in source
