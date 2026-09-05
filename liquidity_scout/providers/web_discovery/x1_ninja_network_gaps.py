"""Deterministic X1.Ninja network/API gap inventory.

This module reconciles the repository-known documented X1.Ninja Developer API
surface against x1_ninja_structured_discovery/v1.

It separates route coverage from access limitations, semantic verification
gaps, and advertised capabilities that lack a stable machine contract. It does
not perform a live request or invent provider endpoints.
"""

from __future__ import annotations

from typing import Any

from .base import DISCOVERED
from .x1_ninja_structured import parse_x1_ninja_url


GAP_INVENTORY_CONTRACT = "x1_ninja_network_api_gap_inventory/v1"

COVERED_READ_ONLY_ROUTE = "covered_read_only_route"
ACCESS_LIMITED_ROUTE = "access_limited_route"
SEMANTIC_GAP_NOT_ROUTE_GAP = "semantic_gap_not_route_gap"
CAPABILITY_WITHOUT_MACHINE_CONTRACT = "capability_without_machine_contract"
UNKNOWN = "unknown"

V9_CONTRACT = "x1_ninja_structured_discovery/v1"
NEXT_CONTRACT = "x1_ninja_semantic_coverage_reconciliation/v1"

_POOL = "11111111111111111111111111111111"

KNOWN_DOCUMENTED_API_ROUTES = (
    {
        "surface_id": "pool_catalog",
        "url": "https://api.x1.ninja/v1/pools?limit=100&offset=0",
        "classification": COVERED_READ_ONLY_ROUTE,
        "provider_evidence": [
            "liquidity_scout.providers.x1.ninja_pool_catalog",
            "liquidity_scout.providers.x1.market",
        ],
    },
    {
        "surface_id": "pool_detail",
        "url": f"https://api.x1.ninja/v1/pools/{_POOL}",
        "classification": COVERED_READ_ONLY_ROUTE,
        "provider_evidence": [
            "liquidity_scout.providers.x1.ninja_pool_detail",
        ],
    },
    {
        "surface_id": "trade_history",
        "url": f"https://api.x1.ninja/v1/trades/{_POOL}",
        "classification": COVERED_READ_ONLY_ROUTE,
        "provider_evidence": [
            "liquidity_scout.providers.x1.ninja_history.fetch_pool_trades_raw",
        ],
    },
    {
        "surface_id": "ohlcv",
        "url": f"https://api.x1.ninja/v1/ohlcv/{_POOL}?tf=1h&limit=300",
        "classification": COVERED_READ_ONLY_ROUTE,
        "provider_evidence": [
            "liquidity_scout.providers.x1.ninja_history.fetch_pool_ohlcv_raw",
        ],
    },
    {
        "surface_id": "trade_stream_access",
        "url": "https://api.x1.ninja/v1/stream/trades",
        "classification": ACCESS_LIMITED_ROUTE,
        "provider_evidence": [
            "liquidity_scout.providers.x1.ninja_trade_stream",
            "docs/X1_PROVIDER_GAP_REGISTER.md",
        ],
        "repository_evidence_access_state": "access_denied",
        "repository_evidence_http_status": 403,
        "live_current_access_verified": False,
        "event_body_consumption_authorized": False,
    },
)

