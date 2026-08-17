"""CMIS contract wrapper for deterministic pre-trade analysis.

The wrapper accepts either a raw deterministic ``risk_check`` result or the
full CMIS ``risk_check`` envelope. It performs no market collection, routing,
simulation, wallet, signing, or transaction work. A pre-trade PASS/WARN/BLOCK
is analysis only and never authorizes execution.
"""

from collections.abc import Mapping
from typing import Any, Dict, Optional, Tuple

from .cmis_contract import ERROR, OK, PARTIAL, UNAVAILABLE, build_service_envelope
from .pre_trade import build_pre_trade_check


_UNVERIFIED_FLAGS = {
    "risk_chain_unverified",
    "trade_asset_mint_unverified",
    "risk_asset_mint_unverified",
    "risk_evidence_incomplete",
    "trade_notional_unverified",
    "sized_trade_liquidity_unverified",
    "risk_timestamp_unverified_for_freshness",
    "evaluation_timestamp_unverified_for_freshness",
    "risk_timestamp_after_evaluation",
}


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _copy_records(value: Any) -> list:
    if not isinstance(value, list):
        return []
    return [dict(item) if isinstance(item, Mapping) else item for item in value]


def _append_source(sources: list, source: str, role: str) -> None:
    record = {"source": source, "role": role}
    if record not in sources:
        sources.append(record)


def _extract_risk_input(value: Any) -> Tuple[Optional[Mapping[str, Any]], Optional[Mapping[str, Any]]]:
    """Return ``(risk_result, risk_envelope)`` for raw or CMIS risk input."""
    if not isinstance(value, Mapping):
        return None, None

    if _text(value.get("service")) == "risk_check":
        risk = value.get("risk")
        return (risk if isinstance(risk, Mapping) else None), value

    return value, None


def _asset_from_trade(trade: Any) -> Dict[str, Any]:
    if not isinstance(trade, Mapping):
        return {}
    asset = trade.get("asset")
    if not isinstance(asset, Mapping):
        return {}
    return {
        "symbol": _text(asset.get("symbol")),
        "mint": _text(asset.get("mint") or asset.get("address")),
    }


def _warnings(result: Mapping[str, Any]) -> list:
    flags = result.get("flags")
    reasons = result.get("reasons")
    flag_list = list(flags) if isinstance(flags, list) else []
    reason_list = list(reasons) if isinstance(reasons, list) else []
    warnings = []
    for index, flag in enumerate(flag_list):
        warning = {"code": str(flag)}
        if index < len(reason_list) and reason_list[index]:
            warning["message"] = str(reason_list[index])
        warnings.append(warning)
    return warnings


def _service_status(result: Mapping[str, Any]) -> str:
    """Separate service completeness from PASS/WARN/BLOCK severity.

    Verified threshold breaches are successful deterministic findings and remain
    ``ok``. Only flags representing missing, invalid, or temporally inconsistent
    required evidence make the service ``partial``.
    """
    flags = result.get("flags")
    flag_set = {str(flag) for flag in flags} if isinstance(flags, list) else set()
    return PARTIAL if flag_set.intersection(_UNVERIFIED_FLAGS) else OK


def _upstream_failure_response(
    envelope: Mapping[str, Any],
    *,
    chain: str,
    trade: Any,
    observed_at: Any,
) -> Optional[Dict[str, Any]]:
    status = (_text(envelope.get("status")) or "").lower()
    effective_observed_at = (
        observed_at if observed_at is not None else envelope.get("observed_at")
    )
    sources = _copy_records(envelope.get("sources"))

    if status == UNAVAILABLE:
        return build_service_envelope(
            "pre_trade_check",
            chain,
            UNAVAILABLE,
            asset=_asset_from_trade(trade),
            data={"trade": dict(trade) if isinstance(trade, Mapping) else {}},
            sources=sources,
            observed_at=effective_observed_at,
            warnings=_copy_records(envelope.get("warnings")) or [{
                "code": "risk_check_unavailable",
                "message": "A deterministic risk_check result is required for pre_trade_check.",
            }],
        )

    if status == ERROR:
        return build_service_envelope(
            "pre_trade_check",
            chain,
            ERROR,
            asset=_asset_from_trade(trade),
            data={"trade": dict(trade) if isinstance(trade, Mapping) else {}},
            sources=sources,
            observed_at=effective_observed_at,
            errors=_copy_records(envelope.get("errors")) or [{
                "code": "risk_check_error",
                "message": "The upstream risk_check service returned an error.",
            }],
        )

    return None


