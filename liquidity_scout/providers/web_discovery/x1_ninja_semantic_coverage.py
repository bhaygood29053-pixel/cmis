"""Deterministic X1.Ninja semantic coverage reconciliation.

This module maps the repository-accepted X1.Ninja evidence contracts into a
bounded semantic-status registry. It is a repository governance/evidence map,
not a live provider probe.

Allowed statuses are exactly:
- verified
- partial
- blocked
- unavailable

A verified status is always accompanied by an explicit scope. Nothing in this
module promotes Web Discovery, X1 Scout reliance, source independence, or
execution authority.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .base import DISCOVERED
from .x1_ninja_network_gaps import x1_ninja_network_api_gap_inventory


SEMANTIC_COVERAGE_CONTRACT = "x1_ninja_semantic_coverage_reconciliation/v1"

VERIFIED = "verified"
PARTIAL = "partial"
BLOCKED = "blocked"
UNAVAILABLE = "unavailable"

ALLOWED_STATUSES = frozenset({VERIFIED, PARTIAL, BLOCKED, UNAVAILABLE})

STATE_AS_OF = "2026-09-05"

SEMANTIC_FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "family_id": "pooled_reserve_roles_units",
        "status": VERIFIED,
        "scope": (
            "Accepted #341 multi-pool semantic proof using exact verified "
            "pool/mint/vault identity, RPC-scaled reserve units, deterministic "
            "Decimal comparison, and the accepted tolerance. Use still requires "
            "the exact identity/evidence prerequisites for the pool in question."
        ),
        "verified_claims": [
            "pooledBase_maps_to_rpc_vault_1_mint_1_scaled_reserve",
            "pooledQuote_maps_to_rpc_vault_0_mint_0_scaled_reserve",
            "multi_pool_role_mapping_verified",
            "reserve_unit_scaling_bound_to_verified_rpc_decimals",
        ],
        "unverified_claims": [
            "universal_all_x1_ninja_pool_identity",
            "provider_freshness",
            "source_independence",
            "liquidity_usd_formula",
            "price_usd_semantics",
        ],
        "evidence_handoffs": [
            "Issue #341",
            "liquidity_scout.providers.x1.ninja_pooled_reserve_semantics",
            "tests/test_x1_ninja_pooled_reserve_semantics_live.py",
            "X1 RPC verified pool/mint/vault reserve evidence",
        ],
        "blocking_issue": None,
        "blocking_pr": None,
        "next_action": (
            "Reuse only with exact pool/mint/vault identity and current RPC "
            "reserve evidence; do not generalize by symbol or field name."
        ),
    },
    {
        "family_id": "price_native_semantics",
        "status": PARTIAL,
        "scope": (
            "Accepted bounded direction/reserve-ratio evidence from #343 exists, "
            "but the follow-up #345 remains open because live pools did not all "
            "match one instantaneous gross-reserve-ratio snapshot and provider "
            "fact-time/update-source semantics remain unresolved."
        ),
        "verified_claims": [
            "bounded_price_native_reserve_ratio_direction_evidence_exists",
            "inverse_ratio_not_promoted_as_default_direction",
        ],
        "unverified_claims": [
            "universal_current_price_native_semantics",
            "provider_price_native_fact_time_contract",
            "provider_update_source_semantics",
            "price_usd_semantics",
            "freshness",
        ],
        "evidence_handoffs": [
            "Issue #343",
            "Issue #345",
            "liquidity_scout.providers.x1.ninja_price_native_semantics",
            "liquidity_scout.providers.x1.ninja_price_fact_time",
        ],
        "blocking_issue": 345,
        "blocking_pr": None,
        "next_action": (
            "Continue #345 aligned fact-time/update-source research without "
            "widening numerical tolerance to hide temporal mismatch."
        ),
    },
    {
        "family_id": "liquidity_fact_time",
        "status": VERIFIED,
        "scope": (
            "PR #465 accepted the repeated-revaluation fact-time policy after "
            "3 unique verified revaluation events across 3 distinct pools with "
            "same-fact X1 RPC reference alignment and no intervening reference-"
            "pool transaction. This is a bounded fact-time claim, not freshness."
        ),
        "verified_claims": [
            "liquidity_fact_time_verified",
            "same_fact_revaluation_policy_verified",
        ],
        "unverified_claims": [
            "x1_ninja_liquidity_usd_semantics_verified",
            "liquidity_freshness_verified",
            "source_independence_verified",
        ],
        "evidence_handoffs": [
            "PR #465",
            "Issue #461",
            "repeated X1.Ninja liquidity revaluation evidence",
            "exact X1 RPC XNT/USDC.X reserve-ratio reference",
        ],
        "blocking_issue": None,
        "blocking_pr": None,
        "next_action": (
            "Use as prerequisite evidence only; do not convert fact-time "
            "verification into liquidity freshness."
        ),
    },
    {
        "family_id": "liquidity_usd_semantics",
        "status": BLOCKED,
        "scope": (
            "Final five-pool X1.Ninja USD-liquidity semantic acceptance remains "
            "open under Issue #461 / PR #470."
        ),
        "verified_claims": [
            "liquidity_fact_time_prerequisite_verified",
            "current_usdcx_usd_equivalence_prerequisite_accepted_separately",
        ],
        "unverified_claims": [
            "x1_ninja_liquidity_usd_semantics_verified",
            "global_provider_liquidity_formula",
            "source_independence_verified",
        ],
        "evidence_handoffs": [
            "Issue #461",
            "PR #470",
            "PR #465",
            "PR #466",
            "PR #468",
            "liquidity_scout.providers.x1.ninja_liquidity_usd_semantics",
        ],
        "blocking_issue": 461,
        "blocking_pr": 470,
        "next_action": (
            "Finish and merge PR #470 only after all five distinct same-fact "
            "revaluation samples pass with freshly recomposed USDC.X/USD evidence."
        ),
    },
    {
        "family_id": "liquidity_freshness",
        "status": BLOCKED,
        "scope": (
            "Field-scoped liquidity freshness remains a separate promotion gate "
            "under Issue #459 even after liquidity fact-time is verified."
        ),
        "verified_claims": [
            "price_freshness_framework_exists",
            "liquidity_fact_time_prerequisite_verified",
        ],
        "unverified_claims": [
            "liquidity_freshness_verified",
            "global_current_market_freshness",
        ],
        "evidence_handoffs": [
            "Issue #459",
            "x1_current_market_freshness/v1",
            "PR #465",
        ],
        "blocking_issue": 459,
        "blocking_pr": None,
        "next_action": (
            "After #470/#461 acceptance, wire exact current RPC corroboration and "
            "eligible valuation evidence into the field-scoped freshness path."
        ),
    },
    {
        "family_id": "rolling_24h_volume_transaction_freshness",
        "status": BLOCKED,
        "scope": (
            "Issue #459 explicitly keeps Ninja rolling 24h volume and transaction "
            "freshness unavailable until bounded on-chain 24h reconstruction and "
            "provider window/count semantics are proven."
        ),
        "verified_claims": [],
        "unverified_claims": [
            "volume_24h_freshness_verified",
            "transactions_24h_freshness_verified",
            "provider_rolling_window_semantics_verified",
        ],
        "evidence_handoffs": [
            "Issue #459",
            "x1_current_market_freshness/v1",
        ],
        "blocking_issue": 459,
        "blocking_pr": None,
        "next_action": (
            "Implement bounded on-chain 24h reconstruction and prove provider "
            "window/count semantics before field promotion."
        ),
    },
    {
        "family_id": "holder_total_semantics",
        "status": UNAVAILABLE,
        "scope": (
            "The #304/PR #305 correction is accepted as a semantic safety guard: "
            "provider holder-looking values, RPC token-account counts, and unique "
            "token-account-authority counts remain distinct evidence classes. "
            "No verified asset-wide holder total is established."
        ),
        "verified_claims": [
            "holder_labeling_guard_accepted",
            "provider_rpc_authority_count_classes_kept_distinct",
        ],
        "unverified_claims": [
            "verified_asset_wide_holder_total",
            "enumeration_completeness",
            "holder_counted_entity_semantics",
            "wallet_identity",
            "beneficial_ownership",
        ],
        "evidence_handoffs": [
            "Issue #304",
            "PR #305",
            "docs/X1_PROVIDER_GAP_REGISTER.md",
        ],
        "blocking_issue": None,
        "blocking_pr": None,
        "next_action": (
            "Require counted-entity and enumeration-coverage proof before any "
            "provider value can be labeled as a verified holder total."
        ),
    },
    {
        "family_id": "trade_history_semantics",
        "status": PARTIAL,
        "scope": (
            "Trade-history response/container and row shape are contract-tested. "
            "Bounded sample evidence can cross-check transaction identity, maker "
            "vs RPC primary signer, provider slot, and wallet-level side where the "
            "independent RPC verification report supports it."
        ),
        "verified_claims": [
            "trade_history_response_shape_verified",
            "trade_row_shape_verified",
            "bounded_sample_transaction_identity_crosscheck_available",
            "bounded_sample_maker_slot_side_crosschecks_available",
        ],
        "unverified_claims": [
            "history_exhaustive_verified",
            "retention_verified",
            "pagination_or_range_verified",
            "finality_verified",
            "timestamp_semantics_verified",
            "amount_price_units_verified",
            "provider_ordering_contract_verified",
        ],
        "evidence_handoffs": [
            "liquidity_scout.providers.x1.ninja_history",
            "liquidity_scout.providers.x1.ninja_trade_history_sample_evidence",
            "liquidity_scout.providers.x1.ninja_trade_history_pool_membership",
            "X1 RPC transaction verification",
        ],
        "blocking_issue": None,
        "blocking_pr": None,
        "next_action": (
            "Promote only individually proven row/transaction facts; keep archive, "
            "pagination, finality, units, and ordering claims unavailable."
        ),
    },
    {
        "family_id": "ohlcv_history_semantics",
        "status": PARTIAL,
        "scope": (
            "OHLCV request/response/candle shape and exact request scope are "
            "contract-tested. CMIS verified-provider price backfill may use XDEX "
            "historical closes only when they match corresponding X1.Ninja OHLCV "
            "closes for the exact pair/time scope."
        ),
        "verified_claims": [
            "ohlcv_request_contract_verified",
            "ohlcv_response_shape_verified",
            "ohlcv_candle_shape_verified",
            "bounded_exact_pair_time_close_crosscheck_used_by_history_backfill",
        ],
        "unverified_claims": [
            "x1_ninja_archive_completeness",
            "continuous_coverage_verified",
            "full_asset_lifetime_verified",
            "all_pair_timeframe_timestamp_semantics",
            "all_pair_quote_unit_semantics",
            "range_gap_behavior_verified",
            "ohlcv_freshness_verified",
        ],
        "evidence_handoffs": [
            "liquidity_scout.providers.x1.ninja_history",
            "CMIS 1.12 verified provider-price backfill",
            "docs/CMIS_PRODUCT_ROADMAP.md",
        ],
        "blocking_issue": None,
        "blocking_pr": None,
        "next_action": (
            "Continue using only exact pair/time cross-checked closes; do not "
            "promote archive completeness, continuous coverage, or lifetime claims."
        ),
    },
    {
        "family_id": "delayed_vault_update_behavior",
        "status": PARTIAL,
        "scope": (
            "Issue #363 is closed with deterministic event-level delayed-link "
            "evidence and bounded-pattern support rules. One exact delayed link "
            "may be verified event evidence; stronger longitudinal/provider-wide "
            "behavior remains separately gated."
        ),
        "verified_claims": [
            "event_level_exact_delayed_link_can_be_verified",
            "bounded_pattern_support_policy_defined",
        ],
        "unverified_claims": [
            "departure_pattern_verified_longitudinally",
            "provider_fact_time_universal",
            "provider_update_source_semantics",
            "freshness",
            "universal_catalog_price_semantics",
        ],
        "evidence_handoffs": [
            "Issue #363",
            "liquidity_scout.providers.x1.ninja_delayed_vault_departure_link",
            "liquidity_scout.providers.x1.ninja_vault_activity_correlation",
        ],
        "blocking_issue": None,
        "blocking_pr": None,
        "next_action": (
            "Accumulate independent event evidence for longitudinal claims without "
            "weakening event identity, exact-pool membership, or fail-closed ambiguity."
        ),
    },
    {
        "family_id": "trade_stream_event_semantics",
        "status": UNAVAILABLE,
        "scope": (
            "The route is documented and v9-structured, but repository evidence "
            "observed HTTP 403/access_denied for the tested credential. No SSE "
            "event body was consumed."
        ),
        "verified_claims": [
            "trade_stream_route_identity_known",
            "bounded_handshake_access_classifier_exists",
        ],
        "unverified_claims": [
            "current_authenticated_stream_access",
            "event_schema_verified",
            "event_ordering_verified",
            "event_finality_verified",
            "reconnect_semantics_verified",
            "backfill_semantics_verified",
            "dropped_event_detection_verified",
            "stream_freshness_verified",
        ],
        "evidence_handoffs": [
            "liquidity_scout.providers.x1.ninja_trade_stream",
            "docs/X1_PROVIDER_GAP_REGISTER.md",
        ],
        "blocking_issue": None,
        "blocking_pr": None,
        "next_action": (
            "Only after authenticated SSE access succeeds should event semantics "
            "be tested; Web Discovery event-body consumption remains unauthorized."
        ),
    },
    {
        "family_id": "price_usd_semantics",
        "status": UNAVAILABLE,
        "scope": (
            "Existing priceNative/reserve work and liquidity evidence do not "
            "establish a direct universal semantic contract for provider priceUsd."
        ),
        "verified_claims": [],
        "unverified_claims": [
            "price_usd_semantics_verified",
            "price_usd_fact_time_verified",
            "price_usd_source_independence_verified",
        ],
        "evidence_handoffs": [
            "Issue #343",
            "Issue #345",
            "Issue #461",
        ],
        "blocking_issue": None,
        "blocking_pr": None,
        "next_action": (
            "Do not infer priceUsd from priceNative or liquidity; require a "
            "separate exact independent valuation/field-semantic gate."
        ),
    },
    {
        "family_id": "source_independence",
        "status": UNAVAILABLE,
        "scope": (
            "Same-fact agreement between provider observations and deterministic "
            "cross-checks does not itself establish independent upstream market "
            "sourcing. X1.Ninja/XDEX relationships must remain provenance-scoped."
        ),
        "verified_claims": [
            "same_fact_crosscheck_framework_exists",
        ],
        "unverified_claims": [
            "x1_ninja_source_independence_verified",
            "independent_market_source_count_verified",
        ],
        "evidence_handoffs": [
            "docs/X1_PROVIDER_GAP_REGISTER.md",
            "CMIS evidence/provenance contracts",
        ],
        "blocking_issue": None,
        "blocking_pr": None,
        "next_action": (
            "Require a fact-specific source-independence proof before using "
            "multiple observations as independent corroboration."
        ),
    },
)


def _validate_registry() -> None:
    family_ids: set[str] = set()
    for row in SEMANTIC_FAMILIES:
        family_id = row.get("family_id")
        status = row.get("status")
        scope = row.get("scope")
        if not isinstance(family_id, str) or not family_id:
            raise ValueError("semantic family_id must be non-empty text")
        if family_id in family_ids:
            raise ValueError(f"duplicate semantic family_id {family_id!r}")
        family_ids.add(family_id)
        if status not in ALLOWED_STATUSES:
            raise ValueError(
                f"semantic family {family_id!r} has unsupported status {status!r}"
            )
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError(
                f"semantic family {family_id!r} must include explicit scope"
            )
        if status == VERIFIED and not row.get("verified_claims"):
            raise ValueError(
                f"verified semantic family {family_id!r} must name verified claims"
            )


def _truth_state() -> dict[str, Any]:
    return {
        "discovery_state": DISCOVERED,
        "provider_response_verified_globally": False,
        "semantic_verification_complete_globally": False,
        "freshness_verified_globally": False,
        "source_independence_verified": False,
        "web_claim_verified": False,
        "cmis_verified_globally": False,
    }


def x1_ninja_semantic_coverage_reconciliation() -> dict[str, Any]:
    """Return the deterministic bounded X1.Ninja semantic coverage map."""

    _validate_registry()

    route_inventory = x1_ninja_network_api_gap_inventory()
    route_complete = bool(
        route_inventory.get("all_known_documented_api_routes_covered_by_v9")
        and route_inventory.get("known_documented_api_route_gap_count") == 0
    )

    families = [dict(row) for row in SEMANTIC_FAMILIES]
    counts = Counter(str(row["status"]) for row in families)

    blocked = [row for row in families if row["status"] == BLOCKED]
    unavailable = [row for row in families if row["status"] == UNAVAILABLE]

    return {
        "contract": SEMANTIC_COVERAGE_CONTRACT,
        "state_as_of": STATE_AS_OF,
        "scope": "repository_accepted_x1_ninja_semantic_evidence",
        "allowed_statuses": sorted(ALLOWED_STATUSES),
        "semantic_family_count": len(families),
        "semantic_families": families,
        "status_counts": {
            VERIFIED: counts.get(VERIFIED, 0),
            PARTIAL: counts.get(PARTIAL, 0),
            BLOCKED: counts.get(BLOCKED, 0),
            UNAVAILABLE: counts.get(UNAVAILABLE, 0),
        },
        "blocked_family_ids": [row["family_id"] for row in blocked],
        "unavailable_family_ids": [row["family_id"] for row in unavailable],
        "route_discovery_complete_for_known_documented_api": route_complete,
        "known_documented_api_route_gap_count": route_inventory.get(
            "known_documented_api_route_gap_count"
        ),
        "browser_capture_required_now": False,
        "semantic_reconciliation_complete": True,
        "liquidity_usd_semantics_status": BLOCKED,
        "liquidity_usd_blocking_issue": 461,
        "liquidity_usd_blocking_pr": 470,
        "liquidity_freshness_status": BLOCKED,
        "liquidity_freshness_blocking_issue": 459,
        "price_native_update_source_status": PARTIAL,
        "price_native_followup_issue": 345,
        "recommended_next_actions": [
            {
                "priority": 1,
                "action": "finish_x1_ninja_liquidity_usd_semantics",
                "issue": 461,
                "pull_request": 470,
            },
            {
                "priority": 2,
                "action": "promote_field_scoped_liquidity_and_rolling_window_freshness",
                "issue": 459,
                "pull_request": None,
            },
            {
                "priority": 3,
                "action": "continue_price_native_fact_time_update_source_research",
                "issue": 345,
                "pull_request": None,
            },
        ],
        "truth_state": _truth_state(),
        "read_only": True,
        "event_body_consumption_authorized": False,
        "request_replay_authorized": False,
        "background_monitoring_authorized": False,
        "public_service_promotion_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "ALLOWED_STATUSES",
    "BLOCKED",
    "PARTIAL",
    "SEMANTIC_COVERAGE_CONTRACT",
    "SEMANTIC_FAMILIES",
    "STATE_AS_OF",
    "UNAVAILABLE",
    "VERIFIED",
    "x1_ninja_semantic_coverage_reconciliation",
]
