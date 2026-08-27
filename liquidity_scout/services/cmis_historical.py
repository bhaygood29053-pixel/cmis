"""CMIS contract wrapper for deterministic historical comparisons.

The wrapper preserves the existing structured historical comparison and exposes
it through the shared chain-aware CMIS envelope. Historical storage remains an
injected backend and this layer performs no live market collection.
"""

from collections.abc import Mapping
from typing import Any, Dict, Optional

from .cmis_contract import ERROR, OK, PARTIAL, UNAVAILABLE, build_service_envelope
from .historical_compare import (
    build_all_available_history_profile,
    build_all_available_pair_comparison,
    build_historical_comparison,
)


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _confidence(comparison: Mapping[str, Any]) -> Dict[str, Any]:
    mode = _text(comparison.get("mode")) or "window"
    if mode == "all_available":
        checks = {
            "verified_history_available": comparison.get("available_metric_count", 0) > 0,
            "multi_point_history_available": comparison.get("multi_point_metric_count", 0) > 0,
            "full_asset_lifetime_verified": comparison.get("full_asset_lifetime_verified") is True,
        }
    elif mode == "all_available_pair":
        checks = {
            "primary_verified_history_available": (
                (comparison.get("primary_profile") or {}).get("available_metric_count", 0) > 0
                if isinstance(comparison.get("primary_profile"), Mapping)
                else False
            ),
            "secondary_verified_history_available": (
                (comparison.get("secondary_profile") or {}).get("available_metric_count", 0) > 0
                if isinstance(comparison.get("secondary_profile"), Mapping)
                else False
            ),
            "common_verified_history_comparable": comparison.get("comparable_metric_count", 0) > 0,
            "full_asset_lifetime_verified": comparison.get("full_asset_lifetime_verified") is True,
        }
    else:
        current_verified = comparison.get("current_verified") is True
        historical_verified = comparison.get("historical_verified") is True
        change_verified = (
            current_verified
            and historical_verified
            and comparison.get("change_pct") is not None
        )
        checks = {
            "current_metric_verified": current_verified,
            "historical_metric_verified": historical_verified,
            "change_verified": change_verified,
        }

    verified = sum(1 for value in checks.values() if value)
    total = len(checks)
    return {
        "complete": verified == total,
        "verified_checks": verified,
        "total_checks": total,
        "verification_ratio": round(verified / total, 6) if total else 0.0,
        "checks": checks,
    }


