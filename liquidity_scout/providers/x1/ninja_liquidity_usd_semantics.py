"""Verify X1.Ninja USD liquidity semantics from exact RPC reserves.

The verifier intentionally avoids circular provider valuation. It uses the
accepted X1.Ninja pooled-reserve -> RPC-vault mapping, requires exact wrapped-XNT
position, derives native-per-asset price from the RPC reserve ratio, and applies
an independently verified XNT/USD valuation input.

It may verify the semantic formula for the provider liquidity field. It does
not establish provider fact time, freshness, source independence, rolling
24-hour activity semantics, or execution authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from liquidity_scout.providers.x1.ninja_pooled_reserve_semantics import (
    DIRECT_MAPPING,
    verify_ninja_pooled_reserve_semantics,
)
from liquidity_scout.providers.x1.xdex_price_history_import import WRAPPED_XNT_MINT


VERSION = "x1_ninja_liquidity_usd_semantics/v1"
DEFAULT_RELATIVE_TOLERANCE = Decimal("1e-4")
DEFAULT_ABSOLUTE_TOLERANCE_USD = Decimal("0.01")


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _pool_address(row: Mapping[str, Any]) -> str | None:
    return _text(
        row.get("address")
        or row.get("poolAddress")
        or row.get("pool_address")
        or row.get("id")
    )


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


def _positive_decimal(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
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
    allowed_error = max(absolute_tolerance, scale * relative_tolerance)
    relative_error = (
        absolute_error / scale
        if scale != 0
        else (Decimal(0) if absolute_error == 0 else None)
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


def _verified_xnt_usd(evidence: Mapping[str, Any]) -> Decimal:
    if not isinstance(evidence, Mapping):
        raise ValueError("xnt_usd_evidence must be a mapping")
    required = (
        "price_usd_verified",
        "provider_fact_time_verified",
        "freshness_verified",
        "same_time_scope_verified",
    )
    missing = [name for name in required if evidence.get(name) is not True]
    if missing:
        raise ValueError(
            "XNT/USD evidence is not eligible: " + ", ".join(missing)
        )
    if not _text(evidence.get("source")):
        raise ValueError("XNT/USD evidence source is required")
    return _positive_decimal(evidence.get("price_usd"), name="XNT/USD price")


def _liquidity_index(
    ninja_pools: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in ninja_pools:
        if not isinstance(row, Mapping):
            continue
        address = _pool_address(row)
        if not address or address in result:
            continue
        if "liquidity" in row:
            result[address] = row.get("liquidity")
    return result


def verify_ninja_liquidity_usd_semantics(
    *,
    ninja_pools: Sequence[Mapping[str, Any]],
    xdex_pools: Sequence[Mapping[str, Any]],
    xnt_usd_evidence: Mapping[str, Any],
    min_verified_pools: int = 5,
    max_samples: int = 5,
    relative_tolerance: Any = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance_usd: Any = DEFAULT_ABSOLUTE_TOLERANCE_USD,
    pooled_reserve_provider: Callable[..., Mapping[str, Any]] = (
        verify_ninja_pooled_reserve_semantics
    ),
    wrapped_xnt_mint: str = WRAPPED_XNT_MINT,
    rpc_url: str | None = None,
    signature_limit: int = 1,
) -> dict[str, Any]:
    """Verify provider pool liquidity as two-sided USD reserve valuation."""

    if isinstance(min_verified_pools, bool) or not isinstance(min_verified_pools, int):
        raise ValueError("min_verified_pools must be an integer")
    if min_verified_pools < 5:
        raise ValueError("min_verified_pools must be at least 5")
    if isinstance(max_samples, bool) or not isinstance(max_samples, int):
        raise ValueError("max_samples must be an integer")
    if max_samples < min_verified_pools:
        raise ValueError("max_samples must be >= min_verified_pools")

    relative = _nonnegative_decimal(relative_tolerance, name="relative_tolerance")
    absolute = _nonnegative_decimal(
        absolute_tolerance_usd,
        name="absolute_tolerance_usd",
    )
    if relative == 0 and absolute == 0:
        raise ValueError("at least one comparison tolerance must be positive")

    wrapped = _text(wrapped_xnt_mint)
    if not wrapped:
        raise ValueError("wrapped_xnt_mint is required")

    try:
        xnt_usd = _verified_xnt_usd(xnt_usd_evidence)
    except ValueError as exc:
        return {
            "service": "x1_ninja_liquidity_usd_semantics",
            "version": VERSION,
            "chain": "x1",
            "status": "unavailable",
            "xnt_usd_input_verified": False,
            "liquidity_usd_semantics_verified": False,
            "samples": [],
            "errors": [{"stage": "xnt_usd_evidence", "error": str(exc)}],
            "freshness_verified": False,
            "source_independence_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }

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
        raw = pooled_reserve_provider(**kwargs)
        upstream = dict(raw) if isinstance(raw, Mapping) else {}
    except Exception as exc:
        return {
            "service": "x1_ninja_liquidity_usd_semantics",
            "version": VERSION,
            "chain": "x1",
            "status": "unavailable",
            "xnt_usd_input_verified": True,
            "liquidity_usd_semantics_verified": False,
            "samples": [],
            "errors": [
                {
                    "stage": "pooled_reserve_provider",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            ],
            "freshness_verified": False,
            "source_independence_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }

    upstream_verified = bool(
        upstream.get("status") == "verified"
        and upstream.get("pooled_reserve_semantics_verified") is True
        and upstream.get("stable_mapping") == DIRECT_MAPPING
    )
    raw_samples = upstream.get("samples")
    raw_samples = (
        list(raw_samples)
        if isinstance(raw_samples, Sequence)
        and not isinstance(raw_samples, (str, bytes))
        else []
    )
    liquidities = _liquidity_index(ninja_pools)

    samples: list[dict[str, Any]] = []
    for raw_sample in raw_samples:
        if not isinstance(raw_sample, Mapping):
            continue
        address = _text(raw_sample.get("pool_address"))
        reasons: list[str] = []

        if raw_sample.get("mapping_verified") is not True:
            reasons.append("pooled_reserve_sample_unverified")
        mint_0 = _text(raw_sample.get("mint_0"))
        mint_1 = _text(raw_sample.get("mint_1"))
        if mint_0 != wrapped or mint_1 in {None, wrapped}:
            reasons.append("wrapped_xnt_position_unverified")

        try:
            xnt_reserve = _positive_decimal(
                raw_sample.get("rpc_vault_0_reserve"),
                name="rpc XNT reserve",
            )
            asset_reserve = _positive_decimal(
                raw_sample.get("rpc_vault_1_reserve"),
                name="rpc asset reserve",
            )
            provider_liquidity = _positive_decimal(
                liquidities.get(address),
                name="provider liquidity",
            )

            native_per_asset = xnt_reserve / asset_reserve
            asset_usd = native_per_asset * xnt_usd
            asset_side_usd = asset_reserve * asset_usd
            xnt_side_usd = xnt_reserve * xnt_usd
            total_usd = asset_side_usd + xnt_side_usd

            total_cmp = _compare(
                provider_liquidity,
                total_usd,
                relative_tolerance=relative,
                absolute_tolerance=absolute,
            )
            asset_side_cmp = _compare(
                provider_liquidity,
                asset_side_usd,
                relative_tolerance=relative,
                absolute_tolerance=absolute,
            )
            xnt_side_cmp = _compare(
                provider_liquidity,
                xnt_side_usd,
                relative_tolerance=relative,
                absolute_tolerance=absolute,
            )

            if total_cmp["within_tolerance"] is not True:
                reasons.append("provider_liquidity_does_not_match_two_sided_rpc_valuation")

            samples.append(
                {
                    "pool_address": address,
                    "mint_0": mint_0,
                    "mint_1": mint_1,
                    "xnt_reserve": format(xnt_reserve, "f"),
                    "asset_reserve": format(asset_reserve, "f"),
                    "verified_xnt_usd": format(xnt_usd, "f"),
                    "derived_native_per_asset": format(native_per_asset, "f"),
                    "derived_asset_usd": format(asset_usd, "f"),
                    "derived_asset_side_usd": format(asset_side_usd, "f"),
                    "derived_xnt_side_usd": format(xnt_side_usd, "f"),
                    "derived_two_sided_liquidity_usd": format(total_usd, "f"),
                    "provider_liquidity_usd": format(provider_liquidity, "f"),
                    "two_sided_comparison": total_cmp,
                    "one_sided_diagnostics": {
                        "asset_side": asset_side_cmp,
                        "xnt_side": xnt_side_cmp,
                    },
                    "liquidity_sample_verified": not reasons,
                    "rejection_reasons": reasons,
                }
            )
        except ValueError as exc:
            reasons.append(str(exc))
            samples.append(
                {
                    "pool_address": address,
                    "mint_0": mint_0,
                    "mint_1": mint_1,
                    "liquidity_sample_verified": False,
                    "rejection_reasons": reasons,
                }
            )

    verified_samples = [
        row for row in samples if row.get("liquidity_sample_verified") is True
    ]
    semantics_verified = bool(
        upstream_verified
        and len(samples) >= min_verified_pools
        and len(verified_samples) == len(samples)
        and len(verified_samples) >= min_verified_pools
    )

    status = "verified" if semantics_verified else ("partial" if samples else "unavailable")
    return {
        "service": "x1_ninja_liquidity_usd_semantics",
        "version": VERSION,
        "chain": "x1",
        "status": status,
        "valuation_formula": (
            "rpc_asset_reserve * ((rpc_xnt_reserve / rpc_asset_reserve) * verified_xnt_usd) "
            "+ rpc_xnt_reserve * verified_xnt_usd"
        ),
        "xnt_usd_input": {
            "price_usd": format(xnt_usd, "f"),
            "source": _text(xnt_usd_evidence.get("source")),
            "provider_fact_time_verified": True,
            "freshness_verified": True,
            "same_time_scope_verified": True,
        },
        "xnt_usd_input_verified": True,
        "upstream_pooled_reserve_semantics_verified": upstream_verified,
        "minimum_verified_pool_count": min_verified_pools,
        "sample_count": len(samples),
        "verified_sample_count": len(verified_samples),
        "all_selected_samples_verified": bool(samples) and len(verified_samples) == len(samples),
        "liquidity_two_sided_valuation_verified": semantics_verified,
        "x1_ninja_liquidity_usd_semantics_verified": semantics_verified,
        "liquidity_usd_semantics_verified": semantics_verified,
        "comparison_policy": {
            "arithmetic": "Decimal(str(value))",
            "relative_tolerance": format(relative, "e"),
            "absolute_tolerance_usd": format(absolute, "f"),
            "rule": (
                "absolute_error <= max(absolute_tolerance_usd, "
                "abs(derived_two_sided_liquidity_usd) * relative_tolerance)"
            ),
        },
        "samples": samples,
        "provider_fact_time_verified": False,
        "liquidity_freshness_verified": False,
        "freshness_verified": False,
        "source_independence_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "DEFAULT_ABSOLUTE_TOLERANCE_USD",
    "DEFAULT_RELATIVE_TOLERANCE",
    "VERSION",
    "verify_ninja_liquidity_usd_semantics",
]
