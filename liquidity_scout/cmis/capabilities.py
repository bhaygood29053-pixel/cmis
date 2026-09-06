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
from liquidity_scout.services.cmis_bridge_to_xdex_public import (
    CONTRACT_VERSION as BRIDGE_TO_XDEX_CONTRACT_VERSION,
    SERVICE as BRIDGE_TO_XDEX_SERVICE,
)
from liquidity_scout.services.cmis_cross_chain_provenance_public import (
    CONTRACT_VERSION as CROSS_CHAIN_PROVENANCE_CONTRACT_VERSION,
    SERVICE as CROSS_CHAIN_PROVENANCE_SERVICE,
)
from liquidity_scout.services.cmis_burn_intelligence import (
    CONTRACT_VERSION as BURN_INTELLIGENCE_CONTRACT_VERSION,
    SERVICE as BURN_INTELLIGENCE_SERVICE,
)
from liquidity_scout.services.cmis_discovery_intelligence import (
    CONTRACT_VERSION as DISCOVERY_INTELLIGENCE_CONTRACT_VERSION,
    SERVICE as DISCOVERY_INTELLIGENCE_SERVICE,
)
from liquidity_scout.services.cmis_concentration_warning_intelligence import (
    CONTRACT_VERSION as CONCENTRATION_WARNING_CONTRACT_VERSION,
    DELIVERY_MODE as CONCENTRATION_WARNING_DELIVERY_MODE,
    SERVICE as CONCENTRATION_WARNING_SERVICE,
)
from liquidity_scout.services.cmis_x1_asset_identity import (
    IDENTITY_CONTRACT as X1_ASSET_IDENTITY_CONTRACT,
)
from liquidity_scout.services.cmis_verified_intelligence import (
    ACCEPTED_CONCLUSION_TYPES as CONCENTRATION_INTELLIGENCE_CONCLUSION_TYPES,
    CONTRACT_VERSION as CONCENTRATION_INTELLIGENCE_CONTRACT_VERSION,
    PROMOTION_SCOPE as CONCENTRATION_INTELLIGENCE_PROMOTION_SCOPE,
    SERVICE as CONCENTRATION_INTELLIGENCE_SERVICE,
)


CAPABILITY_SCHEMA_VERSION = 1
CMIS_CONTRACT_VERSION = "1.23.0"
EVIDENCE_RECEIPT_SCHEMA_VERSION = 1
PROOF_SCORE_SCHEMA_VERSION = 1
INTELLIGENCE_FOUNDATION_SCHEMA_VERSION = 1
INTELLIGENCE_EVIDENCE_SCHEMA_VERSION = 1
CAPABILITY_STATES = frozenset({"supported", "bounded", "partial", "unavailable"})

# Public-shell runtime contract. These identifiers are part of the accepted
# Chain Scout API surface and therefore remain public even though the
# implementation is private. The private facade must match these values exactly.
PUBLIC_RUNTIME_SERVICES = (
    "asset_lookup",
    "market_report",
    "rank",
    "historical_compare",
    "tokenomics",
    "burn_intelligence",
    "discovery_intelligence",
    "risk_check",
    "pre_trade_check",
    "trade_verification",
    "verified_asset_activity",
    "instant_x1_scan",
    "verification_evidence",
    "concentration_change_intelligence",
    "concentration_warning_intelligence",
    "bridge_to_xdex_utilization",
    "cross_chain_asset_provenance",
)
PUBLIC_SUPPORTED_CHAINS = ("x1",)
PUBLIC_KNOWN_CHAINS = ("x1", "solana")


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



