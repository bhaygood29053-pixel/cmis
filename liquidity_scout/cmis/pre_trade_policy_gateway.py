"""Narrow CMIS runtime wiring for explicit pre-trade policy and route evidence.

The generic pre-trade service remains policy-neutral unless a policy is supplied.
At the production X1 composition boundary, an omitted ``params.pre_trade_policy``
selects the versioned conservative X1 operating profile accepted for Issue #99.
An explicitly supplied mapping remains authoritative and does not inherit hidden
thresholds from that profile.

``params.policy`` remains the risk policy and is never reinterpreted as a
trade-size or freshness policy.

XDEX route evidence is derived only by an internal runtime resolver and only
when the proposed trade already supplies a valid exact route plus an exact
positive token input amount. Caller-supplied ``params.route_evidence`` is never
trusted. Notional USD is never converted into a token input amount here.

No raw market report, liquidity value, current-time override, transaction,
execution object, or trusted proof claim may be injected through this boundary.
The deterministic pre-trade core consumes only CMIS-produced risk evidence,
CMIS-produced route evidence, and an internal runtime evaluation clock.
"""

from __future__ import annotations

from collections.abc import Mapping
import time
from typing import Any, Dict, Optional, Tuple

from liquidity_scout.services.cmis_pre_trade import build_pre_trade_check_response
from liquidity_scout.services.pre_trade_liquidity import (
    CMIS_X1_CONSERVATIVE_PRE_TRADE_POLICY,
)
from liquidity_scout.services.pre_trade_route_evidence import (
    normalize_token_in_amount,
    normalize_trade_route,
)


XDEX_ROUTE_EVIDENCE_MAX_AGE_SECONDS = 30.0


def _text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _internal_route_scope(trade: Mapping[str, Any]) -> Tuple[Optional[dict], Optional[str]]:
    """Return a validated exact route and canonical amount without guessing.

    Malformed trade input is left for the deterministic service wrapper to
    reject. This helper exists only to prevent provider collection before the
    public trade shape has enough exact identity to support it.
    """
    route = trade.get("route")
    if route is None:
        return None, None

    asset = trade.get("asset")
    asset = asset if isinstance(asset, Mapping) else {}
    asset_mint = _text(asset.get("mint") or asset.get("address"))
    side = _text(trade.get("side"))
    try:
        normalized_route = normalize_trade_route(
            route,
            asset_mint=asset_mint,
            side=side,
        )
        normalized_amount = normalize_token_in_amount(trade.get("token_in_amount"))
    except ValueError:
        return None, None
    return normalized_route, normalized_amount


def _append_warning(response: Dict[str, Any], warning: Mapping[str, Any]) -> None:
    warnings = response.setdefault("warnings", [])
    record = dict(warning)
    if record not in warnings:
        warnings.append(record)


class PreTradePolicyMixin:
    """Override only the runtime ``pre_trade_check`` composition point."""

    def _pre_trade_check(self, asset: Any, params: Mapping[str, Any]) -> Dict[str, Any]:
        trade = params.get("trade")
        if not isinstance(trade, Mapping):
            return self._gateway_error(
                "pre_trade_check",
                "x1",
                "invalid_trade_context",
                "params.trade must be a mapping.",
            )

        supplied_pre_trade_policy = params.get("pre_trade_policy")
        if supplied_pre_trade_policy is not None and not isinstance(
            supplied_pre_trade_policy, Mapping
        ):
            return self._gateway_error(
                "pre_trade_check",
                "x1",
                "invalid_pre_trade_policy",
                "params.pre_trade_policy must be a mapping when supplied.",
            )

        # Issue #99: the production X1 runtime has one explicit named policy
        # when the caller does not provide another policy.  The generic service
        # core itself remains uncalibrated and therefore reusable by other
        # chains without inheriting X1 thresholds.
        pre_trade_policy = (
            dict(supplied_pre_trade_policy)
            if supplied_pre_trade_policy is not None
            else dict(CMIS_X1_CONSERVATIVE_PRE_TRADE_POLICY)
        )

        definition = self._canonical_definition(asset)
        risk_params = {
            key: params[key]
            for key in ("policy", "historical_question")
            if key in params
        }
        risk = self._risk_check(asset, risk_params)

        normalized_trade = dict(trade)
        if "chain" not in normalized_trade:
            normalized_trade["chain"] = "x1"
        if not isinstance(normalized_trade.get("asset"), Mapping):
            raw_risk = risk.get("risk") if isinstance(risk, Mapping) else None
            raw_risk_asset = raw_risk.get("asset") if isinstance(raw_risk, Mapping) else None
            if isinstance(raw_risk_asset, Mapping):
                normalized_trade["asset"] = dict(raw_risk_asset)
            else:
                risk_asset = risk.get("asset") if isinstance(risk, Mapping) else None
                if isinstance(risk_asset, Mapping):
                    normalized_trade["asset"] = dict(risk_asset)

        now_fn = getattr(self, "pre_trade_now_fn", None) or time.time
        evaluated_at = float(now_fn())

        runtime_warnings = []
        if params.get("route_evidence") is not None:
            runtime_warnings.append({
                "code": "caller_route_evidence_ignored",
                "message": (
                    "Caller-supplied route evidence is not trusted; CMIS derives "
                    "XDEX route evidence internally when exact trade scope is available."
                ),
            })

        route_evidence = None
        exact_route, token_in_amount = _internal_route_scope(normalized_trade)
        if exact_route is not None and token_in_amount is None:
            runtime_warnings.append({
                "code": "xdex_route_evidence_input_amount_required",
                "message": (
                    "An exact positive token_in_amount is required before CMIS can "
                    "derive amount-scoped XDEX route evidence."
                ),
            })

        resolver = getattr(self, "xdex_route_resolver", None)
        risk_status = (
            str(risk.get("status") or "").strip().lower()
            if isinstance(risk, Mapping)
            else ""
        )
        if (
            exact_route is not None
            and token_in_amount is not None
            and callable(resolver)
            and risk_status in {"ok", "partial"}
        ):
            try:
                route_evidence = resolver(exact_route, token_in_amount)
            except Exception:
                # Provider/quote verification failure must not erase the already
                # useful risk result or manufacture execution estimates. The
                # deterministic core simply receives no route evidence.
                route_evidence = None
                runtime_warnings.append({
                    "code": "xdex_route_evidence_unavailable",
                    "message": (
                        "CMIS could not verify the exact XDEX route evidence; "
                        "route execution estimates remain unavailable."
                    ),
                })

        response = build_pre_trade_check_response(
            risk,
            normalized_trade,
            chain="x1",
            policy=pre_trade_policy,
            evaluated_at=evaluated_at,
            observed_at=risk.get("observed_at") if isinstance(risk, Mapping) else None,
            route_evidence=route_evidence,
            route_evidence_max_age_seconds=(
                XDEX_ROUTE_EVIDENCE_MAX_AGE_SECONDS
                if route_evidence is not None
                else None
            ),
        )
        for warning in runtime_warnings:
            _append_warning(response, warning)

        if isinstance(definition, Mapping):
            raw_risk = risk.get("risk") if isinstance(risk, Mapping) else None
            provider_asset = raw_risk.get("asset") if isinstance(raw_risk, Mapping) else None
            response = self._canonicalize(
                response,
                definition,
                provider_asset=provider_asset,
                role="market",
            )
        return response


__all__ = ["PreTradePolicyMixin", "XDEX_ROUTE_EVIDENCE_MAX_AGE_SECONDS"]
