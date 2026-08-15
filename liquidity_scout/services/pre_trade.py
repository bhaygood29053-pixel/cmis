"""Deterministic pre-trade analysis over an existing CMIS risk result.

This module performs no RPC, DEX, routing, simulation, wallet, signing, or
transaction work. It consumes an already-computed deterministic ``risk_check``
result plus proposed trade context and applies fail-closed identity/chain gates.

The result is analysis only. ``PASS`` never authorizes execution, and this core
intentionally does not invent trade-size, slippage, price-impact, fee, or route
thresholds before those policies and calculation methods are explicitly defined
and tested.
"""

from typing import Any, Dict, Mapping, Optional

from .risk import BLOCK, PASS, WARN


_STATUS_ORDER = {PASS: 0, WARN: 1, BLOCK: 2}
_ALLOWED_SIDES = {"buy", "sell"}


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    if number in (float("inf"), float("-inf")):
        return None
    return number


def _merge_status(*statuses: str) -> str:
    if not statuses:
        return PASS
    return max(statuses, key=lambda status: _STATUS_ORDER[status])


def _component(
    status: str,
    *,
    flags=None,
    reasons=None,
    evidence=None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "flags": list(flags or []),
        "reasons": list(reasons or []),
        "evidence": dict(evidence or {}),
    }


def _risk_confidence_complete(risk_result: Mapping[str, Any]) -> bool:
    confidence = risk_result.get("confidence")
    if not isinstance(confidence, Mapping):
        return False
    verified = confidence.get("verified_checks")
    total = confidence.get("total_checks")
    return (
        isinstance(verified, int)
        and not isinstance(verified, bool)
        and isinstance(total, int)
        and not isinstance(total, bool)
        and total > 0
        and verified == total
    )


def _normalize_trade(trade: Mapping[str, Any]) -> Dict[str, Any]:
    side = (_text(trade.get("side")) or "").lower()
    if side not in _ALLOWED_SIDES:
        raise ValueError("trade side must be 'buy' or 'sell'")

    asset = trade.get("asset")
    if not isinstance(asset, Mapping):
        raise ValueError("trade asset must be a mapping")

    notional = None
    if "notional_usd" in trade and trade.get("notional_usd") is not None:
        notional = _number(trade.get("notional_usd"))
        if notional is None or notional <= 0:
            raise ValueError("trade notional_usd must be a positive finite number when supplied")

    return {
        "side": side,
        "chain": (_text(trade.get("chain")) or "").lower() or None,
        "asset": {
            "symbol": _text(asset.get("symbol")),
            "mint": _text(asset.get("mint") or asset.get("address")),
        },
        "notional_usd": notional,
    }


def _assess_identity(
    risk_result: Mapping[str, Any],
    trade: Mapping[str, Any],
    target_chain: str,
) -> Dict[str, Any]:
    flags = []
    reasons = []

    risk_chain = (_text(risk_result.get("chain")) or "").lower() or None
    trade_chain = trade.get("chain")
    risk_asset = risk_result.get("asset")
    risk_asset = risk_asset if isinstance(risk_asset, Mapping) else {}
    trade_asset = trade.get("asset")
    trade_asset = trade_asset if isinstance(trade_asset, Mapping) else {}

    risk_mint = _text(risk_asset.get("mint") or risk_asset.get("address"))
    trade_mint = _text(trade_asset.get("mint") or trade_asset.get("address"))

    if not risk_chain:
        flags.append("risk_chain_unverified")
        reasons.append("The supplied risk result does not identify a verified target chain.")
    elif risk_chain != target_chain:
        flags.append("risk_chain_mismatch")
        reasons.append("The supplied risk result was produced for a different chain.")

    if trade_chain and trade_chain != target_chain:
        flags.append("trade_chain_mismatch")
        reasons.append("The proposed trade context identifies a different chain.")

    if not trade_mint:
        flags.append("trade_asset_mint_unverified")
        reasons.append("The proposed trade asset does not contain a mint/address identity.")
    if not risk_mint:
        flags.append("risk_asset_mint_unverified")
        reasons.append("The supplied risk result does not contain a mint/address identity.")
    if trade_mint and risk_mint and trade_mint != risk_mint:
        flags.append("trade_asset_mismatch")
        reasons.append("The proposed trade asset does not match the asset assessed by risk_check.")

    evidence = {
        "target_chain": target_chain,
        "risk_chain": risk_chain,
        "trade_chain": trade_chain,
        "risk_mint": risk_mint,
        "trade_mint": trade_mint,
        "mint_match": bool(trade_mint and risk_mint and trade_mint == risk_mint),
    }

    return _component(
        BLOCK if flags else PASS,
        flags=flags,
        reasons=reasons,
        evidence=evidence,
    )


