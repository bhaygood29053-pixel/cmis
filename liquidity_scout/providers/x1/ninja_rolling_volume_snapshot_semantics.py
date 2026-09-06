"""Classify X1.Ninja rolling-volume vs trade-row USD snapshot behavior.

This evidence contract is deliberately observational. It can prove that the
provider's trade-history USD display changed between two captures while the
same exact trade set and pool rolling aggregate stayed fixed. It does not infer
the provider's internal formula, database schema, causal implementation, or a
safe USD valuation input for CMIS.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


CONTRACT = "x1_ninja_rolling_volume_snapshot_semantics/v1"
DEFAULT_REL_TOL = Decimal("1e-12")


class X1NinjaRollingVolumeSnapshotError(ValueError):
    pass


def _decimal(value: Any, *, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise X1NinjaRollingVolumeSnapshotError(f"{name} must be numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise X1NinjaRollingVolumeSnapshotError(
            f"{name} must be numeric"
        ) from exc
    if not parsed.is_finite():
        raise X1NinjaRollingVolumeSnapshotError(f"{name} must be finite")
    return parsed


def _trade_map(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(rows, (str, bytes, bytearray)):
        raise X1NinjaRollingVolumeSnapshotError("trade rows must be a sequence")
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise X1NinjaRollingVolumeSnapshotError("trade row must be a mapping")
        signature = str(row.get("txHash") or "").strip()
        if not signature or signature in output:
            raise X1NinjaRollingVolumeSnapshotError(
                "trade rows require unique txHash values"
            )
        amount_native = _decimal(row.get("amountNative"), name="amountNative")
        amount_usd = _decimal(row.get("amountUsd"), name="amountUsd")
        if amount_native <= 0 or amount_usd < 0:
            raise X1NinjaRollingVolumeSnapshotError(
                "trade amounts must be non-negative and amountNative positive"
            )
        output[signature] = {
            "txHash": signature,
            "slot": row.get("slot"),
            "timestamp": row.get("timestamp"),
            "amountNative": amount_native,
            "amountToken": _decimal(row.get("amountToken"), name="amountToken"),
            "amountUsd": amount_usd,
            "priceNative": _decimal(row.get("priceNative"), name="priceNative"),
            "priceUsd": _decimal(row.get("priceUsd"), name="priceUsd"),
            "implied_xnt_usd": amount_usd / amount_native,
        }
    return output


def _same_trade_identity(
    before: Mapping[str, Mapping[str, Any]],
    after: Mapping[str, Mapping[str, Any]],
) -> bool:
    if set(before) != set(after) or not before:
        return False
    for signature in before:
        left = before[signature]
        right = after[signature]
        if (
            left.get("slot") != right.get("slot")
            or left.get("timestamp") != right.get("timestamp")
            or left["amountNative"] != right["amountNative"]
            or left["amountToken"] != right["amountToken"]
            or left["priceNative"] != right["priceNative"]
        ):
            return False
    return True


def _shared_basis(
    rows: Mapping[str, Mapping[str, Any]],
    *,
    relative_tolerance: Decimal,
) -> tuple[bool, Decimal | None, Decimal | None]:
    values = [row["implied_xnt_usd"] for row in rows.values()]
    if len(values) < 2 or min(values) <= 0:
        return False, None, None
    low = min(values)
    high = max(values)
    spread = (high - low) / low
    midpoint = sum(values, Decimal(0)) / Decimal(len(values))
    return spread <= relative_tolerance, midpoint, spread


def evaluate_x1_ninja_rolling_volume_snapshots(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    relative_tolerance: Any = DEFAULT_REL_TOL,
) -> dict[str, Any]:
    """Evaluate two provider captures without assigning an internal formula."""

    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise TypeError("before and after must be mappings")
    rel = _decimal(relative_tolerance, name="relative_tolerance")
    if rel < 0:
        raise X1NinjaRollingVolumeSnapshotError(
            "relative_tolerance must be non-negative"
        )

    before_rows = _trade_map(before.get("trade_rows") or [])
    after_rows = _trade_map(after.get("trade_rows") or [])
    exact_trade_set_stable = _same_trade_identity(before_rows, after_rows)

    before_shared, before_basis, before_spread = _shared_basis(
        before_rows, relative_tolerance=rel
    )
    after_shared, after_basis, after_spread = _shared_basis(
        after_rows, relative_tolerance=rel
    )

    before_volume = _decimal(before.get("volume24h"), name="before volume24h")
    after_volume = _decimal(after.get("volume24h"), name="after volume24h")
    if before_volume < 0 or after_volume < 0:
        raise X1NinjaRollingVolumeSnapshotError("volume24h must be non-negative")

    volume_delta = after_volume - before_volume
    volume_invariant = abs(volume_delta) <= max(
        Decimal("1e-12"),
        abs(before_volume) * rel,
    )

    before_trade_sum = sum(
        (row["amountUsd"] for row in before_rows.values()), Decimal(0)
    )
    after_trade_sum = sum(
        (row["amountUsd"] for row in after_rows.values()), Decimal(0)
    )
    trade_sum_delta = after_trade_sum - before_trade_sum

    shared_basis_changed = bool(
        before_shared
        and after_shared
        and before_basis is not None
        and after_basis is not None
        and abs(after_basis - before_basis)
        > max(abs(before_basis), abs(after_basis)) * rel
    )
    trade_row_usd_repricing_observed = bool(
        exact_trade_set_stable
        and shared_basis_changed
        and abs(trade_sum_delta) > Decimal("1e-12")
    )
    rolling_aggregate_invariant_under_trade_repricing = bool(
        trade_row_usd_repricing_observed and volume_invariant
    )

    return {
        "contract": CONTRACT,
        "exact_trade_set_stable": exact_trade_set_stable,
        "trade_count": len(before_rows) if exact_trade_set_stable else None,
        "before_shared_trade_xnt_basis_verified": before_shared,
        "after_shared_trade_xnt_basis_verified": after_shared,
        "before_implied_xnt_usd": (
            format(before_basis, "f") if before_basis is not None else None
        ),
        "after_implied_xnt_usd": (
            format(after_basis, "f") if after_basis is not None else None
        ),
        "before_basis_relative_spread": (
            format(before_spread, "e") if before_spread is not None else None
        ),
        "after_basis_relative_spread": (
            format(after_spread, "e") if after_spread is not None else None
        ),
        "shared_trade_xnt_basis_changed": shared_basis_changed,
        "before_trade_row_usd_sum": format(before_trade_sum, "f"),
        "after_trade_row_usd_sum": format(after_trade_sum, "f"),
        "trade_row_usd_sum_delta": format(trade_sum_delta, "f"),
        "before_volume24h": format(before_volume, "f"),
        "after_volume24h": format(after_volume, "f"),
        "volume24h_delta": format(volume_delta, "f"),
        "volume24h_invariant": volume_invariant,
        "trade_row_usd_repricing_observed": trade_row_usd_repricing_observed,
        "rolling_aggregate_invariant_under_trade_repricing": (
            rolling_aggregate_invariant_under_trade_repricing
        ),
        "provider_internal_formula_verified": False,
        "provider_volume_fact_time_verified": False,
        "current_price_substitution_authorized": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT",
    "DEFAULT_REL_TOL",
    "X1NinjaRollingVolumeSnapshotError",
    "evaluate_x1_ninja_rolling_volume_snapshots",
]
