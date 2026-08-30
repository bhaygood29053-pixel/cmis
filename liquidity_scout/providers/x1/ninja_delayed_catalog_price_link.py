"""Verify delayed X1.Ninja catalog price incorporation from exact XDEX swaps.

A delayed candidate must already be finalized on-chain before the BEFORE
provider request begins. The BEFORE catalog price must not equal the
candidate's exact execution price, while the AFTER catalog price must equal it.

The search horizon is fixed before evidence collection:

    DEFAULT_LOOKBACK_SECONDS = 900

This 15-minute horizon is an evidence-search bound only. It is not a freshness
policy, provider SLA, or fact-time claim.

Correlation here may verify bounded delayed incorporation examples and lag
bounds. It does not prove the provider's internal update source or timestamp
field semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Callable

from liquidity_scout.providers.x1.candidate_pool_role import (
    verify_candidate_pool_role,
)
from liquidity_scout.providers.x1.ninja_catalog_price_execution_link import (
    _compare,
    _identity,
    _provider_row,
    _vault_delta,
)
from liquidity_scout.providers.x1.ninja_execution_price_semantics import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    DEFAULT_RELATIVE_TOLERANCE,
)
from liquidity_scout.providers.x1.program_accounts import (
    RECOGNIZED_AMM_PROGRAM_IDS,
)
from liquidity_scout.providers.x1.rpc import (
    DEFAULT_X1_RPC_URL,
    get_signatures_for_address,
)
from liquidity_scout.providers.x1.transaction_pool_membership import (
    prove_transaction_pool_membership,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    VerificationReport,
    fetch_transaction,
    verify_transaction,
)


VERSION = "1.0"
DEFAULT_LOOKBACK_SECONDS = 900
DEFAULT_SIGNATURE_LIMIT = 100


def _text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def _positive_decimal(value: Any, *, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be a positive finite number")
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be a positive finite number") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return parsed


def _nonnegative_decimal(value: Any, *, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be a finite non-negative number")
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be a finite non-negative number") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return parsed


def _before_request_slot(snapshot: Mapping[str, Any]) -> int:
    bracket = snapshot.get("rpc_slot_bracket")
    bracket = bracket if isinstance(bracket, Mapping) else {}
    before = bracket.get("before")
    before = before if isinstance(before, Mapping) else {}
    slot = before.get("slot")
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise ValueError("BEFORE request-start RPC slot is unavailable")
    return slot


def _observation_time(snapshot: Mapping[str, Any], field: str) -> Decimal:
    return _nonnegative_decimal(snapshot.get(field), name=field)


def _exact_swap_candidate(
    *,
    pool_address: str,
    signature: str,
    identity: Mapping[str, Any],
    rpc_url: str,
    transaction_fetcher: Callable[..., Mapping[str, Any] | None],
    transaction_verifier: Callable[..., VerificationReport],
    membership_prover: Callable[..., Mapping[str, Any]],
) -> dict[str, Any]:
    tx = transaction_fetcher(signature, rpc_url=rpc_url)
    if not isinstance(tx, Mapping):
        raise ValueError("transaction unavailable")

    report = transaction_verifier(
        tx,
        signature=signature,
        rpc_url=rpc_url,
    )
    membership = membership_prover(
        verification_report=report,
        pool_identity=identity,
        transaction=tx,
    )
    if membership.get("transaction_pool_membership_verified") is not True:
        raise ValueError("exact transaction-to-pool membership unverified")

    asset = _vault_delta(
        report,
        identity["asset_vault"],
        identity["asset_mint"],
    )
    quote = _vault_delta(
        report,
        identity["counter_vault"],
        identity["counter_mint"],
    )

    if asset.delta_ui < 0 and quote.delta_ui > 0:
        side = "BUY"
    elif asset.delta_ui > 0 and quote.delta_ui < 0:
        side = "SELL"
    else:
        raise ValueError("pool-vault deltas do not form one two-sided swap")

    asset_amount = abs(asset.delta_ui)
    quote_amount = abs(quote.delta_ui)
    if asset_amount <= 0 or quote_amount <= 0:
        raise ValueError("swap amounts must be positive")

    if (
        isinstance(report.slot, bool)
        or not isinstance(report.slot, int)
        or report.slot < 0
    ):
        raise ValueError("verified transaction slot unavailable")
    if (
        isinstance(report.block_time, bool)
        or not isinstance(report.block_time, (int, float))
        or report.block_time < 0
    ):
        raise ValueError("verified transaction block time unavailable")

    execution_price = quote_amount / asset_amount
    return {
        "pool_address": pool_address,
        "signature": signature,
        "slot": report.slot,
        "block_time": report.block_time,
        "onchain_side": side,
        "asset_amount": format(asset_amount, "f"),
        "quote_amount": format(quote_amount, "f"),
        "execution_price_native": format(execution_price, "f"),
        "transaction_pool_membership_verified": True,
    }


def verify_delayed_catalog_price_transition(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    pool_address: str,
    lookback_seconds: int = DEFAULT_LOOKBACK_SECONDS,
    signature_limit: int = DEFAULT_SIGNATURE_LIMIT,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    structural_verifier: Callable[..., Mapping[str, Any]] = (
        verify_candidate_pool_role
    ),
    signature_fetcher: Callable[..., Sequence[Mapping[str, Any]]] = (
        get_signatures_for_address
    ),
    transaction_fetcher: Callable[..., Mapping[str, Any] | None] = (
        fetch_transaction
    ),
    transaction_verifier: Callable[..., VerificationReport] = (
        verify_transaction
    ),
    membership_prover: Callable[..., Mapping[str, Any]] = (
        prove_transaction_pool_membership
    ),
    recognized_program_ids: Sequence[str] = RECOGNIZED_AMM_PROGRAM_IDS,
    relative_tolerance: Any = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance: Any = DEFAULT_ABSOLUTE_TOLERANCE,
) -> dict[str, Any]:
    """Verify one delayed catalog-price adoption event."""

    pool_address = _text(pool_address)
    if not pool_address:
        raise ValueError("pool_address is required")
    if isinstance(lookback_seconds, bool) or not isinstance(
        lookback_seconds, int
    ):
        raise ValueError("lookback_seconds must be an integer")
    if lookback_seconds != DEFAULT_LOOKBACK_SECONDS:
        raise ValueError(
            "lookback_seconds is fixed at the declared 900-second evidence horizon"
        )
    if isinstance(signature_limit, bool) or not isinstance(signature_limit, int):
        raise ValueError("signature_limit must be an integer")
    if not 1 <= signature_limit <= DEFAULT_SIGNATURE_LIMIT:
        raise ValueError("signature_limit must be from 1 to 100")

    before_row = _provider_row(before, pool_address)
    after_row = _provider_row(after, pool_address)
    if not isinstance(before_row, Mapping) or not isinstance(after_row, Mapping):
        raise ValueError("pool missing from BEFORE/AFTER snapshots")
    if before_row.get("status") != "ok" or after_row.get("status") != "ok":
        raise ValueError("pool snapshot status is not ok")

    before_provider = before_row.get("provider")
    after_provider = after_row.get("provider")
    if not isinstance(before_provider, Mapping) or not isinstance(
        after_provider, Mapping
    ):
        raise ValueError("provider row data unavailable")

    before_price = _positive_decimal(
        before_provider.get("priceNative"),
        name="BEFORE priceNative",
    )
    after_price = _positive_decimal(
        after_provider.get("priceNative"),
        name="AFTER priceNative",
    )
    if before_price == after_price:
        return {
            "service": "x1_ninja_delayed_catalog_price_transition",
            "version": VERSION,
            "chain": "x1",
            "status": "not_applicable",
            "pool_address": pool_address,
            "price_changed": False,
            "delayed_catalog_price_execution_link_verified": False,
            "incorporation_lag_observed": False,
            "incorporation_lag_policy_verified": False,
            "provider_fact_time_verified": False,
            "update_source_semantics_verified": False,
            "freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }

    relative = _nonnegative_decimal(
        relative_tolerance,
        name="relative_tolerance",
    )
    absolute = _nonnegative_decimal(
        absolute_tolerance,
        name="absolute_tolerance",
    )
    if relative == 0 and absolute == 0:
        raise ValueError("comparison tolerances cannot both be zero")

    before_start_slot = _before_request_slot(before)
    before_end_time = _observation_time(before, "observed_at_end")
    after_end_time = _observation_time(after, "observed_at_end")
    cutoff_time = after_end_time - Decimal(lookback_seconds)
    if cutoff_time < 0:
        cutoff_time = Decimal(0)

    identity, program_id = _identity(
        pool_address,
        structural_verifier=structural_verifier,
        recognized_program_ids=recognized_program_ids,
        rpc_url=rpc_url,
    )

    history = signature_fetcher(
        pool_address,
        limit=signature_limit,
        rpc_url=rpc_url,
    )
    if not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
        raise ValueError("pool signature history unavailable")

    successful = [
        row
        for row in history
        if isinstance(row, Mapping)
        and row.get("err") is None
        and _text(row.get("signature"))
    ]

    known_times = [
        Decimal(str(row.get("block_time")))
        for row in successful
        if isinstance(row.get("block_time"), (int, float))
        and not isinstance(row.get("block_time"), bool)
        and row.get("block_time") >= 0
    ]
    history_complete_for_lookback = bool(
        len(history) < signature_limit
        or (
            known_times
            and min(known_times) <= cutoff_time
        )
    )
    if not history_complete_for_lookback:
        return {
            "service": "x1_ninja_delayed_catalog_price_transition",
            "version": VERSION,
            "chain": "x1",
            "status": "unavailable",
            "pool_address": pool_address,
            "price_changed": True,
            "lookback_seconds": lookback_seconds,
            "history_complete_for_lookback": False,
            "delayed_catalog_price_execution_link_verified": False,
            "incorporation_lag_observed": False,
            "incorporation_lag_policy_verified": False,
            "provider_fact_time_verified": False,
            "update_source_semantics_verified": False,
            "freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
            "warnings": ["signature_history_does_not_cover_declared_lookback"],
        }

    eligible_rows = []
    for row in successful:
        slot = row.get("slot")
        block_time = row.get("block_time")
        if (
            isinstance(slot, bool)
            or not isinstance(slot, int)
            or slot < 0
            or slot > before_start_slot
        ):
            continue
        if (
            isinstance(block_time, bool)
            or not isinstance(block_time, (int, float))
            or block_time < 0
        ):
            continue
        block_decimal = Decimal(str(block_time))
        if cutoff_time <= block_decimal <= after_end_time:
            eligible_rows.append(row)

    candidates = []
    rejections = []
    for row in eligible_rows:
        signature = _text(row.get("signature"))
        if not signature:
            continue
        try:
            candidate = _exact_swap_candidate(
                pool_address=pool_address,
                signature=signature,
                identity=identity,
                rpc_url=rpc_url,
                transaction_fetcher=transaction_fetcher,
                transaction_verifier=transaction_verifier,
                membership_prover=membership_prover,
            )
            execution_price = _positive_decimal(
                candidate["execution_price_native"],
                name="execution_price_native",
            )
            candidate["before_price_comparison"] = _compare(
                before_price,
                execution_price,
                relative=relative,
                absolute=absolute,
            )
            candidate["after_price_comparison"] = _compare(
                after_price,
                execution_price,
                relative=relative,
                absolute=absolute,
            )
            candidates.append(candidate)
        except Exception as exc:
            rejections.append({
                "signature": signature,
                "slot": row.get("slot"),
                "block_time": row.get("block_time"),
                "error": f"{type(exc).__name__}: {exc}",
            })

    qualifying = [
        row
        for row in candidates
        if row["before_price_comparison"]["within_tolerance"] is False
        and row["after_price_comparison"]["within_tolerance"] is True
    ]

    latest_slot = max(
        (
            row.get("slot")
            for row in candidates
            if isinstance(row.get("slot"), int)
        ),
        default=None,
    )
    latest_candidates = [
        row
        for row in candidates
        if latest_slot is not None and row.get("slot") == latest_slot
    ]

    unique_latest_delayed_match = bool(
        len(qualifying) == 1
        and len(latest_candidates) == 1
        and qualifying[0].get("signature")
        == latest_candidates[0].get("signature")
    )

    matched = qualifying[0] if unique_latest_delayed_match else None
    lag = None
    lag_observed = False
    if matched is not None:
        tx_time = Decimal(str(matched["block_time"]))
        lower = before_end_time - tx_time
        upper = after_end_time - tx_time
        if lower < 0:
            lower = Decimal(0)
        if upper >= lower:
            lag = {
                "transaction_block_time": matched["block_time"],
                "before_observed_at_end": format(before_end_time, "f"),
                "after_observed_at_end": format(after_end_time, "f"),
                "minimum_observed_incorporation_lag_seconds": format(
                    lower,
                    "f",
                ),
                "maximum_observed_incorporation_lag_seconds": format(
                    upper,
                    "f",
                ),
            }
            lag_observed = True

    return {
        "service": "x1_ninja_delayed_catalog_price_transition",
        "version": VERSION,
        "chain": "x1",
        "status": "verified" if unique_latest_delayed_match else (
            "partial" if candidates else "unavailable"
        ),
        "pool_address": pool_address,
        "program_id": program_id,
        "price_changed": True,
        "lookback_seconds": lookback_seconds,
        "signature_limit": signature_limit,
        "history_complete_for_lookback": history_complete_for_lookback,
        "before_request_start_slot": before_start_slot,
        "before_provider": dict(before_provider),
        "after_provider": dict(after_provider),
        "provider_timestamp_candidates": {
            "before_global_lastUpdated_raw": (
                before.get("provider_timestamp_candidates", {}).get(
                    "global_lastUpdated_raw"
                )
                if isinstance(
                    before.get("provider_timestamp_candidates"),
                    Mapping,
                )
                else None
            ),
            "after_global_lastUpdated_raw": (
                after.get("provider_timestamp_candidates", {}).get(
                    "global_lastUpdated_raw"
                )
                if isinstance(
                    after.get("provider_timestamp_candidates"),
                    Mapping,
                )
                else None
            ),
            "before_lastSyncedAt_raw": before_provider.get(
                "lastSyncedAt_raw"
            ),
            "after_lastSyncedAt_raw": after_provider.get(
                "lastSyncedAt_raw"
            ),
        },
        "eligible_history_row_count": len(eligible_rows),
        "verified_swap_candidate_count": len(candidates),
        "qualifying_delayed_match_count": len(qualifying),
        "latest_verified_swap_count": len(latest_candidates),
        "matched_transaction": matched,
        "candidates": candidates,
        "rejections": rejections,
        "delayed_catalog_price_execution_link_verified": (
            unique_latest_delayed_match
        ),
        "incorporation_lag_observed": lag_observed,
        "incorporation_lag": lag,
        "incorporation_lag_policy_verified": False,
        "provider_timestamp_units_verified": False,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "universal_catalog_price_semantics_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def aggregate_delayed_catalog_price_links(
    events: Sequence[Mapping[str, Any]],
    *,
    minimum_verified_events: int = 5,
) -> dict[str, Any]:
    """Aggregate delayed-link evidence without claiming universal semantics."""

    if isinstance(minimum_verified_events, bool) or not isinstance(
        minimum_verified_events, int
    ):
        raise ValueError("minimum_verified_events must be an integer")
    if minimum_verified_events < 5:
        raise ValueError("minimum_verified_events must be at least 5")

    rows = [dict(row) for row in events if isinstance(row, Mapping)]
    verified = [
        row
        for row in rows
        if row.get(
            "delayed_catalog_price_execution_link_verified"
        ) is True
        and row.get("incorporation_lag_observed") is True
    ]
    signatures = {
        row.get("matched_transaction", {}).get("signature")
        for row in verified
        if isinstance(row.get("matched_transaction"), Mapping)
    }
    signatures.discard(None)

    contradictions = [
        row
        for row in rows
        if row.get("status") == "partial"
        and row.get("history_complete_for_lookback") is True
        and row.get("verified_swap_candidate_count", 0) > 0
        and row.get(
            "delayed_catalog_price_execution_link_verified"
        ) is False
    ]

    pattern_verified = bool(
        len(verified) >= minimum_verified_events
        and len(signatures) == len(verified)
        and not contradictions
    )

    lag_bounds = [
        row.get("incorporation_lag")
        for row in verified
        if isinstance(row.get("incorporation_lag"), Mapping)
    ]

    return {
        "service": "x1_ninja_delayed_catalog_price_link",
        "version": VERSION,
        "chain": "x1",
        "status": "verified" if pattern_verified else (
            "partial" if rows else "unavailable"
        ),
        "event_count": len(rows),
        "verified_delayed_event_count": len(verified),
        "minimum_verified_events": minimum_verified_events,
        "distinct_pool_count": len({
            row.get("pool_address")
            for row in verified
            if row.get("pool_address")
        }),
        "distinct_transaction_count": len(signatures),
        "contradictory_complete_event_count": len(contradictions),
        "delayed_catalog_price_execution_link_verified": pattern_verified,
        "incorporation_lag_observed": bool(lag_bounds),
        "incorporation_lag_samples": lag_bounds,
        "incorporation_lag_policy_verified": False,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "universal_catalog_price_semantics_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "events": rows,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "DEFAULT_LOOKBACK_SECONDS",
    "DEFAULT_SIGNATURE_LIMIT",
    "VERSION",
    "aggregate_delayed_catalog_price_links",
    "verify_delayed_catalog_price_transition",
]
