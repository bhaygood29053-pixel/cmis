"""Field-level semantic gate for observed XDEX compact history bars.

This module does not perform network I/O. It promotes only the history semantics
that have independent live corroboration and keeps unsupported compact fields
raw/unverified.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


SCHEMA = "xdex_history_field_semantics.v1"


@dataclass(frozen=True)
class XDEXHistorySemanticResult:
    schema: str
    close_native_verified: bool
    timestamp_unix_seconds_verified: bool
    interval_seconds_verified: bool
    interval_seconds: int | None
    volume_semantics_verified: bool
    coverage_complete_verified: bool
    cmis_promotable: bool


def _finite_decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("history numeric fields must not be booleans")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise ValueError("history numeric field must be finite") from exc
    if not parsed.is_finite():
        raise ValueError("history numeric field must be finite")
    return parsed


def classify_xdex_history_semantics(
    bars: Sequence[Mapping[str, Any]],
    *,
    requested_time_from: int,
    requested_time_to: int,
    corroborated_close_native: Any | None = None,
    expected_interval_seconds: int = 60,
) -> XDEXHistorySemanticResult:
    """Classify only independently supported compact-bar semantics.

    ``t`` is eligible only when every observed timestamp is an integer Unix-second
    candidate inside the explicit request window and adjacent bars use one stable
    interval. ``c`` is eligible only when a caller supplies an independently
    corroborated native-price observation equal to the latest close. ``v`` is
    intentionally never promoted by this contract because current live evidence
    disagrees with the independent candle-volume source.
    """

    if isinstance(requested_time_from, bool) or isinstance(requested_time_to, bool):
        raise ValueError("requested times must be integers")
    if not isinstance(requested_time_from, int) or not isinstance(requested_time_to, int):
        raise ValueError("requested times must be integers")
    if requested_time_to <= requested_time_from:
        raise ValueError("requested_time_to must exceed requested_time_from")
    if isinstance(expected_interval_seconds, bool) or not isinstance(expected_interval_seconds, int) or expected_interval_seconds <= 0:
        raise ValueError("expected_interval_seconds must be a positive integer")
    if not bars:
        return XDEXHistorySemanticResult(SCHEMA, False, False, False, None, False, False, False)

    timestamps: list[int] = []
    closes: list[Decimal] = []
    for index, bar in enumerate(bars):
        if not isinstance(bar, Mapping):
            raise ValueError(f"bar {index} must be a mapping")
        if "t" not in bar or "c" not in bar:
            raise ValueError(f"bar {index} must contain raw t and c fields")
        t = bar["t"]
        if isinstance(t, bool) or not isinstance(t, int):
            raise ValueError(f"bar {index} t must be an integer")
        timestamps.append(t)
        closes.append(_finite_decimal(bar["c"]))

    ordered = timestamps == sorted(timestamps) and len(set(timestamps)) == len(timestamps)
    in_window = all(requested_time_from <= t <= requested_time_to for t in timestamps)
    deltas = [b - a for a, b in zip(timestamps, timestamps[1:])]
    stable_interval = bool(deltas) and all(delta == expected_interval_seconds for delta in deltas)
    timestamp_verified = ordered and in_window and stable_interval

    close_verified = False
    if corroborated_close_native is not None:
        close_verified = closes[-1] == _finite_decimal(corroborated_close_native)

    return XDEXHistorySemanticResult(
        schema=SCHEMA,
        close_native_verified=close_verified,
        timestamp_unix_seconds_verified=timestamp_verified,
        interval_seconds_verified=timestamp_verified,
        interval_seconds=expected_interval_seconds if timestamp_verified else None,
        volume_semantics_verified=False,
        coverage_complete_verified=False,
        cmis_promotable=False,
    )


__all__ = ["SCHEMA", "XDEXHistorySemanticResult", "classify_xdex_history_semantics"]
