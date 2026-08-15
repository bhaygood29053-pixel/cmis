"""Chain-aware CMIS request dispatcher for external Scout consumers.

External Scouts send only service intent, target chain, asset identity, and
service parameters. The gateway owns CMIS-side provider collection and service
composition so callers never need pool rows, RPC functions, database handles,
or provider credentials.

Request shape::

    {
        "service": "market_report",
        "chain": "x1",
        "asset": "AGI",
        "params": {}
    }

The returned value is always a standard CMIS service envelope.
"""

from collections.abc import Mapping
from typing import Any, Dict, Optional, Tuple

import historical_metrics as default_history_backend

from liquidity_scout.market.resolver import (
    AmbiguousAssetError,
    find_matches_for_term,
    resolve_asset,
)
from liquidity_scout.providers.x1.market import X1Provider
from liquidity_scout.providers.x1.supply import X1SupplyProvider
from liquidity_scout.services.cmis_asset_lookup import build_asset_lookup_response
from liquidity_scout.services.cmis_contract import (
    AMBIGUOUS,
    ERROR,
    UNAVAILABLE,
    build_service_envelope,
)
from liquidity_scout.services.cmis_historical import build_historical_compare_response
from liquidity_scout.services.cmis_market import build_market_report_response
from liquidity_scout.services.cmis_native_tokenomics import build_native_tokenomics_response
from liquidity_scout.services.cmis_pre_trade import build_pre_trade_check_response
from liquidity_scout.services.cmis_rank import build_rank_response
from liquidity_scout.services.cmis_risk import build_risk_check_response
from liquidity_scout.services.cmis_tokenomics import build_tokenomics_response


SUPPORTED_SERVICES = (
    "asset_lookup",
    "market_report",
    "rank",
    "historical_compare",
    "tokenomics",
    "risk_check",
    "pre_trade_check",
)

KNOWN_CHAINS = ("x1", "solana")
SUPPORTED_CHAINS = ("x1",)


