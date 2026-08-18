"""Machine-readable X1 evidence capability boundary.

This registry closes ambiguous provider-gap states without fabricating proof.
A capability is ``verified`` only for the exact scope named here. ``bounded``
means a deterministic evidence primitive exists but broader semantics or
coverage remain unproven. ``unavailable`` means CMIS must not expose the
claimed fact from the currently accepted provider contracts.

Changing an unavailable capability to bounded/verified requires a new accepted
evidence contract and tests; provider marketing/UI output is never enough.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


SCHEMA_VERSION = 1
STATES = frozenset({"verified", "bounded", "unavailable"})


def _record(
    state: str,
    *,
    scope: str,
    proof_basis: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> dict[str, Any]:
    if state not in STATES:
        raise ValueError(f"invalid X1 evidence capability state: {state}")
    return {
        "state": state,
        "usable_as_verified_fact": state == "verified",
        "scope": scope,
        "proof_basis": list(proof_basis),
        "limitations": list(limitations),
    }


_CAPABILITIES: dict[str, dict[str, Any]] = {
    # Holder / concentration boundary.
    "holder_wallet_or_beneficial_owner_total": _record(
        "unavailable",
        scope="asset_holder_total",
        proof_basis=(
            "x1_ninja_holder_semantics_gate",
            "x1_token_account_enumeration_evidence",
        ),
        limitations=(
            "provider_counted_entity_semantics_unproven",
            "provider_coverage_totality_unproven",
            "token_accounts_are_not_wallets_or_beneficial_owners",
        ),
    ),
    "token_account_concentration": _record(
        "bounded",
        scope="observed_largest_token_accounts_share_of_mint_supply",
        proof_basis=(
            "x1_rpc_largest_token_accounts_contract",
            "x1_token_account_concentration_contract",
        ),
        limitations=(
            "largest_accounts_only",
            "not_holder_concentration",
            "not_wallet_concentration",
            "total_holder_count_unverified",
        ),
    ),
    # Historical / archival boundary.
    "historical_same_fact_block_comparison": _record(
        "bounded",
        scope="explicit_requested_slot_same_fact_comparison",
        proof_basis=(
            "x1_secondary_rpc_contract",
            "x1_historical_block_comparison",
            "x1_historical_comparison_evidence",
        ),
        limitations=(
            "source_independence_must_be_explicit",
            "sparse_samples_only",
            "no_archival_completeness_claim",
        ),
    ),
    "archival_history_completeness": _record(
        "unavailable",
        scope="continuous_chain_history_and_retention",
        proof_basis=("x1_historical_retention_samples",),
        limitations=(
            "continuous_coverage_unproven",
            "retention_depth_unproven",
            "finality_equivalence_unproven",
            "backfill_and_reconnect_unproven",
        ),
    ),
    "provider_trade_range_exhaustiveness": _record(
        "unavailable",
        scope="provider_trade_history_requested_range",
        proof_basis=(
            "x1_ninja_trade_history_contract",
            "x1_history_range_artifact",
        ),
        limitations=(
            "provider_pagination_exhaustiveness_unproven",
            "provider_range_completeness_unproven",
            "ordering_and_stale_behavior_not_fully_proven",
        ),
    ),
    # Direct XDEX read-only boundary. The coarse capabilities are intentionally
    # bounded: accepted field-level semantics exist, but the entire provider
    # payload is not promoted as a verified CMIS fact.
    "xdex_history_semantics": _record(
        "bounded",
        scope="direct_xdex_xencat_native_xnt_history_field_semantics",
        proof_basis=(
            "xdex_read_only_transport_contract",
            "xdex_ninja_history_semantic_evidence",
            "xdex_history_field_semantic_evidence",
        ),
        limitations=(
            "verified_scope_is_pinned_xencat_native_xnt_market",
            "volume_semantics_unverified",
            "range_completeness_unproven",
            "gap_or_forward_fill_semantics_unproven",
            "not_archival_completeness",
        ),
    ),
    "xdex_history_timestamp_interval": _record(
        "verified",
        scope="pinned_xencat_native_xnt_xdex_history_unix_second_60s_oldest_to_newest_timeline",
        proof_basis=(
            "xdex_history_field_semantic_evidence",
            "xdex_ninja_history_semantic_evidence",
        ),
        limitations=(
            "verified_for_observed_xencat_native_xnt_history_contract",
            "does_not_prove_other_pairs_or_intervals",
            "does_not_prove_range_completeness",
        ),
    ),
    "xdex_history_native_close_price": _record(
        "verified",
        scope="pinned_xencat_native_xnt_latest_bar_close_as_native_xnt_price",
        proof_basis=(
            "xdex_history_field_semantic_evidence",
            "x1_ninja_ohlcv_current_price_native_crosscheck",
        ),
        limitations=(
            "latest_close_crosscheck_scope",
            "does_not_promote_volume",
            "does_not_prove_complete_historical_coverage",
        ),
    ),
    "xdex_history_native_ohlc": _record(
        "bounded",
        scope="pinned_xencat_native_xnt_60s_ohlc_native_price_candidates",
        proof_basis=(
            "xdex_ninja_history_semantic_evidence",
            "x1_ninja_price_native_trade_range_crosscheck",
            "xdex_history_field_semantic_evidence",
        ),
        limitations=(
            "not_every_bar_reconstructed_from_individual_trades",
            "provider_gap_fill_behavior_unproven",
            "full_range_completeness_unproven",
        ),
    ),
    "xdex_history_volume_semantics": _record(
        "unavailable",
        scope="direct_xdex_compact_history_v_field",
        proof_basis=("xdex_ninja_history_semantic_evidence",),
        limitations=(
            "v_does_not_match_x1_ninja_candle_volume_in_aligned_sample",
            "token_native_usd_or_other_unit_unproven",
            "cumulative_or_rolling_semantics_unproven",
        ),
    ),
    "xdex_history_range_completeness": _record(
        "unavailable",
        scope="direct_xdex_history_requested_range_completeness_and_gap_behavior",
        proof_basis=("xdex_history_field_semantic_evidence",),
        limitations=(
            "requested_window_exhaustiveness_unproven",
            "gap_forward_fill_behavior_unproven",
            "maximum_retention_and_range_unproven",
        ),
    ),
    "xdex_quote_semantics": _record(
        "bounded",
        scope="direct_xdex_verified_cp_swap_quote_field_semantics",
        proof_basis=(
            "xdex_read_only_transport_contract",
            "xdex_live_contract_evidence",
            "xdex_price_impact_semantic_evidence",
            "xdex_output_slippage_semantic_evidence",
            "xdex_second_pool_effective_fee_evidence",
        ),
        limitations=(
            "field_level_proofs_are_route_and_config_scoped",
            "all_in_fee_business_decomposition_unverified",
            "minimum_received_ui_label_and_instruction_binding_unverified",
            "route_quality_unverified",
            "fill_quality_unverified",
            "freshness_or_expiry_unverified",
        ),
    ),
    "xdex_quote_mint_identity": _record(
        "verified",
        scope="pinned_xencat_native_xnt_exact_in_quote_input_output_mint_identity",
        proof_basis=(
            "xdex_verified_native_pair_live",
            "xdex_price_impact_semantic_evidence",
        ),
        limitations=("verified_for_exact_tested_mint_pair",),
    ),
    "xdex_quote_amm_config_identity": _record(
        "verified",
        scope="pinned_xencat_native_xnt_quote_amm_config_matches_verified_onchain_config",
        proof_basis=(
            "xdex_live_contract_evidence",
            "x1_rpc_program_account_decode",
        ),
        limitations=(
            "amm_config_identity_is_not_full_route_quality",
            "does_not_prove_router_optimality_or_multi_hop_behavior",
        ),
    ),
    "xdex_quote_trade_fee_rate": _record(
        "verified",
        scope="pinned_xencat_native_xnt_amm_config_trade_fee_rate_2800_ppm_0_28_percent",
        proof_basis=(
            "x1_rpc_amm_config_decode",
            "xdex_price_impact_semantic_evidence",
        ),
        limitations=(
            "amm_config_trade_fee_only",
            "quote_zero_slippage_effective_curve_deduction_can_differ_from_config_trade_fee",
            "not_all_in_fee_decomposition",
        ),
    ),
    "xdex_quote_price_impact_semantics": _record(
        "verified",
        scope="pinned_xencat_native_xnt_exact_in_priceImpactPct_as_post_config_trade_fee_cp_curve_impact",
        proof_basis=(
            "x1_rpc_verified_pool_reserves",
            "x1_rpc_amm_config_decode",
            "xdex_price_impact_semantic_evidence_eight_size_direction_cases",
            "xdex_slippage_parameter_independence_evidence",
        ),
        limitations=(
            "verified_for_pinned_cp_swap_route_only",
            "not_generic_to_all_xdex_routes_or_assets",
            "priceImpactPct_is_invariant_to_tested_slippage_values",
            "does_not_equal_user_slippage",
            "do_not_substitute_output_effective_curve_deduction_for_priceImpactPct_semantics",
        ),
    ),
    "xdex_quote_slippage_parameter_semantics": _record(
        "verified",
        scope="current_direct_xdex_exact_in_quote_slippage_query_parameter_in_percent_units",
        proof_basis=(
            "xdex_quote_slippage_parameter_live",
            "xdex_output_slippage_semantic_evidence",
        ),
        limitations=(
            "verified_for_current_read_only_exact_in_quote_contract",
            "does_not_prove_prepare_or_execution_instruction_semantics",
            "future_provider_contract_changes_require_reverification",
        ),
    ),
    "xdex_quote_default_slippage": _record(
        "verified",
        scope="current_direct_xdex_exact_in_quote_default_slippage_0_5_percent",
        proof_basis=("xdex_quote_slippage_parameter_live",),
        limitations=(
            "verified_by_omitted_parameter_equalling_explicit_slippage_0_5",
            "current_live_contract_only",
            "not_an_execution_fill_guarantee",
        ),
    ),
    "xdex_quote_output_slippage_transform": _record(
        "verified",
        scope="tested_direct_exact_in_outputAmount_raw_floor_of_zero_slippage_output_times_one_minus_slippage_percent",
        proof_basis=("xdex_quote_slippage_parameter_live",),
        limitations=(
            "verified_for_tested_exact_in_cp_swap_quotes",
            "does_not_by_itself_prove_user_facing_minimum_received_label",
            "does_not_prove_onchain_minimum_amount_out_instruction_binding",
        ),
    ),
    "xdex_quote_effective_curve_deduction": _record(
        "verified",
        scope="tested_direct_cp_swap_zero_slippage_quotes_use_3000_ppm_effective_curve_deduction_across_observed_2800_and_3000_ppm_configs",
        proof_basis=(
            "xdex_output_slippage_semantic_evidence_bidirectional_cases",
            "xdex_xnt_usdc_second_market_evidence",
            "xdex_different_amm_config_evidence",
            "x1_rpc_637_pool_config_inventory",
        ),
        limitations=(
            "arithmetic_behavior_only_not_business_fee_label",
            "2800_ppm_config_quote_matches_3000_ppm_curve_but_reason_is_unproven",
            "3000_ppm_config_quote_matches_its_own_config_rate",
            "current_inventory_contains_only_2800_and_3000_ppm_configs",
            "hardcoded_3000_vs_minimum_3000_floor_cannot_be_distinguished_without_higher_rate_config",
            "not_generic_to_future_configs_or_non_cp_swap_routes",
        ),
    ),
    "xdex_quote_output_amount_decomposition": _record(
        "bounded",
        scope="tested_direct_cp_swap_outputAmount_curve_and_slippage_arithmetic_decomposition",
        proof_basis=(
            "xdex_output_slippage_semantic_evidence",
            "xdex_quote_slippage_parameter_live",
            "xdex_second_pool_effective_fee_evidence",
            "xdex_token_transfer_fee_evidence",
        ),
        limitations=(
            "tested_output_arithmetic_is_reproducible",
            "business_source_of_2800_to_3000_effective_curve_difference_unproven",
            "minimum_received_ui_label_unproven",
            "execution_instruction_binding_unproven",
            "not_generic_to_all_routes_or_assets",
        ),
    ),
    "xdex_quote_total_fee_decomposition": _record(
        "unavailable",
        scope="all_in_xdex_quote_fee_components_and_business_labels",
        proof_basis=(
            "x1_rpc_amm_config_decode",
            "xdex_output_slippage_semantic_evidence",
            "xdex_second_pool_effective_fee_evidence",
        ),
        limitations=(
            "config_trade_fee_is_verified_but_quote_effective_deduction_can_differ",
            "reason_for_2800_to_3000_effective_curve_difference_unproven",
            "router_platform_protocol_or_other_business_fee_labels_unproven",
        ),
    ),
    "xdex_quote_slippage_minimum_received": _record(
        "bounded",
        scope="direct_xdex_slippage_verified_but_minimum_received_label_and_instruction_binding_unproven",
        proof_basis=(
            "xdex_quote_slippage_parameter_live",
            "xdex_output_slippage_semantic_evidence",
        ),
        limitations=(
            "slippage_parameter_percent_units_verified",
            "default_0_5_percent_verified",
            "outputAmount_slippage_transform_verified",
            "user_facing_minimum_received_label_not_authoritatively_bound_to_outputAmount",
            "onchain_minimum_amount_out_instruction_binding_unproven",
        ),
    ),
    "xdex_quote_route_quality": _record(
        "unavailable",
        scope="xdex_quote_route_optimality_multi_pool_or_multi_hop_quality",
        proof_basis=("xdex_quote_amm_config_identity",),
        limitations=(
            "verified_config_identity_is_not_route_optimality",
            "multi_pool_selection_semantics_unproven",
            "multi_hop_behavior_unproven",
        ),
    ),
    "xdex_quote_fill_quality": _record(
        "unavailable",
        scope="quote_to_actual_execution_fill_quality",
        limitations=(
            "no_quote_to_execution_comparison_contract",
            "no_execution_or_value_movement_permitted",
        ),
    ),
    # Native XNT translation is proven in CMIS and is now also proven for the
    # exact XDEX quote identity used by the accepted XENCAT/native-XNT probe.
    "native_xnt_canonical_translation": _record(
        "verified",
        scope="cmis_native_xnt_identity_and_market_representation_translation",
        proof_basis=(
            "cmis_canonical_xnt_gateway",
            "cmis_xnt_native_gateway",
            "x1_rpc_network_supply",
        ),
        limitations=(
            "wrapped_market_representation_is_not_canonical_native_identity",
            "direct_xdex_quote_scope_is_classified_separately",
        ),
    ),
    "native_xnt_xdex_quote_translation": _record(
        "verified",
        scope="direct_xdex_quote_accepts_and_preserves_so111_native_xnt_market_identity_for_pinned_xencat_pair",
        proof_basis=(
            "xdex_verified_native_pair_live",
            "xdex_price_impact_semantic_evidence",
        ),
        limitations=(
            "verified_for_pinned_xencat_native_xnt_quote_contract",
            "does_not_make_so111_canonical_native_chain_identity",
        ),
    ),
    # Streaming boundary.
    "x1_ninja_sse_access_handshake": _record(
        "bounded",
        scope="http_sse_handshake_classification_only",
        proof_basis=("x1_ninja_trade_stream_access_classifier",),
        limitations=(
            "event_body_not_consumed_by_access_probe",
            "deployment_access_must_be_observed_live",
            "no_event_semantics_claim",
        ),
    ),
    "x1_ninja_sse_live_event_evidence": _record(
        "unavailable",
        scope="cmis_live_trade_event_source",
        proof_basis=("x1_ninja_trade_stream_access_classifier",),
        limitations=(
            "event_schema_unverified",
            "ordering_unverified",
            "duplicate_behavior_unverified",
            "reconnect_and_backfill_unverified",
            "dropped_event_detection_unverified",
            "freshness_semantics_unverified",
        ),
    ),
    # Bridge boundary.
    "warp_bridge_source_provenance_gate": _record(
        "bounded",
        scope="exact_candidate_read_url_provenance_eligibility",
        proof_basis=("x1_bridge_source_provenance_gate",),
        limitations=(
            "gate_does_not_discover_endpoint",
            "gate_does_not_verify_response_semantics",
        ),
    ),
    "warp_bridge_operational_state": _record(
        "unavailable",
        scope="machine_readable_bridge_operational_state",
        proof_basis=("x1_bridge_source_provenance_gate",),
        limitations=("no_provenance_approved_contract_tested_read_source",),
    ),
    "warp_bridge_supported_asset_routes": _record(
        "unavailable",
        scope="machine_readable_supported_asset_and_route_state",
        proof_basis=("canonical_asset_representation_registry",),
        limitations=(
            "canonical_representation_model_is_not_live_bridge_route_proof",
            "no_provenance_approved_contract_tested_read_source",
        ),
    ),
    "warp_bridge_fee_and_capacity": _record(
        "unavailable",
        scope="bridge_fee_components_and_route_capacity",
        limitations=("no_provenance_approved_contract_tested_read_source",),
    ),
    "warp_bridge_transfer_lifecycle": _record(
        "unavailable",
        scope="bridge_transfer_history_and_lifecycle",
        limitations=("no_authoritative_contract_tested_lifecycle_source",),
    ),
    "warp_bridge_guardian_state": _record(
        "unavailable",
        scope="guardian_identity_quorum_and_health",
        limitations=("ui_observation_is_not_machine_readable_verified_fact",),
    ),
}


def build_x1_evidence_capability_manifest() -> dict[str, Any]:
    """Return a fresh copy so callers cannot mutate the registry."""
    return {
        "schema_version": SCHEMA_VERSION,
        "chain": "x1",
        "promotion_rule": "new_accepted_evidence_contract_required",
        "capabilities": deepcopy(_CAPABILITIES),
    }


def validate_x1_evidence_capability_manifest() -> None:
    manifest = build_x1_evidence_capability_manifest()
    capabilities = manifest["capabilities"]
    if not capabilities:
        raise RuntimeError("X1 evidence capability registry must not be empty")
    for name, record in capabilities.items():
        if not name or record.get("state") not in STATES:
            raise RuntimeError(f"invalid X1 evidence capability: {name!r}")
        if record.get("usable_as_verified_fact") is not (
            record.get("state") == "verified"
        ):
            raise RuntimeError(f"inconsistent X1 evidence capability: {name}")
        if not str(record.get("scope") or "").strip():
            raise RuntimeError(f"X1 evidence capability scope is required: {name}")


validate_x1_evidence_capability_manifest()


__all__ = [
    "SCHEMA_VERSION",
    "STATES",
    "build_x1_evidence_capability_manifest",
    "validate_x1_evidence_capability_manifest",
]