def _cross_chain_provenance_capability(*, available: bool) -> dict[str, Any]:
    if not available:
        return {
            "state": "unavailable",
            "callable": False,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "service_contract_version": CROSS_CHAIN_PROVENANCE_CONTRACT_VERSION,
            "requirements": [],
            "limitations": [
                "cross_chain_asset_provenance_not_available_for_chain"
            ],
            "execution_authorized": False,
        }
    return {
        "state": "bounded",
        "callable": True,
        "read_only": True,
        "public_service_promoted": True,
        "scout_reliance_promoted": True,
        "service_contract_version": CROSS_CHAIN_PROVENANCE_CONTRACT_VERSION,
        "requirements": [
            "canonical_cmis_owned_cross_chain_provenance_record",
            "content_addressed_provenance_evidence",
            "exact_current_x1_chain_scoped_asset_id",
            "exact_asset_id_kind",
            "ordered_provenance_hop_continuity",
            "exact_representation_depth",
            "symbol_and_name_identity_shortcuts_rejected",
        ],
        "limitations": [
            "symbol_or_name_equality_is_not_identity_proof",
            "bridge_dependency_is_not_risk",
            "custody_dependency_is_not_risk",
            "provenance_does_not_verify_live_bridge_state",
            "provenance_does_not_verify_backing",
            "provenance_does_not_verify_solvency_or_safety",
            "provenance_does_not_establish_adoption_or_causality",
            "source_independence_unverified_unless_separately_proven",
            "missing_provenance_is_unknown_not_fabricated",
            "no_execution_authorization",
            "x1_current_representation_scope_only",
        ],
        "execution_authorized": False,
    }


def _bridge_to_xdex_capability(*, available: bool) -> dict[str, Any]:
    if not available:
        return {
            "state": "unavailable",
            "callable": False,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "service_contract_version": BRIDGE_TO_XDEX_CONTRACT_VERSION,
            "requirements": [],
            "limitations": ["bridge_to_xdex_utilization_not_available_for_chain"],
            "execution_authorized": False,
        }
    return {
        "state": "bounded",
        "callable": True,
        "read_only": True,
        "public_service_promoted": True,
        "scout_reliance_promoted": True,
        "service_contract_version": BRIDGE_TO_XDEX_CONTRACT_VERSION,
        "requirements": [
            "canonical_cmis_owned_issue_410_record",
            "exact_route_identity",
            "exact_source_and_destination_mints",
            "verified_xdex_program_family_scope",
            "verified_24h_window_coverage_and_volume_semantics",
            "verified_comparable_usd_value_basis",
            "explicit_fact_time_and_freshness_bound",
        ],
        "limitations": [
            "verified_xdex_program_family_is_not_every_x1_dex",
            "bounded_zero_activity_is_not_global_zero_activity",
            "bridge_activity_is_not_adoption",
            "liquidity_is_not_volume",
            "no_causal_inference",
            "no_automatic_risk_conclusion",
            "source_independence_unverified_unless_separately_proven",
            "global_onchain_pool_discovery_unproven",
            "recognized_program_registry_not_globally_exhaustive",
            "no_execution_authorization",
            "x1_only_initial_scope",
        ],
        "execution_authorized": False,
    }


def _burn_intelligence_capability(*, available: bool) -> dict[str, Any]:
    if not available:
        return {
            "state": "unavailable",
            "callable": False,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "service_contract_version": BURN_INTELLIGENCE_CONTRACT_VERSION,
            "requirements": [],
            "limitations": ["burn_intelligence_not_available_for_chain"],
            "execution_authorized": False,
        }
    return {
        "state": "bounded",
        "callable": True,
        "read_only": True,
        "public_service_promoted": True,
        "scout_reliance_promoted": True,
        "service_contract_version": BURN_INTELLIGENCE_CONTRACT_VERSION,
        "requirements": [
            "exact_x1_mint_identity",
            "accepted_tokenomics_burn_metrics",
            "verified_burn_event_semantics",
            "verified_window_coverage_for_numeric_window_claims",
            "verified_prior_window_coverage_for_numeric_percent_change",
        ],
        "limitations": [
            "observed_cumulative_burn_is_not_lifetime_without_archive_completeness",
            "dead_address_transfers_are_not_burns_without_separate_semantic_proof",
            "circulating_supply_requires_independent_supply_semantics",
            "historical_value_destroyed_requires_burn_time_price_evidence",
            "proof_score_separate_from_risk",
            "no_execution_authorization",
            "x1_only_initial_scope",
        ],
        "execution_authorized": False,
    }


