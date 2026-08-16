"""Trade-aware CMIS runtime.

This subclass adds deterministic X1 trade verification without changing the
stable base CMISGateway service contract or its existing market/risk/tokenomics
behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.cmis.risk_evidence_gateway import EvidenceAwareCMISGateway
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL
from liquidity_scout.services.cmis_trade_verification import (
    SERVICE as TRADE_VERIFICATION_SERVICE,
    build_x1_trade_verification_response,
)

BASE_SUPPORTED_SERVICES = (
    "asset_lookup",
    "market_report",
    "rank",
    "historical_compare",
    "tokenomics",
    "risk_check",
    "pre_trade_check",
)
SUPPORTED_SERVICES = BASE_SUPPORTED_SERVICES + (TRADE_VERIFICATION_SERVICE,)


class TradeAwareCMISGateway(EvidenceAwareCMISGateway):
    """CMIS runtime with provider->chain trade verification."""

    def __init__(
        self,
        *,
        x1_trade_rpc_url: str = DEFAULT_X1_RPC_URL,
        x1_trade_verifier=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.x1_trade_rpc_url = str(x1_trade_rpc_url or "").strip()
        if not self.x1_trade_rpc_url:
            raise ValueError("x1_trade_rpc_url must not be empty")
        self.x1_trade_verifier = x1_trade_verifier

    def _trade_verification(self, params: Mapping[str, Any]):
        event = params.get("event")
        kwargs = {"rpc_url": self.x1_trade_rpc_url}
        if self.x1_trade_verifier is not None:
            kwargs["verifier"] = self.x1_trade_verifier
        return build_x1_trade_verification_response(event, **kwargs)

    def dispatch(self, request: Any):
        if isinstance(request, Mapping):
            service = (self._text(request.get("service")) or "").lower()
            if service == TRADE_VERIFICATION_SERVICE:
                chain = (self._text(request.get("chain")) or "").lower()
                if not chain:
                    return self._gateway_error(
                        service,
                        "unknown",
                        "chain_required",
                        "chain is required.",
                    )
                if chain not in ("x1", "solana"):
                    return self._gateway_error(
                        service,
                        chain,
                        "unsupported_chain",
                        "Unsupported chain: " + chain,
                    )
                if chain != "x1":
                    return self._chain_unavailable(service, chain)

                params = request.get("params", {})
                if not isinstance(params, Mapping):
                    return self._gateway_error(
                        service,
                        chain,
                        "invalid_params",
                        "params must be a JSON object/mapping.",
                    )
                return self._trade_verification(params)

        return super().dispatch(request)


__all__ = [
    "BASE_SUPPORTED_SERVICES",
    "SUPPORTED_SERVICES",
    "TRADE_VERIFICATION_SERVICE",
    "TradeAwareCMISGateway",
]
