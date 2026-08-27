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

from liquidity_scout.cmis.assets import (
    AssetRegistry,
    DEFAULT_ASSET_REGISTRY,
    MARKET_PLUS_NATIVE,
    NATIVE,
)
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
        asset_registry: Optional[AssetRegistry] = None,
        auto_record_history: bool = False,
    ):
        self.x1_market_provider = x1_market_provider or X1Provider()
        self.x1_supply_provider = x1_supply_provider or X1SupplyProvider()
        self.history_backend = history_backend or default_history_backend
        self.asset_registry = asset_registry or DEFAULT_ASSET_REGISTRY
        self.auto_record_history = bool(auto_record_history)

    @staticmethod
    def _text(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        return text or None

    def _canonical_definition(self, asset: Any):
        return self.asset_registry.resolve("x1", asset)

    def _market_query(self, asset: Any, definition: Any = None) -> Any:
        if isinstance(definition, Mapping):
            return self.asset_registry.market_query(definition) or asset
        return asset

    @staticmethod
    def _provider_asset_from_data(data: Any) -> Dict[str, Any]:
        if not isinstance(data, Mapping):
            return {}
        return {
            "symbol": data.get("symbol"),
            "name": data.get("name"),
            "mint": data.get("mint"),
        }

    @staticmethod
    def _market_representation_from_envelope(envelope: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(envelope, Mapping):
            return None
        data = envelope.get("data")
        if not isinstance(data, Mapping):
            return None
        representations = data.get("representations")
        if not isinstance(representations, list):
            return None
        for record in representations:
            if isinstance(record, Mapping) and record.get("role") == "market":
                return dict(record)
        return None

    def _canonicalize(
        self,
        envelope: Any,
        definition: Any,
        *,
        provider_asset: Any = None,
        role: str = "market",
        identity_key: Any = None,
    ):
        if not isinstance(definition, Mapping):
            return envelope
        return self.asset_registry.canonicalize_envelope(
            envelope,
            definition,
            provider_asset=provider_asset,
            role=role,
            identity_key=identity_key,
        )

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

        definition = self._canonical_definition(asset)
        query = self._market_query(asset, definition)
        catalog, failure = self._collect_x1_catalog("asset_lookup")
        if failure is not None:
            return failure

        response = build_asset_lookup_response(
            query,
            catalog["pools"],
            chain="x1",
            source=catalog.get("source"),
            observed_at=catalog.get("observed_at"),
        )
        if isinstance(definition, Mapping) and response.get("status") == "ok":
            data = response.get("data")
            identity_key = data.get("identity_key") if isinstance(data, Mapping) else None
            response = self._canonicalize(
                response,
                definition,
                provider_asset=response.get("asset"),
                role="market",
                identity_key=identity_key,
            )
        return response

    def _market_report(self, asset: Any) -> Dict[str, Any]:
        if not self._text(asset):
            return build_market_report_response(
                asset,
                None,
                self.x1_market_provider,
                chain="x1",
            )

        definition = self._canonical_definition(asset)
        query = self._market_query(asset, definition)
        catalog, failure = self._collect_x1_catalog("market_report")
        if failure is not None:
            return failure

        term, matches = self._resolved_matches(query, catalog["pools"])
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
        if isinstance(definition, Mapping) and response.get("status") in {"ok", "partial"}:
            response = self._canonicalize(
                response,
                definition,
                provider_asset=response.get("asset"),
                role="market",
            )
        self._persist_verified_market_observation(response)
        return response

    def _persist_verified_market_observation(
        self,
        market_envelope: Mapping[str, Any],
    ) -> None:
        """Persist bounded verified market facts for future historical analysis."""

        if not getattr(self, "auto_record_history", False):
            return

        data = market_envelope.get("data")
        if not isinstance(data, Mapping):
            return

        completeness = data.get("completeness")
        if not isinstance(completeness, Mapping):
            return

        mint = self._text(data.get("mint"))
        symbol = self._text(data.get("symbol")) or "Unknown"
        if not mint:
            return

        provenance = data.get("provenance")
        observed_at = (
            provenance.get("catalog_last_refresh_unix")
            if isinstance(provenance, Mapping)
            else None
        )

        writer = getattr(self.history_backend, "record_snapshot_if_due", None)
        if not callable(writer):
            return

        writer(
            mint=mint,
            symbol=symbol,
            price=data.get("price_usd") if completeness.get("price") is True else None,
            liquidity=(
                data.get("liquidity_usd")
                if completeness.get("liquidity") is True
                else None
            ),
            volume24=(
                data.get("volume_24h_usd")
                if completeness.get("volume_24h") is True
                else None
            ),
            transactions24=(
                data.get("transactions_24h")
                if completeness.get("transactions_24h") is True
                else None
            ),
            holders=(
                data.get("holders")
                if completeness.get("holders") is True
                else None
            ),
            pool_count=data.get("lp_count"),
            timestamp=observed_at,
        )


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
        if isinstance(identity, Mapping) and identity.get("mint"):
            return dict(identity), None

        representation = self._market_representation_from_envelope(lookup)
        if isinstance(representation, Mapping) and representation.get("mint"):
            return {
                "symbol": representation.get("symbol"),
                "name": representation.get("name"),
                "mint": representation.get("mint"),
            }, None

        return (dict(identity) if isinstance(identity, Mapping) else None), None

    def _native_asset_tokenomics(self, definition: Mapping[str, Any]) -> Dict[str, Any]:
        provider_name = self._text(definition.get("native_tokenomics_provider"))
        if provider_name != "x1_supply":
            return build_service_envelope(
                "tokenomics",
                "x1",
                UNAVAILABLE,
                asset=self.asset_registry.public_identity(definition),
                warnings=[{
                    "code": "native_tokenomics_provider_not_implemented",
                    "message": (
                        "No native tokenomics provider is implemented for the "
                        "registered canonical asset."
                    ),
                }],
            )

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
            symbol=definition.get("symbol"),
            name=definition.get("name"),
            chain=definition.get("chain") or "x1",
            total_supply_record=total_record,
            circulating_supply_record=circulating_record,
        )
        response["warnings"].extend(provider_warnings)
        return self._canonicalize(
            response,
            definition,
            provider_asset=response.get("asset"),
            role="native",
        )

    def _tokenomics(self, asset: Any, params: Mapping[str, Any]) -> Dict[str, Any]:
        supplied_mint = self._text(params.get("mint"))
        definition = self._canonical_definition(asset) if not supplied_mint else None
        if (
            isinstance(definition, Mapping)
            and self.asset_registry.service_mode(definition, "tokenomics") == NATIVE
        ):
            return self._native_asset_tokenomics(definition)

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

        response = build_tokenomics_response(
            identity["mint"],
            symbol=identity.get("symbol"),
            name=identity.get("name"),
            chain="x1",
        )
        if isinstance(definition, Mapping):
            response = self._canonicalize(
                response,
                definition,
                provider_asset=identity,
                role="market",
            )
        return response

    def _historical_from_market(
        self,
        question: Any,
        market_envelope: Mapping[str, Any],
        *,
        mode: str = "window",
        compare_market_envelope: Mapping[str, Any] | None = None,
        metrics: Any = None,
        gap_threshold_seconds: int = 129600,
        anchor_tolerance_seconds: int = 21600,
    ) -> Dict[str, Any]:
        market_data = market_envelope.get("data")
        if not isinstance(market_data, Mapping):
            return self._propagate_upstream("historical_compare", market_envelope)

        snapshot = {"_market_report": dict(market_data)}
        compare_snapshot = None
        if isinstance(compare_market_envelope, Mapping):
            compare_data = compare_market_envelope.get("data")
            if not isinstance(compare_data, Mapping):
                return self._propagate_upstream(
                    "historical_compare",
                    compare_market_envelope,
                )
            compare_snapshot = {"_market_report": dict(compare_data)}

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
            mode=mode,
            compare_snapshot=compare_snapshot,
            metrics=metrics,
            gap_threshold_seconds=gap_threshold_seconds,
            anchor_tolerance_seconds=anchor_tolerance_seconds,
        )

    def _historical_compare(self, asset: Any, params: Mapping[str, Any]) -> Dict[str, Any]:
        definition = self._canonical_definition(asset)
        market = self._market_report(asset)
        if market.get("status") in {ERROR, UNAVAILABLE, AMBIGUOUS}:
            return self._propagate_upstream("historical_compare", market)

        compare_market = None
        compare_asset = self._text(params.get("compare_asset"))
        explicit_mode = self._text(params.get("mode"))
        if explicit_mode:
            mode = explicit_mode.lower()
        else:
            question_text = (self._text(params.get("question")) or "").lower()
            all_history_terms = (
                "entire history",
                "full history",
                "all history",
                "all available history",
                "since inception",
                "since launch",
                "lifetime history",
                "whole history",
            )
            if any(term in question_text for term in all_history_terms):
                mode = "all_available_pair" if compare_asset else "all_available"
            else:
                mode = "window"

        if mode == "all_available_pair":
            compare_asset = self._text(params.get("compare_asset"))
            if not compare_asset:
                return self._gateway_error(
                    "historical_compare",
                    "x1",
                    "compare_asset_required",
                    "params.compare_asset is required for all_available_pair.",
                )
            compare_market = self._market_report(compare_asset)
            if compare_market.get("status") in {ERROR, UNAVAILABLE, AMBIGUOUS}:
                return self._propagate_upstream("historical_compare", compare_market)

        gap_threshold = params.get("gap_threshold_seconds", 129600)
        anchor_tolerance = params.get("anchor_tolerance_seconds", 21600)
        try:
            gap_threshold = max(0, int(gap_threshold))
            anchor_tolerance = max(0, int(anchor_tolerance))
        except (TypeError, ValueError):
            return self._gateway_error(
                "historical_compare",
                "x1",
                "invalid_historical_tolerance",
                (
                    "gap_threshold_seconds and anchor_tolerance_seconds must be "
                    "non-negative integers."
                ),
            )

        response = self._historical_from_market(
            params.get("question"),
            market,
            mode=mode,
            compare_market_envelope=compare_market,
            metrics=params.get("metrics"),
            gap_threshold_seconds=gap_threshold,
            anchor_tolerance_seconds=anchor_tolerance,
        )
        if isinstance(definition, Mapping) and response.get("status") in {"ok", "partial"}:
            response = self._canonicalize(
                response,
                definition,
                provider_asset=self._provider_asset_from_data(market.get("data")),
                role="market",
            )

        if compare_asset and isinstance(response.get("data"), dict):
            response["data"].setdefault("compare_asset_request", compare_asset)
        return response

    def _risk_check(self, asset: Any, params: Mapping[str, Any]) -> Dict[str, Any]:
        definition = self._canonical_definition(asset)
        market = self._market_report(asset)
        if market.get("status") in {ERROR, UNAVAILABLE, AMBIGUOUS}:
            return self._propagate_upstream("risk_check", market)

        market_data = market.get("data")
        market_identity = self._provider_asset_from_data(market_data)
        if (
            isinstance(definition, Mapping)
            and self.asset_registry.service_mode(definition, "risk_check") == MARKET_PLUS_NATIVE
        ):
            tokenomics = self._native_asset_tokenomics(definition)
        else:
            tokenomics = build_tokenomics_response(
                market_identity.get("mint"),
                symbol=market_identity.get("symbol"),
                name=market_identity.get("name"),
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

        response = build_risk_check_response(
            market_data,
            tokenomics_data,
            historical_data,
            chain="x1",
            policy=policy,
            observed_at=market.get("observed_at"),
        )
        if isinstance(definition, Mapping):
            response = self._canonicalize(
                response,
                definition,
                provider_asset=market_identity,
                role="market",
            )
        return response

    def _pre_trade_check(self, asset: Any, params: Mapping[str, Any]) -> Dict[str, Any]:
        trade = params.get("trade")
        if not isinstance(trade, Mapping):
            return self._gateway_error(
                "pre_trade_check",
                "x1",
                "invalid_trade_context",
                "params.trade must be a mapping.",
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
            observed_at=risk.get("observed_at"),
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
