"""Short-window Warp message-account retention for fact-time valuation.

This contract is deliberately separate from warp_message_lifecycle_retention/v1.
The #441 contract owns the 60-day Bridge Flow retention requirement and keeps
its minimum lookback unchanged.  This module proves only one explicitly bounded
interval needed by another fact-time calculation (for example, from the oldest
swap fact in a 24h market window through the current backing observation).

The proof reuses the exact #441 lifecycle mechanics:
- finalized Warp-program signature pagination to the requested interval start;
- exact transaction bodies for every successful program signature in scope;
- exact current OutgoingMsg/IncomingMsg PDA universe;
- closure, recreation and ambiguous zero->zero rejection;
- expected outgoing creation checks;
- current counter/account closure as a prerequisite.

It never promotes the short interval as a 60-day Bridge Flow proof.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import requests

from liquidity_scout.providers.x1.warp_message_lifecycle_retention import (
    CONTRACT as LIFECYCLE_CONTRACT,
    DEFAULT_COMMITMENT,
    DEFAULT_PAGE_SIZE,
    WARP_PROGRAM_ID,
    WarpMessageLifecycleRetentionError,
    _message_universe,
    _rpc_request,
    _scan_trace,
    _signature_row,
    capture_program_transaction_trace,
)
from liquidity_scout.providers.x1.warp_message_retention_coverage import (
    CONTRACT as COUNTER_CLOSURE_CONTRACT,
)
from liquidity_scout.providers.x1.warp_onchain_inventory import (
    SOLANA_RPC_URL,
    X1_RPC_URL,
)

CONTRACT = "warp_message_interval_retention/v1"
DEFAULT_MAX_PAGES = 16
MAX_INTERVAL_SECONDS = 7 * 86400


class WarpMessageIntervalRetentionError(RuntimeError):
    """Raised when the requested short retention interval fails closed."""


def _nonnegative_int(value: Any, field: str) -> int:
    if value is None or isinstance(value, bool):
        raise WarpMessageIntervalRetentionError(
            f"{field} must be a non-negative integer"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise WarpMessageIntervalRetentionError(
            f"{field} must be a non-negative integer"
        ) from None
    if parsed < 0:
        raise WarpMessageIntervalRetentionError(
            f"{field} must be a non-negative integer"
        )
    return parsed


def capture_interval_program_signature_history(
    *,
    chain: str,
    requested_start: Any,
    as_of: Any,
    rpc_url: str | None = None,
    commitment: str = DEFAULT_COMMITMENT,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES,
    requester: Callable[..., Any] = _rpc_request,
) -> dict[str, Any]:
    """Capture finalized Warp-program signatures through one short boundary."""

    chain_value = str(chain or "").strip().casefold()
    if chain_value not in {"solana", "x1"}:
        raise ValueError("chain must be solana or x1")
    start = _nonnegative_int(requested_start, "requested_start")
    end = _nonnegative_int(as_of, "as_of")
    if start >= end:
        raise ValueError("requested_start must be before as_of")
    interval_seconds = end - start
    if interval_seconds > MAX_INTERVAL_SECONDS:
        raise ValueError(
            f"interval exceeds {MAX_INTERVAL_SECONDS} seconds; "
            "use the accepted 60-day lifecycle contract instead"
        )
    if not 1 <= int(page_size) <= 1000:
        raise ValueError("page_size must be between 1 and 1000")
    if int(max_pages) < 1:
        raise ValueError("max_pages must be positive")

    rpc = rpc_url or (
        SOLANA_RPC_URL if chain_value == "solana" else X1_RPC_URL
    )
    before: str | None = None
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    reached_start = False
    exhausted = False
    truncated = False
    missing_block_time_count = 0

    for _page_index in range(int(max_pages)):
        config: dict[str, Any] = {
            "commitment": commitment,
            "limit": int(page_size),
        }
        if before is not None:
            config["before"] = before
        result = requester(
            "getSignaturesForAddress",
            [WARP_PROGRAM_ID, config],
            rpc_url=rpc,
        )
        if not isinstance(result, list):
            raise WarpMessageIntervalRetentionError(
                "getSignaturesForAddress result is not a list"
            )
        if not result:
            exhausted = True
            break

        page_rows = [_signature_row(item) for item in result]
        for row in page_rows:
            signature = row["signature"]
            if signature in seen:
                raise WarpMessageIntervalRetentionError(
                    "signature pagination repeated an already-seen signature"
                )
            seen.add(signature)
            rows.append(row)
            if row["block_time"] is None:
                missing_block_time_count += 1

        oldest = page_rows[-1]
        before = oldest["signature"]
        if (
            oldest["block_time"] is not None
            and int(oldest["block_time"]) <= start
        ):
            reached_start = True
            break
        if len(page_rows) < int(page_size):
            exhausted = True
            break
    else:
        truncated = True

    rows.sort(
        key=lambda item: (
            int(item["block_time"] or -1),
            int(item["slot"]),
            item["signature"],
        ),
        reverse=True,
    )

    # capture_program_transaction_trace is reused only as an exact transaction
    # retrieval primitive.  Its evaluator is not called and no short interval
    # is ever labeled as the 60-day lifecycle contract.
    return {
        "contract": LIFECYCLE_CONTRACT,
        "chain": chain_value,
        "program_id": WARP_PROGRAM_ID,
        "rpc_url": rpc,
        "commitment": commitment,
        "as_of": end,
        "requested_start": start,
        "lookback_seconds": interval_seconds,
        "signature_count": len(rows),
        "signatures": rows,
        "pagination_exhausted": exhausted,
        "pagination_truncated": truncated,
        "reached_requested_start": reached_start,
        "missing_block_time_count": missing_block_time_count,
        "first_available_slot": None,
        "first_available_block_time": None,
        "read_only": True,
        "execution_authorized": False,
    }


def evaluate_warp_message_interval_retention(
    *,
    counter_closure: Any,
    message_state: Any,
    traces: Any,
    requested_start: Any,
    as_of: Any,
) -> dict[str, Any]:
    """Prove exact current-message retention for one explicit short interval."""

    if not isinstance(counter_closure, Mapping):
        raise WarpMessageIntervalRetentionError(
            "counter_closure must be a mapping"
        )
    if counter_closure.get("contract") != COUNTER_CLOSURE_CONTRACT:
        raise WarpMessageIntervalRetentionError(
            f"counter_closure must use {COUNTER_CLOSURE_CONTRACT}"
        )
    if counter_closure.get("counter_account_closure_verified") is not True:
        raise WarpMessageIntervalRetentionError(
            "counter/account closure prerequisite is not verified"
        )
    if counter_closure.get("current_message_universe_count_closed") is not True:
        raise WarpMessageIntervalRetentionError(
            "current message universe is not count-closed"
        )
    if not isinstance(traces, Mapping):
        raise WarpMessageIntervalRetentionError("traces must be a mapping")

    start = _nonnegative_int(requested_start, "requested_start")
    end = _nonnegative_int(as_of, "as_of")
    if start >= end:
        raise ValueError("requested_start must be before as_of")
    interval_seconds = end - start
    if interval_seconds > MAX_INTERVAL_SECONDS:
        raise ValueError(
            f"interval exceeds {MAX_INTERVAL_SECONDS} seconds; "
            "use the accepted 60-day lifecycle contract instead"
        )

    try:
        universe = _message_universe(message_state)
    except WarpMessageLifecycleRetentionError as exc:
        raise WarpMessageIntervalRetentionError(str(exc)) from None

    all_trace_complete = True
    all_no_closure = True
    all_no_recreation = True
    all_no_ambiguous = True
    all_expected_outgoing_creation_seen = True
    per_chain: dict[str, Any] = {}

    for chain in ("solana", "x1"):
        trace = traces.get(chain)
        if not isinstance(trace, Mapping) or trace.get("contract") != LIFECYCLE_CONTRACT:
            raise WarpMessageIntervalRetentionError(
                f"{chain} trace must use {LIFECYCLE_CONTRACT}"
            )
        if trace.get("program_id") != WARP_PROGRAM_ID:
            raise WarpMessageIntervalRetentionError(
                f"{chain} trace program id mismatch"
            )
        if _nonnegative_int(trace.get("as_of"), f"{chain}.trace.as_of") != end:
            raise WarpMessageIntervalRetentionError(
                f"{chain} trace as_of does not match evaluation"
            )
        if _nonnegative_int(
            trace.get("requested_start"),
            f"{chain}.trace.requested_start",
        ) != start:
            raise WarpMessageIntervalRetentionError(
                f"{chain} trace requested_start does not match evaluation"
            )

        try:
            scan = _scan_trace(
                chain=chain,
                trace=trace,
                universe=universe[chain],
            )
        except WarpMessageLifecycleRetentionError as exc:
            raise WarpMessageIntervalRetentionError(str(exc)) from None

        transitions = scan["message_transitions"]
        closure_count = 0
        repeated_creation_pdas: list[str] = []
        unexpected_old_message_creations: list[str] = []
        ambiguous_zero_zero_count = 0
        missing_expected_outgoing_creations: list[str] = []

        for pubkey, meta in universe[chain].items():
            observed = transitions.get(pubkey, [])
            creations = [row for row in observed if row["kind"] == "creation"]
            closures = [row for row in observed if row["kind"] == "closure"]
            ambiguous = [
                row for row in observed if row["kind"] == "zero_zero_touch"
            ]
            closure_count += len(closures)
            ambiguous_zero_zero_count += len(ambiguous)
            if len(creations) > 1:
                repeated_creation_pdas.append(pubkey)

            event_time = int(meta["event_time"])
            if event_time < start and creations:
                unexpected_old_message_creations.append(pubkey)
            if (
                meta["side"] == "outgoing"
                and start <= event_time <= end
                and len(creations) != 1
            ):
                missing_expected_outgoing_creations.append(pubkey)

        reached_start = trace.get("reached_requested_start") is True
        truncated = trace.get("pagination_truncated") is True
        missing_block_times = int(trace.get("missing_block_time_count") or 0)
        transaction_count = int(trace.get("transaction_count") or 0)
        successful_count = int(
            trace.get("successful_signature_count_in_scope") or 0
        )
        fetch_complete = transaction_count == successful_count
        trace_complete = bool(
            reached_start
            and not truncated
            and missing_block_times == 0
            and fetch_complete
        )

        no_closure = closure_count == 0
        no_recreation = bool(
            not repeated_creation_pdas
            and not unexpected_old_message_creations
        )
        no_ambiguous = ambiguous_zero_zero_count == 0
        expected_outgoing_creation_seen = not missing_expected_outgoing_creations

        all_trace_complete = all_trace_complete and trace_complete
        all_no_closure = all_no_closure and no_closure
        all_no_recreation = all_no_recreation and no_recreation
        all_no_ambiguous = all_no_ambiguous and no_ambiguous
        all_expected_outgoing_creation_seen = (
            all_expected_outgoing_creation_seen
            and expected_outgoing_creation_seen
        )

        per_chain[chain] = {
            "message_pda_count": len(universe[chain]),
            "signature_count_in_scope": trace.get("signature_count_in_scope"),
            "successful_signature_count_in_scope": successful_count,
            "transaction_count": transaction_count,
            "reached_requested_start": reached_start,
            "pagination_exhausted": bool(trace.get("pagination_exhausted")),
            "pagination_truncated": truncated,
            "missing_block_time_count": missing_block_times,
            "transaction_fetch_complete": fetch_complete,
            "closure_transition_count": closure_count,
            "repeated_creation_pda_count": len(repeated_creation_pdas),
            "repeated_creation_pdas": sorted(repeated_creation_pdas),
            "unexpected_old_message_creation_count": len(
                unexpected_old_message_creations
            ),
            "unexpected_old_message_creations": sorted(
                unexpected_old_message_creations
            ),
            "ambiguous_zero_zero_touch_count": ambiguous_zero_zero_count,
            "missing_expected_outgoing_creation_count": len(
                missing_expected_outgoing_creations
            ),
            "missing_expected_outgoing_creations": sorted(
                missing_expected_outgoing_creations
            ),
            "no_message_account_closure_observed": no_closure,
            "no_message_account_recreation_observed": no_recreation,
            "no_ambiguous_zero_zero_lifecycle_touch": no_ambiguous,
            "expected_outgoing_creations_verified": expected_outgoing_creation_seen,
            "interval_trace_complete_verified": trace_complete,
            "lifecycle_log_fragment_count": len(
                scan["lifecycle_log_fragments"]
            ),
        }

    interval_verified = bool(
        all_trace_complete
        and all_no_closure
        and all_no_recreation
        and all_no_ambiguous
        and all_expected_outgoing_creation_seen
    )
    coverage_verified = bool(
        interval_verified
        and counter_closure.get("counter_account_closure_verified") is True
        and counter_closure.get("current_message_universe_count_closed") is True
    )

    return {
        "contract": CONTRACT,
        "program_id": WARP_PROGRAM_ID,
        "requested_start": start,
        "as_of": end,
        "interval_seconds": interval_seconds,
        "scope": "exact_current_message_universe_requested_interval_only",
        "counter_account_closure_prerequisite_verified": True,
        "current_message_universe_count_closed": True,
        "per_chain": per_chain,
        "program_signature_trace_complete_verified": all_trace_complete,
        "requested_history_boundary_verified": all_trace_complete,
        "no_message_account_closure_observed": all_no_closure,
        "no_message_account_recreation_observed": all_no_recreation,
        "no_ambiguous_zero_zero_lifecycle_touch": all_no_ambiguous,
        "expected_outgoing_creations_verified": (
            all_expected_outgoing_creation_seen
        ),
        "interval_retention_complete_verified": coverage_verified,
        "requested_window_coverage_verified": coverage_verified,
        "coverage_complete_verified": coverage_verified,
        "missing_history_zero_authorized": coverage_verified,
        "missing_history_zero_scope": (
            "exact_current_message_universe_requested_interval_only"
            if coverage_verified
            else None
        ),
        "sixty_day_bridge_flow_retention_promoted": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


def capture_warp_message_interval_retention(
    *,
    counter_closure: Any,
    message_state: Any,
    requested_start: Any,
    as_of: Any,
    solana_rpc_url: str = SOLANA_RPC_URL,
    x1_rpc_url: str = X1_RPC_URL,
    requester: Callable[..., Any] = _rpc_request,
    post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    """Capture and evaluate one short two-chain retention interval."""

    start = _nonnegative_int(requested_start, "requested_start")
    end = _nonnegative_int(as_of, "as_of")
    traces: dict[str, Any] = {}
    for chain, rpc in (
        ("solana", solana_rpc_url),
        ("x1", x1_rpc_url),
    ):
        history = capture_interval_program_signature_history(
            chain=chain,
            requested_start=start,
            as_of=end,
            rpc_url=rpc,
            requester=requester,
        )
        traces[chain] = capture_program_transaction_trace(
            history,
            post=post,
        )
    return evaluate_warp_message_interval_retention(
        counter_closure=counter_closure,
        message_state=message_state,
        traces=traces,
        requested_start=start,
        as_of=end,
    )


__all__ = [
    "CONTRACT",
    "DEFAULT_MAX_PAGES",
    "MAX_INTERVAL_SECONDS",
    "WarpMessageIntervalRetentionError",
    "capture_interval_program_signature_history",
    "capture_warp_message_interval_retention",
    "evaluate_warp_message_interval_retention",
]
