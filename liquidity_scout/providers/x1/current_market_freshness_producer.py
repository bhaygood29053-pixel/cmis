"""Concrete X1 current-market freshness evidence producer for #511.

This producer operates on the exact market envelope already selected by CMIS.
It never searches for a different candidate market. Expensive work is intended
for the protected #510 background refresh manager, not the user request path.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import time
from typing import Any

from liquidity_scout.providers.x1.bridge_source_provenance import (
    BridgeSourceProof,
    evaluate_bridge_source_provenance,
)
from liquidity_scout.providers.x1.current_pool_identity import (
    capture_x1_current_pool_identity,
)
from liquidity_scout.providers.x1.current_usdcx_usd_capture import (
    capture_current_usdcx_usd_equivalence_evidence,
)
from liquidity_scout.providers.x1.liquidity_freshness import (
    REFERENCE_POOL_ADDRESS,
    evaluate_x1_ninja_current_pool_scope,
    evaluate_x1_ninja_liquidity_freshness,
)
from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_price_fact_time import (
    collect_ninja_price_fact_time_snapshot,
)
from liquidity_scout.providers.x1.rolling_24h_market_activity import (
    evaluate_x1_rolling_24h_market_activity,
    reconstruct_x1_pool_24h_chain_activity,
)
from liquidity_scout.providers.x1.trade_time_usd_valuation import (
    capture_historical_xnt_usdcx_reference_rate,
    capture_kraken_usdc_usd_fact_price,
    evaluate_historical_usdcx_parity,
    resolve_xnt_quote_usd_value,
)
from liquidity_scout.providers.x1.usdcx_destination_parity import (
    SOLANA_USDC_MINT,
    WARP_USDC_ROUTE_ID,
    X1_USDC_X_MINT,
    evaluate_usdcx_destination_parity,
)
from liquidity_scout.providers.x1.warp_bridged_supply_evidence import (
    build_warp_bridged_supply_evidence,
    capture_destination_mint_observation,
    capture_source_vault_observation,
)
from liquidity_scout.providers.x1.warp_config_semantics import (
    WARP_CONFIG_SOURCE_URL,
    build_warp_config_route_observation,
)
from liquidity_scout.providers.x1.warp_lifecycle_rpc_retry import (
    resilient_get_transaction_post,
)
from liquidity_scout.providers.x1.warp_message_interval_retention import (
    capture_warp_message_interval_retention,
)
from liquidity_scout.providers.x1.warp_message_retention_coverage import (
    evaluate_warp_message_counter_closure,
    fetch_classified_warp_config_account,
    fetch_official_warp_config,
)
from liquidity_scout.providers.x1.warp_onchain_transfer_history import (
    capture_warp_message_state,
    normalize_warp_route_events,
)
from liquidity_scout.services.cmis_bridge_route_evidence import (
    qualify_warp_bridge_route,
)
from liquidity_scout.services.cmis_cross_chain_provenance import (
    build_cross_chain_asset_provenance,
)


SCHEMA = "x1_current_market_freshness_producer/v1"
DEFAULT_MAX_SIGNATURES = 5000


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _market_mint(market: Mapping[str, Any]) -> str | None:
    asset = _mapping(market.get("asset"))
    data = _mapping(market.get("data"))
    return _text(asset.get("mint") or data.get("mint"))


def _endpoint(chain: str, mint: str) -> dict[str, str]:
    return {"chain": chain, "asset_id": mint, "asset_id_kind": "mint"}


def build_x1_historical_usd_context(
    *,
    oldest_fact_time: int,
    clock: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Capture the accepted shared Warp context for historical XNT/USD."""

    official = fetch_official_warp_config()
    source = _endpoint("solana", SOLANA_USDC_MINT)
    destination = _endpoint("x1", X1_USDC_X_MINT)
    route_observation = build_warp_config_route_observation(
        config_response=official,
        route_id=WARP_USDC_ROUTE_ID,
        source=source,
        destination=destination,
    )
    provenance = build_cross_chain_asset_provenance(
        canonical_asset_id="usdc",
        origin=source,
        current=destination,
        hops=[
            {
                "source": source,
                "destination": destination,
                "bridge": "Warp Bridge",
                "representation_type": "bridge_representation",
                "custody_model": "unknown",
                "bridge_route_id": WARP_USDC_ROUTE_ID,
            }
        ],
    )
    source_provenance = evaluate_bridge_source_provenance(
        url=WARP_CONFIG_SOURCE_URL,
        proofs=[
            BridgeSourceProof(
                proof_type="official_app_network_observation",
                reference="accepted exact Warp config endpoint",
                exact_url=WARP_CONFIG_SOURCE_URL,
            )
        ],
    )
    qualification = qualify_warp_bridge_route(
        provenance=provenance,
        hop_index=0,
        source_provenance=source_provenance,
        observation=route_observation,
        evaluated_at=route_observation["source_observed_at"] + 1,
    )
    if qualification.get("warp_qualified") is not True:
        raise ValueError("exact Warp USDC route did not qualify")

    backing = build_warp_bridged_supply_evidence(
        route_observation=route_observation,
        source_vault=capture_source_vault_observation(
            source_mint=SOLANA_USDC_MINT
        ),
        destination_mint=capture_destination_mint_observation(
            destination_mint=X1_USDC_X_MINT
        ),
        evaluated_at=float(clock()),
    )
    current_parity = evaluate_usdcx_destination_parity(backing)
    if current_parity.get("current_reserve_backing_verified") is not True:
        raise ValueError("current USDC.X reserve backing is not verified")

    message_state = capture_warp_message_state()
    normalized = normalize_warp_route_events(
        route_observation=route_observation,
        message_state=message_state,
    )
    if not (
        normalized.get("pairing_semantics_verified") is True
        and normalized.get("settled_event_semantics_verified") is True
        and normalized.get("flow_event_normalization_authorized") is True
    ):
        raise ValueError("Warp route-event normalization is not verified")

    classified = {
        "solana": fetch_classified_warp_config_account(chain="solana"),
        "x1": fetch_classified_warp_config_account(chain="x1"),
    }
    counter_closure = evaluate_warp_message_counter_closure(
        config_response=official,
        classified_configs=classified,
        message_state=message_state,
    )
    if not (
        counter_closure.get("counter_account_closure_verified") is True
        and counter_closure.get("current_message_universe_count_closed") is True
    ):
        raise ValueError("Warp current message universe is not closed")

    interval_retention = capture_warp_message_interval_retention(
        counter_closure=counter_closure,
        message_state=message_state,
        requested_start=int(oldest_fact_time),
        as_of=int(clock()),
        post=resilient_get_transaction_post,
    )
    for field in (
        "interval_retention_complete_verified",
        "requested_window_coverage_verified",
        "coverage_complete_verified",
        "missing_history_zero_authorized",
    ):
        if interval_retention.get(field) is not True:
            raise ValueError(f"Warp interval retention missing {field}")
    if interval_retention.get("sixty_day_bridge_flow_retention_promoted") is not False:
        raise ValueError("short interval retention widened into 60-day semantics")

    return {
        "route_qualification": qualification,
        "current_backing": backing,
        "normalized_events": normalized,
        "interval_retention": interval_retention,
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }


def build_x1_historical_usd_resolver(
    context: Mapping[str, Any],
) -> Callable[..., Mapping[str, Any]]:
    """Build a cached per-swap historical XNT/USD resolver."""

    if not isinstance(context, Mapping) or context.get("execution_authorized") is not False:
        raise ValueError("accepted historical USD context is required")

    cache: dict[tuple[Any, ...], Mapping[str, Any]] = {}

    def resolve(
        *,
        block_time: Any,
        quote_mint: Any,
        quote_amount: Any,
        pool_identity: Mapping[str, Any],
        transaction: Mapping[str, Any],
        verification_report: Any,
    ) -> Mapping[str, Any]:
        del pool_identity, verification_report
        fact_time = int(block_time)
        fact_slot = transaction.get("slot")
        key = (fact_time, fact_slot, str(quote_mint), str(quote_amount))
        if key in cache:
            return cache[key]

        reference = capture_historical_xnt_usdcx_reference_rate(
            fact_time=fact_time,
            fact_slot=fact_slot,
        )
        historical_parity = evaluate_historical_usdcx_parity(
            fact_time=fact_time,
            current_backing_evidence=context["current_backing"],
            normalized_events=context["normalized_events"],
            lifecycle_retention=context["interval_retention"],
        )
        canonical = capture_kraken_usdc_usd_fact_price(fact_time=fact_time)
        result = resolve_xnt_quote_usd_value(
            fact_time=fact_time,
            quote_mint=quote_mint,
            quote_amount=quote_amount,
            reference_rate_evidence=reference,
            historical_usdcx_parity=historical_parity,
            canonical_usdc_usd_evidence=canonical,
        )
        cache[key] = result
        return result

    return resolve