def build_pre_trade_check_response(
    risk_result: Any,
    trade: Any,
    *,
    chain: str = "x1",
    policy: Optional[Mapping[str, Any]] = None,
    risk_observed_at: Any = None,
    evaluated_at: Any = None,
    observed_at: Any = None,
) -> Dict[str, Any]:
    """Return ``pre_trade_check`` through the shared CMIS service contract.

    For a full CMIS risk envelope, the envelope's ``observed_at`` is the risk
    evidence timestamp used by freshness analysis. The output envelope's
    optional ``observed_at`` override is presentation/provenance metadata only
    and never substitutes for the evidence timestamp.
    """
    if risk_result is None:
        return build_service_envelope(
            "pre_trade_check",
            chain,
            UNAVAILABLE,
            asset=_asset_from_trade(trade),
            data={"trade": dict(trade) if isinstance(trade, Mapping) else {}},
            warnings=[{
                "code": "risk_check_unavailable",
                "message": "A deterministic risk_check result is required for pre_trade_check.",
            }],
            observed_at=observed_at,
        )

    if not isinstance(risk_result, Mapping):
        return build_service_envelope(
            "pre_trade_check",
            chain,
            ERROR,
            asset=_asset_from_trade(trade),
            errors=[{
                "code": "invalid_risk_result",
                "message": "risk_result must be a mapping, CMIS risk_check envelope, or None.",
            }],
            observed_at=observed_at,
        )

    if not isinstance(trade, Mapping):
        return build_service_envelope(
            "pre_trade_check",
            chain,
            ERROR,
            errors=[{
                "code": "invalid_trade_context",
                "message": "trade must be a mapping.",
            }],
            observed_at=observed_at,
        )

    raw_risk, risk_envelope = _extract_risk_input(risk_result)
    if risk_envelope is not None:
        failure = _upstream_failure_response(
            risk_envelope,
            chain=chain,
            trade=trade,
            observed_at=observed_at,
        )
        if failure is not None:
            return failure
        if raw_risk is None:
            return build_service_envelope(
                "pre_trade_check",
                chain,
                ERROR,
                asset=_asset_from_trade(trade),
                data={"trade": dict(trade)},
                sources=_copy_records(risk_envelope.get("sources")),
                observed_at=(
                    observed_at
                    if observed_at is not None
                    else risk_envelope.get("observed_at")
                ),
                errors=[{
                    "code": "invalid_risk_check_envelope",
                    "message": "The CMIS risk_check envelope does not contain a risk result.",
                }],
            )

    if raw_risk is None:
        return build_service_envelope(
            "pre_trade_check",
            chain,
            ERROR,
            asset=_asset_from_trade(trade),
            errors=[{
                "code": "invalid_risk_result",
                "message": "The supplied risk input does not contain a deterministic risk result.",
            }],
            observed_at=observed_at,
        )

    effective_risk_observed_at = (
        risk_envelope.get("observed_at")
        if risk_envelope is not None
        else risk_observed_at
    )

    try:
        result = build_pre_trade_check(
            raw_risk,
            trade,
            chain=chain,
            policy=policy,
            risk_observed_at=effective_risk_observed_at,
            evaluated_at=evaluated_at,
        )
    except ValueError as exc:
        sources = _copy_records(risk_envelope.get("sources")) if risk_envelope else []
        return build_service_envelope(
            "pre_trade_check",
            chain,
            ERROR,
            asset=_asset_from_trade(trade),
            data={"trade": dict(trade)},
            sources=sources,
            observed_at=(
                observed_at
                if observed_at is not None
                else (risk_envelope.get("observed_at") if risk_envelope else None)
            ),
            errors=[{
                "code": "pre_trade_check_validation_error",
                "message": str(exc),
            }],
        )

    sources = _copy_records(risk_envelope.get("sources")) if risk_envelope else []
    _append_source(sources, "pre_trade_engine", "pre_trade_check")
    effective_observed_at = (
        observed_at
        if observed_at is not None
        else (risk_envelope.get("observed_at") if risk_envelope else None)
    )

    return build_service_envelope(
        "pre_trade_check",
        result.get("chain") or chain,
        _service_status(result),
        asset=result.get("asset"),
        data={
            "trade": result.get("trade") or {},
            "risk_observed_at": result.get("risk_observed_at"),
            "evaluated_at": result.get("evaluated_at"),
            "analysis_only": result.get("analysis_only") is True,
            "execution_authorized": result.get("execution_authorized") is True,
        },
        risk=result,
        confidence=result.get("confidence"),
        sources=sources,
        observed_at=effective_observed_at,
        warnings=_warnings(result),
        errors=[],
    )


__all__ = ["build_pre_trade_check_response"]
