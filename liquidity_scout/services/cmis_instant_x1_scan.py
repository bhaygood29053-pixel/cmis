"""Compact deterministic Instant X1 Scan response builder.

This module performs no provider collection. It composes already-produced CMIS
service envelopes into one bounded ROBERTA-facing scan and preserves each
component's verification state. Missing or unverified facts remain explicit.

Proof Score/evidence-receipt attachment is owned by the runtime
EvidenceQualityMixin after this service returns; this builder never computes or
uses proof quality to rewrite facts, risk, status, or authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.services.cmis_contract import (
    OK,
    PARTIAL,
    build_service_envelope,
)

SERVICE = "instant_x1_scan"
CONTRACT_VERSION = "instant_x1_scan/v2"
HISTORY_METRICS = ("price", "liquidity", "volume", "transactions")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _status(envelope: Any) -> str:
    if not isinstance(envelope, Mapping):
        return "unavailable"
    return str(envelope.get("status") or "unavailable").strip().lower()


def _component_source_records(
    envelope: Any,
    *,
    section: str,
) -> list[dict[str, Any]]:
    if not isinstance(envelope, Mapping):
        return []
    result: list[dict[str, Any]] = []
    sources = envelope.get("sources")
    if not isinstance(sources, list):
        return result
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        record = dict(source)
        role = str(record.get("role") or "").strip()
        record["role"] = f"instant_x1_scan.{section}" + (
            f".{role}" if role else ""
        )
        if record not in result:
            result.append(record)
    return result


def _merge_sources(*parts: tuple[Any, str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for envelope, section in parts:
        for record in _component_source_records(envelope, section=section):
            if record not in result:
                result.append(record)
    return result


def _component_warnings(envelope: Any, *, section: str) -> list[dict[str, Any]]:
    if not isinstance(envelope, Mapping):
        return []
    warnings = envelope.get("warnings")
    if not isinstance(warnings, list):
        return []
    result = []
    for warning in warnings:
        if not isinstance(warning, Mapping):
            continue
        record = dict(warning)
        record.setdefault("section", section)
        result.append(record)
    return result


def _identity_section(envelope: Mapping[str, Any]) -> dict[str, Any]:
    data = _mapping(envelope.get("data"))
    confidence = _mapping(envelope.get("confidence"))
    asset = _mapping(envelope.get("asset"))
    return {
        "status": _status(envelope),
        "verified": confidence.get("complete") is True,
        "symbol": asset.get("symbol"),
        "name": asset.get("name"),
        "mint": asset.get("mint"),
        "resolved_by": data.get("resolved_by"),
        "match_quality": data.get("match_quality"),
        "identity_key": data.get("identity_key"),
        "normalized_identity": (
            dict(data["normalized_identity"])
            if isinstance(data.get("normalized_identity"), Mapping)
            else None
        ),
        "identity_reconciliation": (
            dict(data["identity_reconciliation"])
            if isinstance(data.get("identity_reconciliation"), Mapping)
            else None
        ),
    }


def _market_section(envelope: Mapping[str, Any]) -> dict[str, Any]:
    data = _mapping(envelope.get("data"))
    completeness = _mapping(data.get("completeness"))
    return {
        "status": _status(envelope),
        "observed_at": envelope.get("observed_at"),
        "price_usd": data.get("price_usd"),
        "price_verified": completeness.get("price") is True,
        "liquidity_usd": data.get("liquidity_usd"),
        "liquidity_verified": completeness.get("liquidity") is True,
        "volume_24h_usd": data.get("volume_24h_usd"),
        "volume_24h_verified": completeness.get("volume_24h") is True,
        "transactions_24h": data.get("transactions_24h"),
        "transactions_24h_verified": (
            completeness.get("transactions_24h") is True
        ),
        "#LPs": data.get("#LPs", data.get("lp_count")),
        "market_cap_usd_reported": data.get("market_cap_usd_reported"),
        "market_cap_verified": data.get("market_cap_verified") is True,
        "fdv_usd_reported": data.get("fdv_usd_reported"),
        "fdv_verified": data.get("fdv_verified") is True,
    }


def _activity_section(data: Mapping[str, Any]) -> dict[str, Any]:
    activity = _mapping(data.get("token_activity"))
    return {
        "available": activity.get("available") is True,
        "activity_verified": activity.get("activity_verified") is True,
        "coverage_scope": activity.get("coverage_scope"),
        "coverage_verified": activity.get("coverage_verified") is True,
        "lifetime_coverage_verified": (
            activity.get("lifetime_coverage_verified") is True
        ),
        "mint_events_observed": activity.get("mint_events_observed"),
        "burn_events_observed": activity.get("burn_events_observed"),
        "minted_tokens_observed": activity.get("minted_tokens_observed"),
        "burned_tokens_observed": activity.get("burned_tokens_observed"),
        "net_issuance_verified": activity.get("net_issuance_verified") is True,
        "net_issuance_tokens": activity.get("net_issuance_tokens"),
        "verification_reasons": list(activity.get("verification_reasons") or []),
    }


def _tokenomics_section(envelope: Mapping[str, Any]) -> dict[str, Any]:
    data = _mapping(envelope.get("data"))
    return {
        "status": _status(envelope),
        "current_total_supply": data.get("current_total_supply"),
        "supply_verified": data.get("supply_verified") is True,
        "decimals": data.get("decimals"),
        "rpc_decimals_consistent": data.get("rpc_decimals_consistent") is True,
        "mint_authority": data.get("mint_authority"),
        "mint_authority_verified": data.get("mint_authority_verified") is True,
        "mint_authority_state": data.get("mint_authority_state"),
        "freeze_authority": data.get("freeze_authority"),
        "freeze_authority_verified": data.get("freeze_authority_verified") is True,
        "freeze_authority_state": data.get("freeze_authority_state"),
        "future_minting_possible": data.get("future_minting_possible"),
        "circulating_supply": data.get("circulating_supply"),
        "circulating_supply_verified": (
            data.get("circulating_supply_verified") is True
        ),
        "maximum_supply": data.get("maximum_supply"),
        "maximum_supply_verified": data.get("maximum_supply_verified") is True,
        "token_activity": _activity_section(data),
    }


def _holder_concentration_section(
    market_envelope: Mapping[str, Any],
) -> dict[str, Any]:
    data = _mapping(market_envelope.get("data"))
    completeness = _mapping(data.get("completeness"))
    holders_verified = completeness.get("holders") is True
    return {
        "holders": data.get("holders") if holders_verified else None,
        "holders_verified": holders_verified,
        "holders_reported": data.get("holders_reported"),
        "holders_observed": data.get("holders_observed"),
        "holder_semantics": (
            dict(data["holder_semantics"])
            if isinstance(data.get("holder_semantics"), Mapping)
            else None
        ),
        "top_account_concentration": {
            "value": None,
            "verified": False,
            "state": "unavailable",
            "reason": "current_concentration_not_promoted_for_instant_x1_scan_v2",
        },
    }


def _compact_history_metric(metric: Any) -> dict[str, Any]:
    value = _mapping(metric)
    return {
        "status": value.get("status"),
        "reason": value.get("reason"),
        "observation_count": value.get("observation_count"),
        "current_value": value.get("current_value"),
        "current_verified": value.get("current_verified") is True,
        "first_value": value.get("first_value"),
        "first_observed_at": value.get("first_observed_at"),
        "last_value": value.get("last_value"),
        "last_observed_at": value.get("last_observed_at"),
        "coverage_seconds": value.get("coverage_seconds"),
        "total_change_pct": value.get("total_change_pct"),
        "minimum_value": value.get("minimum_value"),
        "maximum_value": value.get("maximum_value"),
        "sampled_max_drawdown_pct": value.get("sampled_max_drawdown_pct"),
        "observed_gap_count": value.get("observed_gap_count"),
        "largest_observed_gap_seconds": value.get("largest_observed_gap_seconds"),
        "gap_threshold_seconds": value.get("gap_threshold_seconds"),
        "provider_backfill_observation_count": value.get(
            "provider_backfill_observation_count"
        ),
        "provider_history_imported": value.get("provider_history_imported") is True,
        "continuous_coverage_verified": (
            value.get("continuous_coverage_verified") is True
        ),
    }


def _history_section(envelope: Mapping[str, Any]) -> dict[str, Any]:
    data = _mapping(envelope.get("data"))
    metrics = _mapping(data.get("metrics"))
    coverage = _mapping(data.get("coverage"))
    provider_price_history = _mapping(data.get("provider_price_history"))
    provider_backfill = _mapping(data.get("provider_history_backfill"))
    provider_history_imported = data.get("provider_history_imported") is True
    coverage_scope = data.get("coverage_scope")
    if provider_history_imported:
        coverage_scope = (
            "cmis_verified_observations_with_bounded_provider_price_backfill"
        )
    return {
        "status": _status(envelope),
        "mode": data.get("mode"),
        "coverage_scope": coverage_scope,
        "base_coverage_scope": data.get("coverage_scope"),
        "first_verified_observed_at": data.get("first_verified_observed_at"),
        "last_verified_observed_at": data.get("last_verified_observed_at"),
        "coverage_seconds": data.get("coverage_seconds"),
        "available_metric_count": data.get("available_metric_count"),
        "multi_point_metric_count": data.get("multi_point_metric_count"),
        "asset_lifetime_start_verified": (
            data.get("asset_lifetime_start_verified") is True
        ),
        "full_asset_lifetime_verified": (
            data.get("full_asset_lifetime_verified") is True
        ),
        "continuous_coverage_verified": (
            data.get("continuous_coverage_verified") is True
        ),
        "provider_history_imported": provider_history_imported,
        "provider_price_history": dict(provider_price_history),
        "provider_history_backfill": dict(provider_backfill),
        "coverage": dict(coverage),
        "metrics": {
            name: _compact_history_metric(metrics.get(name))
            for name in HISTORY_METRICS
        },
    }


def _risk_section(envelope: Mapping[str, Any]) -> dict[str, Any]:
    risk = _mapping(envelope.get("risk"))
    return {
        "status": _status(envelope),
        "recommendation": risk.get("recommendation"),
        "flags": list(risk.get("flags") or []),
        "reasons": list(risk.get("reasons") or []),
        "confidence": (
            dict(risk["confidence"])
            if isinstance(risk.get("confidence"), Mapping)
            else {}
        ),
        "score": risk.get("score"),
        "score_verified": risk.get("score_verified") is True,
        "score_reason": risk.get("score_reason"),
        "policy": (
            dict(risk["policy"])
            if isinstance(risk.get("policy"), Mapping)
            else {}
        ),
        "execution_authorized": False,
    }


def _confidence(
    identity: Mapping[str, Any],
    market: Mapping[str, Any],
    tokenomics: Mapping[str, Any],
    history: Mapping[str, Any],
    risk_envelope: Mapping[str, Any],
) -> dict[str, Any]:
    identity_confidence = _mapping(identity.get("confidence"))
    market_confidence = _mapping(market.get("confidence"))
    market_data = _mapping(market.get("data"))
    completeness = _mapping(market_data.get("completeness"))
    tokenomics_data = _mapping(tokenomics.get("data"))
    history_data = _mapping(history.get("data"))
    risk = _mapping(risk_envelope.get("risk"))

    checks = {
        "identity_verified": identity_confidence.get("complete") is True,
        "core_market_complete": (
            market_confidence.get("core_market_complete") is True
            or (
                completeness.get("price") is True
                and completeness.get("liquidity") is True
                and completeness.get("volume_24h") is True
                and completeness.get("transactions_24h") is True
            )
        ),
        "supply_verified": tokenomics_data.get("supply_verified") is True,
        "authorities_verified": (
            tokenomics_data.get("mint_authority_verified") is True
            and tokenomics_data.get("freeze_authority_verified") is True
        ),
        "history_available": (
            int(history_data.get("available_metric_count") or 0) > 0
        ),
        "holder_count_verified": completeness.get("holders") is True,
        "deterministic_risk_available": (
            risk.get("recommendation") in {"PASS", "WARN", "BLOCK"}
        ),
    }
    verified = sum(1 for passed in checks.values() if passed)
    total = len(checks)
    return {
        "complete": verified == total,
        "verified_checks": verified,
        "total_checks": total,
        "verification_ratio": round(verified / total, 6),
        "checks": checks,
    }


def build_instant_x1_scan_response(
    identity_envelope: Mapping[str, Any],
    market_envelope: Mapping[str, Any],
    tokenomics_envelope: Mapping[str, Any],
    history_envelope: Mapping[str, Any],
    risk_envelope: Mapping[str, Any],
) -> dict[str, Any]:
    """Compose one compact read-only X1 scan from existing CMIS envelopes."""

    for name, envelope in (
        ("identity_envelope", identity_envelope),
        ("market_envelope", market_envelope),
        ("tokenomics_envelope", tokenomics_envelope),
        ("history_envelope", history_envelope),
        ("risk_envelope", risk_envelope),
    ):
        if not isinstance(envelope, Mapping):
            raise TypeError(f"{name} must be a mapping")

    market_data = _mapping(market_envelope.get("data"))
    market_asset = _mapping(market_envelope.get("asset"))
    identity_asset = _mapping(identity_envelope.get("asset"))
    asset = {
        "symbol": market_asset.get("symbol") or identity_asset.get("symbol"),
        "name": market_asset.get("name") or identity_asset.get("name"),
        "mint": market_asset.get("mint") or identity_asset.get("mint"),
    }

    confidence = _confidence(
        identity_envelope,
        market_envelope,
        tokenomics_envelope,
        history_envelope,
        risk_envelope,
    )
    risk = (
        dict(risk_envelope["risk"])
        if isinstance(risk_envelope.get("risk"), Mapping)
        else None
    )

    warnings = []
    for envelope, section in (
        (identity_envelope, "identity"),
        (market_envelope, "market"),
        (tokenomics_envelope, "tokenomics"),
        (history_envelope, "history"),
        (risk_envelope, "risk"),
    ):
        warnings.extend(_component_warnings(envelope, section=section))

    if _mapping(market_data.get("completeness")).get("holders") is not True:
        warnings.append({
            "code": "instant_x1_scan_holder_count_unverified",
            "section": "holder_concentration",
            "message": (
                "Verified holder count is unavailable; provider holder-looking "
                "observations remain unverified and are not promoted."
            ),
        })
    warnings.append({
        "code": "instant_x1_scan_current_concentration_unavailable",
        "section": "holder_concentration",
        "message": (
            "Current top-account concentration is not promoted into Instant X1 "
            "Scan v2; internal intelligence foundations are not used as a "
            "public-service shortcut."
        ),
    })

    sources = _merge_sources(
        (identity_envelope, "identity"),
        (market_envelope, "market"),
        (tokenomics_envelope, "tokenomics"),
        (history_envelope, "history"),
        (risk_envelope, "risk"),
    )

    data = {
        "contract_version": CONTRACT_VERSION,
        "read_only": True,
        "sections": {
            "identity": _identity_section(identity_envelope),
            "market": _market_section(market_envelope),
            "tokenomics": _tokenomics_section(tokenomics_envelope),
            "holder_concentration": _holder_concentration_section(
                market_envelope
            ),
            "history": _history_section(history_envelope),
            "risk": _risk_section(risk_envelope),
            "evidence": {
                "component_statuses": {
                    "asset_lookup": _status(identity_envelope),
                    "market_report": _status(market_envelope),
                    "tokenomics": _status(tokenomics_envelope),
                    "historical_compare": _status(history_envelope),
                    "risk_check": _status(risk_envelope),
                },
                "component_source_count": len(sources),
                "proof_score_separate_from_risk": True,
                "runtime_evidence_receipt_post_processing_only": True,
            },
        },
        "limitations": [
            "missing_or_unverified_fields_remain_unknown",
            "holder_count_requires_existing_verified_holder_semantics",
            "current_top_account_concentration_not_promoted_in_v2",
            "history_may_include_bounded_verified_provider_price_backfill",
            "provider_price_backfill_is_price_only",
            "provider_source_independence_not_verified",
            "provider_archive_completeness_not_verified",
            "history_does_not_imply_complete_asset_lifetime",
            "continuous_coverage_requires_separate_archive_completeness_proof",
            "proof_score_does_not_modify_market_facts_or_risk",
            "risk_score_remains_unavailable_until_separately_calibrated",
            "execution_authorized_false",
        ],
        "execution_authorized": False,
    }

    return build_service_envelope(
        SERVICE,
        "x1",
        OK if confidence["complete"] else PARTIAL,
        asset=asset,
        data=data,
        risk=risk,
        confidence=confidence,
        sources=sources,
        observed_at=market_envelope.get("observed_at"),
        warnings=warnings,
        errors=[],
    )


__all__ = [
    "CONTRACT_VERSION",
    "HISTORY_METRICS",
    "SERVICE",
    "build_instant_x1_scan_response",
]