def _discovery_intelligence_capability(*, available: bool) -> dict[str, Any]:
    if not available:
        return {
            "state": "unavailable",
            "callable": False,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "service_contract_version": DISCOVERY_INTELLIGENCE_CONTRACT_VERSION,
            "requirements": [],
            "limitations": ["discovery_intelligence_not_available_for_chain"],
            "execution_authorized": False,
        }
    return {
        "state": "bounded",
        "callable": True,
        "read_only": True,
        "public_service_promoted": True,
        "scout_reliance_promoted": True,
        "service_contract_version": DISCOVERY_INTELLIGENCE_CONTRACT_VERSION,
        "requirements": [
            "exact_resolved_x1_mint_identity",
            "cmis_owned_x1_discovery_ledger",
            "verified_observation_state",
            "verified_fact_time",
        ],
        "limitations": [
            "first_verified_observation_is_not_token_launch_time",
            "sparse_observations_do_not_prove_continuous_coverage",
            "archive_completeness_not_verified",
            "missing_observations_are_unknown_not_zero",
            "no_causal_inference",
            "no_execution_authorization",
            "x1_only_initial_scope",
        ],
        "execution_authorized": False,
    }


def _concentration_warning_capability(*, available: bool) -> dict[str, Any]:
    if not available:
        return {
            "state": "unavailable",
            "callable": False,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "service_contract_version": CONCENTRATION_WARNING_CONTRACT_VERSION,
            "delivery_mode": CONCENTRATION_WARNING_DELIVERY_MODE,
            "push_delivery_authorized": False,
            "requirements": [],
            "limitations": [
                "concentration_warning_intelligence_not_available_for_chain"
            ],
            "execution_authorized": False,
        }
    return {
        "state": "bounded",
        "callable": True,
        "read_only": True,
        "public_service_promoted": True,
        "scout_reliance_promoted": True,
        "service_contract_version": CONCENTRATION_WARNING_CONTRACT_VERSION,
        "delivery_mode": CONCENTRATION_WARNING_DELIVERY_MODE,
        "push_delivery_authorized": False,
        "requirements": [
            "x1_only",
            "exact_x1_asset_id",
            "exactly_two_cmis_owned_intelligence_evidence_ids",
            "trusted_internal_intelligence_evidence_resolver",
            "persistent_concentration_warning_v1",
            "strict_fact_time_order",
            "bounded_persistence_window",
            "verified_latest_evidence_freshness",
            "verified_evidence_receipt_freshness",
            "no_unresolved_evidence_fields",
            "content_addressed_evidence_receipts",
            "exact_recomputed_proof_scores",
            "explicit_basis_points_threshold_policy",
            "explicit_gt_or_gte_comparator",
        ],
        "limitations": [
            "pull_only_request_response_service",
            "push_delivery_not_authorized",
            "watch_clear_are_not_risk_severity",
            "warning_does_not_establish_behavior_or_ownership",
            "warning_does_not_establish_manipulation_fraud_intent_or_causality",
            "warning_does_not_predict_imminent_price_movement",
            "token_accounts_are_not_unique_holder_identities",
            "observed_top_account_scope_is_incomplete",
            "proof_strength_remains_separate_from_risk",
            "caller_supplied_trust_material_not_accepted",
            "no_execution_authorization",
            "x1_only_initial_scope",
        ],
        "execution_authorized": False,
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
        "asset_lookup": {
            **_capability(
                "supported",
                limitations=(
                    "exact_mint_is_canonical_fungible_identity_root",
                    "metaplex_name_symbol_uri_are_descriptive_metadata",
                    "xdex_name_symbol_are_provider_market_representation",
                    "same_mint_descriptor_conflicts_return_partial",
                    "xdex_unavailable_is_not_metaplex_only",
                    "symbol_or_name_never_reconciles_different_mints",
                    "metadata_agreement_does_not_imply_risk_or_legitimacy",
                ),
            ),
            "identity_contract_version": X1_ASSET_IDENTITY_CONTRACT,
            "exact_mint_normalization": True,
            "normalized_identity_root": "mint",
            "metaplex_xdex_reconciliation": True,
        },
        "market_report": _capability("supported"),
        "instant_x1_scan": {
            **_capability(
                "bounded",
                requirements=(
                    "verified_x1_asset_identity",
                    "accepted_market_report",
                    "accepted_tokenomics_service",
                    "cmis_verified_history",
                    "bounded_verified_provider_price_backfill",
                    "field_scoped_current_market_freshness",
                    "x1_current_market_freshness_v3",
                    "exact_rolling_24h_chain_window_evidence_when_promoted",
                    "deterministic_risk_core",
                    "instant_x1_scan_history_adequacy_v1",
                    "native_xnt_supported_pair_price_lifetime_when_history_completion_promoted",
                ),
                limitations=(
                    "holder_count_may_remain_unverified_for_non_native_assets",
                    "native_xnt_distribution_uses_native_account_addresses_not_holders",
                    "provider_price_backfill_is_price_only",
                    "provider_source_independence_not_verified",
                    "source_independence_is_stronger_optional_corroboration_for_scan_completion",
                    "global_provider_archive_completeness_not_required_for_scan_completion",
                    "current_market_freshness_is_field_scoped",
                    "price_freshness_uses_timestamped_provider_backfill",
                    "rolling_volume_and_transaction_freshness_require_exact_chain_window_evidence",
                    "provider_fact_time_not_promoted_by_chain_reconstruction",
                    "source_independence_separate_from_freshness",
                    "collection_time_is_not_provider_fact_time",
                    "history_completion_is_exact_supported_pair_price_lifetime_only",
                    "full_usd_lifetime_not_required_for_supported_pair_scan_completion",
                    "non_price_metric_lifetimes_not_required_for_scan_completion",
                    "same_fact_provider_close_corroboration_does_not_prove_source_independence",
                    "proof_score_separate_from_risk",
                    "risk_score_unavailable_until_calibrated",
                    "execution_authorized_false",
                    "x1_only_initial_scope",
                ),
            ),
            "read_only": True,
            "composition_only": True,
            "service_contract_version": "instant_x1_scan/v6",
            "public_service_promoted": True,
            "scout_reliance_promoted": True,
            "execution_authorized": False,
        },
        "rank": _capability("supported"),
        "historical_compare": _capability(
            "supported",
            requirements=("verified_current_market_snapshot",),
            limitations=(
                "window_mode_requires_supported_period",
                "all_available_mode_uses_cmis_stored_verified_observations",
                "verified_provider_price_backfill_may_extend_price_history",
                "verified_provider_backfill_is_price_only",
                "provider_source_independence_not_verified",
                "provider_archive_completeness_not_verified",
                "configured_usd_stable_quote_does_not_prove_historical_one_dollar_peg",
                "all_available_does_not_imply_complete_asset_lifetime",
                "all_available_onchain_coverage_is_mint_address_scope",
                "rpc_visible_mint_history_does_not_imply_asset_wide_activity",
                "rpc_block_boundary_does_not_prove_archive_completeness",
                "continuous_historical_coverage_not_implied",
                "pair_mode_requires_compare_asset_and_overlapping_verified_history",
            ),
        ),
        "tokenomics": _capability("supported"),
        BURN_INTELLIGENCE_SERVICE: _burn_intelligence_capability(available=True),
        DISCOVERY_INTELLIGENCE_SERVICE: _discovery_intelligence_capability(available=True),
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
        CONCENTRATION_WARNING_SERVICE: _concentration_warning_capability(
            available=True
        ),
        BRIDGE_TO_XDEX_SERVICE: _bridge_to_xdex_capability(available=True),
        CROSS_CHAIN_PROVENANCE_SERVICE: _cross_chain_provenance_capability(
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
        "instant_x1_scan": {
            **_capability(
                "unavailable",
                limitations=(
                    "instant_x1_scan_x1_only_initial_scope",
                    "solana_product_expansion_and_release_deferred",
                ),
            ),
            "read_only": True,
            "composition_only": True,
            "service_contract_version": "instant_x1_scan/v3",
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        },
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
        BURN_INTELLIGENCE_SERVICE: _burn_intelligence_capability(available=False),
        DISCOVERY_INTELLIGENCE_SERVICE: _discovery_intelligence_capability(available=False),
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
        CONCENTRATION_WARNING_SERVICE: _concentration_warning_capability(
            available=False
        ),
        BRIDGE_TO_XDEX_SERVICE: _bridge_to_xdex_capability(available=False),
        CROSS_CHAIN_PROVENANCE_SERVICE: _cross_chain_provenance_capability(
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
    "PUBLIC_KNOWN_CHAINS",
    "PUBLIC_RUNTIME_SERVICES",
    "PUBLIC_SUPPORTED_CHAINS",
    "build_capability_manifest",
    "service_capability",
    "validate_capability_contract",
]
