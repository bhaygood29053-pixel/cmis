"""CMIS 1.21 Instant X1 Scan v4 freshness projection.

v4 preserves the accepted v3/v2 scan composition and changes only the accepted
current-market freshness envelope from x1_current_market_freshness/v1 to the
already-accepted x1_current_market_freshness/v2 contract.

The v2 freshness object remains field-scoped. A verified rolling-volume or
transaction field does not imply provider fact-time, source independence,
global market freshness, or execution authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from liquidity_scout.services.cmis_instant_x1_scan_v3 import (
    HISTORY_METRICS,
    SERVICE,
    build_instant_x1_scan_v3_response,
)

CONTRACT_VERSION = "instant_x1_scan/v4"
FRESHNESS_CONTRACT_VERSION = "x1_current_market_freshness/v2"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _default_freshness() -> dict[str, Any]:
    return {
        "contract_version": FRESHNESS_CONTRACT_VERSION,
        "scope": "instant_x1_scan.current_market",
        "freshness_state": "NOT_VERIFIED",
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
                "reason": "aggregate_liquidity_current_chain_proof_incomplete",
            },
            "volume_24h_usd": {
                "freshness_verified": False,
                "reason": "rolling_volume_exact_chain_window_proof_incomplete",
            },
            "transactions_24h": {
                "freshness_verified": False,
                "reason": "rolling_transactions_exact_chain_window_proof_incomplete",
            },
        },
        "limitations": [
            "collection_time_is_not_provider_fact_time",
            "price_freshness_requires_timestamped_provider_price_match",
            "aggregate_liquidity_current_chain_proof_incomplete",
            "rolling_volume_exact_chain_window_proof_incomplete",
            "rolling_transactions_exact_chain_window_proof_incomplete",
            "provider_collection_time_is_not_promoted_to_liquidity_fact_time",
            "source_independence_separate_from_freshness",
        ],
        "execution_authorized": False,
    }


def build_instant_x1_scan_v4_response(
    identity_envelope: Mapping[str, Any],
    market_envelope: Mapping[str, Any],
    tokenomics_envelope: Mapping[str, Any],
    history_envelope: Mapping[str, Any],
    risk_envelope: Mapping[str, Any],
    *,
    freshness_assessment: Mapping[str, Any] | None = None,
    native_distribution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project accepted v3 facts into v4 with exact v2 freshness only."""

    # Build the accepted v3 composition with its own fail-closed default, then
    # replace only the freshness projection. This preserves v3 identity,
    # market, tokenomics, history, risk, and native-distribution behavior.
    result = build_instant_x1_scan_v3_response(
        identity_envelope,
        market_envelope,
        tokenomics_envelope,
        history_envelope,
        risk_envelope,
        native_distribution=native_distribution,
    )
    result = deepcopy(result)

    data = result.get("data")
    if not isinstance(data, dict):
        raise ValueError("Instant X1 Scan v3 response is missing data")
    sections = data.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("Instant X1 Scan v3 response is missing sections")
    market = sections.get("market")
    if not isinstance(market, dict):
        raise ValueError("Instant X1 Scan v3 response is missing market section")

    freshness = (
        deepcopy(dict(freshness_assessment))
        if isinstance(freshness_assessment, Mapping)
        else _default_freshness()
    )
    if freshness.get("contract_version") != FRESHNESS_CONTRACT_VERSION:
        raise ValueError(
            "Instant X1 Scan v4 requires x1_current_market_freshness/v2"
        )
    if freshness.get("execution_authorized") is True:
        raise ValueError("freshness assessment may not authorize execution")

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

    stale = {
        "liquidity_volume_transaction_fact_time_not_verified",
        "rolling_volume_fact_time_not_verified",
        "rolling_transactions_fact_time_not_verified",
    }
    limitations[:] = [item for item in limitations if item not in stale]
    for limitation in (
        "current_market_freshness_is_field_scoped",
        "rolling_freshness_requires_exact_chain_window_evidence",
        "provider_fact_time_not_promoted_by_chain_reconstruction",
        "source_independence_separate_from_freshness",
        "collection_time_is_not_provider_fact_time",
        "execution_authorized_false",
    ):
        if limitation not in limitations:
            limitations.append(limitation)

    return result


__all__ = [
    "CONTRACT_VERSION",
    "FRESHNESS_CONTRACT_VERSION",
    "HISTORY_METRICS",
    "SERVICE",
    "build_instant_x1_scan_v4_response",
]
