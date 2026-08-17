"""Collect one bounded read-only X1 reserve evidence bundle.

This provider-level collector sequences an X1.Ninja pool-detail observation with
direct X1 RPC token-account balance and parsed identity observations for caller-
supplied reserve candidates. It records collection ordering and timestamps but
never infers reserve-field semantics, common observation scope, freshness, or
value agreement.

The output is evidence for later deterministic CMIS gates. It is never
CMIS-promotable by itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import math
import time
from typing import Any

from liquidity_scout.providers.x1.ninja_pool_detail import fetch_pool_detail_raw
from liquidity_scout.providers.x1.rpc_balance import fetch_token_account_balance_raw
from liquidity_scout.providers.x1.rpc_token_account import (
    fetch_token_account_identity_raw,
)
from liquidity_scout.providers.x1.rpc_token_identity import (
    verify_x1_rpc_token_account_identity,
)


VERSION = "1.0"
ROLES = ("asset", "counter")


def _text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty")
    return text


def _timestamp(clock: Callable[[], Any]) -> float:
    value = clock()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError("reserve evidence clock returned an invalid timestamp")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise RuntimeError("reserve evidence clock returned a non-finite timestamp")
    return parsed


def _validate_timeline(started_at: float, sequence: list[dict[str, Any]], ended_at: float) -> None:
    times = [started_at]
    times.extend(float(step["completed_at"]) for step in sequence)
    times.append(ended_at)
    if any(current < previous for previous, current in zip(times, times[1:])):
        raise RuntimeError("reserve evidence clock moved backwards during collection")


def _field_at_path(value: Mapping[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise ValueError(f"provider field path is missing: {path}")
        current = current[part]
    return current


def _role_spec(role_specs: Mapping[str, Any], role: str) -> dict[str, Any]:
    spec = role_specs.get(role)
    if not isinstance(spec, Mapping):
        raise ValueError(f"{role} role specification is required")

    decimals = spec.get("decimals")
    if isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0:
        raise ValueError(f"{role}.decimals must be a non-negative integer")

    return {
        "vault": _text(f"{role}.vault", spec.get("vault")),
        "mint": _text(f"{role}.mint", spec.get("mint")),
        "provider_field_path": _text(
            f"{role}.provider_field_path", spec.get("provider_field_path")
        ),
        "decimals": decimals,
    }


def collect_x1_reserve_live_evidence(
    pool_address: Any,
    role_specs: Mapping[str, Any],
    *,
    shared_authority: Any,
    api_key: str | None = None,
    rpc_url: str | None = None,
    commitment: str = "confirmed",
    pool_detail_fetcher=fetch_pool_detail_raw,
    balance_fetcher=fetch_token_account_balance_raw,
    identity_fetcher=fetch_token_account_identity_raw,
    identity_verifier=verify_x1_rpc_token_account_identity,
    clock=time.time,
) -> dict[str, Any]:
    """Collect raw provider/RPC reserve evidence without semantic promotion."""
    if not isinstance(role_specs, Mapping):
        raise TypeError("role_specs must be a mapping")

    pool = _text("pool_address", pool_address)
    authority = _text("shared_authority", shared_authority)
    specs = {role: _role_spec(role_specs, role) for role in ROLES}

    started_at = _timestamp(clock)
    pool_detail = pool_detail_fetcher(pool, api_key=api_key)
    provider_completed_at = _timestamp(clock)

    if not isinstance(pool_detail, Mapping):
        raise TypeError("pool_detail_fetcher must return a mapping")
    if pool_detail.get("chain") != "x1":
        raise ValueError("pool detail observation is not for x1")
    if str(pool_detail.get("pool_address_requested") or "").strip() != pool:
        raise ValueError("pool detail observation does not match requested pool")

    raw_response = pool_detail.get("raw_response")
    if not isinstance(raw_response, Mapping):
        raise ValueError("pool detail raw_response is missing or malformed")

    raw_pool = raw_response.get("pool")
    raw_pool = raw_pool if isinstance(raw_pool, Mapping) else {}

    sequence: list[dict[str, Any]] = [
        {
            "step": "provider_pool_detail",
            "completed_at": provider_completed_at,
            "provider_observed_at": pool_detail.get("observed_at"),
        }
    ]
    roles: dict[str, dict[str, Any]] = {}

    for role in ROLES:
        spec = specs[role]
        provider_value = _field_at_path(raw_response, spec["provider_field_path"])

        balance = balance_fetcher(
            spec["vault"],
            rpc_url=rpc_url,
            commitment=commitment,
        )
        balance_completed_at = _timestamp(clock)
        if not isinstance(balance, Mapping):
            raise TypeError("balance_fetcher must return a mapping")
        sequence.append(
            {
                "step": f"{role}_rpc_balance",
                "completed_at": balance_completed_at,
                "slot": balance.get("slot"),
            }
        )

        identity_observation = identity_fetcher(
            spec["vault"],
            rpc_url=rpc_url,
            commitment=commitment,
        )
        identity_completed_at = _timestamp(clock)
        if not isinstance(identity_observation, Mapping):
            raise TypeError("identity_fetcher must return a mapping")
        sequence.append(
            {
                "step": f"{role}_rpc_identity",
                "completed_at": identity_completed_at,
                "slot": identity_observation.get("slot"),
            }
        )

        identity_verification = identity_verifier(
            identity_observation,
            expected_account=spec["vault"],
            expected_mint=spec["mint"],
            expected_authority=authority,
        )
        if not isinstance(identity_verification, Mapping):
            raise TypeError("identity_verifier must return a mapping")

        roles[role] = {
            "expected": {
                "vault": spec["vault"],
                "mint": spec["mint"],
                "decimals": spec["decimals"],
                "shared_authority": authority,
                "provider_field_path": spec["provider_field_path"],
            },
            "provider_raw_value": provider_value,
            "rpc_balance": dict(balance),
            "rpc_identity_observation": dict(identity_observation),
            "rpc_identity_verification": dict(identity_verification),
            "rpc_decimals_match": balance.get("decimals") == spec["decimals"],
        }

    ended_at = _timestamp(clock)
    _validate_timeline(started_at, sequence, ended_at)

    identity_verified = all(
        roles[role]["rpc_identity_verification"].get("identity_verified") is True
        for role in ROLES
    )
    decimals_match = all(roles[role]["rpc_decimals_match"] is True for role in ROLES)

    return {
        "service": "x1_reserve_live_evidence",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool,
        "collection": {
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": ended_at - started_at,
            "sequence": sequence,
        },
        "provider": {
            "source": pool_detail.get("source"),
            "observed_at": pool_detail.get("observed_at"),
            "last_synced_at": raw_pool.get("lastSyncedAt"),
            "last_updated": raw_response.get("lastUpdated"),
            "pool_detail": dict(pool_detail),
        },
        "roles": roles,
        "rpc_identity_verified": identity_verified,
        "rpc_decimals_match": decimals_match,
        "reserve_field_semantics_verified": False,
        "observation_scope_verified": False,
        "value_agreement_verified": False,
        "cmis_promotable": False,
        "warnings": [
            "provider_field_semantics_not_verified_by_collector",
            "observation_scope_not_verified_by_collector",
            "value_agreement_not_evaluated_by_collector",
        ],
        "errors": [],
    }


__all__ = ["ROLES", "VERSION", "collect_x1_reserve_live_evidence"]
