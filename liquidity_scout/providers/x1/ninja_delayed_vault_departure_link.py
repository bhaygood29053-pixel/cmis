"""Link price-only reserve-ratio departures to earlier exact XDEX vault swaps.

This evidence layer follows the accepted #358 departure classifier. It first
requires a verified price-only gross-reserve-ratio departure with unchanged
provider reserves and zero exact vault activity in the safe between-snapshot
window. Only then does it inspect a fixed 900-second pre-BEFORE lookback on
both exact vault histories.

The hypothesis is deliberately narrow: the unique latest exact XDEX swap in
that fixed lookback may have an execution price that the catalog adopts only
at the AFTER observation. Timing correlation does not prove provider-internal
source semantics, fact-time, freshness, or universal catalog price semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from liquidity_scout.providers.x1.ninja_execution_price_semantics import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    DEFAULT_RELATIVE_TOLERANCE,
)
from liquidity_scout.providers.x1.ninja_price_only_reserve_ratio_mode import (
    DEPARTURE,
    verify_price_only_reserve_ratio_event,
)
from liquidity_scout.providers.x1.ninja_vault_activity_correlation import (
    _classify_vault_transaction,
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

DELAYED_LATEST_SWAP_LINK = "delayed_latest_swap_link"
LATEST_SWAP_MATCHES_BEFORE = "latest_swap_matches_before"
LATEST_SWAP_MATCHES_NEITHER = "latest_swap_matches_neither"
SAME_SLOT_AMBIGUITY = "same_slot_ambiguity"
UNAVAILABLE_OR_INCOMPLETE = "unavailable_or_incomplete"


def _text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def _decimal(value: Any, *, name: str, nonnegative: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be finite")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be finite")
    if nonnegative and parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def _slot(snapshot: Mapping[str, Any], side: str) -> int:
    bracket = snapshot.get("rpc_slot_bracket")
    bracket = bracket if isinstance(bracket, Mapping) else {}
    row = bracket.get(side)
    row = row if isinstance(row, Mapping) else {}
    value = row.get("slot")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"RPC slot bracket {side} slot unavailable")
    return value


def _compare(
    observed: Decimal,
    expected: Decimal,
    *,
    relative: Decimal,
    absolute: Decimal,
) -> dict[str, Any]:
    error = abs(observed - expected)
    scale = abs(expected)
    relative_error = (
        error / scale
        if scale != 0
        else (Decimal(0) if error == 0 else None)
    )
    allowed = max(absolute, scale * relative)
    return {
        "observed": format(observed, "f"),
        "expected": format(expected, "f"),
        "absolute_error": format(error, "f"),
        "relative_error": (
            format(relative_error, "e")
            if relative_error is not None
            else None
        ),
        "allowed_absolute_error": format(allowed, "f"),
        "within_tolerance": error <= allowed,
    }


def _pre_before_history(
    address: str,
    *,
    cutoff_time: Decimal,
    before_start_time: Decimal,
    before_start_slot: int,
    limit: int,
    rpc_url: str,
    signature_fetcher: Callable[..., Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    rows = signature_fetcher(address, limit=limit, rpc_url=rpc_url)
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("vault signature history unavailable")

    normalized = [dict(row) for row in rows if isinstance(row, Mapping)]
    known_times: list[Decimal] = []
    missing_time_before_slot = False
    eligible: list[dict[str, Any]] = []

    for row in normalized:
        slot = row.get("slot")
        block_time = row.get("block_time")
        signature = _text(row.get("signature"))

        valid_slot = bool(
            isinstance(slot, int)
            and not isinstance(slot, bool)
            and slot >= 0
        )
        valid_time = bool(
            isinstance(block_time, (int, float))
            and not isinstance(block_time, bool)
            and block_time >= 0
        )
        if valid_time:
            known_times.append(Decimal(str(block_time)))

        if (
            row.get("err") is None
            and signature
            and valid_slot
            and slot <= before_start_slot
        ):
            if not valid_time:
                missing_time_before_slot = True
                continue
            block_decimal = Decimal(str(block_time))
            if cutoff_time <= block_decimal <= before_start_time:
                eligible.append({
                    "signature": signature,
                    "slot": slot,
                    "block_time": block_time,
                    "confirmation_status": row.get("confirmation_status"),
                })

    history_complete = bool(
        not missing_time_before_slot
        and (
            len(normalized) < limit
            or (known_times and min(known_times) < cutoff_time)
        )
    )

    return {
        "address": address,
        "returned_row_count": len(normalized),
        "history_complete_for_lookback": history_complete,
        "missing_block_time_before_start_slot": missing_time_before_slot,
        "eligible_rows": eligible,
    }


def _merge_histories(
    histories: Sequence[tuple[str, Mapping[str, Any]]],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source_name, history in histories:
        rows = history.get("eligible_rows")
        rows = rows if isinstance(rows, Sequence) else []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            signature = _text(row.get("signature"))
            if not signature:
                continue
            slot = row.get("slot")
            block_time = row.get("block_time")
            current = merged.setdefault(signature, {
                "signature": signature,
                "slot": slot,
                "block_time": block_time,
                "seen_on": [],
            })
            if current.get("slot") != slot:
                raise ValueError("same signature has inconsistent vault-history slot")
            if (
                current.get("block_time") is not None
                and block_time is not None
                and Decimal(str(current.get("block_time")))
                != Decimal(str(block_time))
            ):
                raise ValueError(
                    "same signature has inconsistent vault-history block time"
                )
            current["seen_on"].append(source_name)
    return merged


def _inspect_transaction(
    *,
    history_row: Mapping[str, Any],
    identity: Mapping[str, Any],
    rpc_url: str,
    transaction_fetcher: Callable[..., Mapping[str, Any] | None],
    transaction_verifier: Callable[..., VerificationReport],
    membership_prover: Callable[..., Mapping[str, Any]],
) -> dict[str, Any]:
    signature = _text(history_row.get("signature"))
    if not signature:
        raise ValueError("signature unavailable")
    tx = transaction_fetcher(signature, rpc_url=rpc_url)
    if not isinstance(tx, Mapping):
        raise ValueError("transaction unavailable")

    report = transaction_verifier(tx, signature=signature, rpc_url=rpc_url)
    if report.found is not True or report.succeeded is not True:
        raise ValueError("transaction not found/successful")
    if report.slot != history_row.get("slot"):
        raise ValueError("vault-history slot mismatches transaction slot")
    if (
        history_row.get("block_time") is not None
        and report.block_time is not None
        and Decimal(str(history_row.get("block_time")))
        != Decimal(str(report.block_time))
    ):
        raise ValueError(
            "vault-history block time mismatches transaction block time"
        )

    classified = _classify_vault_transaction(
        transaction=tx,
        report=report,
        identity=identity,
        membership_prover=membership_prover,
    )
    membership = classified.get("membership")
    membership = membership if isinstance(membership, Mapping) else None

    if classified.get("recognized_amm_invoked") is True:
        if membership is None:
            raise ValueError("recognized AMM exact-pool membership unavailable")
        if membership.get("recognized_amm_instruction_count") != 1:
            raise ValueError("routed_or_multi_amm_instruction_ambiguity")
        if membership.get("selected_pool_instruction_count") != 1:
            raise ValueError("multiple_selected_pool_instruction_ambiguity")
        if membership.get("transaction_pool_membership_verified") is not True:
            raise ValueError("exact transaction-to-pool membership unverified")

    return {
        "signature": signature,
        "slot": report.slot,
        "block_time": report.block_time,
        "seen_on": sorted(set(history_row.get("seen_on") or [])),
        "program_ids": list(report.program_ids),
        **classified,
    }


def _unavailable_result(
    *,
    pool_address: str,
    departure: Mapping[str, Any] | None,
    warning: str,
    histories: Mapping[str, Any] | None = None,
    rejections: Sequence[Mapping[str, Any]] | None = None,
    outcome: str = UNAVAILABLE_OR_INCOMPLETE,
) -> dict[str, Any]:
    return {
        "service": "x1_ninja_delayed_vault_departure_link",
        "version": VERSION,
        "chain": "x1",
        "status": "unavailable",
        "pool_address": pool_address,
        "event_key": (
            departure.get("event_key")
            if isinstance(departure, Mapping)
            else None
        ),
        "outcome": outcome,
        "price_only_reserve_ratio_departure_verified": bool(
            isinstance(departure, Mapping)
            and departure.get("classification") == DEPARTURE
            and departure.get("price_only_update_verified") is True
        ),
        "delayed_vault_swap_execution_link_verified": False,
        "departure_lag_observed": False,
        "departure_pattern_verified": False,
        "vault_histories": (
            dict(histories) if isinstance(histories, Mapping) else None
        ),
        "rejections": list(rejections or []),
        "warnings": [warning],
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "universal_catalog_price_semantics_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
        "departure_evidence": (
            dict(departure) if isinstance(departure, Mapping) else departure
        ),
    }


def verify_delayed_vault_departure_link(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    pool_address: str,
    lookback_seconds: int = DEFAULT_LOOKBACK_SECONDS,
    signature_limit: int = DEFAULT_SIGNATURE_LIMIT,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    departure_verifier: Callable[..., Mapping[str, Any]] = (
        verify_price_only_reserve_ratio_event
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
    **departure_kwargs: Any,
) -> dict[str, Any]:
    """Verify one price-only departure against the latest pre-BEFORE vault swap."""

    pool_address = _text(pool_address)
    if not pool_address:
        raise ValueError("pool_address is required")
    if isinstance(lookback_seconds, bool) or not isinstance(
        lookback_seconds, int
    ):
        raise ValueError("lookback_seconds must be an integer")
    if lookback_seconds != DEFAULT_LOOKBACK_SECONDS:
        raise ValueError("lookback_seconds is fixed at 900 seconds")
    if isinstance(signature_limit, bool) or not isinstance(signature_limit, int):
        raise ValueError("signature_limit must be an integer")
    if not 1 <= signature_limit <= DEFAULT_SIGNATURE_LIMIT:
        raise ValueError("signature_limit must be from 1 to 100")

    departure_raw = departure_verifier(
        before=before,
        after=after,
        pool_address=pool_address,
        signature_limit=signature_limit,
        rpc_url=rpc_url,
        signature_fetcher=signature_fetcher,
        transaction_fetcher=transaction_fetcher,
        transaction_verifier=transaction_verifier,
        membership_prover=membership_prover,
        recognized_program_ids=recognized_program_ids,
        relative_tolerance=relative_tolerance,
        absolute_tolerance=absolute_tolerance,
        **departure_kwargs,
    )
    if not isinstance(departure_raw, Mapping):
        raise ValueError("departure verifier returned malformed evidence")
    departure = dict(departure_raw)

    base = departure.get("base_evidence")
    base = base if isinstance(base, Mapping) else {}
    prerequisite = bool(
        departure.get("classification") == DEPARTURE
        and departure.get("price_only_update_verified") is True
        and departure.get("gross_reserve_ratio_departure_observed") is True
        and base.get("vault_history_complete_for_window") is True
        and base.get("transaction_coverage_complete") is True
        and base.get("unique_vault_history_signature_count") == 0
        and base.get("verified_vault_transaction_count") == 0
        and base.get("provider_reserve_changed") is False
        and base.get("price_changed") is True
    )
    if not prerequisite:
        return _unavailable_result(
            pool_address=pool_address,
            departure=departure,
            warning="verified_price_only_reserve_ratio_departure_required",
        )

    identity = base.get("identity")
    identity = identity if isinstance(identity, Mapping) else {}
    required_identity = (
        "pool_address",
        "mint_0",
        "mint_1",
        "vault_0",
        "vault_1",
        "asset_mint",
        "asset_vault",
        "counter_mint",
        "counter_vault",
    )
    if identity.get("identity_verified") is not True or any(
        not _text(identity.get(key)) for key in required_identity
    ):
        return _unavailable_result(
            pool_address=pool_address,
            departure=departure,
            warning="exact_rpc_pool_vault_identity_unavailable",
        )
    if _text(identity.get("pool_address")) != pool_address:
        raise ValueError("departure identity pool address mismatch")

    before_start_time = _decimal(
        before.get("observed_at_start"),
        name="BEFORE observed_at_start",
        nonnegative=True,
    )
    before_end_time = _decimal(
        before.get("observed_at_end"),
        name="BEFORE observed_at_end",
        nonnegative=True,
    )
    after_end_time = _decimal(
        after.get("observed_at_end"),
        name="AFTER observed_at_end",
        nonnegative=True,
    )
    if before_end_time < before_start_time or after_end_time < before_end_time:
        raise ValueError("CMIS observation times are not monotonic")

    before_start_slot = _slot(before, "before")
    cutoff_time = before_start_time - Decimal(lookback_seconds)
    if cutoff_time < 0:
        cutoff_time = Decimal(0)

    vault0_history = _pre_before_history(
        identity["vault_0"],
        cutoff_time=cutoff_time,
        before_start_time=before_start_time,
        before_start_slot=before_start_slot,
        limit=signature_limit,
        rpc_url=rpc_url,
        signature_fetcher=signature_fetcher,
    )
    vault1_history = _pre_before_history(
        identity["vault_1"],
        cutoff_time=cutoff_time,
        before_start_time=before_start_time,
        before_start_slot=before_start_slot,
        limit=signature_limit,
        rpc_url=rpc_url,
        signature_fetcher=signature_fetcher,
    )
    histories = {"vault_0": vault0_history, "vault_1": vault1_history}
    history_complete = bool(
        vault0_history["history_complete_for_lookback"]
        and vault1_history["history_complete_for_lookback"]
    )
    if not history_complete:
        return _unavailable_result(
            pool_address=pool_address,
            departure=departure,
            warning="vault_history_does_not_cover_fixed_pre_before_lookback",
            histories=histories,
        )

    merged = _merge_histories((
        ("vault_0", vault0_history),
        ("vault_1", vault1_history),
    ))
    transactions: list[dict[str, Any]] = []
    exact_swaps: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []

    for signature, history_row in sorted(
        merged.items(),
        key=lambda item: item[1].get("slot", -1),
        reverse=True,
    ):
        try:
            row = _inspect_transaction(
                history_row=history_row,
                identity=identity,
                rpc_url=rpc_url,
                transaction_fetcher=transaction_fetcher,
                transaction_verifier=transaction_verifier,
                membership_prover=membership_prover,
            )
            transactions.append(row)
            if (
                row.get("classification") == "exact_xdex_swap"
                and row.get("exact_pool_amm_membership_verified") is True
                and row.get("execution_price_native") is not None
            ):
                exact_swaps.append(row)
        except Exception as exc:
            rejections.append({
                "signature": signature,
                "slot": history_row.get("slot"),
                "block_time": history_row.get("block_time"),
                "error": f"{type(exc).__name__}: {exc}",
            })

    if rejections:
        return _unavailable_result(
            pool_address=pool_address,
            departure=departure,
            warning="pre_before_transaction_coverage_incomplete_or_ambiguous",
            histories=histories,
            rejections=rejections,
        )

    if not exact_swaps:
        return _unavailable_result(
            pool_address=pool_address,
            departure=departure,
            warning="no_exact_xdex_swap_in_fixed_pre_before_lookback",
            histories=histories,
        )

    latest_slot = max(row["slot"] for row in exact_swaps)
    latest = [row for row in exact_swaps if row.get("slot") == latest_slot]
    if len(latest) != 1:
        return _unavailable_result(
            pool_address=pool_address,
            departure=departure,
            warning="multiple_exact_xdex_swaps_share_latest_slot",
            histories=histories,
            outcome=SAME_SLOT_AMBIGUITY,
        )
    candidate = latest[0]

    before_provider = base.get("before_provider")
    after_provider = base.get("after_provider")
    if not isinstance(before_provider, Mapping) or not isinstance(
        after_provider, Mapping
    ):
        raise ValueError("departure provider rows unavailable")
    before_price = _decimal(
        before_provider.get("priceNative"),
        name="BEFORE priceNative",
    )
    after_price = _decimal(
        after_provider.get("priceNative"),
        name="AFTER priceNative",
    )
    execution_price = _decimal(
        candidate.get("execution_price_native"),
        name="execution_price_native",
    )
    if before_price <= 0 or after_price <= 0 or execution_price <= 0:
        raise ValueError("price values must be positive")

    relative = _decimal(
        relative_tolerance,
        name="relative_tolerance",
        nonnegative=True,
    )
    absolute = _decimal(
        absolute_tolerance,
        name="absolute_tolerance",
        nonnegative=True,
    )
    if relative == 0 and absolute == 0:
        raise ValueError("comparison tolerances cannot both be zero")

    before_comparison = _compare(
        before_price,
        execution_price,
        relative=relative,
        absolute=absolute,
    )
    after_comparison = _compare(
        after_price,
        execution_price,
        relative=relative,
        absolute=absolute,
    )
    before_matches = before_comparison["within_tolerance"] is True
    after_matches = after_comparison["within_tolerance"] is True

    if not before_matches and after_matches:
        outcome = DELAYED_LATEST_SWAP_LINK
    elif before_matches and not after_matches:
        outcome = LATEST_SWAP_MATCHES_BEFORE
    elif not before_matches and not after_matches:
        outcome = LATEST_SWAP_MATCHES_NEITHER
    else:
        return _unavailable_result(
            pool_address=pool_address,
            departure=departure,
            warning="latest_swap_matches_both_provider_prices_within_tolerance",
            histories=histories,
        )

    delayed_link = outcome == DELAYED_LATEST_SWAP_LINK
    lag = None
    lag_observed = False
    if delayed_link:
        tx_time = _decimal(
            candidate.get("block_time"),
            name="transaction block_time",
            nonnegative=True,
        )
        lower = before_end_time - tx_time
        upper = after_end_time - tx_time
        if lower >= 0 and upper >= lower:
            lag = {
                "transaction_block_time": candidate.get("block_time"),
                "before_observed_at_start": format(before_start_time, "f"),
                "before_observed_at_end": format(before_end_time, "f"),
                "after_observed_at_end": format(after_end_time, "f"),
                "minimum_observed_departure_lag_seconds": format(lower, "f"),
                "maximum_observed_departure_lag_seconds": format(upper, "f"),
            }
            lag_observed = True

    provider_timestamps = departure.get("provider_timestamp_candidates")
    if not isinstance(provider_timestamps, Mapping):
        provider_timestamps = base.get("provider_timestamp_candidates")

    return {
        "service": "x1_ninja_delayed_vault_departure_link",
        "version": VERSION,
        "chain": "x1",
        "status": "verified" if delayed_link and lag_observed else "partial",
        "pool_address": pool_address,
        "event_key": departure.get("event_key"),
        "outcome": outcome,
        "lookback_seconds": lookback_seconds,
        "signature_limit_per_vault": signature_limit,
        "before_request_start_slot": before_start_slot,
        "lookback_cutoff_time": format(cutoff_time, "f"),
        "vault_history_complete_for_lookback": True,
        "vault_histories": histories,
        "unique_vault_history_signature_count": len(merged),
        "verified_vault_transaction_count": len(transactions),
        "transaction_coverage_complete": True,
        "exact_xdex_swap_count": len(exact_swaps),
        "latest_exact_swap_slot": latest_slot,
        "latest_exact_swap_count": 1,
        "latest_exact_swap": candidate,
        "before_price_vs_latest_swap": before_comparison,
        "after_price_vs_latest_swap": after_comparison,
        "price_only_reserve_ratio_departure_verified": True,
        "delayed_vault_swap_execution_link_verified": delayed_link,
        "departure_lag_observed": lag_observed,
        "departure_lag": lag,
        "departure_pattern_verified": False,
        "provider_timestamp_candidates": (
            dict(provider_timestamps)
            if isinstance(provider_timestamps, Mapping)
            else None
        ),
        "departure_evidence": departure,
        "transactions": transactions,
        "rejections": [],
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "universal_catalog_price_semantics_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def aggregate_delayed_vault_departure_links(
    events: Sequence[Mapping[str, Any]],
    *,
    minimum_verified_departures: int = 5,
) -> dict[str, Any]:
    """Aggregate bounded delayed-departure evidence without cherry-picking."""

    if isinstance(minimum_verified_departures, bool) or not isinstance(
        minimum_verified_departures, int
    ):
        raise ValueError("minimum_verified_departures must be an integer")
    if minimum_verified_departures < 5:
        raise ValueError("minimum_verified_departures must be at least 5")

    rows = [dict(row) for row in events if isinstance(row, Mapping)]
    departures = [
        row
        for row in rows
        if row.get("price_only_reserve_ratio_departure_verified") is True
    ]
    keys = [
        row.get("event_key")
        for row in departures
        if isinstance(row.get("event_key"), str) and row.get("event_key")
    ]
    delayed = [
        row
        for row in departures
        if row.get("outcome") == DELAYED_LATEST_SWAP_LINK
        and row.get("delayed_vault_swap_execution_link_verified") is True
        and row.get("departure_lag_observed") is True
    ]
    signatures = [
        row.get("latest_exact_swap", {}).get("signature")
        for row in delayed
        if isinstance(row.get("latest_exact_swap"), Mapping)
    ]
    signatures = [value for value in signatures if value]

    counts = {
        DELAYED_LATEST_SWAP_LINK: 0,
        LATEST_SWAP_MATCHES_BEFORE: 0,
        LATEST_SWAP_MATCHES_NEITHER: 0,
        UNAVAILABLE_OR_INCOMPLETE: 0,
        SAME_SLOT_AMBIGUITY: 0,
    }
    for row in rows:
        outcome = row.get("outcome")
        if outcome in counts:
            counts[outcome] += 1
        elif row.get("status") == "unavailable":
            counts[UNAVAILABLE_OR_INCOMPLETE] += 1

    enough = len(departures) >= minimum_verified_departures
    all_rows_are_departures = bool(rows and len(departures) == len(rows))
    unique_events = bool(
        len(keys) == len(departures) == len(set(keys))
    )
    unique_swaps = bool(
        len(signatures) == len(delayed) == len(set(signatures))
    )
    no_counterexample = bool(
        counts[LATEST_SWAP_MATCHES_BEFORE] == 0
        and counts[LATEST_SWAP_MATCHES_NEITHER] == 0
        and counts[UNAVAILABLE_OR_INCOMPLETE] == 0
        and counts[SAME_SLOT_AMBIGUITY] == 0
    )
    pattern_verified = bool(
        enough
        and all_rows_are_departures
        and unique_events
        and len(delayed) == len(departures)
        and unique_swaps
        and no_counterexample
    )

    return {
        "service": "x1_ninja_delayed_vault_departure_pattern",
        "version": VERSION,
        "chain": "x1",
        "status": "verified" if pattern_verified else (
            "partial" if rows else "unavailable"
        ),
        "event_count": len(rows),
        "verified_departure_count": len(departures),
        "minimum_verified_departures": minimum_verified_departures,
        "distinct_event_count": len(set(keys)),
        "delayed_link_count": len(delayed),
        "distinct_linked_swap_count": len(set(signatures)),
        "outcome_counts": counts,
        "price_only_reserve_ratio_departure_verified": bool(
            enough and all_rows_are_departures and unique_events
        ),
        "delayed_vault_swap_execution_link_verified": pattern_verified,
        "departure_lag_observed": bool(delayed),
        "departure_lag_samples": [
            row.get("departure_lag")
            for row in delayed
            if isinstance(row.get("departure_lag"), Mapping)
        ],
        "departure_pattern_verified": pattern_verified,
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
    "DELAYED_LATEST_SWAP_LINK",
    "LATEST_SWAP_MATCHES_BEFORE",
    "LATEST_SWAP_MATCHES_NEITHER",
    "SAME_SLOT_AMBIGUITY",
    "UNAVAILABLE_OR_INCOMPLETE",
    "VERSION",
    "aggregate_delayed_vault_departure_links",
    "verify_delayed_vault_departure_link",
]
