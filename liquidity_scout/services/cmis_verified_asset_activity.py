"""Deterministic aggregation for CMIS Verified Asset Activity."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.services.cmis_contract import (
    OK,
    PARTIAL,
    UNAVAILABLE,
    build_service_envelope,
)

SERVICE = "verified_asset_activity"
EXACT_POOL_LEG = "EXACT_POOL_LEG_AMOUNTS"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _compact_event(verification, pool_address, requested_mint):
    data = verification.get("data") if isinstance(verification, Mapping) else {}
    data = data if isinstance(data, Mapping) else {}

    inferred_mint = _text(data.get("asset_mint"))
    side_verified = data.get("side_verified") is True
    asset_scope_verified = bool(
        side_verified and inferred_mint and inferred_mint == requested_mint
    )

    exact_pool_leg = None
    if (
        asset_scope_verified
        and data.get("verification_basis") == EXACT_POOL_LEG
        and isinstance(data.get("pool_leg"), Mapping)
    ):
        exact_pool_leg = dict(data["pool_leg"])

    return {
        "status": verification.get("status"),
        "pool_address": pool_address,
        "transaction_signature": data.get("transaction_signature"),
        "provider_type": data.get("provider_type"),
        "side": data.get("side"),
        "side_verified": side_verified,
        "asset_scope_verified": asset_scope_verified,
        "asset_mint": inferred_mint,
        "quote_mint": data.get("quote_mint"),
        "verification_level": data.get("verification_level"),
        "verification_basis": data.get("verification_basis"),
        "identity": data.get("identity"),
        "exact_pool_leg": exact_pool_leg,
        "warnings": list(verification.get("warnings") or []),
        "errors": list(verification.get("errors") or []),
    }


def build_verified_asset_activity_response(
    *,
    market_envelope: Mapping[str, Any],
    pool_records: Sequence[Mapping[str, Any]],
    matched_pool_count: int,
    selected_pool_count: int,
) -> dict[str, Any]:
    asset = market_envelope.get("asset")
    asset = dict(asset) if isinstance(asset, Mapping) else {}
    requested_mint = _text(asset.get("mint"))

    if not requested_mint:
        return build_service_envelope(
            SERVICE,
            market_envelope.get("chain") or "x1",
            UNAVAILABLE,
            asset=asset,
            warnings=[{
                "code": "verified_asset_mint_required",
                "message": (
                    "A resolved asset mint is required before activity can be "
                    "attributed to an asset."
                ),
            }],
        )

    provider_events = 0
    processed_events = 0
    successful_histories = 0
    verified_trades = 0
    verified_buys = 0
    verified_sells = 0
    swap_candidates = 0
    gated_non_swap = 0
    conflicts = 0
    unresolved = 0
    asset_scope_mismatches = 0
    bounded_event_pools = 0
    exact_amount_trades = 0
    exact_buy_amount_trades = 0
    exact_sell_amount_trades = 0

    exact_buy_asset = Decimal(0)
    exact_sell_asset = Decimal(0)
    quote_totals = {}

    warnings = []
    events = []
    pools = []

    for pool_record in pool_records:
        address = _text(pool_record.get("pool_address")) or ""
        history_ok = pool_record.get("history_ok") is True
        returned = int(pool_record.get("provider_event_count") or 0)
        selected = int(pool_record.get("processed_event_count") or 0)
        verifications = pool_record.get("verifications")
        verifications = (
            list(verifications)
            if isinstance(verifications, Sequence)
            and not isinstance(verifications, (str, bytes))
            else []
        )

        provider_events += returned
        processed_events += len(verifications)

        if history_ok:
            successful_histories += 1
            if selected < returned:
                bounded_event_pools += 1
        else:
            warning = pool_record.get("warning")
            if isinstance(warning, Mapping):
                warnings.append(dict(warning))

        pool_verified = 0
        pool_buys = 0
        pool_sells = 0
        pool_gated = 0
        pool_conflicts = 0
        pool_unresolved = 0

        for verification in verifications:
            if not isinstance(verification, Mapping):
                unresolved += 1
                pool_unresolved += 1
                continue

            event = _compact_event(
                verification,
                address,
                requested_mint,
            )
            events.append(event)

            provider_type = (_text(event.get("provider_type")) or "").lower()
            if provider_type in {"buy", "sell"}:
                swap_candidates += 1

            if event.get("verification_level") == "PROVIDER_EVENT_SEMANTICS_GATED":
                gated_non_swap += 1
                pool_gated += 1
                continue

            if verification.get("status") == "ambiguous":
                conflicts += 1
                pool_conflicts += 1
                continue

            if (
                event.get("side_verified") is True
                and event.get("asset_scope_verified") is not True
            ):
                asset_scope_mismatches += 1
                unresolved += 1
                pool_unresolved += 1
                continue

            if event.get("asset_scope_verified") is not True:
                unresolved += 1
                pool_unresolved += 1
                continue

            verified_trades += 1
            pool_verified += 1
            side = event.get("side")

            if side == "BUY":
                verified_buys += 1
                pool_buys += 1
            elif side == "SELL":
                verified_sells += 1
                pool_sells += 1

            leg = event.get("exact_pool_leg")
            if isinstance(leg, Mapping):
                asset_amount = _decimal(leg.get("asset_amount"))
                quote_amount = _decimal(leg.get("quote_amount"))
                quote_mint = _text(leg.get("quote_mint"))
                if (
                    asset_amount is not None
                    and quote_amount is not None
                    and quote_mint
                ):
                    exact_amount_trades += 1
                    if side == "BUY":
                        exact_buy_amount_trades += 1
                        exact_buy_asset += asset_amount
                    elif side == "SELL":
                        exact_sell_amount_trades += 1
                        exact_sell_asset += asset_amount

                    bucket = quote_totals.setdefault(
                        quote_mint,
                        {"buy": Decimal(0), "sell": Decimal(0)},
                    )
                    if side == "BUY":
                        bucket["buy"] += quote_amount
                    elif side == "SELL":
                        bucket["sell"] += quote_amount

        pools.append({
            "pool_address": address or None,
            "pair": pool_record.get("pair"),
            "history_ok": history_ok,
            "provider_event_count": returned,
            "processed_event_count": len(verifications),
            "event_coverage_bounded": history_ok and len(verifications) < returned,
            "verified_trade_count": pool_verified,
            "verified_buy_count": pool_buys,
            "verified_sell_count": pool_sells,
            "gated_event_count": pool_gated,
            "conflict_count": pool_conflicts,
            "unresolved_count": pool_unresolved,
        })

    pool_selection_complete = selected_pool_count >= matched_pool_count
    pool_history_complete = (
        selected_pool_count > 0
        and successful_histories == selected_pool_count
    )
    event_coverage_complete = bounded_event_pools == 0
    verification_complete = (
        conflicts == 0
        and unresolved == 0
        and asset_scope_mismatches == 0
        and gated_non_swap == 0
    )
    market_data_for_completeness = market_envelope.get("data")
    market_data_for_completeness = (
        market_data_for_completeness
        if isinstance(market_data_for_completeness, Mapping)
        else {}
    )
    market_completeness = market_data_for_completeness.get("completeness")
    market_completeness = (
        market_completeness if isinstance(market_completeness, Mapping) else {}
    )
    # Verified Asset Activity does not consume holder identity/count semantics.
    # A market_report that is partial only because holder semantics are
    # unverified must not silently downgrade otherwise complete trade/activity
    # evidence. Preserve the pre-#304 activity contract by evaluating only the
    # market fields this service actually carries in its snapshot.
    activity_market_keys = (
        "price",
        "liquidity",
        "volume_24h",
        "transactions_24h",
    )
    market_complete = all(
        market_completeness.get(key) is True for key in activity_market_keys
    )

    complete = bool(
        pool_selection_complete
        and pool_history_complete
        and event_coverage_complete
        and verification_complete
        and market_complete
    )

    if selected_pool_count <= 0 or successful_histories <= 0:
        status = UNAVAILABLE
    else:
        status = OK if complete else PARTIAL

    if matched_pool_count == 0:
        warnings.append({
            "code": "asset_pool_coverage_unavailable",
            "message": "No exact XDEX pool matches were found for the resolved mint.",
        })
    if not pool_selection_complete:
        warnings.append({
            "code": "activity_pool_coverage_bounded",
            "message": (
                f"Only {selected_pool_count} of {matched_pool_count} matched pools "
                "were examined because of the configured pool bound."
            ),
        })
    if bounded_event_pools:
        warnings.append({
            "code": "activity_event_coverage_bounded",
            "message": (
                f"{bounded_event_pools} pool(s) returned more history rows than the "
                "configured per-pool verification bound. Provider ordering is not "
                "independently verified, so this subset must not be described as "
                "guaranteed latest activity."
            ),
        })
    if not market_complete:
        warnings.append({
            "code": "market_snapshot_partial",
            "message": (
                "One or more market fields required by Verified Asset Activity "
                "are partial or unavailable."
            ),
        })
    if gated_non_swap:
        warnings.append({
            "code": "non_swap_events_gated",
            "message": (
                f"{gated_non_swap} non-swap/LP event(s) remain gated and were "
                "not promoted."
            ),
        })
    if conflicts:
        warnings.append({
            "code": "trade_direction_conflicts_present",
            "message": f"{conflicts} trade direction conflict(s) were excluded.",
        })
    if asset_scope_mismatches:
        warnings.append({
            "code": "asset_scope_mismatch_present",
            "message": (
                f"{asset_scope_mismatches} side-verified trade(s) resolved to a "
                "different asset mint and were excluded."
            ),
        })
    if unresolved:
        warnings.append({
            "code": "trade_verification_incomplete",
            "message": (
                f"{unresolved} processed event(s) could not be fully attributed "
                "and verified for the requested asset."
            ),
        })

    market_data = market_envelope.get("data")
    market_data = market_data if isinstance(market_data, Mapping) else {}

    exact_quotes = {
        mint: {
            "buy_quote_amount": _decimal_text(values["buy"]),
            "sell_quote_amount": _decimal_text(values["sell"]),
        }
        for mint, values in sorted(quote_totals.items())
    }

    verification_ratio = (
        round(verified_trades / swap_candidates, 6)
        if swap_candidates > 0
        else None
    )

    sources = list(market_envelope.get("sources") or [])
    sources.append({"source": "X1 RPC", "role": "on_chain_trade_verification"})

    return build_service_envelope(
        SERVICE,
        market_envelope.get("chain") or "x1",
        status,
        asset=asset,
        data={
            "market_snapshot": {
                "price_usd": market_data.get("price_usd"),
                "liquidity_usd": market_data.get("liquidity_usd"),
                "volume_24h_usd": market_data.get("volume_24h_usd"),
                "transactions_24h": market_data.get("transactions_24h"),
                "#LPs": market_data.get("#LPs", market_data.get("lp_count")),
                "price_change_1h_pct": market_data.get("price_change_1h_pct"),
                "price_change_24h_pct": market_data.get("price_change_24h_pct"),
            },
            "matched_pool_count": matched_pool_count,
            "selected_pool_count": selected_pool_count,
            "successful_pool_history_count": successful_histories,
            "provider_event_count": provider_events,
            "processed_event_count": processed_events,
            "swap_candidate_count": swap_candidates,
            "verified_trade_count": verified_trades,
            "verified_buy_count": verified_buys,
            "verified_sell_count": verified_sells,
            "exact_amount_verified_trade_count": exact_amount_trades,
            "gated_non_swap_event_count": gated_non_swap,
            "conflict_count": conflicts,
            "unresolved_event_count": unresolved,
            "asset_scope_mismatch_count": asset_scope_mismatches,
            "exact_verified_asset_amounts": {
                "buy_asset_amount": (
                    _decimal_text(exact_buy_asset)
                    if exact_buy_amount_trades > 0
                    else None
                ),
                "sell_asset_amount": (
                    _decimal_text(exact_sell_asset)
                    if exact_sell_amount_trades > 0
                    else None
                ),
            },
            "exact_verified_quote_amounts_by_mint": exact_quotes,
            "pools": pools,
            "events": events,
        },
        confidence={
            "complete": complete,
            "market_complete": market_complete,
            "pool_selection_complete": pool_selection_complete,
            "pool_history_complete": pool_history_complete,
            "event_coverage_complete": event_coverage_complete,
            "verification_complete": verification_complete,
            "verification_ratio": verification_ratio,
        },
        sources=sources,
        observed_at=market_envelope.get("observed_at"),
        warnings=warnings,
        errors=[],
    )


__all__ = [
    "EXACT_POOL_LEG",
    "SERVICE",
    "build_verified_asset_activity_response",
]


# CMIS_VERIFIED_ASSET_ACTIVITY_V1_1_TRANSACTION_AGGREGATION
# Keep the proven v1 deterministic collector as the core, then enrich its
# envelope with transaction-aware accounting. This avoids changing trade/RPC
# verification semantics while separating transaction counts from pool legs.
from liquidity_scout.services.cmis_activity_transactions import (
    attach_transaction_aggregation as _attach_transaction_aggregation_v1_1,
)

_build_verified_asset_activity_response_v1 = build_verified_asset_activity_response


def build_verified_asset_activity_response(*args, **kwargs):
    response = _build_verified_asset_activity_response_v1(*args, **kwargs)
    return _attach_transaction_aggregation_v1_1(response)