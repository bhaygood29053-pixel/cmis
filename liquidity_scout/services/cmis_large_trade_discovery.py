"""Verified X1 large-trade discovery across an exact bounded 24h pool scope.

Issue #531 ranks already-verified exact-pool swaps by historical USD notional.
It does not fetch providers, infer a globally exhaustive X1 DEX universe,
identify real-world wallet owners, label wallets behaviorally, infer intent or
coordination, or turn one trade into a market-wide causality/risk conclusion.

The initial ranking scope is the exact provider-scoped current market pool set
proven by x1_ninja_current_pool_scope/v1, with one aligned complete
x1_pool_24h_chain_activity/v1 window for every pool in that set.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.services.cmis_contract import OK, build_service_envelope


SERVICE = "large_trade_discovery"
CONTRACT_VERSION = "large_trade_discovery/v1"
SUPPORTED_CHAIN = "x1"
POOL_SCOPE_CONTRACT = "x1_ninja_current_pool_scope/v1"
POOL_WINDOW_CONTRACT = "x1_pool_24h_chain_activity/v1"
RANKING_SCOPE = "verified_provider_scoped_current_market_pool_set_exact_24h"
WINDOW_SECONDS = Decimal("86400")
MAX_EVALUATION_SKEW_SECONDS = Decimal("120")
MAX_RESULTS = 20


class LargeTradeDiscoveryError(ValueError):
    """Raised when evidence cannot support the bounded #531 ranking."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LargeTradeDiscoveryError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise LargeTradeDiscoveryError(f"{field} must be a list")
    return list(value)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LargeTradeDiscoveryError(f"{field} is required")
    return value.strip()


