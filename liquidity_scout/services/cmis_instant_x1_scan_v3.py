"""CMIS 1.17 Instant X1 Scan v3 freshness projection.

v3 deliberately composes the accepted v2 scan rather than forking its history,
identity, tokenomics, or risk logic. The only new product dimension is the
field-scoped current-market freshness assessment supplied by protected runtime.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from liquidity_scout.services.cmis_instant_x1_scan import (
    HISTORY_METRICS,
    SERVICE,
    build_instant_x1_scan_response as build_v2_response,
)

CONTRACT_VERSION = "instant_x1_scan/v3"
FRESHNESS_CONTRACT_VERSION = "x1_current_market_freshness/v1"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _default_freshness() -> dict[str, Any]:
    return {
        "contract_version": FRESHNESS_CONTRACT_VERSION,
        "scope": "instant_x1_scan.current_market",
        "freshness_state": "NOT_VERIFIED",
        "collection_freshness_verified": False,
        "provider_price_fact_time_verified": False,
        "current_market_freshness_verified": False,
        "verified_field_count": 0,
        "total_field_count": 4,
        "fields": {
            "price_usd": {
                "freshness_verified": False,
                "reason": "freshness_assessment_not_supplied",
            },
            "liquidity_usd": {
                "freshness_verified": False,
                "reason": "liquidity_provider_fact_time_not_verified",
            },
            "volume_24h_usd": {
                "freshness_verified": False,
                "reason": "rolling_volume_provider_fact_time_not_verified",
            },
            "transactions_24h": {
                "freshness_verified": False,
                "reason": "rolling_transactions_provider_fact_time_not_verified",
            },
        },
        "limitations": [
            "collection_time_is_not_provider_fact_time",
            "price_freshness_requires_timestamped_provider_price_match",
            "liquidity_fact_time_not_verified",
            "rolling_volume_fact_time_not_verified",
            "rolling_transactions_fact_time_not_verified",
        ],
    }


def build_instant_x1_scan_v3_response(
    identity_envelope: Mapping[str, Any],
    market_envelope: Mapping[str, Any],
    tokenomics_envelope: Mapping[str, Any],
    history_envelope: Mapping[str, Any],
    risk_envelope: Mapping[str, Any],
    *,
    freshness_assessment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project v2 facts into v3 while preserving every existing fact boundary."""

    response = build_v2_response(
        identity_envelope,
        market_envelope,
        tokenomics_envelope,
        history_envelope,
        risk_envelope,
    )
    result = deepcopy(response)
    data = result.get("data")
    if not isinstance(data, dict):
        raise ValueError("Instant X1 Scan v2 response is missing data")
    sections = data.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("Instant X1 Scan v2 response is missing sections")
    market = sections.get("market")
    if not isinstance(market, dict):
        raise ValueError("Instant X1 Scan v2 response is missing market section")

    freshness = (
        deepcopy(dict(freshness_assessment))
        if isinstance(freshness_assessment, Mapping)
        else _default_freshness()
    )
    if freshness.get("contract_version") != FRESHNESS_CONTRACT_VERSION:
        raise ValueError("Instant X1 Scan v3 requires x1_current_market_freshness/v1")

    fields = _mapping(freshness.get("fields"))
    market["freshness"] = freshness
    market["price_freshness_verified"] = (
        _mapping(fields.get("price_usd")).get("freshness_verified") is True
    )
    market["liquidity_freshness_verified"] = (
        _mapping(fields.get("liquidity_usd")).get("freshness_verified") is True
    )
    market["volume_24h_freshness_verified"] = (
        _mapping(fields.get("volume_24h_usd")).get("freshness_verified") is True
    )
    market["transactions_24h_freshness_verified"] = (
        _mapping(fields.get("transactions_24h")).get("freshness_verified") is True
    )

    data["contract_version"] = CONTRACT_VERSION
    limitations = data.get("limitations")
    if not isinstance(limitations, list):
        limitations = []
        data["limitations"] = limitations
    for limitation in (
        "current_market_freshness_is_field_scoped",
        "price_freshness_uses_timestamped_provider_backfill",
        "liquidity_volume_transaction_fact_time_not_verified",
        "collection_time_is_not_provider_fact_time",
    ):
        if limitation not in limitations:
            limitations.append(limitation)

    return result


__all__ = [
    "CONTRACT_VERSION",
    "FRESHNESS_CONTRACT_VERSION",
    "HISTORY_METRICS",
    "SERVICE",
    "build_instant_x1_scan_v3_response",
]
