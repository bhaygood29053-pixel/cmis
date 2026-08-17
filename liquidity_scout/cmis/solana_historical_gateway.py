"""Narrow Solana historical-comparison gateway for CMIS.

The first accepted Solana history slice compares only Jupiter Price V3 source
values for one exact mint. It requires the provenance-safe Solana observation
ledger and an explicit deployment-owned history-distance policy. It never mixes
providers, DEX pairs, or collection time with provider observation time.

Because current Solana price freshness and shared observation scope are not yet
verified, a numerical historical comparison remains partial/non-promotable.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation
import math
import time
from typing import Any

from liquidity_scout.cmis.evidence import AGREEMENT, CONFLICT
from liquidity_scout.cmis.solana_observation_ledger import (
    JUPITER_SCOPE,
    JUPITER_SOURCE,
    PRICE_USD,
)
from liquidity_scout.services.cmis_contract import (
    ERROR,
    OK,
    PARTIAL,
    UNAVAILABLE,
    build_service_envelope,
)

SERVICE = "historical_compare"
CHAIN = "solana"
_ALLOWED_PARAMS = frozenset({"metric", "period_seconds", "source"})


def _nonnegative_seconds(value: Any, *, field: str, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a non-negative finite number")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{field} must be a non-negative finite number")
    return parsed


def _period_seconds(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("period_seconds must be a positive integer")
    return value


def _decimal(value: Any, *, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field} must be a positive finite decimal")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a positive finite decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{field} must be a positive finite decimal")
    return parsed


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    normalized = text.rstrip("0").rstrip(".") if "." in text else text
    return normalized or "0"


def _jupiter_block_id(envelope: Mapping[str, Any]) -> int | None:
    sources = envelope.get("sources")
    if not isinstance(sources, list):
        return None
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        if source.get("source") != JUPITER_SOURCE:
            continue
        if source.get("role") != "market_report.price_source":
            continue
        block_id = source.get("block_id")
        if isinstance(block_id, bool) or not isinstance(block_id, int) or block_id < 0:
            return None
        return block_id
    return None


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


class SolanaHistoricalCompareMixin:
    """Cooperative CMIS mixin for same-source Jupiter price history."""

    def __init__(
        self,
        *,
        solana_observation_ledger: Any = None,
        solana_history_max_distance_seconds: Any = None,
        solana_history_clock: Callable[[], Any] | None = None,
        **kwargs: Any,
    ):
        self.solana_observation_ledger = solana_observation_ledger
        self.solana_history_max_distance_seconds = _nonnegative_seconds(
            solana_history_max_distance_seconds,
            field="solana_history_max_distance_seconds",
            allow_none=True,
        )
        clock = time.time if solana_history_clock is None else solana_history_clock
        if not callable(clock):
            raise ValueError("solana_history_clock must be callable")
        self.solana_history_clock = clock
        super().__init__(**kwargs)

    def _history_error(self, code: str, message: str):
        return build_service_envelope(
            SERVICE,
            CHAIN,
            ERROR,
            errors=[{"code": code, "message": message}],
        )

    def _history_unavailable(self, code: str, message: str, *, data=None, warnings=None):
        warning_items = list(warnings or [])
        warning_items.insert(0, _warning(code, message))
        return build_service_envelope(
            SERVICE,
            CHAIN,
            UNAVAILABLE,
            data=data,
            warnings=warning_items,
        )

    def _validate_history_request(self, params: Mapping[str, Any]):
        unknown = sorted(set(params) - _ALLOWED_PARAMS)
        if unknown:
            return None, self._history_error(
                "solana_historical_params_not_supported",
                "Unsupported Solana historical parameters: " + ", ".join(unknown) + ".",
            )

        metric = params.get("metric")
        source = params.get("source")
        if metric != PRICE_USD:
            return None, self._history_error(
                "solana_historical_metric_not_supported",
                "The first Solana historical slice supports price_usd only.",
            )
        if source != JUPITER_SOURCE:
            return None, self._history_error(
                "solana_historical_source_not_supported",
                "The first Solana price-history slice requires source=jupiter_price_v3.",
            )
        try:
            period = _period_seconds(params.get("period_seconds"))
        except ValueError as exc:
            return None, self._history_error(
                "solana_historical_period_invalid",
                str(exc),
            )

        return {
            "metric": metric,
            "source": source,
            "period_seconds": period,
        }, None

    def _solana_historical_compare(self, asset: Any, params: Mapping[str, Any]):
        request, failure = self._validate_history_request(params)
        if failure is not None:
            return failure
        assert request is not None

        ledger = self.solana_observation_ledger
        if ledger is None:
            return self._history_unavailable(
                "solana_observation_ledger_not_configured",
                "The provenance-safe Solana observation ledger is not configured.",
            )
        max_distance = self.solana_history_max_distance_seconds
        if max_distance is None:
            return self._history_unavailable(
                "solana_history_distance_policy_not_configured",
                "No explicit maximum historical collection-time distance is configured.",
            )
        if max_distance >= request["period_seconds"]:
            return self._history_error(
                "solana_history_window_overlaps_current",
                (
                    "The maximum historical distance must be smaller than the requested "
                    "period so a near-current observation cannot become the baseline."
                ),
            )

        try:
            now = _nonnegative_seconds(
                self.solana_history_clock(),
                field="solana_history_clock result",
            )
        except Exception as exc:
            return self._history_error(
                "solana_history_clock_invalid",
                f"Solana history clock failed ({type(exc).__name__}).",
            )
        assert now is not None
        target_time = now - request["period_seconds"]
        if target_time < 0:
            return self._history_error(
                "solana_historical_period_before_epoch",
                "The requested period extends before the Unix epoch.",
            )

        market = self._solana_market_report(asset)
        if not isinstance(market, Mapping):
            return self._history_error(
                "solana_market_report_contract_invalid",
                "The Solana market-report prerequisite returned a malformed result.",
            )
        if market.get("status") not in {OK, PARTIAL}:
            return self._propagate_upstream(SERVICE, market)

        market_asset = market.get("asset")
        market_data = market.get("data")
        if not isinstance(market_asset, Mapping) or not isinstance(market_data, Mapping):
            return self._history_error(
                "solana_market_report_contract_invalid",
                "The Solana market-report prerequisite is incomplete.",
            )
        mint = market_asset.get("mint")
        if not isinstance(mint, str) or not mint:
            return self._history_error(
                "solana_market_report_contract_invalid",
                "The Solana market-report prerequisite contains no exact mint.",
            )
        if market_data.get("price_source") != JUPITER_SOURCE:
            return self._history_error(
                "solana_jupiter_price_contract_invalid",
                "The accepted market report does not identify Jupiter as the source value.",
            )
        try:
            current_price = _decimal(
                market_data.get("price_usd_source_value"),
                field="current Jupiter price",
            )
        except ValueError as exc:
            return self._history_error(
                "solana_jupiter_price_contract_invalid",
                str(exc),
            )
        block_id = _jupiter_block_id(market)
        if block_id is None:
            return self._history_error(
                "solana_jupiter_block_contract_invalid",
                "The current Jupiter source observation has no valid block_id provenance.",
            )

        crosscheck = market_data.get("price_crosscheck")
        if not isinstance(crosscheck, Mapping) or crosscheck.get("semantics_verified") is not True:
            return self._history_error(
                "solana_price_semantics_unverified",
                "The current Jupiter price does not carry accepted cross-source semantics.",
            )
        crosscheck_status = crosscheck.get("status")
        if crosscheck_status not in {AGREEMENT, CONFLICT}:
            return self._history_error(
                "solana_price_crosscheck_status_invalid",
                "Historical price collection requires a bounded agreement/conflict result.",
            )

        try:
            historical = ledger.nearest(
                mint=mint,
                metric=PRICE_USD,
                source=JUPITER_SOURCE,
                scope=JUPITER_SCOPE,
                subject_id=mint,
                target_time=target_time,
                max_distance_seconds=max_distance,
            )
        except Exception as exc:
            return self._history_error(
                "solana_history_lookup_failed_closed",
                f"Solana history lookup failed ({type(exc).__name__}).",
            )

        current_observation = {
            "chain": CHAIN,
            "mint": mint,
            "metric": PRICE_USD,
            "source": JUPITER_SOURCE,
            "scope": JUPITER_SCOPE,
            "subject_id": mint,
            "pair_address": None,
            "requested_mint_role": None,
            "base_mint": None,
            "quote_mint": None,
            "value": _decimal_text(current_price),
            "provider_observed_at": None,
            "provider_block_id": block_id,
            "provider_block_slot": None,
            "identity_verified": True,
            "semantics_verified": True,
            "freshness_verified": False,
        }
        try:
            stored = ledger.store(current_observation, collected_at=now)
        except Exception as exc:
            return self._history_error(
                "solana_history_store_failed_closed",
                f"Solana history persistence failed ({type(exc).__name__}).",
            )
        if not isinstance(stored, Mapping) or not isinstance(stored.get("observation_id"), str):
            return self._history_error(
                "solana_history_store_contract_invalid",
                "The Solana observation ledger returned a malformed persistence result.",
            )

        common_data = {
            "metric": PRICE_USD,
            "source": JUPITER_SOURCE,
            "scope": JUPITER_SCOPE,
            "period_seconds": request["period_seconds"],
            "target_collection_time": target_time,
            "max_distance_seconds": max_distance,
            "timestamp_basis": "collection_time",
            "current_value": _decimal_text(current_price),
            "current_collection_time": now,
            "current_observation_id": stored["observation_id"],
            "current_provider_block_id": block_id,
            "current_freshness_verified": False,
            "current_market_crosscheck_status": crosscheck_status,
            "cmis_promotable": False,
        }
        common_warnings = [
            _warning(
                "solana_history_collection_time_basis",
                "Historical selection uses CMIS collection time, not verified provider observation time.",
            ),
            _warning(
                "solana_history_absolute_freshness_unverified",
                "The current accepted Jupiter price does not establish absolute wall-clock freshness.",
            ),
            _warning(
                "solana_history_not_promotable",
                "This historical price comparison is bounded source evidence and is not promotable as verified current-price truth.",
            ),
        ]
        if crosscheck_status == CONFLICT:
            common_warnings.append(
                _warning(
                    "solana_current_price_cross_source_conflict",
                    "The current Jupiter source value conflicts with at least one eligible DEX Screener base-pair price.",
                )
            )

        if not isinstance(historical, Mapping):
            return self._history_unavailable(
                "solana_historical_baseline_unavailable",
                "No comparable verified Jupiter observation exists within the configured historical window yet.",
                data=common_data,
                warnings=common_warnings,
            )

        old_observation = historical.get("observation")
        if not isinstance(old_observation, Mapping):
            return self._history_error(
                "solana_historical_baseline_contract_invalid",
                "The Solana observation ledger returned a malformed historical observation.",
            )
        try:
            historical_price = _decimal(
                old_observation.get("value"),
                field="historical Jupiter price",
            )
        except ValueError as exc:
            return self._history_error(
                "solana_historical_baseline_contract_invalid",
                str(exc),
            )

        absolute_change = current_price - historical_price
        change_pct = (absolute_change / historical_price) * Decimal("100")
        historical_freshness = old_observation.get("freshness_verified") is True
        data = dict(common_data)
        data.update(
            {
                "historical_value": _decimal_text(historical_price),
                "historical_collection_time": old_observation.get("collected_at"),
                "historical_observation_id": historical.get("observation_id"),
                "historical_distance_seconds": historical.get("distance_seconds"),
                "historical_freshness_verified": historical_freshness,
                "absolute_change": _decimal_text(absolute_change),
                "change_pct": _decimal_text(change_pct),
                "source_consistency_verified": True,
                "scope_consistency_verified": True,
                "subject_consistency_verified": True,
                "comparison_semantics_verified": True,
                "provider_observation_time_verified": False,
            }
        )
        checks = {
            "identity_verified": True,
            "current_semantics_verified": True,
            "historical_identity_semantics_verified": True,
            "source_scope_subject_match": True,
            "current_freshness_verified": False,
            "historical_freshness_verified": historical_freshness,
            "provider_observation_time_verified": False,
        }
        verified = sum(1 for value in checks.values() if value)
        sources = [
            {
                "source": JUPITER_SOURCE,
                "role": "historical_compare.current_source_value",
                "block_id": block_id,
                "collected_at": now,
            },
            {
                "source": "solana_observation_ledger",
                "role": "historical_compare.same_source_baseline",
                "observation_id": historical.get("observation_id"),
                "collected_at": old_observation.get("collected_at"),
                "underlying_source": JUPITER_SOURCE,
                "scope": JUPITER_SCOPE,
            },
        ]
        return build_service_envelope(
            SERVICE,
            CHAIN,
            PARTIAL,
            asset={"chain": CHAIN, "mint": mint},
            data=data,
            confidence={
                "complete": False,
                "verified_checks": verified,
                "total_checks": len(checks),
                "verification_ratio": round(verified / len(checks), 6),
                "checks": checks,
            },
            sources=sources,
            observed_at=None,
            warnings=common_warnings,
            errors=[],
        )

    def dispatch(self, request: Any):
        if isinstance(request, Mapping):
            service = (self._text(request.get("service")) or "").lower()
            chain = (self._text(request.get("chain")) or "").lower()
            if service == SERVICE and chain == CHAIN:
                params = request.get("params", {})
                if not isinstance(params, Mapping):
                    return self._gateway_error(
                        SERVICE,
                        CHAIN,
                        "invalid_params",
                        "params must be a JSON object/mapping.",
                    )
                return self._solana_historical_compare(request.get("asset"), params)
        return super().dispatch(request)


__all__ = ["CHAIN", "SERVICE", "SolanaHistoricalCompareMixin"]
