"""Trade-aware CMIS runtime with asset-level verified activity."""

from __future__ import annotations

from collections.abc import Mapping
import time
from typing import Any

from liquidity_scout.cmis.risk_evidence_gateway import EvidenceAwareCMISGateway
from liquidity_scout.market.resolver import find_matches_for_term, pair_name, pool_address
from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL
from liquidity_scout.services.cmis_activity_window import (
    apply_activity_window,
    parse_activity_window_seconds,
)
from liquidity_scout.services.cmis_chain_window_dex import (
    enumerate_chain_window_dex_activity,
)
from liquidity_scout.services.cmis_trade_verification import (
    SERVICE as TRADE_VERIFICATION_SERVICE,
    build_x1_trade_verification_response,
)
from liquidity_scout.services.cmis_verified_asset_activity import (
    SERVICE as VERIFIED_ASSET_ACTIVITY_SERVICE,
    build_verified_asset_activity_response,
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
SUPPORTED_SERVICES = BASE_SUPPORTED_SERVICES + (
    TRADE_VERIFICATION_SERVICE,
    VERIFIED_ASSET_ACTIVITY_SERVICE,
)


class TradeAwareCMISGateway(EvidenceAwareCMISGateway):
    """CMIS runtime with deterministic X1 trade and asset-activity verification."""

    def __init__(
        self,
        *,
        x1_trade_rpc_url: str = DEFAULT_X1_RPC_URL,
        x1_trade_verifier=None,
        x1_trade_history_fetcher=None,
        x1_activity_now_fn=None,
        x1_chain_window_enumerator=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.x1_trade_rpc_url = str(x1_trade_rpc_url or "").strip()
        if not self.x1_trade_rpc_url:
            raise ValueError("x1_trade_rpc_url must not be empty")
        self.x1_trade_verifier = x1_trade_verifier
        self.x1_trade_history_fetcher = (
            x1_trade_history_fetcher or fetch_pool_trades_raw
        )
        self.x1_activity_now_fn = x1_activity_now_fn or time.time
        self.x1_chain_window_enumerator = (
            x1_chain_window_enumerator or enumerate_chain_window_dex_activity
        )

    @staticmethod
    def _bounded_positive_int(name, value, *, default, maximum):
        raw = default if value is None else value
        if isinstance(raw, bool):
            raise ValueError(f"{name} must be a positive integer <= {maximum}")
        try:
            parsed = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{name} must be a positive integer <= {maximum}"
            ) from exc
        if parsed <= 0 or parsed > maximum:
            raise ValueError(f"{name} must be a positive integer <= {maximum}")
        return parsed

    @staticmethod
    def _bool_param(name, value, *, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        raise ValueError(f"{name} must be a boolean")

    def _trade_verification(self, params: Mapping[str, Any]):
        event = params.get("event")
        kwargs = {"rpc_url": self.x1_trade_rpc_url}
        if self.x1_trade_verifier is not None:
            kwargs["verifier"] = self.x1_trade_verifier
        return build_x1_trade_verification_response(event, **kwargs)

    @staticmethod
    def _attach_chain_window_activity(response, activity):
        """Attach chain-first selected-pool evidence without promoting asset completeness."""
        if not isinstance(response, dict) or not isinstance(activity, Mapping):
            return response

        data = response.get("data")
        if not isinstance(data, dict):
            data = {}
            response["data"] = data
        data["chain_window_dex_activity"] = dict(activity)

        summary = activity.get("summary")
        summary = summary if isinstance(summary, Mapping) else {}

        selected_pool_complete = (
            summary.get("selected_pool_chain_window_complete") is True
        )
        asset_window_complete = summary.get("asset_window_complete") is True
        asset_completion_promoted = (
            summary.get("asset_window_completion_promoted") is True
        )

        confidence = response.get("confidence")
        if not isinstance(confidence, dict):
            confidence = {}
            response["confidence"] = confidence
        confidence["selected_pool_chain_window_complete"] = selected_pool_complete
        confidence["chain_window_asset_window_complete"] = asset_window_complete
        confidence["chain_window_asset_completion_promoted"] = (
            asset_completion_promoted
        )
        confidence["provider_window_coverage_complete"] = (
            confidence.get("window_coverage_complete") is True
        )

        transaction_count = summary.get("unique_window_transaction_count")
        if isinstance(transaction_count, int) and transaction_count >= 0:
            confidence["chain_window_unique_transaction_count"] = transaction_count
            confidence["selected_pool_chain_window_empty"] = (
                selected_pool_complete and transaction_count == 0
            )

        activity_window = data.get("activity_window")
        if isinstance(activity_window, Mapping):
            activity_window = dict(activity_window)
            activity_window["provider_coverage_complete"] = (
                activity_window.get("coverage_complete") is True
            )
            activity_window["selected_pool_chain_coverage_complete"] = (
                selected_pool_complete
            )
            activity_window["selected_pool_chain_coverage_basis"] = (
                "X1_RPC_ADDRESS_HISTORY"
            )
            activity_window["asset_window_complete"] = asset_window_complete
            if asset_window_complete:
                activity_window["effective_coverage_scope"] = "asset"
            elif selected_pool_complete:
                activity_window["effective_coverage_scope"] = "selected_pools"
            else:
                activity_window["effective_coverage_scope"] = (
                    "provider_observations_only"
                )
            data["activity_window"] = activity_window

        if selected_pool_complete:
            warnings = response.get("warnings")
            warnings = list(warnings) if isinstance(warnings, list) else []
            reconciled = []
            for warning in warnings:
                if not isinstance(warning, Mapping):
                    reconciled.append(warning)
                    continue
                item = dict(warning)
                code = item.get("code")
                if code == "activity_window_range_not_proven":
                    item = {
                        "code": "activity_window_asset_scope_not_proven",
                        "message": (
                            "Direct X1 RPC address-history evidence proves the "
                            "requested window for every selected pool. Asset-wide "
                            "window coverage is still not proven because global "
                            "on-chain pool discovery is not independently exhaustive."
                        ),
                    }
                elif code == "activity_window_timestamp_membership_incomplete":
                    item["message"] = (
                        str(item.get("message") or "").rstrip()
                        + " This affects provider-derived event membership only; "
                        "direct X1 chain-window evidence remains authoritative for "
                        "the selected pools."
                    )
                reconciled.append(item)
            response["warnings"] = reconciled

        # Deliberately do not alter status/window_coverage_complete. The chain-first
        # service proves selected pool address ranges, not globally exhaustive pool
        # discovery for the asset.
        return response

    def _verified_asset_activity(self, asset, params: Mapping[str, Any]):
        if not self._text(asset):
            return self._gateway_error(
                VERIFIED_ASSET_ACTIVITY_SERVICE,
                "x1",
                "asset_query_required",
                "An asset symbol, name, mint, or pool identifier is required.",
            )

        window_raw = params.get("window")
        window_seconds = None
        if window_raw is not None:
            try:
                window_seconds = parse_activity_window_seconds(window_raw)
            except ValueError as exc:
                return self._gateway_error(
                    VERIFIED_ASSET_ACTIVITY_SERVICE,
                    "x1",
                    "invalid_activity_window",
                    str(exc),
                )

        try:
            chain_window_requested = self._bool_param(
                "chain_window", params.get("chain_window"), default=False
            )
        except ValueError as exc:
            return self._gateway_error(
                VERIFIED_ASSET_ACTIVITY_SERVICE,
                "x1",
                "invalid_activity_bound",
                str(exc),
            )

        if chain_window_requested and window_seconds is None:
            return self._gateway_error(
                VERIFIED_ASSET_ACTIVITY_SERVICE,
                "x1",
                "chain_window_requires_window",
                "chain_window=true requires one supported window: 1h, 6h, or 24h.",
            )

        try:
            max_pools = self._bounded_positive_int(
                "max_pools", params.get("max_pools"), default=5, maximum=10
            )
            per_pool_limit = self._bounded_positive_int(
                "per_pool_limit",
                params.get("per_pool_limit"),
                default=50 if window_seconds is not None else 5,
                maximum=50,
            )
            chain_page_size = self._bounded_positive_int(
                "chain_page_size",
                params.get("chain_page_size"),
                default=1000,
                maximum=1000,
            )
            chain_max_signatures_per_pool = self._bounded_positive_int(
                "chain_max_signatures_per_pool",
                params.get("chain_max_signatures_per_pool"),
                default=1000,
                maximum=5000,
            )
        except ValueError as exc:
            return self._gateway_error(
                VERIFIED_ASSET_ACTIVITY_SERVICE,
                "x1",
                "invalid_activity_bound",
                str(exc),
            )

        window_end_epoch = None
        if window_seconds is not None:
            now_fn = getattr(self, "x1_activity_now_fn", None) or time.time
            window_end_epoch = float(now_fn())

        # Reuse the existing market path so activity attribution starts from
        # one canonical resolved asset identity.
        market = self._market_report(asset)
        if market.get("status") not in {"ok", "partial"}:
            return self._propagate_upstream(
                VERIFIED_ASSET_ACTIVITY_SERVICE, market
            )

        resolved_asset = market.get("asset")
        resolved_asset = (
            resolved_asset if isinstance(resolved_asset, Mapping) else {}
        )
        resolved_mint = self._text(resolved_asset.get("mint"))
        if not resolved_mint:
            response = build_verified_asset_activity_response(
                market_envelope=market,
                pool_records=[],
                matched_pool_count=0,
                selected_pool_count=0,
            )
            if window_seconds is not None:
                response = apply_activity_window(
                    response,
                    window_seconds=window_seconds,
                    window_end_epoch=window_end_epoch,
                    pool_records=[],
                )
            return response

        catalog, failure = self._collect_x1_catalog(
            VERIFIED_ASSET_ACTIVITY_SERVICE
        )
        if failure is not None:
            return failure

        # Find pools from the exact resolved mint, not the loose symbol.
        matches = [
            match
            for match in find_matches_for_term(resolved_mint, catalog["pools"])
            if match[3] >= 90
        ]

        unique_pools = []
        seen = set()
        for match in matches:
            pool = match[0]
            address = pool_address(pool)
            if address and address not in seen:
                seen.add(address)
                unique_pools.append(pool)

        selected_pools = unique_pools[:max_pools]
        pool_records = []

        for pool in selected_pools:
            address = pool_address(pool)
            record = {
                "pool_address": address,
                "pair": pair_name(pool),
                "history_ok": False,
                "provider_event_count": 0,
                "processed_event_count": 0,
                "verifications": [],
                "history_semantics": {},
                "provider_total_raw": None,
            }
            try:
                history = self.x1_trade_history_fetcher(address)
                raw = (
                    history.get("raw_response")
                    if isinstance(history, Mapping)
                    else None
                )
                rows = raw.get("trades") if isinstance(raw, Mapping) else None
                if not isinstance(rows, list):
                    raise ValueError(
                        "trade-history transport returned no usable trades list"
                    )

                selected_rows = rows[:per_pool_limit]
                record["history_ok"] = True
                record["provider_event_count"] = len(rows)
                record["processed_event_count"] = len(selected_rows)
                record["source"] = history.get("source")
                record["observed_at"] = history.get("observed_at")

                semantics = history.get("semantics")
                if isinstance(semantics, Mapping):
                    record["history_semantics"] = dict(semantics)

                contract = history.get("contract")
                if isinstance(contract, Mapping):
                    record["provider_total_raw"] = contract.get(
                        "provider_total_raw"
                    )

                for row in selected_rows:
                    record["verifications"].append(
                        self._trade_verification({"event": row})
                    )
            except Exception as exc:
                record["warning"] = {
                    "code": "pool_trade_history_unavailable",
                    "message": (
                        f"Trade history could not be collected for pool "
                        f"{address}: {exc}"
                    ),
                }
            pool_records.append(record)

        response = build_verified_asset_activity_response(
            market_envelope=market,
            pool_records=pool_records,
            matched_pool_count=len(unique_pools),
            selected_pool_count=len(selected_pools),
        )

        if window_seconds is not None:
            response = apply_activity_window(
                response,
                window_seconds=window_seconds,
                window_end_epoch=window_end_epoch,
                pool_records=pool_records,
            )

        if chain_window_requested:
            enumerator = (
                getattr(self, "x1_chain_window_enumerator", None)
                or enumerate_chain_window_dex_activity
            )
            pool_descriptors = [
                {
                    "pool_address": pool_address(pool),
                    "pair": pair_name(pool),
                }
                for pool in selected_pools
                if pool_address(pool)
            ]
            try:
                activity = enumerator(
                    asset_mint=resolved_mint,
                    pools=pool_descriptors,
                    start_epoch=window_end_epoch - window_seconds,
                    end_epoch=window_end_epoch,
                    rpc_url=self.x1_trade_rpc_url,
                    page_size=chain_page_size,
                    max_signatures_per_pool=chain_max_signatures_per_pool,
                )
                response = self._attach_chain_window_activity(response, activity)
            except Exception as exc:
                confidence = response.get("confidence")
                if not isinstance(confidence, dict):
                    confidence = {}
                    response["confidence"] = confidence
                confidence["selected_pool_chain_window_complete"] = False
                confidence["chain_window_asset_window_complete"] = False
                confidence["chain_window_asset_completion_promoted"] = False

                warnings = response.get("warnings")
                warnings = list(warnings) if isinstance(warnings, list) else []
                warnings.append({
                    "code": "chain_window_enumeration_unavailable",
                    "message": (
                        "Direct X1 chain-window enumeration could not be completed; "
                        f"provider-backed activity remains available. {type(exc).__name__}: {exc}"
                    ),
                })
                response["warnings"] = warnings
                if response.get("status") == "ok":
                    response["status"] = "partial"

        return response

    def dispatch(self, request: Any):
        if isinstance(request, Mapping):
            service = (self._text(request.get("service")) or "").lower()

            if service in {
                TRADE_VERIFICATION_SERVICE,
                VERIFIED_ASSET_ACTIVITY_SERVICE,
            }:
                chain = (self._text(request.get("chain")) or "").lower()
                if not chain:
                    return self._gateway_error(
                        service, "unknown", "chain_required", "chain is required."
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

                if service == TRADE_VERIFICATION_SERVICE:
                    return self._trade_verification(params)

                return self._verified_asset_activity(
                    request.get("asset"), params
                )

        return super().dispatch(request)


__all__ = [
    "BASE_SUPPORTED_SERVICES",
    "SUPPORTED_SERVICES",
    "TRADE_VERIFICATION_SERVICE",
    "VERIFIED_ASSET_ACTIVITY_SERVICE",
    "TradeAwareCMISGateway",
]
