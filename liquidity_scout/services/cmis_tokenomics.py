"""CMIS contract wrapper for deterministic tokenomics facts.

The wrapper preserves the existing tokenomics service and exposes its verified
current RPC facts plus separately supplied bounded mint/burn activity and
independently verified circulating-supply exclusion evidence through the shared
chain-aware CMIS envelope. It does not infer circulating supply from burns or
wallet balances, and it does not infer maximum supply or lifetime coverage.
"""

from collections.abc import Mapping
from typing import Any, Dict, Optional

from .cmis_contract import ERROR, OK, PARTIAL, UNAVAILABLE, build_service_envelope
from .tokenomics import build_tokenomics_report


_CHECK_KEYS = (
    "supply_verified",
    "mint_authority_verified",
    "freeze_authority_verified",
    "token_activity_verified",
)


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _confidence(report: Mapping[str, Any]) -> Dict[str, Any]:
    activity = report.get("token_activity")
    activity = activity if isinstance(activity, Mapping) else {}
    checks = {
        "supply_verified": report.get("supply_verified") is True,
        "mint_authority_verified": report.get("mint_authority_verified") is True,
        "freeze_authority_verified": report.get("freeze_authority_verified") is True,
        "token_activity_verified": (
            activity.get("available") is True
            and activity.get("activity_verified") is True
        ),
    }
    verified = sum(1 for value in checks.values() if value)
    total = len(_CHECK_KEYS)
    return {
        "complete": verified == total,
        "verified_checks": verified,
        "total_checks": total,
        "verification_ratio": round(verified / total, 6),
        "checks": checks,
    }


def _source_records(report: Mapping[str, Any]) -> list:
    result = []
    sources = report.get("sources")
    if not isinstance(sources, Mapping):
        return result

    for role, source in sources.items():
        source_name = _text(source)
        if not source_name:
            continue
        record = {"source": source_name, "role": f"tokenomics.{role}"}
        if record not in result:
            result.append(record)
    return result


def _warnings(report: Mapping[str, Any]) -> list:
    warnings = []

    unavailable_reasons = report.get("unavailable_reasons")
    if isinstance(unavailable_reasons, list):
        for reason in unavailable_reasons:
            code = _text(reason)
            if code:
                warnings.append({"code": code})

    activity = report.get("token_activity")
    activity = activity if isinstance(activity, Mapping) else {}
    verification_reasons = activity.get("verification_reasons")
    if isinstance(verification_reasons, list):
        for reason in verification_reasons:
            code = _text(reason)
            if code and not any(item.get("code") == code for item in warnings):
                warnings.append({"code": code})

    if activity.get("available") is True and activity.get("lifetime_coverage_verified") is not True:
        warnings.append({
            "code": "lifetime_coverage_unverified",
            "message": (
                "Bounded mint/burn activity may be verified, but chain-lifetime "
                "coverage is not independently verified."
            ),
        })

    burn_metrics = report.get("burn_metrics")
    burn_metrics = burn_metrics if isinstance(burn_metrics, Mapping) else {}
    if burn_metrics.get("available") is not True:
        warnings.append({
            "code": "burn_metrics_unavailable",
            "message": (
                "Deterministic burn-window metrics are unavailable because "
                "verified scanner fact-time coverage or event payloads are missing."
            ),
            "reason": _text(burn_metrics.get("reason")),
        })
    else:
        if burn_metrics.get("status") == "partial":
            warnings.append({
                "code": "burn_metrics_partial",
                "message": (
                    "Burn intelligence is only partially complete; independent "
                    "supply and/or historical valuation layers remain unavailable."
                ),
                "reasons": list(burn_metrics.get("partial_reasons") or []),
            })

        unavailable_windows = list(
            burn_metrics.get("unavailable_windows") or []
        )
        unavailable_comparisons = list(
            burn_metrics.get("unavailable_comparisons") or []
        )
        if unavailable_windows or unavailable_comparisons:
            warnings.append({
                "code": "burn_metrics_window_coverage_partial",
                "message": (
                    "Burn metrics were computed, but one or more requested "
                    "time windows or prior-period comparisons lack sufficient "
                    "verified coverage."
                ),
                "windows": unavailable_windows,
                "comparisons": unavailable_comparisons,
            })

    if report.get("circulating_supply_verified") is not True:
        circulating = report.get("circulating_supply_details")
        circulating = circulating if isinstance(circulating, Mapping) else {}
        warnings.append({
            "code": "circulating_supply_unverified",
            "message": (
                "Circulating supply is unavailable unless a complete, "
                "independently verified exclusion contract is supplied."
            ),
            "reason": _text(circulating.get("reason")),
        })
    if report.get("maximum_supply_verified") is not True:
        warnings.append({
            "code": "maximum_supply_unverified",
            "message": "Maximum supply is not independently verified by this service.",
        })
    return warnings


def _status(report: Mapping[str, Any], confidence: Mapping[str, Any]) -> str:
    if confidence.get("complete") is True:
        return OK

    # If none of the current RPC facts nor bounded activity can be verified, the
    # tokenomics service has no verified substantive result to expose.
    if confidence.get("verified_checks") == 0:
        return UNAVAILABLE
    return PARTIAL


def build_tokenomics_response(
    mint: Any,
    *,
    symbol: Any = None,
    name: Any = None,
    chain: str = "x1",
    observed_at: Any = None,
    rpc_url: Any = None,
    get_token_supply=None,
    get_mint_info=None,
    activity_report: Optional[Mapping[str, Any]] = None,
    circulating_supply_report: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return ``tokenomics`` through the shared CMIS response contract.

    Current supply and authority facts come from the existing deterministic
    tokenomics service. Bounded mint/burn activity remains a separately supplied
    scanner result. Circulating supply is accepted only through a separately
    supplied verified exclusion contract. A complete bounded result is ``ok``
    even when optional circulating/maximum supply enrichment is unavailable.
    Missing core verification becomes ``partial`` or ``unavailable``;
    validation failures become ``error``.
    """
    mint_text = _text(mint)
    if not mint_text:
        return build_service_envelope(
            "tokenomics",
            chain,
            ERROR,
            errors=[{
                "code": "token_mint_required",
                "message": "A token mint is required for tokenomics.",
            }],
            observed_at=observed_at,
        )

    kwargs = {
        "symbol": symbol,
        "name": name,
        "activity_report": activity_report,
        "circulating_supply_report": circulating_supply_report,
    }
    if rpc_url is not None:
        kwargs["rpc_url"] = rpc_url
    if get_token_supply is not None:
        kwargs["get_token_supply"] = get_token_supply
    if get_mint_info is not None:
        kwargs["get_mint_info"] = get_mint_info

    try:
        report = build_tokenomics_report(mint_text, **kwargs)
    except (TypeError, ValueError) as exc:
        return build_service_envelope(
            "tokenomics",
            chain,
            ERROR,
            asset={"symbol": _text(symbol), "name": _text(name), "mint": mint_text},
            observed_at=observed_at,
            errors=[{
                "code": "tokenomics_validation_error",
                "message": str(exc),
            }],
        )

    confidence = _confidence(report)
    return build_service_envelope(
        "tokenomics",
        chain,
        _status(report, confidence),
        asset={
            "symbol": report.get("symbol"),
            "name": report.get("name"),
            "mint": report.get("mint"),
        },
        data=report,
        risk=None,
        confidence=confidence,
        sources=_source_records(report),
        observed_at=observed_at,
        warnings=_warnings(report),
        errors=[],
    )


__all__ = ["build_tokenomics_response"]
