"""CMIS contract wrapper for deterministic historical comparisons.

The wrapper preserves the existing structured historical comparison and exposes
it through the shared chain-aware CMIS envelope. Historical storage remains an
injected backend and this layer performs no live market collection.
"""

from collections.abc import Mapping
from typing import Any, Dict, Optional

from .cmis_contract import ERROR, OK, PARTIAL, UNAVAILABLE, build_service_envelope
from .historical_compare import build_historical_comparison


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _confidence(comparison: Mapping[str, Any]) -> Dict[str, Any]:
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
        "verification_ratio": round(verified / total, 6),
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


def _sources(comparison: Mapping[str, Any], snapshot: Any) -> list:
    result = []
    current_source = _market_source(snapshot)
    if current_source is not None:
        result.append(current_source)

    source = _text(comparison.get("source"))
    if source:
        record = {"source": source, "role": "historical_compare.baseline"}
        historical_observed_at = comparison.get("historical_observed_at")
        if historical_observed_at is not None:
            record["observed_at"] = historical_observed_at
        if record not in result:
            result.append(record)
    return result


def _warnings(comparison: Mapping[str, Any], confidence: Mapping[str, Any]) -> list:
    warnings = []
    reason = _text(comparison.get("reason"))
    if reason:
        warnings.append({"code": reason})

    checks = confidence.get("checks")
    checks = checks if isinstance(checks, Mapping) else {}
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
    question: str,
    snapshot: Any,
    *,
    history_backend: Any,
    get_total_supply=None,
    chain: str = "x1",
    observed_at: Any = None,
) -> Dict[str, Any]:
    """Return ``historical_compare`` through the shared CMIS contract.

    The structured comparison remains unchanged in ``data`` so it can be passed
    directly to deterministic downstream consumers such as ``risk_check``.
    Legacy snapshots remain presentation-compatible but are not upgraded to
    verified current evidence. Backend or input failures become explicit error
    responses rather than fabricated historical facts.
    """
    query = _text(question)
    if not query:
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
            data={"query": query},
            errors=[{
                "code": "invalid_market_snapshot",
                "message": "snapshot must be a mapping.",
            }],
            observed_at=observed_at,
        )

    try:
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
            data={"query": query},
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
            data={"query": query},
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
        sources=_sources(comparison, snapshot),
        observed_at=effective_observed_at,
        warnings=_warnings(comparison, confidence),
        errors=(
            [{"code": "historical_compare_invalid_status"}]
            if status == ERROR
            else []
        ),
    )


__all__ = ["build_historical_compare_response"]