SEMANTIC_GAPS = (
    {
        "gap_id": "pool_identity_reserve_holder_semantics",
        "classification": SEMANTIC_GAP_NOT_ROUTE_GAP,
        "surface_ids": ["pool_catalog", "pool_detail"],
        "description": (
            "Pool identity, reserve roles/units, holder counted-entity semantics, "
            "enumeration completeness, and wallet/beneficial-ownership meaning "
            "remain separate verification gates."
        ),
        "evidence_handoffs": [
            "ninja_pool_detail",
            "ninja_pooled_reserve_semantics",
            "X1 RPC vault/token-account corroboration",
            "docs/X1_PROVIDER_GAP_REGISTER.md",
        ],
    },
    {
        "gap_id": "trade_history_semantics",
        "classification": SEMANTIC_GAP_NOT_ROUTE_GAP,
        "surface_ids": ["trade_history"],
        "description": (
            "Trade side, token amount units, USD derivation, LP-event meaning, "
            "signature/finality, pagination/range, duplicates, and ordering are "
            "not implied by route coverage."
        ),
        "evidence_handoffs": [
            "ninja_trade_history_sample_evidence",
            "ninja_trade_history_pool_membership",
            "X1 RPC transaction verification",
        ],
    },
    {
        "gap_id": "ohlcv_semantics",
        "classification": SEMANTIC_GAP_NOT_ROUTE_GAP,
        "surface_ids": ["ohlcv"],
        "description": (
            "Timestamp units, pair direction, quote units, interval/range "
            "coverage, gaps, stale/interpolated behavior, and freshness remain "
            "scope-specific evidence gates."
        ),
        "evidence_handoffs": [
            "ninja_history.fetch_pool_ohlcv_raw",
            "xdex_ninja_history_semantics",
            "xdex_price_history_import",
        ],
    },
    {
        "gap_id": "liquidity_usd_fact_time_freshness",
        "classification": SEMANTIC_GAP_NOT_ROUTE_GAP,
        "surface_ids": ["pool_catalog", "pool_detail"],
        "description": (
            "Provider liquidity USD meaning, fact time, freshness, and stable-"
            "quote/USD equivalence remain separate accepted-or-pending evidence."
        ),
        "evidence_handoffs": [
            "ninja_liquidity_usd_semantics",
            "x1_ninja_current_market_fact_time",
            "x1_ninja_liquidity_usd_semantics_evidence workflow",
        ],
    },
    {
        "gap_id": "delayed_vault_departure_semantics",
        "classification": SEMANTIC_GAP_NOT_ROUTE_GAP,
        "surface_ids": ["pool_catalog", "pool_detail"],
        "description": (
            "Delayed reserve/vault departure evidence is a provider-to-chain "
            "semantic question, not an endpoint discovery problem."
        ),
        "evidence_handoffs": [
            "ninja_delayed_vault_departure_link",
            "ninja_vault_activity_correlation",
        ],
    },
    {
        "gap_id": "trade_stream_event_semantics",
        "classification": SEMANTIC_GAP_NOT_ROUTE_GAP,
        "surface_ids": ["trade_stream_access"],
        "description": (
            "Event schema, ordering, finality, reconnect, backfill, dropped-event "
            "detection, and stream freshness remain unverified; event-body "
            "consumption is unauthorized."
        ),
        "evidence_handoffs": [
            "ninja_trade_stream.probe_trade_stream_access",
        ],
    },
)

ADVERTISED_CAPABILITIES_WITHOUT_MACHINE_CONTRACT = (
    {
        "capability_id": "general_wallet_indexer",
        "classification": CAPABILITY_WITHOUT_MACHINE_CONTRACT,
        "description": (
            "Public research supports deep wallet/indexer capability, but CMIS "
            "does not own an exact stable general-wallet Developer API route."
        ),
        "source_evidence": [
            "docs/X1_PROVIDER_SOURCE_RESEARCH.md",
            "X1.Ninja release notes",
        ],
        "invented_endpoint_authorized": False,
    },
    {
        "capability_id": "wallet_metrics",
        "classification": CAPABILITY_WITHOUT_MACHINE_CONTRACT,
        "description": (
            "Release notes advertise wallet metrics, but no exact documented "
            "Developer API request/response contract is accepted by CMIS."
        ),
        "source_evidence": [
            "docs/X1_PROVIDER_SOURCE_RESEARCH.md",
            "X1.Ninja release notes",
        ],
        "invented_endpoint_authorized": False,
    },
)


def _truth_state() -> dict[str, Any]:
    return {
        "discovery_state": DISCOVERED,
        "provider_response_verified": False,
        "semantic_verification_complete": False,
        "freshness_verified": False,
        "source_independence_verified": False,
        "web_claim_verified": False,
        "cmis_verified": False,
    }


