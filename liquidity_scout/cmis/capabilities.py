"""Machine-readable CMIS capability contract for external Chain Scouts.

This module is the CMIS-side source of truth for service eligibility and for the
accepted evidence boundaries. Runtime capability does not imply provider health,
universal asset coverage, public-service promotion, or proof beyond the scope
explicitly named.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

from liquidity_scout.cmis.x1_evidence_capabilities import (
    build_x1_evidence_capability_manifest,
)
from liquidity_scout.services.cmis_verified_intelligence import (
    ACCEPTED_CONCLUSION_TYPES as CONCENTRATION_INTELLIGENCE_CONCLUSION_TYPES,
    CONTRACT_VERSION as CONCENTRATION_INTELLIGENCE_CONTRACT_VERSION,
    PROMOTION_SCOPE as CONCENTRATION_INTELLIGENCE_PROMOTION_SCOPE,
    SERVICE as CONCENTRATION_INTELLIGENCE_SERVICE,
)


CAPABILITY_SCHEMA_VERSION = 1
CMIS_CONTRACT_VERSION = "1.10.0"
EVIDENCE_RECEIPT_SCHEMA_VERSION = 1
PROOF_SCORE_SCHEMA_VERSION = 1
INTELLIGENCE_FOUNDATION_SCHEMA_VERSION = 1
INTELLIGENCE_EVIDENCE_SCHEMA_VERSION = 1
CAPABILITY_STATES = frozenset({"supported", "bounded", "partial", "unavailable"})


def _capability(
    state: str,
    *,
    requirements: Iterable[str] = (),
    limitations: Iterable[str] = (),
) -> dict[str, Any]:
    if state not in CAPABILITY_STATES:
        raise ValueError(f"Unsupported CMIS capability state: {state!r}")
    return {
        "state": state,
        "callable": state != "unavailable",
        "requirements": list(requirements),
        "limitations": list(limitations),
    }


def _intelligence_capability(
    *,
    requirements: Iterable[str] = (),
    limitations: Iterable[str] = (),
) -> dict[str, Any]:
    """Describe a read-only foundation primitive without promoting an API service."""
    return {
        "state": "bounded",
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "requirements": list(requirements),
        "limitations": list(limitations),
    }


def _promoted_concentration_intelligence_capability(*, available: bool) -> dict[str, Any]:
    if not available:
        return {
            "state": "unavailable",
            "callable": False,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "service_contract_version": CONCENTRATION_INTELLIGENCE_CONTRACT_VERSION,
            "promotion_scope": None,
            "accepted_conclusion_types": [],
            "requirements": [],
            "limitations": ["concentration_change_intelligence_not_available_for_chain"],
            "execution_authorized": False,
        }
    return {
        "state": "bounded",
        "callable": True,
        "read_only": True,
        "public_service_promoted": True,
        "scout_reliance_promoted": True,
        "service_contract_version": CONCENTRATION_INTELLIGENCE_CONTRACT_VERSION,
        "promotion_scope": CONCENTRATION_INTELLIGENCE_PROMOTION_SCOPE,
        "accepted_conclusion_types": sorted(CONCENTRATION_INTELLIGENCE_CONCLUSION_TYPES),
        "requirements": [
            "exact_x1_asset_id",
            "cmis_owned_intelligence_evidence_id",
            "trusted_internal_evidence_resolver",
            "deterministic_bundle_revalidation",
            "top_account_concentration_change_only",
            "content_addressed_evidence_receipts",
            "exact_recomputed_proof_scores",
            "receipt_chain_source_and_asset_coverage",
        ],
        "limitations": [
            "caller_supplied_intelligence_evidence_not_accepted",
            "phase_11_foundation_objects_remain_unpromoted",
            "observed_top_token_account_scope_is_incomplete",
            "token_accounts_are_not_unique_holders",
            "beneficial_owner_identity_unverified",
            "proof_strength_remains_separate_from_risk",
            "threshold_policy_is_not_a_market_fact",
            "unresolved_receipt_fields_keep_service_partial",
            "no_behavioral_or_ownership_labels",
            "no_provider_assertion_promotion",
            "no_execution_authorization",
            "x1_only_initial_scope",
        ],
        "execution_authorized": False,
    }


_CHAIN_SERVICE_CAPABILITIES: dict[str, dict[str, dict[str, Any]]] = {
    "x1": {
        "asset_lookup": _capability("supported"),
        "market_report": _capability("supported"),
        "rank": _capability("supported"),
        "historical_compare": _capability(
            "supported",
            requirements=("verified_current_market_snapshot",),
            limitations=(
                "window_mode_requires_supported_period",
                "all_available_mode_uses_cmis_stored_verified_observations_only",
                "all_available_does_not_imply_complete_asset_lifetime",
                "all_available_onchain_coverage_is_mint_address_scope",
                "rpc_visible_mint_history_does_not_imply_asset_wide_activity",
                "rpc_block_boundary_does_not_prove_archive_completeness",
                "continuous_historical_coverage_not_implied",
                "external_ohlcv_or_archive_history_not_promoted_by_this_mode",
                "pair_mode_requires_compare_asset_and_overlapping_verified_history",
            ),
        ),
        "tokenomics": _capability("supported"),
        "risk_check": _capability("supported"),
        "pre_trade_check": _capability(
            "bounded",
            limitations=(
                "analysis_only",
                "execution_authorized_false",
                "slippage_unavailable",
                "price_impact_unavailable",
                "route_quality_unavailable",
                "fees_unavailable",
                "transaction_simulation_unavailable",
            ),
        ),
        "trade_verification": _capability(
            "bounded",
            requirements=("provider_trade_event", "x1_rpc_verification"),
            limitations=("recognized_xdex_program_scope",),
        ),
        "verified_asset_activity": _capability(
            "bounded",
            limitations=(
                "selected_pool_scope_may_be_smaller_than_asset_scope",
                "asset_wide_completeness_fails_closed",
            ),
        ),
        "verification_evidence": _capability(
            "bounded",
            requirements=("exact_evidence_id_or_fact_type_subject_id",),
            limitations=("read_only_persisted_evidence_lookup",),
        ),
        CONCENTRATION_INTELLIGENCE_SERVICE: _promoted_concentration_intelligence_capability(
            available=True
        ),
    },
    "solana": {
        "asset_lookup": _capability(
            "bounded",
            requirements=("exact_mint", "solana_rpc_provider_configured"),
            limitations=("symbol_name_discovery_unavailable",),
        ),
        "market_report": _capability(
            "partial",
            requirements=(
                "exact_mint",
                "solana_rpc_provider_configured",
                "jupiter_price_v3_provider_configured",
                "dexscreener_provider_configured",
                "explicit_cross_source_price_tolerance",
            ),
            limitations=(
                "cross_source_price_agreement_not_canonical_price",
                "asset_wide_liquidity_unverified",
                "asset_wide_volume_unverified",
                "shared_absolute_freshness_unverified",
            ),
        ),
        "rank": _capability(
            "unavailable",
            limitations=("solana_asset_ranking_not_implemented",),
        ),
        "historical_compare": _capability(
            "partial",
            requirements=(
                "exact_mint",
                "jupiter_price_v3_source",
                "price_usd_metric",
                "solana_observation_ledger_configured",
                "deployment_history_distance_policy",
            ),
            limitations=(
                "jupiter_price_v3_history_only",
                "absolute_price_freshness_unverified",
                "dex_pair_history_unavailable",
            ),
        ),
        "tokenomics": _capability(
            "partial",
            requirements=("exact_mint", "solana_rpc_provider_configured"),
            limitations=(
                "circulating_supply_unavailable",
                "maximum_supply_unavailable",
                "lifetime_mint_burn_coverage_unavailable",
            ),
        ),
        "risk_check": _capability(
            "partial",
            requirements=("exact_mint",),
            limitations=(
                "asset_wide_market_inputs_incomplete",
                "bounded_mint_burn_activity_unavailable",
                "historical_risk_inputs_incomplete",
            ),
        ),
        "pre_trade_check": _capability(
            "unavailable",
            limitations=("solana_pre_trade_not_implemented",),
        ),
        "trade_verification": _capability(
            "unavailable",
            limitations=("solana_trade_verification_not_implemented",),
        ),
        "verified_asset_activity": _capability(
            "unavailable",
            limitations=("solana_verified_asset_activity_not_implemented",),
        ),
        "verification_evidence": _capability(
            "unavailable",
            limitations=("solana_persisted_verification_lookup_not_promoted",),
        ),
        CONCENTRATION_INTELLIGENCE_SERVICE: _promoted_concentration_intelligence_capability(
            available=False
        ),
    },
}


_INTELLIGENCE_FOUNDATION_CAPABILITIES: dict[str, dict[str, Any]] = {
    "top_account_concentration": _intelligence_capability(
        requirements=(
            "explicit_observed_top_token_account_set",
            "independently_supplied_total_supply",
            "verified_asset_and_account_identity",
            "explicit_requested_top_n_scope",
        ),
        limitations=(
            "token_accounts_are_not_unique_holders",
            "beneficial_owner_identity_unverified",
            "complete_holder_coverage_unproven",
            "behavioral_interpretation_not_authorized",
        ),
    ),
    "wallet_activity_facts": _intelligence_capability(
        requirements=(
            "verified_wallet_asset_transaction_identity",
            "explicit_source_provenance",
            "activity_specific_direction_or_semantic_proof",
        ),
        limitations=(
            "behavioral_identity_labels_not_authorized",
            "complete_wallet_history_unproven",
            "missing_amounts_remain_unknown",
        ),
    ),
    "sanitized_intelligence_history": _intelligence_capability(
        requirements=(
            "content_addressed_normalized_observation",
            "verified_identity_and_metric_semantics",
            "explicit_source_scope_unit_and_observation_time",
        ),
        limitations=(
            "sparse_observation_history_only",
            "continuous_coverage_unproven",
            "archival_completeness_unproven",
            "no_interpolation_or_zero_fill",
            "no_cross_source_scope_or_unit_reconciliation",
        ),
    ),
    "evidence_bound_conclusions": _intelligence_capability(
        requirements=(
            "valid_content_addressed_evidence_receipt",
            "exact_recomputed_proof_score",
            "receipt_chain_source_and_asset_coverage",
            "deterministically_revalidated_conclusion",
        ),
        limitations=(
            "proof_strength_separate_from_risk",
            "provider_assertions_not_promoted",
            "scout_reliance_not_promoted",
            "public_service_not_promoted",
            "execution_authorized_false",
        ),
    ),
}


def _normalized(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip().lower()
        if text and text not in result:
            result.append(text)
    return tuple(result)


def validate_capability_contract(
    *,
    runtime_services: Iterable[object],
    known_chains: Iterable[object],
) -> None:
    """Fail loudly when runtime services/chains drift from the public manifest."""
    services = set(_normalized(runtime_services))
    chains = set(_normalized(known_chains))
    manifest_chains = set(_CHAIN_SERVICE_CAPABILITIES)
    if chains != manifest_chains:
        raise RuntimeError(
            "CMIS capability contract chain drift: runtime/known chains do not "
            f"match the manifest ({sorted(chains)!r} != {sorted(manifest_chains)!r})."
        )

    for chain, capabilities in _CHAIN_SERVICE_CAPABILITIES.items():
        capability_services = set(capabilities)
        if capability_services != services:
            missing = sorted(services - capability_services)
            extra = sorted(capability_services - services)
            raise RuntimeError(
                "CMIS capability contract service drift for "
                f"{chain}: missing={missing!r}, extra={extra!r}."
            )
        for service, capability in capabilities.items():
            state = capability.get("state")
            callable_flag = capability.get("callable")
            if state not in CAPABILITY_STATES:
                raise RuntimeError(
                    f"CMIS capability {chain}/{service} has invalid state {state!r}."
                )
            if callable_flag is not (state != "unavailable"):
                raise RuntimeError(
                    f"CMIS capability {chain}/{service} has inconsistent callable flag."
                )
            if capability.get("public_service_promoted") is True and callable_flag is not True:
                raise RuntimeError(
                    f"CMIS capability {chain}/{service} promotes a non-callable service."
                )
            if capability.get("scout_reliance_promoted") is True and capability.get(
                "public_service_promoted"
            ) is not True:
                raise RuntimeError(
                    f"CMIS capability {chain}/{service} promotes Scout reliance without public promotion."
                )


def build_capability_manifest(
    *,
    runtime_services: Iterable[object],
    legacy_supported_chains: Iterable[object],
    known_chains: Iterable[object],
    request_path: str = "/v1/cmis",
) -> dict[str, Any]:
    """Return a fresh JSON-safe capability manifest for Chain Scouts."""
    runtime_services = _normalized(runtime_services)
    known_chains = _normalized(known_chains)
    legacy_supported_chains = _normalized(legacy_supported_chains)
    validate_capability_contract(
        runtime_services=runtime_services,
        known_chains=known_chains,
    )

    chains: dict[str, Any] = {}
    for chain in known_chains:
        services = deepcopy(_CHAIN_SERVICE_CAPABILITIES[chain])
        chain_record: dict[str, Any] = {
            "services": services,
            "callable_services": [
                service
                for service in runtime_services
                if services[service]["callable"] is True
            ],
        }
        if chain == "x1":
            x1_evidence = build_x1_evidence_capability_manifest()
            chain_record["evidence_capability_schema_version"] = x1_evidence[
                "schema_version"
            ]
            chain_record["evidence_promotion_rule"] = x1_evidence[
                "promotion_rule"
            ]
            chain_record["evidence_capabilities"] = x1_evidence["capabilities"]
        chains[chain] = chain_record

    return {
        "service": "cmis_gateway",
        "schema_version": CAPABILITY_SCHEMA_VERSION,
        "contract_version": CMIS_CONTRACT_VERSION,
        "request_path": request_path,
        "evidence_quality": {
            "evidence_receipt_schema_version": EVIDENCE_RECEIPT_SCHEMA_VERSION,
            "proof_score_schema_version": PROOF_SCORE_SCHEMA_VERSION,
            "proof_strength_values": ["STRONG", "MODERATE", "WEAK"],
            "risk_separate_from_proof": True,
            "missing_evidence_is_unknown": True,
        },
        "intelligence_foundation": {
            "schema_version": INTELLIGENCE_FOUNDATION_SCHEMA_VERSION,
            "phase": "phase_11_verified_intelligence_foundation",
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "promotion_rule": "new_accepted_public_service_contract_required",
            "intelligence_evidence_schema_version": INTELLIGENCE_EVIDENCE_SCHEMA_VERSION,
            "capabilities": deepcopy(_INTELLIGENCE_FOUNDATION_CAPABILITIES),
        },
        "supported_services": list(runtime_services),
        "supported_chains": list(legacy_supported_chains),
        "known_chains": list(known_chains),
        "chains": chains,
    }


def service_capability(
    manifest: Mapping[str, Any],
    *,
    chain: str,
    service: str,
) -> Mapping[str, Any] | None:
    """Read one public-service capability record without guessing defaults."""
    chains = manifest.get("chains")
    if not isinstance(chains, Mapping):
        return None
    chain_record = chains.get(str(chain or "").strip().lower())
    if not isinstance(chain_record, Mapping):
        return None
    services = chain_record.get("services")
    if not isinstance(services, Mapping):
        return None
    capability = services.get(str(service or "").strip().lower())
    return capability if isinstance(capability, Mapping) else None


__all__ = [
    "CAPABILITY_SCHEMA_VERSION",
    "CAPABILITY_STATES",
    "CMIS_CONTRACT_VERSION",
    "EVIDENCE_RECEIPT_SCHEMA_VERSION",
    "INTELLIGENCE_EVIDENCE_SCHEMA_VERSION",
    "INTELLIGENCE_FOUNDATION_SCHEMA_VERSION",
    "PROOF_SCORE_SCHEMA_VERSION",
    "build_capability_manifest",
    "service_capability",
    "validate_capability_contract",
]