def _assess_risk_gate(risk_result: Mapping[str, Any]) -> Dict[str, Any]:
    recommendation = _text(risk_result.get("recommendation"))
    if recommendation not in _STATUS_ORDER:
        raise ValueError("risk_result recommendation must be PASS, WARN, or BLOCK")

    confidence_complete = _risk_confidence_complete(risk_result)
    flags = []
    reasons = []

    if recommendation == BLOCK:
        flags.append("risk_check_block")
        reasons.append("The deterministic risk_check outcome is BLOCK.")
    elif recommendation == WARN:
        flags.append("risk_check_warn")
        reasons.append("The deterministic risk_check outcome is WARN.")

    if not confidence_complete:
        flags.append("risk_evidence_incomplete")
        reasons.append("The supplied risk_check result does not have complete verification coverage.")

    status = recommendation
    if not confidence_complete:
        status = _merge_status(status, WARN)

    return _component(
        status,
        flags=flags,
        reasons=reasons,
        evidence={
            "risk_recommendation": recommendation,
            "risk_confidence_complete": confidence_complete,
            "risk_confidence": (
                dict(risk_result.get("confidence"))
                if isinstance(risk_result.get("confidence"), Mapping)
                else {}
            ),
        },
    )


def _confidence(
    identity_component: Mapping[str, Any],
    risk_component: Mapping[str, Any],
) -> Dict[str, Any]:
    identity_evidence = identity_component.get("evidence")
    identity_evidence = identity_evidence if isinstance(identity_evidence, Mapping) else {}
    risk_evidence = risk_component.get("evidence")
    risk_evidence = risk_evidence if isinstance(risk_evidence, Mapping) else {}

    checks = {
        "chain_consistent": identity_component.get("status") != BLOCK
        or not any(
            flag in {"risk_chain_unverified", "risk_chain_mismatch", "trade_chain_mismatch"}
            for flag in identity_component.get("flags", [])
        ),
        "trade_asset_mint_verified": bool(identity_evidence.get("trade_mint")),
        "risk_asset_mint_verified": bool(identity_evidence.get("risk_mint")),
        "asset_identity_matches": identity_evidence.get("mint_match") is True,
        "risk_evidence_complete": risk_evidence.get("risk_confidence_complete") is True,
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


def build_pre_trade_check(
    risk_result: Mapping[str, Any],
    trade: Mapping[str, Any],
    *,
    chain: str = "x1",
) -> Dict[str, Any]:
    """Evaluate deterministic pre-trade gates without authorizing execution.

    The core propagates the existing ``risk_check`` severity, blocks chain or
    mint mismatches, and warns when the supplied risk evidence is incomplete.
    Trade notional may be carried as context, but this milestone does not use it
    to calculate slippage, price impact, or a safe-size threshold.
    """
    if not isinstance(risk_result, Mapping):
        raise ValueError("risk_result must be a mapping")
    if not isinstance(trade, Mapping):
        raise ValueError("trade must be a mapping")

    chain_name = (_text(chain) or "").lower()
    if not chain_name:
        raise ValueError("chain is required")

    normalized_trade = _normalize_trade(trade)
    identity = _assess_identity(risk_result, normalized_trade, chain_name)
    risk_gate = _assess_risk_gate(risk_result)
    components = {
        "identity": identity,
        "risk_gate": risk_gate,
    }
    recommendation = _merge_status(identity["status"], risk_gate["status"])

    flags = []
    reasons = []
    for name in ("identity", "risk_gate"):
        flags.extend(components[name]["flags"])
        reasons.extend(components[name]["reasons"])

    risk_asset = risk_result.get("asset")
    risk_asset = risk_asset if isinstance(risk_asset, Mapping) else {}

    return {
        "chain": chain_name,
        "asset": {
            "symbol": _text(risk_asset.get("symbol")) or normalized_trade["asset"].get("symbol"),
            "mint": _text(risk_asset.get("mint") or risk_asset.get("address")),
        },
        "trade": normalized_trade,
        "recommendation": recommendation,
        "components": components,
        "confidence": _confidence(identity, risk_gate),
        "flags": flags,
        "reasons": reasons,
        "analysis_only": True,
        "execution_authorized": False,
        "authorization_reason": "pre_trade_check_analysis_only",
        "assessment_scope": {
            "included": [
                "chain_consistency",
                "asset_identity_consistency",
                "risk_check_severity_propagation",
                "risk_evidence_completeness",
            ],
            "not_yet_included": [
                "trade_size_thresholds",
                "slippage",
                "price_impact",
                "route_quality",
                "transaction_simulation",
                "fees",
                "execution_authorization",
            ],
        },
    }


__all__ = ["build_pre_trade_check"]