def x1_ninja_network_api_gap_inventory() -> dict[str, Any]:
    """Return deterministic X1.Ninja route/access/semantic gap inventory."""

    route_rows: list[dict[str, Any]] = []
    route_gaps: list[dict[str, Any]] = []

    for spec in KNOWN_DOCUMENTED_API_ROUTES:
        structured = parse_x1_ninja_url(str(spec["url"]))
        supported = bool(structured.get("supported"))
        expected_endpoint = spec["surface_id"]
        endpoint_matches = structured.get("endpoint_type") == expected_endpoint

        row = {
            "surface_id": expected_endpoint,
            "url": spec["url"],
            "classification": spec["classification"],
            "covered_by_v9": supported and endpoint_matches,
            "v9_contract": structured.get("contract"),
            "structured_endpoint_type": structured.get("endpoint_type"),
            "structured_route_verified": bool(
                structured.get("truth_state", {}).get(
                    "x1_ninja_route_verified",
                    False,
                )
            ),
            "provider_evidence": list(spec.get("provider_evidence", [])),
            "provider_response_verified": False,
            "semantic_verification_complete": False,
        }

        if spec["classification"] == ACCESS_LIMITED_ROUTE:
            row.update(
                {
                    "repository_evidence_access_state": spec[
                        "repository_evidence_access_state"
                    ],
                    "repository_evidence_http_status": spec[
                        "repository_evidence_http_status"
                    ],
                    "live_current_access_verified": spec[
                        "live_current_access_verified"
                    ],
                    "event_body_consumption_authorized": spec[
                        "event_body_consumption_authorized"
                    ],
                    "access_limitation_is_route_gap": False,
                }
            )

        route_rows.append(row)
        if not row["covered_by_v9"]:
            route_gaps.append(row)

    access_limited_rows = [
        row for row in route_rows if row["classification"] == ACCESS_LIMITED_ROUTE
    ]

    return {
        "contract": GAP_INVENTORY_CONTRACT,
        "scope": "known_repository_owned_documented_x1_ninja_api_inventory",
        "universal_x1_ninja_endpoint_completeness_verified": False,
        "known_documented_api_route_count": len(route_rows),
        "known_documented_api_routes": route_rows,
        "known_documented_api_route_gap_count": len(route_gaps),
        "known_documented_api_route_gaps": route_gaps,
        "all_known_documented_api_routes_covered_by_v9": (
            len(route_rows) > 0
            and not route_gaps
            and all(row["covered_by_v9"] for row in route_rows)
        ),
        "access_limited_route_count": len(access_limited_rows),
        "access_limited_routes": access_limited_rows,
        "access_limitations_are_route_gaps": False,
        "semantic_gap_count": len(SEMANTIC_GAPS),
        "semantic_gaps": [dict(row) for row in SEMANTIC_GAPS],
        "semantic_gaps_are_route_gaps": False,
        "capability_without_machine_contract_count": len(
            ADVERTISED_CAPABILITIES_WITHOUT_MACHINE_CONTRACT
        ),
        "capabilities_without_machine_contract": [
            dict(row) for row in ADVERTISED_CAPABILITIES_WITHOUT_MACHINE_CONTRACT
        ],
        "invented_endpoint_authorized": False,
        "browser_capture_required_now": False,
        "browser_capture_decision_basis": (
            "All known documented Developer API routes are covered by v9. "
            "Remaining work is access- or semantic-scoped, while advertised "
            "wallet capabilities lack a stable exact machine contract and must "
            "not be converted into guessed endpoints or browser-derived truth."
        ),
        "recommended_next_contract": NEXT_CONTRACT,
        "recommended_next_task": "x1_ninja_semantic_coverage_reconciliation",
        "truth_state": _truth_state(),
        "read_only": True,
        "event_body_consumption_authorized": False,
        "request_replay_authorized": False,
        "background_monitoring_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "ACCESS_LIMITED_ROUTE",
    "ADVERTISED_CAPABILITIES_WITHOUT_MACHINE_CONTRACT",
    "CAPABILITY_WITHOUT_MACHINE_CONTRACT",
    "COVERED_READ_ONLY_ROUTE",
    "GAP_INVENTORY_CONTRACT",
    "KNOWN_DOCUMENTED_API_ROUTES",
    "SEMANTIC_GAP_NOT_ROUTE_GAP",
    "SEMANTIC_GAPS",
    "UNKNOWN",
    "x1_ninja_network_api_gap_inventory",
]
