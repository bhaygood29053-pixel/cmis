"""CMIS contract wrapper for the deterministic risk_check core.

The wrapper does not collect market data. It translates already-structured
market, tokenomics, and historical reports into the shared CMIS response
envelope while preserving the underlying Risk Engine result verbatim.
"""

from typing import Any, Dict, Mapping, Optional

from .cmis_contract import ERROR, OK, PARTIAL, UNAVAILABLE, build_service_envelope
from .risk import build_risk_check


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _asset_from_market(market_report: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(market_report, Mapping):
        return {}
    return {
        "symbol": _text(market_report.get("symbol")),
        "mint": _text(market_report.get("mint")),
    }


def _append_source(
    sources: list,
    source: Any,
    *,
    role: str,
    observed_at: Any = None,
) -> None:
    source_name = _text(source)
    if not source_name:
        return
    record = {"source": source_name, "role": role}
    if observed_at is not None:
        record["observed_at"] = observed_at
    if record not in sources:
        sources.append(record)


def _sources(
    market_report: Mapping[str, Any],
    tokenomics_report: Optional[Mapping[str, Any]],
    historical_report: Optional[Mapping[str, Any]],
) -> list:
    result = []

    provenance = market_report.get("provenance")
    if isinstance(provenance, Mapping):
        _append_source(
            result,
            provenance.get("source"),
            role="market_report",
            observed_at=provenance.get("catalog_last_refresh_unix"),
        )

    if isinstance(tokenomics_report, Mapping):
        token_sources = tokenomics_report.get("sources")
        if isinstance(token_sources, Mapping):
            for role, source in token_sources.items():
                _append_source(
                    result,
                    source,
                    role=f"tokenomics.{role}",
                )

    if isinstance(historical_report, Mapping):
        _append_source(
            result,
            historical_report.get("source"),
            role="historical_compare",
            observed_at=historical_report.get("current_observed_at"),
        )

    # The deterministic calculation layer itself is always part of the result
    # provenance, independent of which external sources were available.
    _append_source(result, "risk_engine", role="risk_check")
    return result


def _warnings(
    risk_result: Mapping[str, Any],
    tokenomics_report: Optional[Mapping[str, Any]] = None,
) -> list:
    flags = risk_result.get("flags")
    reasons = risk_result.get("reasons")
    flag_list = list(flags) if isinstance(flags, list) else []
    reason_list = list(reasons) if isinstance(reasons, list) else []
    native_asset = (
        isinstance(tokenomics_report, Mapping)
        and tokenomics_report.get("asset_type") == "native"
    )

    warnings = []
    for index, flag in enumerate(flag_list):
        warning = {"code": str(flag)}
        if index < len(reason_list) and reason_list[index]:
            message = str(reason_list[index])
            if (
                native_asset
                and str(flag) == "token_activity_unavailable"
                and message == "Verified bounded mint/burn activity was not supplied."
            ):
                message = "Verified native-network issuance/burn activity was not supplied."
            warning["message"] = message
        warnings.append(warning)
    return warnings


def _service_status(risk_result: Mapping[str, Any]) -> str:
    confidence = risk_result.get("confidence")
    if not isinstance(confidence, Mapping):
        return PARTIAL
    verified = confidence.get("verified_checks")
    total = confidence.get("total_checks")
    if isinstance(verified, int) and isinstance(total, int) and total > 0:
        return OK if verified == total else PARTIAL
    return PARTIAL


def build_risk_check_response(
    market_report: Optional[Mapping[str, Any]],
    tokenomics_report: Optional[Mapping[str, Any]] = None,
    historical_report: Optional[Mapping[str, Any]] = None,
    freshness_report: Optional[Mapping[str, Any]] = None,
    *,
    chain: str = "x1",
    policy: Optional[Mapping[str, Any]] = None,
    observed_at: Any = None,
) -> Dict[str, Any]:
    """Return ``risk_check`` through the shared CMIS service contract.

    A fully verified WARN or BLOCK remains service status ``ok`` because the
    request succeeded and the risk outcome is itself a verified result. Service
    status ``partial`` means one or more verification checks are incomplete.
    Missing required market input returns ``unavailable``. Deterministic input
    validation failures return ``error`` rather than escaping as fabricated
    results.
    """
    if market_report is None:
        return build_service_envelope(
            "risk_check",
            chain,
            UNAVAILABLE,
            asset={},
            warnings=[{
                "code": "market_report_unavailable",
                "message": "A verified market report is required for risk_check.",
            }],
            observed_at=observed_at,
        )

    if not isinstance(market_report, Mapping):
        return build_service_envelope(
            "risk_check",
            chain,
            ERROR,
            asset={},
            errors=[{
                "code": "invalid_market_report",
                "message": "market_report must be a mapping or None.",
            }],
            observed_at=observed_at,
        )

    try:
        risk_result = build_risk_check(
            market_report,
            tokenomics_report,
            historical_report,
            freshness_report,
            chain=chain,
            policy=policy,
        )
    except ValueError as exc:
        return build_service_envelope(
            "risk_check",
            chain,
            ERROR,
            asset=_asset_from_market(market_report),
            sources=_sources(market_report, tokenomics_report, historical_report),
            observed_at=observed_at,
            errors=[{
                "code": "risk_check_validation_error",
                "message": str(exc),
            }],
        )

    return build_service_envelope(
        "risk_check",
        risk_result.get("chain") or chain,
        _service_status(risk_result),
        asset=risk_result.get("asset"),
        data={},
        risk=risk_result,
        confidence=risk_result.get("confidence"),
        sources=_sources(market_report, tokenomics_report, historical_report),
        observed_at=observed_at,
        freshness=(freshness_report if isinstance(freshness_report, Mapping) else None),
        warnings=_warnings(risk_result, tokenomics_report),
        errors=[],
    )


__all__ = ["build_risk_check_response"]