def produce_x1_current_market_freshness_evidence(
    market: Mapping[str, Any],
    *,
    evaluated_at: float | None = None,
    max_signatures: int = DEFAULT_MAX_SIGNATURES,
    clock: Callable[[], float] = time.time,
    catalog_fetcher: Callable[..., Any] = fetch_all_pools,
    scope_evaluator: Callable[..., Mapping[str, Any]] = (
        evaluate_x1_ninja_current_pool_scope
    ),
    snapshot_collector: Callable[..., Mapping[str, Any]] = (
        collect_ninja_price_fact_time_snapshot
    ),
    current_usdcx_capturer: Callable[..., Mapping[str, Any]] = (
        capture_current_usdcx_usd_equivalence_evidence
    ),
    liquidity_evaluator: Callable[..., Mapping[str, Any]] = (
        evaluate_x1_ninja_liquidity_freshness
    ),
    identity_capturer: Callable[..., Mapping[str, Any]] = (
        capture_x1_current_pool_identity
    ),
    window_reconstructor: Callable[..., Mapping[str, Any]] = (
        reconstruct_x1_pool_24h_chain_activity
    ),
    rolling_evaluator: Callable[..., Mapping[str, Any]] = (
        evaluate_x1_rolling_24h_market_activity
    ),
    historical_context_builder: Callable[..., Mapping[str, Any]] = (
        build_x1_historical_usd_context
    ),
    historical_resolver_builder: Callable[
        [Mapping[str, Any]], Callable[..., Mapping[str, Any]]
    ] = build_x1_historical_usd_resolver,
) -> dict[str, Any]:
    """Produce exact-market liquidity and rolling freshness evidence."""

    del evaluated_at  # request evaluation time is not provider fact time.
    if not isinstance(market, Mapping):
        raise TypeError("market must be a mapping")
    if market.get("chain") not in {None, "x1"}:
        raise ValueError("X1 market envelope required")
    mint = _market_mint(market)
    if not mint:
        raise ValueError("market exact mint is required")
    if isinstance(max_signatures, bool) or not isinstance(max_signatures, int):
        raise ValueError("max_signatures must be an integer")
    if max_signatures < 100 or max_signatures > 100000:
        raise ValueError("max_signatures must be between 100 and 100000")

    started_at = float(clock())
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "chain": "x1",
        "asset_mint": mint,
        "started_at": started_at,
        "liquidity_freshness_evidence": None,
        "rolling_activity_evidence": None,
        "failures": [],
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }

    pools, _xnt_price = catalog_fetcher(sleep_seconds=0)
    if not isinstance(pools, Sequence) or isinstance(pools, (str, bytes, bytearray)):
        result["failures"].append("provider_catalog_unavailable")
        return result

    scope = scope_evaluator(market_envelope=market, catalog_pools=pools)
    if scope.get("provider_scoped_pool_universe_verified") is not True:
        result["failures"].append("provider_scoped_pool_universe_unverified")
        result["pool_scope_evidence"] = scope
        return result
    result["pool_scope_evidence"] = scope
    addresses = list(scope.get("market_contributing_pool_addresses") or [])
    if not addresses:
        result["failures"].append("market_contributing_pool_set_unavailable")
        return result

    requested = list(addresses)
    if REFERENCE_POOL_ADDRESS not in requested:
        requested.append(REFERENCE_POOL_ADDRESS)
    snapshot = snapshot_collector(pool_addresses=requested)

    try:
        usdcx = current_usdcx_capturer()
        equivalence = _mapping(usdcx.get("equivalence"))
        liquidity = liquidity_evaluator(
            market_envelope=market,
            snapshot=snapshot,
            current_usdcx_usd_equivalence=equivalence,
            pool_scope_evidence=scope,
            evaluated_at=float(clock()),
            max_pools=150,
        )
        if liquidity.get("execution_authorized") is not False:
            raise ValueError("liquidity evidence attempted execution authority")
        result["liquidity_freshness_evidence"] = liquidity
        if liquidity.get("liquidity_freshness_verified") is not True:
            result["failures"].append("liquidity_freshness_unverified")
    except Exception as exc:
        result["failures"].append(
            f"liquidity_production_failed:{type(exc).__name__}:{exc}"
        )

    end_epoch = int(clock())
    start_epoch = end_epoch - 86400
    identities: dict[str, Mapping[str, Any]] = {}
    unvalued_windows: list[Mapping[str, Any]] = []

    try:
        for address in addresses:
            identity = identity_capturer(
                pool_address=address,
                asset_mint=mint,
                snapshot=snapshot,
            )
            if identity.get("identity_verified") is not True:
                raise ValueError(f"pool identity unverified: {address}")
            identities[address] = identity
            unvalued_windows.append(
                window_reconstructor(
                    pool_identity=identity,
                    start_epoch=start_epoch,
                    end_epoch=end_epoch,
                    max_signatures=max_signatures,
                )
            )

        swap_times = [
            int(row["block_time"])
            for window in unvalued_windows
            for row in (window.get("transactions") or [])
            if isinstance(row, Mapping)
            and row.get("classification") == "EXACT_POOL_SWAP"
            and row.get("block_time") is not None
        ]

        windows = unvalued_windows
        if swap_times:
            try:
                context = historical_context_builder(
                    oldest_fact_time=min(swap_times),
                    clock=clock,
                )
                usd_resolver = historical_resolver_builder(context)
                windows = [
                    window_reconstructor(
                        pool_identity=identities[address],
                        start_epoch=start_epoch,
                        end_epoch=end_epoch,
                        max_signatures=max_signatures,
                        usd_quote_resolver=usd_resolver,
                    )
                    for address in addresses
                ]
            except Exception as exc:
                # Keep the exact unvalued windows so transaction-count freshness
                # can still be independently evaluated. Only USD volume remains
                # fail-closed.
                result["failures"].append(
                    f"historical_usd_production_failed:{type(exc).__name__}:{exc}"
                )

        rolling = rolling_evaluator(
            market_envelope=market,
            pool_scope_evidence=scope,
            pool_windows=windows,
            evaluated_at=end_epoch,
        )
        if rolling.get("execution_authorized") is not False:
            raise ValueError("rolling evidence attempted execution authority")
        result["rolling_activity_evidence"] = rolling
        if not (
            rolling.get("volume_24h_freshness_verified") is True
            and rolling.get("transactions_24h_freshness_verified") is True
        ):
            result["failures"].append("rolling_freshness_partial_or_unverified")
    except Exception as exc:
        result["failures"].append(
            f"rolling_production_failed:{type(exc).__name__}:{exc}"
        )

    result["completed_at"] = float(clock())
    result["liquidity_freshness_verified"] = bool(
        _mapping(result.get("liquidity_freshness_evidence")).get(
            "liquidity_freshness_verified"
        )
        is True
    )
    rolling = _mapping(result.get("rolling_activity_evidence"))
    result["volume_24h_freshness_verified"] = bool(
        rolling.get("volume_24h_freshness_verified") is True
    )
    result["transactions_24h_freshness_verified"] = bool(
        rolling.get("transactions_24h_freshness_verified") is True
    )
    return result


__all__ = [
    "DEFAULT_MAX_SIGNATURES",
    "SCHEMA",
    "build_x1_historical_usd_context",
    "build_x1_historical_usd_resolver",
    "produce_x1_current_market_freshness_evidence",
]
