"""Verified XDEX historical USD-price backfill for X1 CMIS.

This importer is deliberately narrower than the raw XDEX history transport.
It persists only price observations whose compact XDEX close is corroborated
bar-by-bar by the X1.Ninja OHLCV view for the same provider pair.

Two paths are supported:
1. direct asset / configured USD-stable quote;
2. asset / XNT multiplied by XNT / configured USD-stable quote.

The stable quote's USD equivalence is an explicit configuration fact, not proof
of a historical one-dollar peg. Provider source independence, provider archive
completeness, continuous coverage, and full asset lifetime remain unverified.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Callable

from .ninja_history import fetch_pool_ohlcv_raw
from .xdex import fetch_price_history


CHAIN = "x1"
SOURCE = "XDEX public API + X1.Ninja OHLCV"
WRAPPED_XNT_MINT = "So11111111111111111111111111111111111111112"
USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"

_INTERVAL_TO_TIMEFRAME = {
    60: "1m",
    300: "5m",
    900: "15m",
    3600: "1h",
    14400: "4h",
    86400: "1D",
}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _finite_positive(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def _token_mint(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key in ("mint", "address", "tokenAddress", "id"):
            text = _text(value.get(key))
            if text:
                return text
        return None
    return _text(value)


def _pool_address(pool: Mapping[str, Any]) -> str | None:
    for key in ("address", "poolAddress", "pool_address", "id"):
        text = _text(pool.get(key))
        if text:
            return text
    return None


def _pool_liquidity(pool: Mapping[str, Any]) -> float:
    value = _finite_positive(pool.get("liquidity"))
    return value if value is not None else 0.0


def _pool_pair(pool: Mapping[str, Any]) -> tuple[str | None, str | None]:
    return _token_mint(pool.get("baseToken")), _token_mint(pool.get("quoteToken"))


def _best_pool(
    pools: Sequence[Any],
    *,
    base_mint: str,
    quote_mint: str,
) -> Mapping[str, Any] | None:
    candidates = []
    for pool in pools:
        if not isinstance(pool, Mapping):
            continue
        base, quote = _pool_pair(pool)
        if base == base_mint and quote == quote_mint and _pool_address(pool):
            candidates.append(pool)
    if not candidates:
        return None
    return max(candidates, key=_pool_liquidity)


def _epoch(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                value = float(text)
            except ValueError:
                return None
        else:
            if dt.tzinfo is None:
                return None
            return int(dt.astimezone(timezone.utc).timestamp())

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed < 0:
        return None
    if parsed > 10_000_000_000:
        parsed /= 1000.0
    return int(round(parsed))


def _normalized_xdex_bars(
    bars: Any,
    *,
    time_from: int,
    time_to: int,
) -> tuple[list[dict[str, Any]], int, str] | None:
    if not isinstance(bars, list) or len(bars) < 2:
        return None

    result = []
    for row in bars:
        if not isinstance(row, Mapping):
            return None
        t = row.get("t")
        if isinstance(t, bool) or not isinstance(t, int):
            return None
        close = _finite_positive(row.get("c"))
        if close is None or t < time_from or t > time_to:
            return None
        result.append({"timestamp": t, "close": close})

    timestamps = [row["timestamp"] for row in result]
    if timestamps != sorted(timestamps) or len(set(timestamps)) != len(timestamps):
        return None
    deltas = [
        right - left
        for left, right in zip(timestamps, timestamps[1:])
    ]
    if not deltas or len(set(deltas)) != 1:
        return None
    interval = deltas[0]
    timeframe = _INTERVAL_TO_TIMEFRAME.get(interval)
    if timeframe is None:
        return None
    return result, interval, timeframe


def _ninja_pair_scope(
    observation: Any,
    *,
    pool_address: str,
    base_mint: str,
    quote_mint: str,
) -> tuple[Mapping[str, Any], list[Any]] | None:
    if not isinstance(observation, Mapping):
        return None
    if observation.get("pool_address") != pool_address:
        return None
    contract = observation.get("contract")
    if not isinstance(contract, Mapping):
        return None
    required = (
        "request_contract_verified",
        "response_contract_verified",
        "candle_schema_verified",
        "request_scope_verified",
    )
    if not all(contract.get(key) is True for key in required):
        return None

    body = observation.get("raw_response")
    if not isinstance(body, Mapping):
        return None
    if body.get("poolAddress") != pool_address:
        return None
    if _token_mint(body.get("baseToken")) != base_mint:
        return None
    if _token_mint(body.get("quoteToken")) != quote_mint:
        return None

    candles = body.get("ohlcv")
    if not isinstance(candles, list):
        return None
    return body, candles


def _cross_verified_pair_closes(
    *,
    base_mint: str,
    quote_mint: str,
    pool: Mapping[str, Any],
    time_from: int,
    time_to: int,
    xdex_fetcher: Callable[..., Any],
    ninja_fetcher: Callable[..., Any],
    rel_tolerance: float,
) -> dict[str, Any]:
    pool_address = _pool_address(pool)
    if not pool_address:
        return {
            "status": "unavailable",
            "reason": "provider_pool_address_unavailable",
        }

    try:
        raw_bars = xdex_fetcher(
            base_mint,
            quote_mint,
            time_from=time_from,
            time_to=time_to,
        )
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": "xdex_price_history_fetch_failed",
            "details": f"{type(exc).__name__}: {exc}",
        }

    normalized = _normalized_xdex_bars(
        raw_bars,
        time_from=time_from,
        time_to=time_to,
    )
    if normalized is None:
        return {
            "status": "unavailable",
            "reason": "xdex_history_timestamp_or_interval_unverified",
        }
    bars, interval, timeframe = normalized

    try:
        ninja = ninja_fetcher(
            pool_address,
            timeframe=timeframe,
            limit=min(300, max(2, len(bars) + 4)),
        )
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": "x1_ninja_ohlcv_fetch_failed",
            "details": f"{type(exc).__name__}: {exc}",
        }

    scope = _ninja_pair_scope(
        ninja,
        pool_address=pool_address,
        base_mint=base_mint,
        quote_mint=quote_mint,
    )
    if scope is None:
        return {
            "status": "unavailable",
            "reason": "cross_provider_pair_scope_unverified",
        }
    _body, candles = scope

    ninja_by_time = {}
    for row in candles:
        if not isinstance(row, Mapping):
            continue
        ts = _epoch(row.get("time"))
        close = _finite_positive(row.get("close"))
        if ts is not None and close is not None:
            ninja_by_time[ts] = close
    if not ninja_by_time:
        return {
            "status": "unavailable",
            "reason": "x1_ninja_ohlcv_semantic_rows_unavailable",
        }

    shifts = (0, -interval, interval)
    candidates = []
    for shift in shifts:
        verified = []
        overlap_count = 0
        for row in bars:
            other_ts = row["timestamp"] + shift
            other_close = ninja_by_time.get(other_ts)
            if other_close is None:
                continue
            overlap_count += 1
            if math.isclose(
                row["close"],
                other_close,
                rel_tol=rel_tolerance,
                abs_tol=1e-12,
            ):
                verified.append({
                    "timestamp": row["timestamp"],
                    "close": row["close"],
                    "ninja_timestamp": other_ts,
                    "ninja_close": other_close,
                })
        candidates.append((len(verified), overlap_count, -abs(shift), shift, verified))

    _matches, overlap_count, _shift_rank, shift, verified = max(candidates)
    if not verified:
        return {
            "status": "unavailable",
            "reason": "cross_provider_close_corroboration_unavailable",
            "interval_seconds": interval,
            "timeframe": timeframe,
            "overlap_count": overlap_count,
        }

    return {
        "status": "partial",
        "reason": "cross_provider_close_observations_verified",
        "base_mint": base_mint,
        "quote_mint": quote_mint,
        "pool_address": pool_address,
        "provider_pair": f"{base_mint}/{quote_mint}",
        "interval_seconds": interval,
        "timeframe": timeframe,
        "timestamp_alignment_shift_seconds": shift,
        "xdex_bar_count": len(bars),
        "cross_provider_overlap_count": overlap_count,
        "verified_close_count": len(verified),
        "verified_closes": verified,
        "source_independence_verified": False,
        "provider_range_complete_verified": False,
        "continuous_coverage_verified": False,
    }


def _unavailable(mint: str, reason: str, **extra: Any) -> dict[str, Any]:
    result = {
        "chain": CHAIN,
        "status": "unavailable",
        "reason": reason,
        "mint": mint,
        "source": SOURCE,
        "provider_history_imported": False,
        "imported_observation_count": 0,
        "first_imported_observed_at": None,
        "last_imported_observed_at": None,
        "full_asset_lifetime_verified": False,
        "continuous_coverage_verified": False,
        "provider_range_complete_verified": False,
        "source_independence_verified": False,
        "limitations": [
            "imports_verified_price_only",
            "volume_and_liquidity_history_not_imported",
            "provider_source_independence_not_verified",
            "provider_archive_completeness_not_verified",
            "configured_usd_stable_quote_does_not_prove_historical_one_dollar_peg",
            "no_claim_of_complete_asset_lifetime_history",
        ],
    }
    result.update(extra)
    return result


def backfill_verified_xdex_usd_price_history(
    mint: Any,
    symbol: Any,
    *,
    catalog_pools: Sequence[Any],
    history_backend: Any,
    time_from: int,
    time_to: int,
    stable_quote_mint: str = USDC_X_MINT,
    wrapped_xnt_mint: str = WRAPPED_XNT_MINT,
    xdex_fetcher: Callable[..., Any] = fetch_price_history,
    ninja_fetcher: Callable[..., Any] = fetch_pool_ohlcv_raw,
    rel_tolerance: float = 5e-3,
    imported_at: int | None = None,
) -> dict[str, Any]:
    """Backfill the earliest currently defensible provider USD observations."""

    mint_text = _text(mint)
    symbol_text = _text(symbol) or "Unknown"
    stable_quote = _text(stable_quote_mint)
    wrapped_xnt = _text(wrapped_xnt_mint)
    if not mint_text or not stable_quote or not wrapped_xnt:
        raise ValueError("mint and configured quote mints are required")
    if not isinstance(catalog_pools, Sequence) or isinstance(
        catalog_pools, (str, bytes)
    ):
        raise TypeError("catalog_pools must be a sequence")
    if isinstance(time_from, bool) or isinstance(time_to, bool):
        raise ValueError("time bounds must be integers")
    if not isinstance(time_from, int) or not isinstance(time_to, int):
        raise ValueError("time bounds must be integers")
    if time_from < 0 or time_to <= time_from:
        raise ValueError("time_to must exceed non-negative time_from")
    if not math.isfinite(float(rel_tolerance)) or not 0 <= float(rel_tolerance) <= 0.05:
        raise ValueError("rel_tolerance must be between 0 and 0.05")

    writer = getattr(history_backend, "record_verified_price_observation", None)
    if not callable(writer):
        return _unavailable(
            mint_text,
            "verified_price_history_writer_unavailable",
        )

    direct_pool = _best_pool(
        catalog_pools,
        base_mint=mint_text,
        quote_mint=stable_quote,
    )
    native_pool = _best_pool(
        catalog_pools,
        base_mint=mint_text,
        quote_mint=wrapped_xnt,
    )
    xnt_usd_pool = _best_pool(
        catalog_pools,
        base_mint=wrapped_xnt,
        quote_mint=stable_quote,
    )

    method = None
    derived = []
    evidence = {}

    if direct_pool is not None:
        direct = _cross_verified_pair_closes(
            base_mint=mint_text,
            quote_mint=stable_quote,
            pool=direct_pool,
            time_from=time_from,
            time_to=time_to,
            xdex_fetcher=xdex_fetcher,
            ninja_fetcher=ninja_fetcher,
            rel_tolerance=float(rel_tolerance),
        )
        if direct.get("verified_close_count", 0) > 0:
            method = "direct_configured_usd_stable_quote"
            derived = [
                {
                    "timestamp": row["timestamp"],
                    "price_usd": row["close"],
                    "legs": [row],
                }
                for row in direct["verified_closes"]
            ]
            evidence = {"direct": direct}

    if not derived and native_pool is not None and xnt_usd_pool is not None:
        native = _cross_verified_pair_closes(
            base_mint=mint_text,
            quote_mint=wrapped_xnt,
            pool=native_pool,
            time_from=time_from,
            time_to=time_to,
            xdex_fetcher=xdex_fetcher,
            ninja_fetcher=ninja_fetcher,
            rel_tolerance=float(rel_tolerance),
        )
        xnt_usd = _cross_verified_pair_closes(
            base_mint=wrapped_xnt,
            quote_mint=stable_quote,
            pool=xnt_usd_pool,
            time_from=time_from,
            time_to=time_to,
            xdex_fetcher=xdex_fetcher,
            ninja_fetcher=ninja_fetcher,
            rel_tolerance=float(rel_tolerance),
        )
        if (
            native.get("verified_close_count", 0) > 0
            and xnt_usd.get("verified_close_count", 0) > 0
            and native.get("interval_seconds") == xnt_usd.get("interval_seconds")
        ):
            native_by_time = {
                row["timestamp"]: row
                for row in native["verified_closes"]
            }
            usd_by_time = {
                row["timestamp"]: row
                for row in xnt_usd["verified_closes"]
            }
            for ts in sorted(set(native_by_time) & set(usd_by_time)):
                first = native_by_time[ts]
                second = usd_by_time[ts]
                price_usd = first["close"] * second["close"]
                if math.isfinite(price_usd) and price_usd > 0:
                    derived.append({
                        "timestamp": ts,
                        "price_usd": price_usd,
                        "legs": [first, second],
                    })
            if derived:
                method = "two_leg_xnt_to_configured_usd_stable_quote"
                evidence = {"asset_xnt": native, "xnt_usd": xnt_usd}

    if not derived:
        return _unavailable(
            mint_text,
            "verified_provider_usd_price_path_unavailable",
            direct_pool_available=direct_pool is not None,
            asset_xnt_pool_available=native_pool is not None,
            xnt_usd_pool_available=xnt_usd_pool is not None,
        )

    provider_pair = (
        f"{mint_text}/{stable_quote}"
        if method == "direct_configured_usd_stable_quote"
        else f"{mint_text}/{wrapped_xnt}*{wrapped_xnt}/{stable_quote}"
    )

    inserted = 0
    for row in derived:
        row_evidence = {
            "schema": "xdex_verified_price_backfill.v1",
            "method": method,
            "timestamp": row["timestamp"],
            "legs": row["legs"],
            "provider_scope": evidence,
            "configured_usd_stable_quote_mint": stable_quote,
            "source_independence_verified": False,
            "provider_range_complete_verified": False,
            "continuous_coverage_verified": False,
            "historical_stable_quote_peg_verified": False,
        }
        if writer(
            mint=mint_text,
            symbol=symbol_text,
            timestamp=row["timestamp"],
            price_usd=row["price_usd"],
            source=SOURCE,
            provider_pair=provider_pair,
            quote_mint=stable_quote,
            quote_unit="configured_usd_stable",
            evidence=row_evidence,
            imported_at=imported_at,
        ):
            inserted += 1

    summary_reader = getattr(history_backend, "verified_price_import_summary", None)
    summary = summary_reader(mint_text) if callable(summary_reader) else None
    if not isinstance(summary, Mapping):
        summary = {}

    return {
        "chain": CHAIN,
        "status": "partial",
        "reason": "verified_provider_price_history_backfilled",
        "mint": mint_text,
        "symbol": symbol_text,
        "source": SOURCE,
        "method": method,
        "provider_pair": provider_pair,
        "configured_usd_stable_quote_mint": stable_quote,
        "candidate_verified_observation_count": len(derived),
        "imported_observation_count": inserted,
        "stored_verified_provider_observation_count": int(
            summary.get("observation_count") or 0
        ),
        "first_imported_observed_at": summary.get("first_observed_at"),
        "last_imported_observed_at": summary.get("last_observed_at"),
        "provider_history_imported": bool(
            inserted > 0 or summary.get("available") is True
        ),
        "full_asset_lifetime_verified": False,
        "continuous_coverage_verified": False,
        "provider_range_complete_verified": False,
        "source_independence_verified": False,
        "historical_stable_quote_peg_verified": False,
        "limitations": [
            "imports_verified_price_only",
            "volume_and_liquidity_history_not_imported",
            "only_cross_provider_close_matched_bars_are_persisted",
            "provider_source_independence_not_verified",
            "provider_archive_completeness_not_verified",
            "configured_usd_stable_quote_does_not_prove_historical_one_dollar_peg",
            "no_claim_of_complete_asset_lifetime_history",
        ],
    }


__all__ = [
    "CHAIN",
    "SOURCE",
    "USDC_X_MINT",
    "WRAPPED_XNT_MINT",
    "backfill_verified_xdex_usd_price_history",
]