class CMISGateway:
    """Dispatch external chain-aware requests into deterministic CMIS services.

    Only X1 collection is enabled today. Solana is a known planned chain and
    therefore returns ``unavailable`` rather than being silently routed through
    X1. Unknown chains fail with ``error``.
    """

    def __init__(
        self,
        *,
        x1_market_provider: Optional[X1Provider] = None,
        x1_supply_provider: Optional[X1SupplyProvider] = None,
        history_backend: Any = None,
    ):
        self.x1_market_provider = x1_market_provider or X1Provider()
        self.x1_supply_provider = x1_supply_provider or X1SupplyProvider()
        self.history_backend = history_backend or default_history_backend

    @staticmethod
    def _text(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        return text or None

    def _gateway_error(
        self,
        service: Any,
        chain: Any,
        code: str,
        message: str,
        *,
        data: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        return build_service_envelope(
            self._text(service) or "cmis_gateway",
            (self._text(chain) or "unknown").lower(),
            ERROR,
            data=data,
            errors=[{"code": code, "message": message}],
        )

    def _chain_unavailable(self, service: str, chain: str) -> Dict[str, Any]:
        return build_service_envelope(
            service,
            chain,
            UNAVAILABLE,
            warnings=[{
                "code": "chain_provider_not_implemented",
                "message": (
                    f"CMIS recognizes chain '{chain}', but its provider is not "
                    "implemented in this deployment."
                ),
            }],
        )

    def _collect_x1_catalog(
        self,
        service: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        try:
            self.x1_market_provider.refresh_if_needed()
            catalog = self.x1_market_provider.market_catalog()
        except Exception as exc:  # Provider failures must become explicit CMIS state.
            return None, build_service_envelope(
                service,
                "x1",
                UNAVAILABLE,
                sources=[{"source": "X1.Ninja/XDEX", "role": "market_collection"}],
                warnings=[{
                    "code": "x1_market_provider_unavailable",
                    "message": f"X1 market collection failed: {exc}",
                }],
            )

        pools = catalog.get("pools") if isinstance(catalog, Mapping) else None
        if not isinstance(pools, list):
            return None, build_service_envelope(
                service,
                "x1",
                UNAVAILABLE,
                sources=[{"source": "X1.Ninja/XDEX", "role": "market_collection"}],
                warnings=[{
                    "code": "x1_market_catalog_unavailable",
                    "message": "The X1 market provider returned no usable pool catalog.",
                }],
            )
        return dict(catalog), None

    @staticmethod
    def _resolved_matches(asset: Any, pools: list):
        """Resolve one request while preserving exact ambiguity for wrappers."""
        query = str(asset or "").strip()
        if not query:
            return query, []
        try:
            term, matches = resolve_asset(query, pools)
            return term or query, matches or []
        except AmbiguousAssetError as exc:
            term = exc.term or query
            matches = [
                match
                for match in find_matches_for_term(term, pools)
                if isinstance(match, (tuple, list))
                and len(match) >= 4
                and match[3] >= 90
            ]
            return term, matches

    @staticmethod
    def _propagate_upstream(
        service: str,
        upstream: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Translate a failed prerequisite into the requested service envelope."""
        status = str(upstream.get("status") or UNAVAILABLE).lower()
        if status not in {ERROR, UNAVAILABLE, AMBIGUOUS}:
            status = UNAVAILABLE
        return build_service_envelope(
            service,
            upstream.get("chain") or "x1",
            status,
            asset=upstream.get("asset"),
            data={"upstream_service": upstream.get("service")},
            confidence=upstream.get("confidence"),
            sources=upstream.get("sources") or [],
            observed_at=upstream.get("observed_at"),
            warnings=upstream.get("warnings") or [],
            errors=upstream.get("errors") or [],
        )

    def _asset_lookup(self, asset: Any) -> Dict[str, Any]:
        if not self._text(asset):
            return build_asset_lookup_response(asset, [], chain="x1")
        catalog, failure = self._collect_x1_catalog("asset_lookup")
        if failure is not None:
            return failure
        return build_asset_lookup_response(
            asset,
            catalog["pools"],
            chain="x1",
            source=catalog.get("source"),
            observed_at=catalog.get("observed_at"),
        )

    def _market_report(self, asset: Any) -> Dict[str, Any]:
        if not self._text(asset):
            return build_market_report_response(
                asset,
                None,
                self.x1_market_provider,
                chain="x1",
            )
        catalog, failure = self._collect_x1_catalog("market_report")
        if failure is not None:
            return failure
        term, matches = self._resolved_matches(asset, catalog["pools"])
        response = build_market_report_response(
            term,
            matches,
            self.x1_market_provider,
            chain="x1",
            observed_at=catalog.get("observed_at"),
        )
        data = response.get("data")
        if isinstance(data, dict) and "lp_count" in data:
            data["#LPs"] = data.get("lp_count")
        return response

    def _rank(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        catalog, failure = self._collect_x1_catalog("rank")
        if failure is not None:
            return failure
        return build_rank_response(
            catalog["pools"],
            metric=params.get("metric", "volume"),
            limit=params.get("limit", 10),
            chain="x1",
            source=catalog.get("source"),
            observed_at=catalog.get("observed_at"),
        )

    def _resolve_tokenomics_identity(
        self,
        asset: Any,
        params: Mapping[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        supplied_mint = self._text(params.get("mint"))
        if supplied_mint:
            return {
                "symbol": self._text(params.get("symbol")),
                "name": self._text(params.get("name")),
                "mint": supplied_mint,
            }, None

        lookup = self._asset_lookup(asset)
        if lookup.get("status") != "ok":
            return None, self._propagate_upstream("tokenomics", lookup)
        identity = lookup.get("asset")
        return (dict(identity) if isinstance(identity, Mapping) else None), None

    def _native_xnt_tokenomics(self) -> Dict[str, Any]:
        total_record = None
        circulating_record = None
        provider_warnings = []

        try:
            total_record = self.x1_supply_provider.get_total_supply()
        except Exception as exc:
            provider_warnings.append({
                "code": "x1_native_total_supply_provider_unavailable",
                "message": f"X1 native total-supply collection failed: {exc}",
            })

        try:
            circulating_record = self.x1_supply_provider.get_circulating_supply()
        except Exception as exc:
            provider_warnings.append({
                "code": "x1_native_circulating_supply_provider_unavailable",
                "message": f"X1 native circulating-supply collection failed: {exc}",
            })

        response = build_native_tokenomics_response(
            symbol="XNT",
            name="XNT",
            chain="x1",
            total_supply_record=total_record,
            circulating_supply_record=circulating_record,
        )
        response["warnings"].extend(provider_warnings)
        return response

    def _tokenomics(self, asset: Any, params: Mapping[str, Any]) -> Dict[str, Any]:
        supplied_mint = self._text(params.get("mint"))
        asset_text = self._text(asset)
        if not supplied_mint and asset_text and asset_text.upper() == "XNT":
            return self._native_xnt_tokenomics()

        identity, failure = self._resolve_tokenomics_identity(asset, params)
        if failure is not None:
            return failure
        if not identity or not identity.get("mint"):
            return self._gateway_error(
                "tokenomics",
                "x1",
                "token_mint_required",
                "A verified mint is required for mint-scoped tokenomics.",
            )
        return build_tokenomics_response(
            identity["mint"],
            symbol=identity.get("symbol"),
            name=identity.get("name"),
            chain="x1",
        )

    def _historical_from_market(
        self,
        question: Any,
        market_envelope: Mapping[str, Any],
    ) -> Dict[str, Any]:
        market_data = market_envelope.get("data")
        if not isinstance(market_data, Mapping):
            return self._propagate_upstream("historical_compare", market_envelope)

        snapshot = {"_market_report": dict(market_data)}

        def current_total_supply(mint: str):
            tokenomics = build_tokenomics_response(mint, chain="x1")
            data = tokenomics.get("data")
            if not isinstance(data, Mapping) or data.get("supply_verified") is not True:
                return None
            return data.get("total_supply")

        return build_historical_compare_response(
            question,
            snapshot,
            history_backend=self.history_backend,
            get_total_supply=current_total_supply,
            chain="x1",
            observed_at=market_envelope.get("observed_at"),
        )

    def _historical_compare(self, asset: Any, params: Mapping[str, Any]) -> Dict[str, Any]:
        market = self._market_report(asset)
        if market.get("status") in {ERROR, UNAVAILABLE, AMBIGUOUS}:
            return self._propagate_upstream("historical_compare", market)
        return self._historical_from_market(params.get("question"), market)

    def _risk_check(self, asset: Any, params: Mapping[str, Any]) -> Dict[str, Any]:
        market = self._market_report(asset)
        if market.get("status") in {ERROR, UNAVAILABLE, AMBIGUOUS}:
            return self._propagate_upstream("risk_check", market)

        market_data = market.get("data")
        identity = market.get("asset") if isinstance(market.get("asset"), Mapping) else {}
        asset_text = self._text(asset)
        if asset_text and asset_text.upper() == "XNT":
            tokenomics = self._native_xnt_tokenomics()
        else:
            tokenomics = build_tokenomics_response(
                identity.get("mint"),
                symbol=identity.get("symbol"),
                name=identity.get("name"),
                chain="x1",
            )
        tokenomics_data = (
            tokenomics.get("data")
            if tokenomics.get("status") != ERROR and isinstance(tokenomics.get("data"), Mapping)
            else None
        )

        historical_data = None
        historical_question = self._text(params.get("historical_question"))
        if historical_question:
            historical = self._historical_from_market(historical_question, market)
            if historical.get("status") != ERROR and isinstance(historical.get("data"), Mapping):
                historical_data = historical.get("data")

        policy = params.get("policy")
        if policy is not None and not isinstance(policy, Mapping):
            return self._gateway_error(
                "risk_check",
                "x1",
                "invalid_risk_policy",
                "params.policy must be a mapping when supplied.",
            )

        return build_risk_check_response(
            market_data,
            tokenomics_data,
            historical_data,
            chain="x1",
            policy=policy,
            observed_at=market.get("observed_at"),
        )

    def _pre_trade_check(self, asset: Any, params: Mapping[str, Any]) -> Dict[str, Any]:
        trade = params.get("trade")
        if not isinstance(trade, Mapping):
            return self._gateway_error(
                "pre_trade_check",
                "x1",
                "invalid_trade_context",
                "params.trade must be a mapping.",
            )

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
            risk_asset = risk.get("asset")
            if isinstance(risk_asset, Mapping):
                normalized_trade["asset"] = dict(risk_asset)

        return build_pre_trade_check_response(
            risk,
            normalized_trade,
            chain="x1",
            observed_at=risk.get("observed_at"),
        )

    def dispatch(self, request: Any) -> Dict[str, Any]:
        """Dispatch one external request and always return a CMIS envelope."""
        if not isinstance(request, Mapping):
            return self._gateway_error(
                "cmis_gateway",
                "unknown",
                "invalid_request",
                "CMIS request must be a JSON object/mapping.",
            )

        service = (self._text(request.get("service")) or "").lower()
        chain = (self._text(request.get("chain")) or "").lower()
        asset = request.get("asset")
        params = request.get("params", {})

        if not service:
            return self._gateway_error(
                "cmis_gateway",
                chain or "unknown",
                "service_required",
                "service is required.",
            )
        if service not in SUPPORTED_SERVICES:
            return self._gateway_error(
                service,
                chain or "unknown",
                "unsupported_service",
                "service must be one of: " + ", ".join(SUPPORTED_SERVICES),
            )
        if not chain:
            return self._gateway_error(
                service,
                "unknown",
                "chain_required",
                "chain is required.",
            )
        if chain not in KNOWN_CHAINS:
            return self._gateway_error(
                service,
                chain,
                "unsupported_chain",
                "Unsupported chain: " + chain,
            )
        if chain not in SUPPORTED_CHAINS:
            return self._chain_unavailable(service, chain)
        if not isinstance(params, Mapping):
            return self._gateway_error(
                service,
                chain,
                "invalid_params",
                "params must be a JSON object/mapping.",
            )

        if service == "asset_lookup":
            return self._asset_lookup(asset)
        if service == "market_report":
            return self._market_report(asset)
        if service == "rank":
            return self._rank(params)
        if service == "historical_compare":
            return self._historical_compare(asset, params)
        if service == "tokenomics":
            return self._tokenomics(asset, params)
        if service == "risk_check":
            return self._risk_check(asset, params)
        if service == "pre_trade_check":
            return self._pre_trade_check(asset, params)

        return self._gateway_error(
            service,
            chain,
            "unsupported_service",
            "No dispatcher is registered for the requested service.",
        )


__all__ = [
    "CMISGateway",
    "KNOWN_CHAINS",
    "SUPPORTED_CHAINS",
    "SUPPORTED_SERVICES",
]
