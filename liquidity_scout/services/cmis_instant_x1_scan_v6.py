"""CMIS Instant X1 Scan v6 Gate C history-adequacy projection.

v6 preserves every accepted v5 fact and freshness field. It adds one explicit,
fail-closed answer to a narrower product question: is the historical evidence
required by Instant X1 Scan complete for the exact native-XNT supported market?

This is deliberately not a claim of source independence, global provider
archive completeness, USD-denominated lifetime completeness, or lifetime
coverage for liquidity/volume/transaction metrics.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)
from liquidity_scout.services.cmis_instant_x1_scan_v5 import (
    FRESHNESS_CONTRACT_VERSION,
    HISTORY_METRICS,
    SERVICE,
    build_instant_x1_scan_v5_response,
)

CONTRACT_VERSION = "instant_x1_scan/v6"
HISTORY_ADEQUACY_CONTRACT_VERSION = "instant_x1_scan_history_adequacy/v1"
REQUIRED_HISTORY_SCOPE = "supported_pair_price_lifetime"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _native_xnt_history_adequacy(
    *,
    identity: Mapping[str, Any],
    history: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate only the accepted native-XNT scan-history completion gates."""

    proof = _mapping(history.get("price_lifetime_coverage"))
    metrics = _mapping(history.get("metrics"))
    price = _mapping(metrics.get("price"))

    native_identity_verified = bool(
        identity.get("verified") is True
        and identity.get("identity_key") == "native:xnt"
        and str(identity.get("symbol") or "").strip().upper() == "XNT"
    )
    all_available_history = history.get("mode") == "all_available"
    price_history_available = bool(
        int(history.get("available_metric_count") or 0) > 0
        and int(price.get("observation_count") or 0) > 0
    )
    exact_pair_identity_bound = bool(
        proof.get("asset_identity_bound") is True
        and proof.get("base_mint") == WRAPPED_XNT_MINT
        and proof.get("quote_mint") == USDC_X_MINT
    )
    pair_lifetime_verified = (
        history.get("full_supported_pair_lifetime_verified") is True
        and proof.get("full_supported_pair_lifetime_verified") is True
    )
    pair_continuity_verified = (
        history.get("continuous_pair_price_coverage_verified") is True
        and proof.get("continuous_pair_price_coverage_verified") is True
    )
    supported_range_verified = (
        history.get("provider_range_complete_verified") is True
        and proof.get("provider_range_complete_verified") is True
    )

    checks = {
        "native_xnt_identity_verified": native_identity_verified,
        "all_available_history_mode": all_available_history,
        "verified_price_history_available": price_history_available,
        "exact_xnt_usdcx_pair_identity_bound": exact_pair_identity_bound,
        "full_supported_pair_lifetime_verified": pair_lifetime_verified,
        "continuous_pair_price_coverage_verified": pair_continuity_verified,
        "provider_supported_range_complete_verified": supported_range_verified,
    }
    completion = all(checks.values())

    provider_backfill = history.get("provider_history_imported") is True
    return {
        "contract_version": HISTORY_ADEQUACY_CONTRACT_VERSION,
        "status": "VERIFIED" if completion else "NOT_VERIFIED",
        "required_history_scope": REQUIRED_HISTORY_SCOPE,
        "history_completion_verified": completion,
        "checks": checks,
        "same_fact_corroboration": {
            "state": (
                "BOUNDED_PROVIDER_CLOSE_CORROBORATION"
                if provider_backfill
                else "NOT_VERIFIED"
            ),
            "scope": (
                "accepted_provider_price_backfill_only"
                if provider_backfill
                else None
            ),
            "source_independence_implied": False,
        },
        "source_independence_verified": False,
        "source_independence_required_for_scan_completion": False,
        "historical_quote_usd_equivalence_verified": (
            history.get("historical_quote_usd_equivalence_verified") is True
        ),
        "full_usd_lifetime_verified": (
            history.get("full_usd_lifetime_verified") is True
        ),
        "full_usd_lifetime_required_for_scan_completion": False,
        "global_provider_archive_complete_verified": False,
        "global_archive_completeness_required_for_scan_completion": False,
        "non_price_metric_lifetimes_verified": False,
        "non_price_metric_lifetimes_required_for_scan_completion": False,
        "stronger_corroboration_still_available": True,
        "execution_authorized": False,
    }


def build_instant_x1_scan_v6_response(
    identity_envelope: Mapping[str, Any],
    market_envelope: Mapping[str, Any],
    tokenomics_envelope: Mapping[str, Any],
    history_envelope: Mapping[str, Any],
    risk_envelope: Mapping[str, Any],
    *,
    freshness_assessment: Mapping[str, Any] | None = None,
    native_distribution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Preserve v5 and add exact Gate C history adequacy without overclaiming."""

    result = build_instant_x1_scan_v5_response(
        identity_envelope,
        market_envelope,
        tokenomics_envelope,
        history_envelope,
        risk_envelope,
        freshness_assessment=freshness_assessment,
        native_distribution=native_distribution,
    )
    result = deepcopy(result)

    data = result.get("data")
    if not isinstance(data, dict):
        raise ValueError("Instant X1 Scan v5 response is missing data")
    sections = data.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("Instant X1 Scan v5 response is missing sections")
    identity = sections.get("identity")
    history = sections.get("history")
    if not isinstance(identity, dict) or not isinstance(history, dict):
        raise ValueError("Instant X1 Scan v5 identity/history sections are missing")

    adequacy = _native_xnt_history_adequacy(
        identity=identity,
        history=history,
    )
    history["scan_completion"] = adequacy
    data["contract_version"] = CONTRACT_VERSION

    limitations = data.get("limitations")
    if not isinstance(limitations, list):
        limitations = []
        data["limitations"] = limitations

    for limitation in (
        "scan_history_completion_is_supported_pair_price_lifetime_only",
        "source_independence_is_stronger_optional_corroboration_for_scan_completion",
        "global_provider_archive_completeness_not_required_for_scan_completion",
        "full_usd_lifetime_not_required_for_supported_pair_scan_completion",
        "non_price_metric_lifetimes_not_required_for_scan_completion",
        "same_fact_provider_close_corroboration_does_not_prove_source_independence",
        "execution_authorized_false",
    ):
        if limitation not in limitations:
            limitations.append(limitation)

    return result


__all__ = [
    "CONTRACT_VERSION",
    "FRESHNESS_CONTRACT_VERSION",
    "HISTORY_ADEQUACY_CONTRACT_VERSION",
    "HISTORY_METRICS",
    "REQUIRED_HISTORY_SCOPE",
    "SERVICE",
    "build_instant_x1_scan_v6_response",
]
