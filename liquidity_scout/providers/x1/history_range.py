"""Read-only X1 history-range proof primitives for CMIS v1.3.

This module does not promote provider pagination/range semantics. It proves only
what the X1 RPC itself can establish for an address history scan:

- getSignaturesForAddress pagination advances with a deterministic `before`
  cursor;
- returned slots/times are monotonic newest -> oldest during the observed scan;
- the requested start boundary was reached (or RPC history was exhausted);
- no malformed rows, duplicate signatures, cursor stalls, or RPC errors were
  encountered before the boundary.

The module can also compare a market-data provider's returned pool-history rows
to the signatures observed on X1 RPC. That comparison is evidence about the
sample, not proof that the provider index is exhaustive.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Callable

from .rpc import DEFAULT_X1_RPC_URL, rpc_request

CHAIN = "x1"
SOURCE = "X1 RPC getSignaturesForAddress"
DEFAULT_PAGE_SIZE = 1000
DEFAULT_MAX_SIGNATURES = 5000


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _positive_int(name: str, value: Any, *, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer <= {maximum}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} must be a positive integer <= {maximum}"
        ) from exc
    if parsed <= 0 or parsed > maximum:
        raise ValueError(f"{name} must be a positive integer <= {maximum}")
    return parsed


def _epoch(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _iso(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(
        epoch, tz=timezone.utc
    ).isoformat()


def _parse_iso_epoch(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).timestamp()


def _rpc_callable(
    rpc: Callable[[str, list], Any] | None,
    *,
    rpc_url: str,
):
    if rpc is not None:
        if not callable(rpc):
            raise ValueError("rpc must be callable")
        return rpc

    def call(method: str, params: list):
        return rpc_request(
            method,
            params,
            rpc_url=rpc_url,
        )

    return call


def _normalized_signature_entry(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None

    signature = _text(raw.get("signature"))
    slot = raw.get("slot")
    if (
        not signature
        or isinstance(slot, bool)
        or not isinstance(slot, int)
        or slot < 0
        or "err" not in raw
    ):
        return None

    block_time = raw.get("blockTime")
    if block_time is not None:
        if isinstance(block_time, bool) or not isinstance(
            block_time, (int, float)
        ):
            return None
        block_time = float(block_time)

    return {
        "signature": signature,
        "slot": slot,
        "err": raw.get("err"),
        "block_time": block_time,
        "confirmation_status": _text(raw.get("confirmationStatus")),
    }


def _nonincreasing(values: Sequence[int | float]) -> bool:
    return all(
        values[index] >= values[index + 1]
        for index in range(len(values) - 1)
    )


def scan_address_history_range(
    address: str,
    *,
    start_epoch: float,
    end_epoch: float,
    rpc: Callable[[str, list], Any] | None = None,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_signatures: int = DEFAULT_MAX_SIGNATURES,
) -> dict[str, Any]:
    """Scan X1 address signatures newest -> oldest until a time boundary.

    `range_proven=True` means this observed X1 RPC scan reached the requested
    start boundary (or exhausted the RPC-visible history) without integrity
    failures. It does not assert chain-lifetime archival completeness.
    """

    address = _text(address)
    if not address:
        raise ValueError("address is required")

    start_epoch = _epoch(start_epoch)
    end_epoch = _epoch(end_epoch)
    if start_epoch is None or end_epoch is None:
        raise ValueError("start_epoch and end_epoch must be non-negative times")
    if start_epoch > end_epoch:
        raise ValueError("start_epoch must be <= end_epoch")

    page_size = _positive_int(
        "page_size", page_size, maximum=1000
    )
    max_signatures = _positive_int(
        "max_signatures", max_signatures, maximum=100000
    )
    call = _rpc_callable(rpc, rpc_url=rpc_url)

    entries: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    seen_cursors: set[str] = set()
    before: str | None = None

    pages = 0
    rpc_errors = 0
    malformed_entries = 0
    duplicate_signatures = 0
    cursor_stalls = 0
    history_exhausted = False
    start_boundary_reached = False
    bound_reached = False

    while len(entries) < max_signatures:
        remaining = max_signatures - len(entries)
        limit = min(page_size, remaining)
        options: dict[str, Any] = {"limit": limit}
        if before:
            options["before"] = before

        try:
            batch = call(
                "getSignaturesForAddress",
                [address, options],
            )
        except Exception:
            rpc_errors += 1
            break

        pages += 1
        if not isinstance(batch, list):
            rpc_errors += 1
            break

        if not batch:
            history_exhausted = True
            break

        last_raw_signature = None

        for raw in batch:
            if isinstance(raw, Mapping):
                last_raw_signature = _text(raw.get("signature"))

            item = _normalized_signature_entry(raw)
            if item is None:
                malformed_entries += 1
                continue

            signature = item["signature"]
            if signature in seen_signatures:
                duplicate_signatures += 1
                continue

            seen_signatures.add(signature)
            entries.append(item)

        valid_times = [
            entry["block_time"]
            for entry in entries
            if entry["block_time"] is not None
        ]
        if valid_times and min(valid_times) <= start_epoch:
            start_boundary_reached = True
            break

        if len(batch) < limit:
            history_exhausted = True
            break

        if not last_raw_signature:
            cursor_stalls += 1
            break
        if last_raw_signature == before or last_raw_signature in seen_cursors:
            cursor_stalls += 1
            break

        seen_cursors.add(last_raw_signature)
        before = last_raw_signature

        if len(entries) >= max_signatures:
            bound_reached = True
            break

    if (
        len(entries) >= max_signatures
        and not start_boundary_reached
        and not history_exhausted
    ):
        bound_reached = True

    slots = [entry["slot"] for entry in entries]
    block_times = [
        entry["block_time"]
        for entry in entries
        if entry["block_time"] is not None
    ]

    slot_order_verified = _nonincreasing(slots)
    block_time_complete = (
        len(entries) > 0
        and len(block_times) == len(entries)
    )
    block_time_order_verified = bool(
        block_time_complete and _nonincreasing(block_times)
    )

    integrity_verified = bool(
        rpc_errors == 0
        and malformed_entries == 0
        and duplicate_signatures == 0
        and cursor_stalls == 0
        and slot_order_verified
        and block_time_order_verified
    )

    terminal_boundary_verified = bool(
        start_boundary_reached or history_exhausted
    )

    range_proven = bool(
        integrity_verified
        and terminal_boundary_verified
        and not bound_reached
    )

    newest = entries[0] if entries else None
    oldest = entries[-1] if entries else None

    window_entries = [
        entry
        for entry in entries
        if (
            entry["block_time"] is not None
            and start_epoch <= entry["block_time"] <= end_epoch
        )
    ]

    return {
        "chain": CHAIN,
        "source": SOURCE,
        "address": address,
        "requested_start_epoch": start_epoch,
        "requested_start_utc": _iso(start_epoch),
        "requested_end_epoch": end_epoch,
        "requested_end_utc": _iso(end_epoch),
        "page_size": page_size,
        "max_signatures": max_signatures,
        "pages_fetched": pages,
        "signature_count": len(entries),
        "successful_signature_count": sum(
            1 for entry in entries if entry["err"] is None
        ),
        "failed_signature_count": sum(
            1 for entry in entries if entry["err"] is not None
        ),
        "window_signature_count": len(window_entries),
        "rpc_errors": rpc_errors,
        "malformed_entries": malformed_entries,
        "duplicate_signatures": duplicate_signatures,
        "cursor_stalls": cursor_stalls,
        "history_exhausted": history_exhausted,
        "start_boundary_reached": start_boundary_reached,
        "bound_reached": bound_reached,
        "slot_order_verified": slot_order_verified,
        "block_time_complete": block_time_complete,
        "block_time_order_verified": block_time_order_verified,
        "integrity_verified": integrity_verified,
        "range_proven": range_proven,
        "coverage_scope": (
            "window_boundary_reached"
            if range_proven and start_boundary_reached
            else (
                "rpc_history_exhausted"
                if range_proven and history_exhausted
                else (
                    "bounded_before_boundary"
                    if bound_reached
                    else "incomplete"
                )
            )
        ),
        "newest_signature": (
            newest["signature"] if newest else None
        ),
        "newest_slot": newest["slot"] if newest else None,
        "newest_block_time_utc": (
            _iso(newest["block_time"]) if newest else None
        ),
        "oldest_signature": (
            oldest["signature"] if oldest else None
        ),
        "oldest_slot": oldest["slot"] if oldest else None,
        "oldest_block_time_utc": (
            _iso(oldest["block_time"]) if oldest else None
        ),
        # Returned for deterministic comparison by callers. CLI probes should
        # summarize/remove this field before printing large JSON.
        "entries": entries,
    }


def compare_provider_rows_to_chain(
    rows: Sequence[Mapping[str, Any]],
    chain_entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare provider pool-history sample identity/order to X1 RPC evidence.

    This never promotes provider range completeness.
    """

    provider_rows = [
        row for row in rows if isinstance(row, Mapping)
    ]
    chain_by_signature = {
        _text(entry.get("signature")): entry
        for entry in chain_entries
        if isinstance(entry, Mapping)
        and _text(entry.get("signature"))
    }

    provider_signatures: list[str] = []
    provider_slots: list[int] = []
    provider_times: list[float] = []
    malformed_rows = 0
    duplicate_rows = 0
    seen = set()

    overlap_count = 0
    slot_match_count = 0
    timestamp_match_count = 0
    timestamp_comparable_count = 0

    for row in provider_rows:
        signature = _text(row.get("txHash"))
        slot = row.get("slot")
        timestamp = _parse_iso_epoch(row.get("timestamp"))

        if (
            not signature
            or isinstance(slot, bool)
            or not isinstance(slot, int)
            or slot < 0
            or timestamp is None
        ):
            malformed_rows += 1
            continue

        if signature in seen:
            duplicate_rows += 1
        else:
            seen.add(signature)

        provider_signatures.append(signature)
        provider_slots.append(slot)
        provider_times.append(timestamp)

        chain = chain_by_signature.get(signature)
        if not isinstance(chain, Mapping):
            continue

        overlap_count += 1
        if chain.get("slot") == slot:
            slot_match_count += 1

        chain_time = chain.get("block_time")
        if isinstance(chain_time, (int, float)) and not isinstance(
            chain_time, bool
        ):
            timestamp_comparable_count += 1
            if abs(float(chain_time) - timestamp) <= 1.0:
                timestamp_match_count += 1

    valid_count = len(provider_signatures)
    provider_slot_order_observed = (
        valid_count > 0 and _nonincreasing(provider_slots)
    )
    provider_time_order_observed = (
        valid_count > 0 and _nonincreasing(provider_times)
    )

    overlapping_identity_verified = bool(
        overlap_count > 0
        and slot_match_count == overlap_count
        and timestamp_comparable_count == overlap_count
        and timestamp_match_count == overlap_count
    )

    return {
        "provider_row_count": len(provider_rows),
        "provider_valid_identity_row_count": valid_count,
        "provider_malformed_row_count": malformed_rows,
        "provider_duplicate_signature_count": duplicate_rows,
        "provider_slot_order_newest_to_oldest_observed": (
            provider_slot_order_observed
        ),
        "provider_time_order_newest_to_oldest_observed": (
            provider_time_order_observed
        ),
        "provider_ordering_observed_consistent": bool(
            provider_slot_order_observed
            and provider_time_order_observed
        ),
        "provider_oldest_timestamp_utc": (
            _iso(min(provider_times)) if provider_times else None
        ),
        "provider_newest_timestamp_utc": (
            _iso(max(provider_times)) if provider_times else None
        ),
        "provider_signatures_found_in_chain_scan": overlap_count,
        "provider_chain_slot_match_count": slot_match_count,
        "provider_chain_timestamp_match_count": timestamp_match_count,
        "provider_chain_timestamp_comparable_count": (
            timestamp_comparable_count
        ),
        "overlapping_identity_verified": overlapping_identity_verified,
        "provider_range_contract_verified": False,
        "provider_range_contract_reason": (
            "Live ordering/linkage observations do not independently prove "
            "that the provider index is exhaustive or that undocumented "
            "pagination/range behavior is stable."
        ),
    }


__all__ = [
    "CHAIN",
    "DEFAULT_MAX_SIGNATURES",
    "DEFAULT_PAGE_SIZE",
    "SOURCE",
    "compare_provider_rows_to_chain",
    "scan_address_history_range",
]