def _market_source(snapshot: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(snapshot, Mapping):
        return None
    report = snapshot.get("_market_report")
    if not isinstance(report, Mapping):
        return None
    provenance = report.get("provenance")
    if not isinstance(provenance, Mapping):
        return None
    source = _text(provenance.get("source"))
    if not source:
        return None
    record = {"source": source, "role": "historical_compare.current"}
    observed_at = provenance.get("catalog_last_refresh_unix")
    if observed_at is not None:
        record["observed_at"] = observed_at
    return record


def _sources(
    comparison: Mapping[str, Any],
    snapshot: Any,
    compare_snapshot: Any = None,
) -> list:
    result = []
    current_source = _market_source(snapshot)
    if current_source is not None:
        result.append(current_source)

    compare_source = _market_source(compare_snapshot)
    if compare_source is not None:
        compare_source["role"] = "historical_compare.compare_current"
        if compare_source not in result:
            result.append(compare_source)

    source = _text(comparison.get("source"))
    if source:
        mode = _text(comparison.get("mode")) or "window"
        role = (
            "historical_compare.baseline"
            if mode == "window"
            else f"historical_compare.{mode}"
        )
        record = {"source": source, "role": role}
        historical_observed_at = comparison.get("historical_observed_at")
        if historical_observed_at is not None:
            record["observed_at"] = historical_observed_at
        first = comparison.get("first_verified_observed_at")
        last = comparison.get("last_verified_observed_at")
        if first is not None:
            record["first_observed_at"] = first
        if last is not None:
            record["last_observed_at"] = last
        if record not in result:
            result.append(record)
    return result


def _warnings(comparison: Mapping[str, Any], confidence: Mapping[str, Any]) -> list:
    warnings = []
    reason = _text(comparison.get("reason"))
    if reason:
        warnings.append({"code": reason})

    mode = _text(comparison.get("mode")) or "window"
    checks = confidence.get("checks")
    checks = checks if isinstance(checks, Mapping) else {}

    if mode in {"all_available", "all_available_pair"}:
        limitations = comparison.get("limitations")
        if isinstance(limitations, list):
            for item in limitations:
                code = _text(item)
                if code:
                    warnings.append({"code": code})
        if comparison.get("full_asset_lifetime_verified") is not True:
            warnings.append({
                "code": "asset_lifetime_coverage_unverified",
                "message": (
                    "All-available history is bounded to verified CMIS observations; "
                    "it is not proof of the asset's complete lifetime."
                ),
            })
        return warnings

    messages = {
        "current_metric_verified": "Current comparison value is not verified.",
        "historical_metric_verified": "Historical baseline value is not verified.",
        "change_verified": "Historical percentage change is not verified.",
    }
    for key, message in messages.items():
        if checks.get(key) is not True and not any(item.get("code") == key for item in warnings):
            warnings.append({"code": key, "message": message})
    return warnings


def _service_status(comparison: Mapping[str, Any]) -> str:
    status = _text(comparison.get("status"))
    if status == "ok":
        return OK
    if status == "partial":
        return PARTIAL
    if status == "unavailable":
        return UNAVAILABLE
    return ERROR


def build_historical_compare_response(
    question: str | None,
    snapshot: Any,
    *,
    history_backend: Any,
    get_total_supply=None,
    chain: str = "x1",
    observed_at: Any = None,
    mode: str = "window",
    compare_snapshot: Any = None,
    metrics: Any = None,
    gap_threshold_seconds: int = 129600,
    anchor_tolerance_seconds: int = 21600,
) -> Dict[str, Any]:
    """Return deterministic window or all-available history through CMIS."""

    normalized_mode = (_text(mode) or "window").lower()
    if normalized_mode not in {"window", "all_available", "all_available_pair"}:
        return build_service_envelope(
            "historical_compare",
            chain,
            ERROR,
            errors=[{
                "code": "historical_mode_invalid",
                "message": (
                    "mode must be one of: window, all_available, all_available_pair"
                ),
            }],
            observed_at=observed_at,
        )

    query = _text(question)
    if normalized_mode == "window" and not query:
        return build_service_envelope(
            "historical_compare",
            chain,
            ERROR,
            errors=[{
                "code": "historical_query_required",
                "message": "A historical comparison request is required.",
            }],
            observed_at=observed_at,
        )

    if not isinstance(snapshot, Mapping):
        return build_service_envelope(
            "historical_compare",
            chain,
            ERROR,
            data={"query": query, "mode": normalized_mode},
            errors=[{
                "code": "invalid_market_snapshot",
                "message": "snapshot must be a mapping.",
            }],
            observed_at=observed_at,
        )

    if normalized_mode == "all_available_pair" and not isinstance(compare_snapshot, Mapping):
        return build_service_envelope(
            "historical_compare",
            chain,
            ERROR,
            data={"query": query, "mode": normalized_mode},
            errors=[{
                "code": "compare_market_snapshot_required",
                "message": "all_available_pair requires a second verified market snapshot.",
            }],
            observed_at=observed_at,
        )

    try:
        if normalized_mode == "all_available":
            comparison = build_all_available_history_profile(
                dict(snapshot),
                history_backend=history_backend,
                get_total_supply=get_total_supply,
                metrics=metrics,
                gap_threshold_seconds=gap_threshold_seconds,
            )
        elif normalized_mode == "all_available_pair":
            comparison = build_all_available_pair_comparison(
                dict(snapshot),
                dict(compare_snapshot),
                history_backend=history_backend,
                get_total_supply=get_total_supply,
                metrics=metrics,
                gap_threshold_seconds=gap_threshold_seconds,
                anchor_tolerance_seconds=anchor_tolerance_seconds,
            )
        else:
            comparison = build_historical_comparison(
                query,
                dict(snapshot),
                history_backend=history_backend,
                get_total_supply=get_total_supply,
            )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return build_service_envelope(
            "historical_compare",
            chain,
            ERROR,
            data={"query": query, "mode": normalized_mode},
            errors=[{
                "code": "historical_compare_validation_error",
                "message": str(exc),
            }],
            observed_at=observed_at,
        )

    if comparison is None:
        return build_service_envelope(
            "historical_compare",
            chain,
            ERROR,
            data={"query": query, "mode": normalized_mode},
            errors=[{
                "code": "historical_request_unrecognized",
                "message": "The historical backend did not recognize the comparison request.",
            }],
            observed_at=observed_at,
        )

    confidence = _confidence(comparison)
    status = _service_status(comparison)
    effective_observed_at = (
        observed_at
        if observed_at is not None
        else comparison.get("current_observed_at")
    )

    return build_service_envelope(
        "historical_compare",
        chain,
        status,
        asset=comparison.get("asset"),
        data=comparison,
        risk=None,
        confidence=confidence,
        sources=_sources(comparison, snapshot, compare_snapshot),
        observed_at=effective_observed_at,
        warnings=_warnings(comparison, confidence),
        errors=(
            [{"code": "historical_compare_invalid_status"}]
            if status == ERROR
            else []
        ),
    )


__all__ = ["build_historical_compare_response"]
