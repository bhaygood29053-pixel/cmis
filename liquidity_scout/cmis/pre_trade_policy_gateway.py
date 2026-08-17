"""Narrow CMIS runtime wiring for explicit pre-trade size policy.

The stable gateway already composes ``risk_check`` before ``pre_trade_check``.
This mixin changes only the pre-trade composition point so callers can supply a
separate ``params.pre_trade_policy`` mapping. ``params.policy`` remains the risk
policy and is never reinterpreted as a trade-size policy.

No raw market report, liquidity value, quote, route, or execution object may be
injected through this boundary. The deterministic pre-trade core consumes only
the verified evidence already present in the CMIS risk result.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict

from liquidity_scout.services.cmis_pre_trade import build_pre_trade_check_response


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

        pre_trade_policy = params.get("pre_trade_policy")
        if pre_trade_policy is not None and not isinstance(pre_trade_policy, Mapping):
            return self._gateway_error(
                "pre_trade_check",
                "x1",
                "invalid_pre_trade_policy",
                "params.pre_trade_policy must be a mapping when supplied.",
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

        response = build_pre_trade_check_response(
            risk,
            normalized_trade,
            chain="x1",
            policy=pre_trade_policy,
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
