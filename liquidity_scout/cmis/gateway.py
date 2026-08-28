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
import time

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
from liquidity_scout.providers.x1.rpc import X1RPCProvider
from liquidity_scout.providers.x1.supply import X1SupplyProvider
from liquidity_scout.providers.x1.token_metadata import X1TokenMetadataProvider
from liquidity_scout.providers.x1.xdex_price_history_import import (
    backfill_verified_xdex_usd_price_history,
)
from liquidity_scout.services.cmis_asset_lookup import build_asset_lookup_response
from liquidity_scout.services.cmis_x1_asset_identity import (
    build_exact_mint_identity_response,
    is_exact_x1_public_key,
)
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
        x1_rpc_provider: Optional[X1RPCProvider] = None,
        x1_token_metadata_provider: Optional[X1TokenMetadataProvider] = None,
        history_backend: Any = None,
        asset_registry: Optional[AssetRegistry] = None,
        auto_record_history: bool = False,
    ):
        self.x1_market_provider = x1_market_provider or X1Provider()
        self.x1_supply_provider = x1_supply_provider or X1SupplyProvider()
        self.x1_rpc_provider = x1_rpc_provider or X1RPCProvider()
        self.x1_token_metadata_provider = (
            x1_token_metadata_provider or X1TokenMetadataProvider()
        )
        self.history_backend = history_backend or default_history_backend
        self.asset_registry = asset_registry or DEFAULT_ASSET_REGISTRY
        self.auto_record_history = bool(auto_record_history)
        self._provider_history_backfill_attempts = {}

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
        query_text = self._text(asset)
        if not query_text:
            return build_asset_lookup_response(asset, [], chain="x1")

        if is_exact_x1_public_key(query_text):
            metadata_evidence = None
            metadata_warning = None
            try:
                metadata_evidence = self.x1_token_metadata_provider.get_metadata(
                    query_text
                )
            except Exception as exc:
                metadata_warning = {
                    "code": "x1_token_metadata_provider_unavailable",
                    "message": (
                        "Exact-mint Token Metadata verification failed: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                }

            catalog = None
            catalog_failure = None
            try:
                catalog, catalog_failure = self._collect_x1_catalog("asset_lookup")
            except Exception as exc:  # pragma: no cover - defensive provider boundary
                catalog_failure = build_service_envelope(
                    "asset_lookup",
                    "x1",
                    UNAVAILABLE,
                    warnings=[{
                        "code": "x1_market_provider_unavailable",
                        "message": f"X1 market collection failed: {exc}",
                    }],
                )

            pools = (
                catalog.get("pools")
                if isinstance(catalog, Mapping)
                else []
            )
            response = build_exact_mint_identity_response(
                query_text,
                metadata_evidence=metadata_evidence,
                xdex_pools=pools,
                xdex_available=catalog_failure is None,
                xdex_source=(
                    catalog.get("source")
                    if isinstance(catalog, Mapping)
                    else None
                ),
                xdex_observed_at=(
                    catalog.get("observed_at")
                    if isinstance(catalog, Mapping)
                    else None
                ),
            )
            if metadata_warning is not None:
                response["warnings"].append(metadata_warning)
            if catalog_failure is not None:
                response["warnings"].extend(
                    catalog_failure.get("warnings") or []
                )
            return response

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


    def _maybe_backfill_verified_xdex_price_history(
        self,
        market_envelope: Mapping[str, Any],
        *,
        lookback_days: int,
        min_refresh_seconds: int,
        rel_tolerance: float,
    ) -> Dict[str, Any]:
        """Attempt bounded verified provider price backfill for one resolved asset."""

        data = market_envelope.get("data")
        if not isinstance(data, Mapping):
            return {
                "status": "unavailable",
                "reason": "market_report_data_unavailable_for_provider_backfill",
                "provider_history_imported": False,
            }

        mint = self._text(data.get("mint"))
        symbol = self._text(data.get("symbol")) or "Unknown"
        if not mint:
            return {
                "status": "unavailable",
                "reason": "market_mint_unavailable_for_provider_backfill",
                "provider_history_imported": False,
            }

        now = int(time.time())
        summary_reader = getattr(
            self.history_backend,
            "verified_price_import_summary",
            None,
        )
        summary = summary_reader(mint) if callable(summary_reader) else None
        if isinstance(summary, Mapping) and summary.get("available") is True:
            last_imported = summary.get("last_imported_at")
            if (
                last_imported is not None
                and now - int(last_imported) < int(min_refresh_seconds)
            ):
                return {
                    "status": "partial",
                    "reason": "verified_provider_price_history_recently_backfilled",
                    "provider_history_imported": True,
                    "imported_observation_count": 0,
                    "stored_verified_provider_observation_count": int(
                        summary.get(
                            "usable_observation_count",
                            summary.get("observation_count") or 0,
                        )
                        or 0
                    ),
                    "conflicting_provider_timestamp_count": int(
                        summary.get("conflicting_timestamp_count") or 0
                    ),
                    "first_imported_observed_at": summary.get(
                        "first_observed_at"
                    ),
                    "last_imported_observed_at": summary.get(
                        "last_observed_at"
                    ),
                    "full_asset_lifetime_verified": False,
                    "continuous_coverage_verified": False,
                }

        last_attempt = self._provider_history_backfill_attempts.get(mint)
        if (
            last_attempt is not None
            and now - int(last_attempt) < int(min_refresh_seconds)
        ):
            return {
                "status": "unavailable",
                "reason": "provider_price_history_backfill_attempt_recent",
                "provider_history_imported": bool(
                    isinstance(summary, Mapping)
                    and summary.get("available") is True
                ),
            }

        self._provider_history_backfill_attempts[mint] = now
        try:
            return backfill_verified_xdex_usd_price_history(
                mint,
                symbol,
                catalog_pools=list(self.x1_market_provider.pools),
                history_backend=self.history_backend,
                time_from=max(1, now - int(lookback_days) * 86400),
                time_to=now,
                rel_tolerance=float(rel_tolerance),
                imported_at=now,
            )
        except Exception as exc:
            return {
                "status": "unavailable",
                "reason": "provider_price_history_backfill_failed",
                "details": f"{type(exc).__name__}: {exc}",
                "provider_history_imported": False,
                "full_asset_lifetime_verified": False,
                "continuous_coverage_verified": False,
            }


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
        onchain_page_size: int = 1000,
        onchain_max_signatures: int = 5000,
        include_onchain_coverage: bool = True,
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
            onchain_coverage_provider=(
                self.x1_rpc_provider if include_onchain_coverage else None
            ),
            onchain_page_size=onchain_page_size,
            onchain_max_signatures=onchain_max_signatures,
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
        onchain_page_size = params.get("onchain_page_size", 1000)
        onchain_max_signatures = params.get("onchain_max_signatures", 5000)
        provider_history_backfill = params.get("provider_history_backfill", True)
        provider_history_lookback_days = params.get(
            "provider_history_lookback_days",
            300,
        )
        provider_history_min_refresh_seconds = params.get(
            "provider_history_min_refresh_seconds",
            21600,
        )
        provider_history_rel_tolerance = params.get(
            "provider_history_rel_tolerance",
            0.005,
        )
        try:
            gap_threshold = max(0, int(gap_threshold))
            anchor_tolerance = max(0, int(anchor_tolerance))
            onchain_page_size = int(onchain_page_size)
            onchain_max_signatures = int(onchain_max_signatures)
            if not 1 <= onchain_page_size <= 1000:
                raise ValueError
            if not 1 <= onchain_max_signatures <= 100000:
                raise ValueError
            if not isinstance(provider_history_backfill, bool):
                raise ValueError
            provider_history_lookback_days = int(
                provider_history_lookback_days
            )
            provider_history_min_refresh_seconds = int(
                provider_history_min_refresh_seconds
            )
            provider_history_rel_tolerance = float(
                provider_history_rel_tolerance
            )
            if not 1 <= provider_history_lookback_days <= 3650:
                raise ValueError
            if not 0 <= provider_history_min_refresh_seconds <= 604800:
                raise ValueError
            if not 0 <= provider_history_rel_tolerance <= 0.05:
                raise ValueError
        except (TypeError, ValueError):
            return self._gateway_error(
                "historical_compare",
                "x1",
                "invalid_historical_tolerance",
                (
                    "gap_threshold_seconds and anchor_tolerance_seconds must be "
                    "non-negative integers; onchain_page_size must be 1..1000; "
                    "onchain_max_signatures must be 1..100000; "
                    "provider_history_backfill must be boolean; "
                    "provider_history_lookback_days must be 1..3650; "
                    "provider_history_min_refresh_seconds must be 0..604800; "
                    "provider_history_rel_tolerance must be 0..0.05."
                ),
            )

        provider_backfill = None
        compare_provider_backfill = None
        if (
            provider_history_backfill
            and mode in {"all_available", "all_available_pair"}
        ):
            provider_backfill = self._maybe_backfill_verified_xdex_price_history(
                market,
                lookback_days=provider_history_lookback_days,
                min_refresh_seconds=provider_history_min_refresh_seconds,
                rel_tolerance=provider_history_rel_tolerance,
            )
            if mode == "all_available_pair" and isinstance(compare_market, Mapping):
                compare_provider_backfill = (
                    self._maybe_backfill_verified_xdex_price_history(
                        compare_market,
                        lookback_days=provider_history_lookback_days,
                        min_refresh_seconds=provider_history_min_refresh_seconds,
                        rel_tolerance=provider_history_rel_tolerance,
                    )
                )

        response = self._historical_from_market(
            params.get("question"),
            market,
            mode=mode,
            compare_market_envelope=compare_market,
            metrics=params.get("metrics"),
            gap_threshold_seconds=gap_threshold,
            anchor_tolerance_seconds=anchor_tolerance,
            onchain_page_size=onchain_page_size,
            onchain_max_signatures=onchain_max_signatures,
        )
        if isinstance(definition, Mapping) and response.get("status") in {"ok", "partial"}:
            response = self._canonicalize(
                response,
                definition,
                provider_asset=self._provider_asset_from_data(market.get("data")),
                role="market",
            )

        if isinstance(response.get("data"), dict):
            if provider_backfill is not None:
                response["data"]["provider_history_backfill"] = provider_backfill
            if compare_provider_backfill is not None:
                response["data"][
                    "compare_provider_history_backfill"
                ] = compare_provider_backfill

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