def _decimal(value: Any, field: str, *, positive: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise LargeTradeDiscoveryError(f"{field} must be numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise LargeTradeDiscoveryError(f"{field} must be numeric") from exc
    if not parsed.is_finite():
        raise LargeTradeDiscoveryError(f"{field} must be finite")
    if positive and parsed <= 0:
        raise LargeTradeDiscoveryError(f"{field} must be positive")
    return parsed


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LargeTradeDiscoveryError(
            f"{field} must be a non-negative integer"
        )
    return value


def _strict_true(value: Any, field: str) -> None:
    if value is not True:
        raise LargeTradeDiscoveryError(f"{field} must be verified")


def _strict_false(value: Any, field: str) -> None:
    if value is not False:
        raise LargeTradeDiscoveryError(f"{field} must remain false")


def _fmt(value: Decimal) -> str:
    return format(value, "f")


def _direction(value: Any) -> str:
    direction = _text(value, "direction").upper()
    if direction not in {"ANY", "BUY", "SELL"}:
        raise LargeTradeDiscoveryError(
            "direction must be ANY, BUY, or SELL"
        )
    return direction


def _limit(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LargeTradeDiscoveryError("limit must be an integer")
    if value < 1 or value > MAX_RESULTS:
        raise LargeTradeDiscoveryError(
            f"limit must be between 1 and {MAX_RESULTS}"
        )
    return value


def _pool_scope(
    evidence: Mapping[str, Any],
    *,
    requested_asset_mint: str,
) -> list[str]:
    if evidence.get("contract_version") != POOL_SCOPE_CONTRACT:
        raise LargeTradeDiscoveryError("pool scope contract mismatch")
    if evidence.get("chain") != SUPPORTED_CHAIN:
        raise LargeTradeDiscoveryError("pool scope chain must be x1")
    if evidence.get("asset_mint") != requested_asset_mint:
        raise LargeTradeDiscoveryError("pool scope asset identity mismatch")
    _strict_true(
        evidence.get("provider_scoped_pool_universe_verified"),
        "pool_scope.provider_scoped_pool_universe_verified",
    )
    _strict_false(
        evidence.get("global_xdex_pool_universe_verified"),
        "pool_scope.global_xdex_pool_universe_verified",
    )
    _strict_false(
        evidence.get("execution_authorized"),
        "pool_scope.execution_authorized",
    )

    market = _sequence(
        evidence.get("market_contributing_pool_addresses"),
        "pool_scope.market_contributing_pool_addresses",
    )
    catalog = _sequence(
        evidence.get("current_catalog_exact_mint_pool_addresses"),
        "pool_scope.current_catalog_exact_mint_pool_addresses",
    )
    market_addresses = [
        _text(item, "pool_scope market pool address") for item in market
    ]
    catalog_addresses = [
        _text(item, "pool_scope catalog pool address") for item in catalog
    ]
    if len(set(market_addresses)) != len(market_addresses):
        raise LargeTradeDiscoveryError(
            "pool scope market addresses must be unique"
        )
    if len(set(catalog_addresses)) != len(catalog_addresses):
        raise LargeTradeDiscoveryError(
            "pool scope catalog addresses must be unique"
        )
    if set(market_addresses) != set(catalog_addresses):
        raise LargeTradeDiscoveryError(
            "provider-scoped market and exact-mint catalog pool sets disagree"
        )

    market_count = _nonnegative_int(
        evidence.get("market_pool_count"),
        "pool_scope.market_pool_count",
    )
    catalog_count = _nonnegative_int(
        evidence.get("current_catalog_exact_mint_pool_count"),
        "pool_scope.current_catalog_exact_mint_pool_count",
    )
    if market_count != len(market_addresses) or catalog_count != len(
        catalog_addresses
    ):
        raise LargeTradeDiscoveryError("pool scope counts do not match pool sets")
    return market_addresses


def _window_candidates(
    pool_windows: Sequence[Mapping[str, Any]],
    *,
    requested_asset_mint: str,
    expected_pool_addresses: Sequence[str],
    evaluated_at: Decimal,
) -> tuple[list[dict[str, Any]], dict[str, str], int]:
    by_pool: dict[str, Mapping[str, Any]] = {}
    for raw in pool_windows:
        window = _mapping(raw, "pool_window")
        address = _text(window.get("pool_address"), "pool_window.pool_address")
        if address in by_pool:
            raise LargeTradeDiscoveryError("duplicate pool window")
        by_pool[address] = window

    if set(by_pool) != set(expected_pool_addresses):
        raise LargeTradeDiscoveryError(
            "pool window set must exactly match the verified provider-scoped pool set"
        )

    common_start: Decimal | None = None
    common_end: Decimal | None = None
    candidates: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    exact_swap_count = 0

    for address in expected_pool_addresses:
        window = by_pool[address]
        if window.get("contract_version") != POOL_WINDOW_CONTRACT:
            raise LargeTradeDiscoveryError("pool window contract mismatch")
        if window.get("chain") != SUPPORTED_CHAIN:
            raise LargeTradeDiscoveryError("pool window chain must be x1")
        if window.get("asset_mint") != requested_asset_mint:
            raise LargeTradeDiscoveryError("pool window asset identity mismatch")
        _strict_false(
            window.get("execution_authorized"),
            "pool_window.execution_authorized",
        )
        for field in (
            "history_range_proven",
            "history_integrity_verified",
            "all_successful_transactions_verified",
            "all_pool_relevant_transactions_classified",
            "transactions_24h_window_coverage_verified",
            "swap_count_semantics_verified",
            "quote_volume_semantics_verified",
            "usd_valuation_coverage_verified",
            "volume_24h_value_verified",
        ):
            _strict_true(window.get(field), f"pool_window.{field}")

        requested = _mapping(
            window.get("requested_window"),
            "pool_window.requested_window",
        )
        start = _decimal(
            requested.get("start_epoch"),
            "pool_window.requested_window.start_epoch",
        )
        end = _decimal(
            requested.get("end_epoch"),
            "pool_window.requested_window.end_epoch",
        )
        duration = _decimal(
            requested.get("duration_seconds"),
            "pool_window.requested_window.duration_seconds",
        )
        if duration != WINDOW_SECONDS or end - start != WINDOW_SECONDS:
            raise LargeTradeDiscoveryError(
                "pool window must be an exact 24-hour interval"
            )
        if abs(end - evaluated_at) > MAX_EVALUATION_SKEW_SECONDS:
            raise LargeTradeDiscoveryError(
                "pool window end must be current to evaluated_at within 120 seconds"
            )
        if common_start is None:
            common_start = start
            common_end = end
        elif start != common_start or end != common_end:
            raise LargeTradeDiscoveryError("pool windows must be time aligned")

        rows = _sequence(window.get("transactions"), "pool_window.transactions")
        pool_swap_count = 0
        for raw_row in rows:
            row = _mapping(raw_row, "pool_window transaction")
            if row.get("classification") != "EXACT_POOL_SWAP":
                continue
            exact_swap_count += 1
            pool_swap_count += 1
            _strict_true(
                row.get("membership_verified"),
                "pool_window swap membership_verified",
            )
            _strict_true(
                row.get("historical_usd_value_verified"),
                "pool_window swap historical_usd_value_verified",
            )
            signature = _text(
                row.get("signature"),
                "pool_window swap signature",
            )
            if signature in seen_signatures:
                raise LargeTradeDiscoveryError(
                    "duplicate exact-swap signature across pool windows; routed or multi-pool ranking fails closed"
                )
            seen_signatures.add(signature)
            slot = _nonnegative_int(
                row.get("slot"),
                "pool_window swap slot",
            )
            block_time = _decimal(
                row.get("block_time"),
                "pool_window swap block_time",
            )
            usd_value = _decimal(
                row.get("usd_value"),
                "pool_window swap usd_value",
                positive=True,
            )
            asset_delta = _decimal(
                row.get("asset_vault_delta_ui"),
                "pool_window swap asset_vault_delta_ui",
            )
            counter_delta = _decimal(
                row.get("counter_vault_delta_ui"),
                "pool_window swap counter_vault_delta_ui",
            )
            if asset_delta == 0 or counter_delta == 0:
                raise LargeTradeDiscoveryError(
                    "exact swap vault deltas must be non-zero"
                )
            if (asset_delta < 0) is (counter_delta < 0):
                raise LargeTradeDiscoveryError(
                    "exact swap asset/counter vault deltas must have opposite signs"
                )
            side = "BUY" if asset_delta < 0 and counter_delta > 0 else "SELL"
            quote_mint = _text(
                row.get("quote_mint"),
                "pool_window swap quote_mint",
            )
            candidates.append(
                {
                    "signature": signature,
                    "slot": slot,
                    "block_time": _fmt(block_time),
                    "pool_address": address,
                    "direction": side,
                    "asset_amount": _fmt(abs(asset_delta)),
                    "quote_amount": _fmt(abs(counter_delta)),
                    "quote_mint": quote_mint,
                    "usd_notional": usd_value,
                }
            )

        verified_count = _nonnegative_int(
            window.get("verified_transactions_24h"),
            "pool_window.verified_transactions_24h",
        )
        if verified_count != pool_swap_count:
            raise LargeTradeDiscoveryError(
                "verified_transactions_24h must equal exact swap rows available for ranking"
            )

    if common_start is None or common_end is None:
        common_start = evaluated_at - WINDOW_SECONDS
        common_end = evaluated_at

    return (
        candidates,
        {
            "start_epoch": _fmt(common_start),
            "end_epoch": _fmt(common_end),
            "duration_seconds": _fmt(WINDOW_SECONDS),
        },
        exact_swap_count,
    )


def _wallet_map(
    observations: Sequence[Mapping[str, Any]],
    *,
    requested_asset_mint: str,
    known_signatures: set[str],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in observations:
        observation = _mapping(raw, "wallet_observation")
        if observation.get("chain") != SUPPORTED_CHAIN:
            raise LargeTradeDiscoveryError(
                "wallet observation chain must be x1"
            )
        signature = _text(
            observation.get("transaction_signature"),
            "wallet_observation.transaction_signature",
        )
        if signature in result:
            raise LargeTradeDiscoveryError(
                "duplicate wallet observation for one transaction"
            )
        if signature not in known_signatures:
            raise LargeTradeDiscoveryError(
                "wallet observation signature is outside the ranked pool-window evidence"
            )
        if observation.get("asset_id") != requested_asset_mint:
            raise LargeTradeDiscoveryError(
                "wallet observation asset identity mismatch"
            )
        side = _text(
            observation.get("activity_type"),
            "wallet_observation.activity_type",
        ).upper()
        if side not in {"BUY", "SELL"}:
            raise LargeTradeDiscoveryError(
                "wallet observation activity_type must be BUY or SELL"
            )
        verification = _mapping(
            observation.get("verification"),
            "wallet_observation.verification",
        )
        for field in (
            "wallet_identity_verified",
            "asset_identity_verified",
            "transaction_identity_verified",
            "trade_direction_verified",
        ):
            _strict_true(
                verification.get(field),
                f"wallet_observation.verification.{field}",
            )
        _strict_false(
            observation.get("classification_authorized"),
            "wallet_observation.classification_authorized",
        )
        _strict_false(
            observation.get("complete_wallet_history_proven"),
            "wallet_observation.complete_wallet_history_proven",
        )
        result[signature] = {
            "wallet_address": _text(
                observation.get("wallet"),
                "wallet_observation.wallet",
            ),
            "slot": _nonnegative_int(
                observation.get("block_slot"),
                "wallet_observation.block_slot",
            ),
            "direction": side,
            "fact_time": _text(
                observation.get("observed_at"),
                "wallet_observation.observed_at",
            ),
        }
    return result


def _handoff_map(
    values: Mapping[str, Any] | None,
    *,
    known_signatures: set[str],
) -> dict[str, str]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise LargeTradeDiscoveryError(
            "trusted_trade_price_impact_evidence_ids must be an object"
        )
    result: dict[str, str] = {}
    for raw_signature, raw_evidence_id in values.items():
        signature = _text(
            raw_signature,
            "trade price-impact handoff signature",
        )
        if signature not in known_signatures:
            raise LargeTradeDiscoveryError(
                "trade price-impact handoff signature is outside discovery evidence"
            )
        result[signature] = _text(
            raw_evidence_id,
            "trade price-impact evidence id",
        )
    return result


def build_large_trade_discovery_response(
    *,
    requested_asset_mint: str,
    pool_scope_evidence: Mapping[str, Any],
    pool_windows: Sequence[Mapping[str, Any]],
    evaluated_at: Any,
    direction: str = "ANY",
    limit: int = 5,
    wallet_observations: Sequence[Mapping[str, Any]] = (),
    trusted_trade_price_impact_evidence_ids: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Rank exact verified pool swaps inside one complete bounded 24h scope."""

    requested_asset_mint = _text(
        requested_asset_mint,
        "requested_asset_mint",
    )
    evaluated = _decimal(evaluated_at, "evaluated_at")
    requested_direction = _direction(direction)
    requested_limit = _limit(limit)

    scope = _mapping(pool_scope_evidence, "pool_scope_evidence")
    pool_addresses = _pool_scope(
        scope,
        requested_asset_mint=requested_asset_mint,
    )
    windows = [
        _mapping(item, "pool_window")
        for item in _sequence(pool_windows, "pool_windows")
    ]
    candidates, requested_window, exact_swap_count = _window_candidates(
        windows,
        requested_asset_mint=requested_asset_mint,
        expected_pool_addresses=pool_addresses,
        evaluated_at=evaluated,
    )
    known_signatures = {item["signature"] for item in candidates}
    wallets = _wallet_map(
        [
            _mapping(item, "wallet_observation")
            for item in _sequence(wallet_observations, "wallet_observations")
        ],
        requested_asset_mint=requested_asset_mint,
        known_signatures=known_signatures,
    )
    handoffs = _handoff_map(
        trusted_trade_price_impact_evidence_ids,
        known_signatures=known_signatures,
    )

    eligible = [
        item
        for item in candidates
        if requested_direction == "ANY"
        or item["direction"] == requested_direction
    ]
    eligible.sort(
        key=lambda item: (
            -item["usd_notional"],
            item["slot"],
            item["signature"],
            item["pool_address"],
        )
    )

    results: list[dict[str, Any]] = []
    for rank, item in enumerate(eligible[:requested_limit], start=1):
        wallet = wallets.get(item["signature"])
        if wallet is not None:
            if wallet["slot"] != item["slot"]:
                raise LargeTradeDiscoveryError(
                    "wallet attribution slot disagrees with ranked exact swap"
                )
            if wallet["direction"] != item["direction"]:
                raise LargeTradeDiscoveryError(
                    "wallet attribution direction disagrees with ranked exact swap"
                )
        evidence_id = handoffs.get(item["signature"])
        results.append(
            {
                "rank": rank,
                "transaction_signature": item["signature"],
                "slot": item["slot"],
                "block_time": item["block_time"],
                "pool_address": item["pool_address"],
                "direction": item["direction"],
                "asset_mint": requested_asset_mint,
                "asset_amount": item["asset_amount"],
                "quote_mint": item["quote_mint"],
                "quote_amount": item["quote_amount"],
                "verified_usd_notional": _fmt(item["usd_notional"]),
                "usd_notional_verified": True,
                "wallet_address": (
                    wallet["wallet_address"] if wallet is not None else None
                ),
                "wallet_attribution_verified": wallet is not None,
                "real_world_wallet_owner_verified": False,
                "wallet_fact_time": (
                    wallet["fact_time"] if wallet is not None else None
                ),
                "trade_price_impact_evidence_id": evidence_id,
                "trade_price_impact_handoff_ready": bool(
                    wallet is not None and evidence_id is not None
                ),
            }
        )

    return build_service_envelope(
        SERVICE,
        SUPPORTED_CHAIN,
        OK,
        asset={
            "canonical_id": requested_asset_mint,
            "mint": requested_asset_mint,
        },
        data={
            "contract_version": CONTRACT_VERSION,
            "public_service_promoted": True,
            "scout_reliance_promoted": True,
            "read_only": True,
            "ranking_metric": "verified_historical_usd_notional",
            "ranking_order": (
                "usd_notional_desc_then_slot_asc_then_signature_then_pool"
            ),
            "ranking_scope": RANKING_SCOPE,
            "requested_direction": requested_direction,
            "requested_limit": requested_limit,
            "requested_window": requested_window,
            "evaluated_at": _fmt(evaluated),
            "pool_scope": {
                "contract_version": POOL_SCOPE_CONTRACT,
                "pool_addresses": list(pool_addresses),
                "pool_count": len(pool_addresses),
                "provider_scoped_pool_universe_verified": True,
                "global_xdex_pool_universe_verified": False,
            },
            "exact_swap_count_examined": exact_swap_count,
            "eligible_trade_count": len(eligible),
            "result_count": len(results),
            "ranking_complete_for_scope": True,
            "results": results,
            "evidence_boundaries": {
                "global_x1_dex_trade_ranking_authorized": False,
                "wallet_owner_identity_inference_authorized": False,
                "whale_insider_manipulator_label_authorized": False,
                "intent_inference_authorized": False,
                "coordinated_wallet_inference_authorized": False,
                "whole_market_price_impact_claim_authorized": False,
                "volume_causality_claim_authorized": False,
                "automatic_risk_conclusion_authorized": False,
                "trade_recommendation_authorized": False,
                "source_independence_verified": False,
            },
            "execution_authorized": False,
        },
        risk=None,
        confidence={
            "ranking_complete_for_scope": True,
            "pool_scope_verified": True,
            "window_coverage_verified": True,
            "usd_notional_basis_verified": True,
            "wallet_attribution_complete_for_results": all(
                row["wallet_attribution_verified"] for row in results
            ),
            "source_independence_verified": False,
        },
        sources=[
            {
                "source": "CMIS verified X1 pool-scope + exact pool 24h windows",
                "scope": RANKING_SCOPE,
                "pool_count": len(pool_addresses),
            }
        ],
        observed_at=_fmt(evaluated),
        warnings=[
            {
                "code": "provider_scoped_pool_universe_only",
                "message": (
                    "Ranking is complete only for the verified provider-scoped "
                    "current market pool set, not every X1 DEX."
                ),
            }
        ],
        errors=[],
    )


__all__ = [
    "CONTRACT_VERSION",
    "LargeTradeDiscoveryError",
    "MAX_RESULTS",
    "RANKING_SCOPE",
    "SERVICE",
    "build_large_trade_discovery_response",
]
