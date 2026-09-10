from __future__ import annotations

from liquidity_scout.cmis import KNOWN_CHAINS, SUPPORTED_CHAINS, SUPPORTED_SERVICES
from liquidity_scout.cmis.capabilities import (
    CMIS_CONTRACT_VERSION,
    PUBLIC_RUNTIME_SERVICES,
    build_capability_manifest,
    service_capability,
)
from liquidity_scout.services.cmis_x1_intelligence_brief_service import (
    CONTRACT_VERSION,
    SERVICE,
)


def _manifest():
    return build_capability_manifest(
        runtime_services=PUBLIC_RUNTIME_SERVICES,
        legacy_supported_chains=SUPPORTED_CHAINS,
        known_chains=KNOWN_CHAINS,
    )


def test_cmis_129_promotes_x1_intelligence_brief_without_replacing_wallet_relationship():
    assert CMIS_CONTRACT_VERSION == "1.29.0"
    assert tuple(SUPPORTED_SERVICES) == tuple(PUBLIC_RUNTIME_SERVICES)
    assert PUBLIC_RUNTIME_SERVICES[-2:] == (
        "x1_intelligence_brief_inputs",
        "wallet_relationship_intelligence",
    )
    assert PUBLIC_RUNTIME_SERVICES.count(SERVICE) == 1
    assert PUBLIC_RUNTIME_SERVICES.count("wallet_relationship_intelligence") == 1


def test_x1_intelligence_brief_is_bounded_read_only_and_scout_promoted():
    x1 = service_capability(_manifest(), chain="x1", service=SERVICE)
    assert x1["state"] == "bounded"
    assert x1["callable"] is True
    assert x1["read_only"] is True
    assert x1["public_service_promoted"] is True
    assert x1["scout_reliance_promoted"] is True
    assert x1["service_contract_version"] == CONTRACT_VERSION
    assert x1["request_contract_version"] == "x1_intelligence_brief_request/v1"
    assert x1["composition_contract_version"] == "x1_intelligence_brief_inputs/v1"
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
    solana = service_capability(_manifest(), chain="solana", service=SERVICE)
    assert solana["state"] == "unavailable"
    assert solana["callable"] is False
    assert solana["read_only"] is True
    assert solana["public_service_promoted"] is False
    assert solana["scout_reliance_promoted"] is False
    assert solana["complete_x1_ecosystem_coverage_verified"] is False
    assert solana["execution_authorized"] is False


def test_wallet_relationship_128_capability_survives_129_release():
    manifest = _manifest()
    x1 = service_capability(
        manifest,
        chain="x1",
        service="wallet_relationship_intelligence",
    )
    solana = service_capability(
        manifest,
        chain="solana",
        service="wallet_relationship_intelligence",
    )
    assert x1["state"] == "bounded"
    assert x1["public_service_promoted"] is True
    assert x1["scout_reliance_promoted"] is True
    assert x1["observed_relationships_only"] is True
    assert x1["ownership_inference_authorized"] is False
    assert x1["risk_inference_authorized"] is False
    assert x1["execution_authorized"] is False
    assert solana["state"] == "unavailable"
    assert solana["execution_authorized"] is False
