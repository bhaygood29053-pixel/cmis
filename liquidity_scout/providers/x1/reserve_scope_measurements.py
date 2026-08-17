"""Measure one X1 reserve evidence collection scope without judging freshness.

This module consumes the bounded evidence bundle produced by
``collect_x1_reserve_live_evidence`` and derives deterministic timing/slot
measurements only. It does not decide whether any age, duration, or slot span is
acceptable. Threshold policy belongs in a separate, explicit CMIS gate after
provider behavior has been observed and justified.

The measurements are therefore diagnostic evidence, not promotion evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import math
from typing import Any


VERSION = "1.0"
ROLES = ("asset", "counter")
EXPECTED_SERVICE = "x1_reserve_live_evidence"


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _slot(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _iso_epoch_seconds(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).timestamp()


def measure_x1_reserve_scope(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Derive timing and RPC-slot measurements without freshness promotion."""
    if not isinstance(bundle, Mapping):
        raise TypeError("bundle must be a mapping")

    warnings: list[str] = []
    errors: list[str] = []

    if bundle.get("service") != EXPECTED_SERVICE:
        errors.append("unexpected_bundle_service")
    if bundle.get("chain") != "x1":
        errors.append("wrong_chain")

    collection = bundle.get("collection")
    collection = collection if isinstance(collection, Mapping) else {}
    provider = bundle.get("provider")
    provider = provider if isinstance(provider, Mapping) else {}
    roles = bundle.get("roles")
    roles = roles if isinstance(roles, Mapping) else {}

    started_at = _number(collection.get("started_at"))
    ended_at = _number(collection.get("ended_at"))
    duration = None
    collection_monotonic = False
    if started_at is None or ended_at is None:
        errors.append("collection_bounds_invalid")
    elif ended_at < started_at:
        errors.append("collection_bounds_non_monotonic")
    else:
        duration = ended_at - started_at
        collection_monotonic = True

    sequence = collection.get("sequence")
    sequence = sequence if isinstance(sequence, list) else []
    sequence_times: list[float] = []
    sequence_invalid = False
    for item in sequence:
        if not isinstance(item, Mapping):
            sequence_invalid = True
            continue
        completed_at = _number(item.get("completed_at"))
        if completed_at is None:
            sequence_invalid = True
        else:
            sequence_times.append(completed_at)

    sequence_monotonic = (
        bool(sequence)
        and not sequence_invalid
        and all(
            earlier <= later
            for earlier, later in zip(sequence_times, sequence_times[1:])
        )
    )
    if not sequence:
        warnings.append("collection_sequence_missing")
    elif not sequence_monotonic:
        errors.append("collection_sequence_non_monotonic_or_invalid")

    if collection_monotonic and sequence_monotonic:
        if any(
            timestamp < started_at or timestamp > ended_at
            for timestamp in sequence_times
        ):
            errors.append("collection_sequence_outside_bounds")

    provider_observed_at = _number(provider.get("observed_at"))
    provider_observed_within_collection = None
    if provider_observed_at is None:
        warnings.append("provider_observed_at_unavailable")
    elif collection_monotonic:
        provider_observed_within_collection = (
            started_at <= provider_observed_at <= ended_at
        )
        if not provider_observed_within_collection:
            warnings.append("provider_observed_at_outside_collection")

    provider_last_synced_raw = provider.get("last_synced_at")
    provider_last_synced_epoch = _iso_epoch_seconds(provider_last_synced_raw)
    provider_last_synced_age = None
    if provider_last_synced_raw is None:
        warnings.append("provider_last_synced_at_unavailable")
    elif provider_last_synced_epoch is None:
        warnings.append("provider_last_synced_at_unparseable")
    elif ended_at is not None:
        provider_last_synced_age = ended_at - provider_last_synced_epoch

    all_slots: list[int] = []
    role_metrics: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        role_record = roles.get(role)
        role_record = role_record if isinstance(role_record, Mapping) else {}
        balance = role_record.get("rpc_balance")
        balance = balance if isinstance(balance, Mapping) else {}
        identity = role_record.get("rpc_identity_observation")
        identity = identity if isinstance(identity, Mapping) else {}

        balance_slot = _slot(balance.get("slot"))
        identity_slot = _slot(identity.get("slot"))
        if balance_slot is not None:
            all_slots.append(balance_slot)
        if identity_slot is not None:
            all_slots.append(identity_slot)

        slot_delta = None
        same_slot = None
        if balance_slot is None or identity_slot is None:
            warnings.append(f"{role}_rpc_slot_unavailable")
        else:
            slot_delta = abs(identity_slot - balance_slot)
            same_slot = identity_slot == balance_slot

        identity_verification = role_record.get("rpc_identity_verification")
        identity_verification = (
            identity_verification if isinstance(identity_verification, Mapping) else {}
        )

        role_metrics[role] = {
            "balance_slot": balance_slot,
            "identity_slot": identity_slot,
            "balance_identity_slot_delta": slot_delta,
            "balance_identity_same_slot": same_slot,
            "rpc_identity_verified": (
                identity_verification.get("identity_verified") is True
            ),
            "rpc_decimals_match": role_record.get("rpc_decimals_match") is True,
        }

    rpc_min_slot = min(all_slots) if all_slots else None
    rpc_max_slot = max(all_slots) if all_slots else None
    rpc_slot_span = (
        rpc_max_slot - rpc_min_slot
        if rpc_min_slot is not None and rpc_max_slot is not None
        else None
    )
    if not all_slots:
        warnings.append("rpc_slots_unavailable")

    status = "error" if errors else ("partial" if warnings else "ok")

    return {
        "service": "x1_reserve_scope_measurements",
        "version": VERSION,
        "chain": "x1",
        "status": status,
        "pool_address": bundle.get("pool_address"),
        "metrics": {
            "collection_started_at": started_at,
            "collection_ended_at": ended_at,
            "collection_duration_seconds": duration,
            "collection_sequence_monotonic": sequence_monotonic,
            "provider_observed_at": provider_observed_at,
            "provider_observed_within_collection": provider_observed_within_collection,
            "provider_reported_last_synced_at": provider_last_synced_raw,
            "provider_reported_last_synced_epoch_seconds": provider_last_synced_epoch,
            "provider_reported_last_synced_age_at_collection_end_seconds": (
                provider_last_synced_age
            ),
            "provider_last_updated_raw": provider.get("last_updated"),
            "rpc_min_slot": rpc_min_slot,
            "rpc_max_slot": rpc_max_slot,
            "rpc_slot_span": rpc_slot_span,
            "roles": role_metrics,
        },
        "evidence_flags": {
            "collection_bounds_monotonic": collection_monotonic,
            "rpc_identity_verified": bundle.get("rpc_identity_verified") is True,
            "rpc_decimals_match": bundle.get("rpc_decimals_match") is True,
        },
        "freshness_verified": False,
        "observation_scope_verified": False,
        "cmis_promotable": False,
        "warnings": list(dict.fromkeys(warnings)),
        "errors": list(dict.fromkeys(errors)),
    }


__all__ = ["EXPECTED_SERVICE", "ROLES", "VERSION", "measure_x1_reserve_scope"]
