"""Narrow CMIS runtime wiring for explicit pre-trade policy.

The generic pre-trade service remains policy-neutral unless a policy is supplied.
At the production X1 composition boundary, an omitted ``params.pre_trade_policy``
selects the versioned conservative X1 operating profile accepted for Issue #99.
An explicitly supplied mapping remains authoritative and does not inherit hidden
thresholds from that profile.

``params.policy`` remains the risk policy and is never reinterpreted as a
trade-size or freshness policy.

No raw market report, liquidity value, quote, route, current-time override, or
execution object may be injected through this boundary. The deterministic
pre-trade core consumes only CMIS-produced risk evidence and an internal
runtime evaluation clock.
"""

from __future__ import annotations

from collections.abc import Mapping
import time
from typing import Any, Dict

from liquidity_scout.services.cmis_pre_trade import build_pre_trade_check_response
from liquidity_scout.services.pre_trade_liquidity import (
    CMIS_X1_CONSERVATIVE_PRE_TRADE_POLICY,
)


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

        response = build_pre_trade_check_response(
            risk,
            normalized_trade,
            chain="x1",
            policy=pre_trade_policy,
            evaluated_at=evaluated_at,
            observed_at=risk.get("observed_at") if isinstance(risk, Mapping) else None,
        )
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


__all__ = ["PreTradePolicyMixin"]
