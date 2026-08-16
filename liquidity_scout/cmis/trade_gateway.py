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

    def _trade_verification(self, params: Mapping[str, Any]):
        event = params.get("event")
        kwargs = {"rpc_url": self.x1_trade_rpc_url}
        if self.x1_trade_verifier is not None:
            kwargs["verifier"] = self.x1_trade_verifier
        return build_x1_trade_verification_response(event, **kwargs)

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
            max_pools = self._bounded_positive_int(
                "max_pools", params.get("max_pools"), default=5, maximum=10
            )
            per_pool_limit = self._bounded_positive_int(
                "per_pool_limit",
                params.get("per_pool_limit"),
                default=50 if window_seconds is not None else 5,
                maximum=50,
            )
        except ValueError as exc:
            return self._gateway_error(
                VERIFIED_ASSET_ACTIVITY_SERVICE,
                "x1",
                "invalid_activity_bound",
                str(exc),
            )

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
                    window_end_epoch=float(
                        getattr(self, "x1_activity_now_fn", time.time)()
                    ),
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
            now_fn = getattr(self, "x1_activity_now_fn", None) or time.time
            response = apply_activity_window(
                response,
                window_seconds=window_seconds,
                window_end_epoch=float(now_fn()),
                pool_records=pool_records,
            )

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
