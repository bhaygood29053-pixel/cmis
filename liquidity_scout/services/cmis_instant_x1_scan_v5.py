"""CMIS Instant X1 Scan v5 split-liquidity freshness projection.

v5 preserves the accepted v4 scan composition and adds explicit projection for
provider-nominal liquidity and independently valued current USD liquidity from
x1_current_market_freshness/v3.

The legacy v4 liquidity_usd freshness meaning is preserved unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from liquidity_scout.services.cmis_instant_x1_scan_v4 import (
    HISTORY_METRICS,
    SERVICE,
    build_instant_x1_scan_v4_response,
)

CONTRACT_VERSION = "instant_x1_scan/v5"
FRESHNESS_CONTRACT_VERSION = "x1_current_market_freshness/v3"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _default_freshness() -> dict[str, Any]:
    return {
        "contract_version": FRESHNESS_CONTRACT_VERSION,
        "scope": "instant_x1_scan.current_market",
        "freshness_state": "NOT_VERIFIED",
        "current_market_freshness_verified": False,
        "verified_field_count": 0,
        "total_field_count": 6,
        "fields": {
            "price_usd": {
                "freshness_verified": False,
                "reason": "freshness_assessment_not_supplied",
            },
            "liquidity_usd": {
                "freshness_verified": False,
                "reason": "legacy_liquidity_current_chain_proof_incomplete",
            },
            "provider_nominal_liquidity": {
                "freshness_verified": False,
                "reason": "provider_nominal_liquidity_current_chain_proof_incomplete",
                "value": None,
                "unit": None,
            },
            "independent_liquidity_usd": {
                "freshness_verified": False,
                "reason": "independent_current_usd_liquidity_proof_incomplete",
                "value": None,
                "unit": None,
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
            "provider_nominal_liquidity_is_not_independent_external_usd",
            "legacy_liquidity_usd_freshness_semantics_preserved_from_v2",
            "collection_time_is_not_provider_fact_time",
            "source_independence_separate_from_freshness",
        ],
        "execution_authorized": False,
    }


def build_instant_x1_scan_v5_response(
    identity_envelope: Mapping[str, Any],
    market_envelope: Mapping[str, Any],
    tokenomics_envelope: Mapping[str, Any],
    history_envelope: Mapping[str, Any],
    risk_envelope: Mapping[str, Any],
    *,
    freshness_assessment: Mapping[str, Any] | None = None,
    native_distribution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project accepted v4 facts into v5 with exact v3 freshness only."""

    # Build v4 with its own fail-closed default to preserve all existing section
    # composition, then replace only the freshness projection with v3.
    result = build_instant_x1_scan_v4_response(
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
        raise ValueError("Instant X1 Scan v4 response is missing data")
    sections = data.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("Instant X1 Scan v4 response is missing sections")
    market = sections.get("market")
    if not isinstance(market, dict):
        raise ValueError("Instant X1 Scan v4 response is missing market section")

    freshness = (
        deepcopy(dict(freshness_assessment))
        if isinstance(freshness_assessment, Mapping)
        else _default_freshness()
    )
    if freshness.get("contract_version") != FRESHNESS_CONTRACT_VERSION:
        raise ValueError(
            "Instant X1 Scan v5 requires x1_current_market_freshness/v3"
        )
    if freshness.get("execution_authorized") is True:
        raise ValueError("freshness assessment may not authorize execution")

    fields = _mapping(freshness.get("fields"))
    nominal = _mapping(fields.get("provider_nominal_liquidity"))
    independent = _mapping(fields.get("independent_liquidity_usd"))

    market["freshness"] = freshness
    market["price_freshness_verified"] = (
        _mapping(fields.get("price_usd")).get("freshness_verified") is True
    )
    # Legacy compatibility field remains exactly scoped to liquidity_usd.
    market["liquidity_freshness_verified"] = (
        _mapping(fields.get("liquidity_usd")).get("freshness_verified") is True
    )
    market["provider_nominal_liquidity"] = nominal.get("value")
    market["provider_nominal_liquidity_unit"] = nominal.get("unit")
    market["provider_nominal_liquidity_freshness_verified"] = (
        nominal.get("freshness_verified") is True
    )
    market["independent_liquidity_usd"] = independent.get("value")
    market["independent_liquidity_usd_freshness_verified"] = (
        independent.get("freshness_verified") is True
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
        "provider_nominal_liquidity_is_not_independent_external_usd",
        "legacy_liquidity_usd_freshness_semantics_preserved_from_v2",
        "current_market_freshness_is_field_scoped",
        "provider_fact_time_not_promoted_by_chain_reconstruction",
        "source_independence_separate_from_freshness",
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
    "build_instant_x1_scan_v5_response",
]
