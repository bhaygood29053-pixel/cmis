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
    # Direct XDEX read-only boundary.
    "xdex_history_semantics": _record(
        "unavailable",
        scope="direct_xdex_price_history_as_cmis_historical_fact",
        proof_basis=("xdex_read_only_transport_contract",),
        limitations=(
            "pair_direction_unproven",
            "timestamp_semantics_unproven",
            "quote_unit_unproven",
            "range_and_gap_semantics_unproven",
        ),
    ),
    "xdex_quote_semantics": _record(
        "unavailable",
        scope="direct_xdex_quote_as_pretrade_execution_evidence",
        proof_basis=("xdex_read_only_transport_contract",),
        limitations=(
            "amount_and_rate_semantics_unproven",
            "route_and_fee_semantics_unproven",
            "freshness_or_expiry_unproven",
            "price_impact_semantics_unproven",
        ),
    ),
    # Native XNT translation is proven in CMIS, but not in the blocked direct
    # XDEX quote path. Keep those claims separate.
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
            "does_not_verify_direct_xdex_quote_translation",
        ),
    ),
    "native_xnt_xdex_quote_translation": _record(
        "unavailable",
        scope="direct_xdex_quote_native_xnt_translation",
        proof_basis=("xdex_read_only_transport_contract",),
        limitations=("native_xnt_quote_provider_semantics_unresolved",),
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
