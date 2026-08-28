"""Runtime composition for the bounded Instant X1 Scan service."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.services.cmis_contract import AMBIGUOUS, ERROR, UNAVAILABLE
from liquidity_scout.services.cmis_instant_x1_scan import (
    HISTORY_METRICS,
    SERVICE,
    build_instant_x1_scan_response,
)
from liquidity_scout.services.cmis_risk import build_risk_check_response


class InstantX1ScanMixin:
    """Compose accepted X1 CMIS services into one compact read-only scan."""

    @staticmethod
    def _scan_text(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    def _instant_x1_scan(
        self,
        asset: Any,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        unknown = sorted(set(params) - {"risk_policy"})
        if unknown:
            return self._gateway_error(
                SERVICE,
                "x1",
                "unsupported_scan_params",
                "Unsupported instant_x1_scan params: " + ", ".join(unknown),
            )

        risk_policy = params.get("risk_policy")
        if risk_policy is not None and not isinstance(risk_policy, Mapping):
            return self._gateway_error(
                SERVICE,
                "x1",
                "invalid_risk_policy",
                "params.risk_policy must be a mapping when supplied.",
            )

        identity = self._asset_lookup(asset)
        if identity.get("status") in {ERROR, UNAVAILABLE, AMBIGUOUS}:
            return self._propagate_upstream(SERVICE, identity)

        market = self._market_report(asset)
        if market.get("status") in {ERROR, UNAVAILABLE, AMBIGUOUS}:
            return self._propagate_upstream(SERVICE, market)

        # Preserve the existing tokenomics service as the source of truth,
        # including native-XNT special handling. Provider refreshes remain owned
        # by the existing gateway/service implementation.
        tokenomics = self._tokenomics(asset, {})

        # "Instant" history is local-only: summarize verified CMIS observations
        # already in the configured history backend. Do not invoke provider
        # backfill or expand network history in this composition path.
        history = self._historical_from_market(
            None,
            market,
            mode="all_available",
            metrics=HISTORY_METRICS,
            include_onchain_coverage=False,
            include_supply_lookup=False,
        )
        risk_history = self._historical_from_market(
            "Has price changed in the last 24 hours?",
            market,
            mode="window",
            include_onchain_coverage=False,
            include_supply_lookup=False,
        )

        market_data = (
            market.get("data") if isinstance(market.get("data"), Mapping) else {}
        )
        tokenomics_data = (
            tokenomics.get("data")
            if tokenomics.get("status") != ERROR
            and isinstance(tokenomics.get("data"), Mapping)
            else None
        )
        risk_history_data = (
            risk_history.get("data")
            if risk_history.get("status") != ERROR
            and isinstance(risk_history.get("data"), Mapping)
            else None
        )

        risk = build_risk_check_response(
            market_data,
            tokenomics_data,
            risk_history_data,
            chain="x1",
            policy=risk_policy,
            observed_at=market.get("observed_at"),
        )
        if risk.get("status") == ERROR:
            return self._propagate_upstream(SERVICE, risk)

        return build_instant_x1_scan_response(
            identity,
            market,
            tokenomics,
            history,
            risk,
        )

    def dispatch(self, request: Any):
        if isinstance(request, Mapping):
            service = (
                self._scan_text(request.get("service")) or ""
            ).lower()
            if service == SERVICE:
                chain = (
                    self._scan_text(request.get("chain")) or ""
                ).lower()
                if not chain:
                    return self._gateway_error(
                        SERVICE,
                        "unknown",
                        "chain_required",
                        "chain is required.",
                    )
                if chain not in {"x1", "solana"}:
                    return self._gateway_error(
                        SERVICE,
                        chain,
                        "unsupported_chain",
                        "Unsupported chain: " + chain,
                    )
                if chain != "x1":
                    return self._chain_unavailable(SERVICE, chain)

                params = request.get("params", {})
                if not isinstance(params, Mapping):
                    return self._gateway_error(
                        SERVICE,
                        chain,
                        "invalid_params",
                        "params must be a JSON object/mapping.",
                    )
                return self._instant_x1_scan(request.get("asset"), params)

        return super().dispatch(request)


__all__ = ["InstantX1ScanMixin", "SERVICE"]
