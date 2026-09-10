from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


SERVICE = "x1_intelligence_brief_inputs"
CONTRACT_VERSION = "x1_intelligence_brief_inputs/v1"
REQUEST_CONTRACT_VERSION = "x1_intelligence_brief_request/v1"
WALLET_SERVICE = "wallet_relationship_intelligence"
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


def _brief_helper():
    return _helper(
        "_x1_intelligence_brief_capability",
        {"X1_INTELLIGENCE_BRIEF_CONTRACT_VERSION": CONTRACT_VERSION},
    )


def _wallet_helper():
    return _helper(
        "_wallet_relationship_capability",
        {
            "WALLET_RELATIONSHIP_CONTRACT_VERSION": "wallet_relationship_intelligence/v1",
            "WALLET_RELATIONSHIP_REQUEST_CONTRACT_VERSION": "wallet_relationship_intelligence_request/v1",
        },
    )


def test_cmis_129_promotes_brief_without_replacing_wallet_relationship():
    assert _assignment("CMIS_CONTRACT_VERSION") == "1.29.0"
    services = _assignment("PUBLIC_RUNTIME_SERVICES")
    assert services[-2:] == (SERVICE, WALLET_SERVICE)
    assert services.count(SERVICE) == 1
    assert services.count(WALLET_SERVICE) == 1
    public_init = PUBLIC_INIT_PATH.read_text(encoding="utf-8")
    assert f'"{SERVICE}"' in public_init
    assert f'"{WALLET_SERVICE}"' in public_init


def test_x1_intelligence_brief_is_bounded_read_only_and_scout_promoted():
    x1 = _brief_helper()(available=True)
    assert x1["state"] == "bounded"
    assert x1["callable"] is True
    assert x1["read_only"] is True
    assert x1["public_service_promoted"] is True
    assert x1["scout_reliance_promoted"] is True
    assert x1["service_contract_version"] == CONTRACT_VERSION
    assert x1["request_contract_version"] == REQUEST_CONTRACT_VERSION
    assert x1["composition_contract_version"] == CONTRACT_VERSION
    assert x1["complete_x1_ecosystem_coverage_verified"] is False
    assert x1["execution_authorized"] is False

    for requirement in (
        "exact_x1_mint_subjects",
        "canonical_utc_bounded_window_max_86400_seconds",
        "complete_subject_service_response_matrix",
        "cmis_internal_component_invocation_only",
        "caller_fact_evidence_provider_injection_rejected",
        "service_specific_fact_time",
        "deterministic_priority_separate_from_risk",
        "proof_score_separate_from_risk",
    ):
        assert requirement in x1["requirements"]

    for limitation in (
        "exact_requested_scope_is_not_complete_x1_ecosystem_coverage",
        "empty_bounded_brief_is_not_global_no_activity",
        "concentration_warning_requires_cmis_owned_policy_and_evidence_selector",
        "warning_level_is_not_risk_severity",
        "wallet_address_is_not_real_world_identity",
        "large_trade_is_not_whale_insider_owner_or_manipulator",
        "sequence_or_activity_is_not_causality",
        "first_verified_observation_is_not_token_launch_time",
        "top_level_freshness_not_inferred_from_item_fact_time",
        "missing_evidence_is_unknown_not_zero",
        "no_trade_recommendation",
        "no_execution_authorization",
    ):
        assert limitation in x1["limitations"]


def test_solana_intelligence_brief_remains_explicitly_unavailable():
    solana = _brief_helper()(available=False)
    assert solana["state"] == "unavailable"
    assert solana["callable"] is False
    assert solana["read_only"] is True
    assert solana["public_service_promoted"] is False
    assert solana["scout_reliance_promoted"] is False
    assert solana["complete_x1_ecosystem_coverage_verified"] is False
    assert solana["execution_authorized"] is False


def test_wallet_relationship_128_capability_survives_129_release():
    x1 = _wallet_helper()(available=True)
    solana = _wallet_helper()(available=False)
    assert x1["state"] == "bounded"
    assert x1["public_service_promoted"] is True
    assert x1["scout_reliance_promoted"] is True
    assert x1["observed_relationships_only"] is True
    assert x1["ownership_inference_authorized"] is False
    assert x1["risk_inference_authorized"] is False
    assert x1["execution_authorized"] is False
    assert solana["state"] == "unavailable"
    assert solana["execution_authorized"] is False


def test_capability_helpers_are_wired_for_x1_and_solana():
    source = _source()
    assert "X1_INTELLIGENCE_BRIEF_SERVICE: _x1_intelligence_brief_capability(\n            available=True\n        )" in source
    assert "X1_INTELLIGENCE_BRIEF_SERVICE: _x1_intelligence_brief_capability(\n            available=False\n        )" in source
    assert "WALLET_RELATIONSHIP_SERVICE: _wallet_relationship_capability(available=True)" in source
    assert "WALLET_RELATIONSHIP_SERVICE: _wallet_relationship_capability(available=False)" in source
