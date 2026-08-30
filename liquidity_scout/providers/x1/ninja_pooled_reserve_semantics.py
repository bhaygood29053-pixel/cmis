"""Verify X1.Ninja pooledBase/pooledQuote semantics against exact X1 RPC reserves.

This gate consumes the accepted RPC reserve-unit proof from CMIS #339 and asks
one narrow question: which exact RPC vault reserve does each X1.Ninja pooled
field represent?

Both possible two-sided mappings are tested with deterministic Decimal
arithmetic. A sample is accepted only when exactly one mapping matches within a
tight explicit tolerance. The mapping must then remain stable across at least
five independently RPC-verified current pools.

The tolerance is intentionally small:
- relative: 5e-16
- absolute floor: 5e-12 token units

This is sized to tolerate the observed JSON / binary floating-point
serialization noise without treating material reserve differences as equal.

This module does not verify USD liquidity, XDEX TVL, price, volume, market cap,
freshness, source independence, general base/quote semantics, or execution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from liquidity_scout.providers.x1.rpc_vault_reserve_units import (
    verify_rpc_vault_reserve_units,
)


VERSION = "1.0"
DEFAULT_RELATIVE_TOLERANCE = Decimal("5e-16")
DEFAULT_ABSOLUTE_TOLERANCE = Decimal("5e-12")

DIRECT_MAPPING = "pooledBase_to_vault1__pooledQuote_to_vault0"
REVERSED_MAPPING = "pooledBase_to_vault0__pooledQuote_to_vault1"


def _decimal(value: Any, *, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be a finite number")
    return parsed


def _nonnegative_decimal(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name)
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def _compare(
    observed: Decimal,
    expected: Decimal,
    *,
    relative_tolerance: Decimal,
    absolute_tolerance: Decimal,
) -> dict[str, Any]:
    absolute_error = abs(observed - expected)
    scale = abs(expected)
    relative_error = (
        absolute_error / scale
        if scale != 0
        else (Decimal(0) if absolute_error == 0 else None)
    )
    allowed_error = max(
        absolute_tolerance,
        scale * relative_tolerance,
    )
    return {
        "observed": format(observed, "f"),
        "expected": format(expected, "f"),
        "absolute_error": format(absolute_error, "f"),
        "relative_error": (
            format(relative_error, "e") if relative_error is not None else None
        ),
        "allowed_absolute_error": format(allowed_error, "f"),
        "within_tolerance": absolute_error <= allowed_error,
    }


def _vault_amounts(sample: Mapping[str, Any]) -> tuple[Decimal, Decimal]:
    vaults = sample.get("vaults")
    if not isinstance(vaults, Sequence) or isinstance(vaults, (str, bytes)):
        raise ValueError("verified sample vaults are missing")

    by_slot: dict[int, Mapping[str, Any]] = {}
    for raw in vaults:
        if not isinstance(raw, Mapping):
            continue
        slot = raw.get("slot_index")
        if isinstance(slot, int) and not isinstance(slot, bool):
            by_slot[slot] = raw

    if set(by_slot) != {0, 1}:
        raise ValueError("verified sample must contain exactly vault slots 0 and 1")

    for slot in (0, 1):
        if by_slot[slot].get("verified") is not True:
            raise ValueError(f"vault_{slot} is not verified")

    return (
        _nonnegative_decimal(
            by_slot[0].get("scaled_amount"),
            name="vault_0.scaled_amount",
        ),
        _nonnegative_decimal(
            by_slot[1].get("scaled_amount"),
            name="vault_1.scaled_amount",
        ),
    )


def _ninja_pooled_values(sample: Mapping[str, Any]) -> tuple[Decimal, Decimal]:
    provider = sample.get("provider_raw_candidates")
    provider = provider if isinstance(provider, Mapping) else {}
    ninja = provider.get("x1_ninja")
    ninja = ninja if isinstance(ninja, Mapping) else {}

    if "pooledBase" not in ninja or "pooledQuote" not in ninja:
        raise ValueError("X1.Ninja pooledBase/pooledQuote fields are required")

    return (
        _nonnegative_decimal(ninja.get("pooledBase"), name="pooledBase"),
        _nonnegative_decimal(ninja.get("pooledQuote"), name="pooledQuote"),
    )


def _mapping_evidence(
    *,
    pooled_base: Decimal,
    pooled_quote: Decimal,
    vault_0: Decimal,
    vault_1: Decimal,
    relative_tolerance: Decimal,
    absolute_tolerance: Decimal,
) -> dict[str, Any]:
    direct = {
        "pooledBase_vs_vault1": _compare(
            pooled_base,
            vault_1,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        ),
        "pooledQuote_vs_vault0": _compare(
            pooled_quote,
            vault_0,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        ),
    }
    direct["mapping_matches"] = all(
        row["within_tolerance"]
        for key, row in direct.items()
        if key != "mapping_matches"
    )

    reversed_mapping = {
        "pooledBase_vs_vault0": _compare(
            pooled_base,
            vault_0,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        ),
        "pooledQuote_vs_vault1": _compare(
            pooled_quote,
            vault_1,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        ),
    }
    reversed_mapping["mapping_matches"] = all(
        row["within_tolerance"]
        for key, row in reversed_mapping.items()
        if key != "mapping_matches"
    )

    matching = []
    if direct["mapping_matches"]:
        matching.append(DIRECT_MAPPING)
    if reversed_mapping["mapping_matches"]:
        matching.append(REVERSED_MAPPING)

    return {
        "candidate_mappings": {
            DIRECT_MAPPING: direct,
            REVERSED_MAPPING: reversed_mapping,
        },
        "matching_mapping_count": len(matching),
        "unique_matching_mapping": matching[0] if len(matching) == 1 else None,
        "mapping_verified": len(matching) == 1,
    }


def verify_ninja_pooled_reserve_semantics(
    *,
    ninja_pools: Sequence[Mapping[str, Any]],
    xdex_pools: Sequence[Mapping[str, Any]],
    min_verified_pools: int = 5,
    max_samples: int = 5,
    relative_tolerance: Any = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance: Any = DEFAULT_ABSOLUTE_TOLERANCE,
    reserve_unit_provider: Callable[..., Mapping[str, Any]] = (
        verify_rpc_vault_reserve_units
    ),
    rpc_url: str | None = None,
    signature_limit: int = 1,
) -> dict[str, Any]:
    """Verify X1.Ninja pooled field roles/units against exact RPC reserves."""

    if isinstance(min_verified_pools, bool) or not isinstance(min_verified_pools, int):
        raise ValueError("min_verified_pools must be an integer")
    if min_verified_pools < 5:
        raise ValueError("min_verified_pools must be at least 5")
    if isinstance(max_samples, bool) or not isinstance(max_samples, int):
        raise ValueError("max_samples must be an integer")
    if max_samples < min_verified_pools:
        raise ValueError("max_samples must be >= min_verified_pools")

    relative = _nonnegative_decimal(
        relative_tolerance,
        name="relative_tolerance",
    )
    absolute = _nonnegative_decimal(
        absolute_tolerance,
        name="absolute_tolerance",
    )
    if relative == 0 and absolute == 0:
        raise ValueError("at least one comparison tolerance must be positive")

    kwargs: dict[str, Any] = {
        "ninja_pools": ninja_pools,
        "xdex_pools": xdex_pools,
        "min_verified_pools": min_verified_pools,
        "max_samples": max_samples,
        "signature_limit": signature_limit,
    }
    if rpc_url is not None:
        kwargs["rpc_url"] = rpc_url

    try:
        raw_report = reserve_unit_provider(**kwargs)
        reserve_report = (
            dict(raw_report) if isinstance(raw_report, Mapping) else {}
        )
    except Exception as exc:
        return {
            "service": "x1_ninja_pooled_reserve_semantics",
            "version": VERSION,
            "chain": "x1",
            "status": "unavailable",
            "pooled_reserve_semantics_verified": False,
            "stable_mapping": None,
            "samples": [],
            "errors": [
                {
                    "stage": "rpc_reserve_unit_provider",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            ],
            "cmis_promotable": False,
            "execution_authorized": False,
        }

    upstream_verified = bool(
        reserve_report.get("status") == "verified"
        and reserve_report.get("rpc_vault_reserve_amounts_verified") is True
        and reserve_report.get("rpc_reserve_unit_scaling_verified") is True
        and reserve_report.get("position_mapping_verified") is True
    )

    raw_samples = reserve_report.get("samples")
    raw_samples = (
        list(raw_samples)
        if isinstance(raw_samples, Sequence)
        and not isinstance(raw_samples, (str, bytes))
        else []
    )

    samples: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for raw in raw_samples:
        if not isinstance(raw, Mapping):
            continue

        pool_address = str(raw.get("pool_address") or "").strip() or None
        if raw.get("verified") is not True:
            samples.append(
                {
                    "pool_address": pool_address,
                    "mapping_verified": False,
                    "rejection_reasons": ["upstream_rpc_reserve_sample_unverified"],
                }
            )
            continue

        try:
            vault_0, vault_1 = _vault_amounts(raw)
            pooled_base, pooled_quote = _ninja_pooled_values(raw)
            evidence = _mapping_evidence(
                pooled_base=pooled_base,
                pooled_quote=pooled_quote,
                vault_0=vault_0,
                vault_1=vault_1,
                relative_tolerance=relative,
                absolute_tolerance=absolute,
            )
            samples.append(
                {
                    "pool_address": pool_address,
                    "rpc_vault_0_reserve": format(vault_0, "f"),
                    "rpc_vault_1_reserve": format(vault_1, "f"),
                    "x1_ninja_pooledBase": format(pooled_base, "f"),
                    "x1_ninja_pooledQuote": format(pooled_quote, "f"),
                    **evidence,
                    "provider_liquidity_semantics_verified": False,
                    "xdex_tvl_semantics_verified": False,
                }
            )
        except Exception as exc:
            samples.append(
                {
                    "pool_address": pool_address,
                    "mapping_verified": False,
                    "unique_matching_mapping": None,
                    "rejection_reasons": [
                        f"{type(exc).__name__}: {exc}"
                    ],
                }
            )

    verified_samples = [
        row for row in samples if row.get("mapping_verified") is True
    ]
    mappings = {
        row.get("unique_matching_mapping")
        for row in verified_samples
        if row.get("unique_matching_mapping")
    }

    stable = bool(
        upstream_verified
        and len(verified_samples) >= min_verified_pools
        and len(verified_samples) == len(samples)
        and len(mappings) == 1
    )
    stable_mapping = next(iter(mappings)) if stable else None

    status = "verified" if stable else ("partial" if samples else "unavailable")

    return {
        "service": "x1_ninja_pooled_reserve_semantics",
        "version": VERSION,
        "chain": "x1",
        "status": status,
        "upstream_rpc_reserve_units_verified": upstream_verified,
        "sample_count": len(samples),
        "verified_sample_count": len(verified_samples),
        "minimum_verified_pool_count": min_verified_pools,
        "stable_mapping": stable_mapping,
        "pooled_reserve_field_roles_verified": stable,
        "pooled_reserve_units_verified": stable,
        "pooled_reserve_semantics_verified": stable,
        "x1_ninja_pooled_base_quote_role_mapping_verified": stable,
        "general_base_quote_semantics_verified": False,
        "comparison_policy": {
            "arithmetic": "Decimal(str(value))",
            "relative_tolerance": format(relative, "e"),
            "absolute_tolerance_token_units": format(absolute, "e"),
            "rule": "absolute_error <= max(absolute_tolerance, abs(rpc_reserve) * relative_tolerance)",
            "purpose": (
                "Permit only tiny JSON/binary-float representation differences; "
                "material reserve disagreement fails closed."
            ),
        },
        "samples": samples,
        "errors": errors,
        "semantics": {
            "x1_ninja_liquidity_semantics_verified": False,
            "xdex_tvl_semantics_verified": False,
            "usd_valuation_verified": False,
            "price_semantics_verified": False,
            "volume_semantics_verified": False,
            "market_cap_semantics_verified": False,
            "freshness_verified": False,
            "source_independence_verified": False,
        },
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "DEFAULT_ABSOLUTE_TOLERANCE",
    "DEFAULT_RELATIVE_TOLERANCE",
    "DIRECT_MAPPING",
    "REVERSED_MAPPING",
    "VERSION",
    "verify_ninja_pooled_reserve_semantics",
]
