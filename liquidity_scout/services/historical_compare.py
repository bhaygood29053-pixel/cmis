"""Deterministic historical comparison over verified current facts.

The service keeps historical storage behind an injected backend and refuses to
persist structured XDEX metrics as exact values when the current market report
marks them missing or incomplete. It exposes a structured comparison for CMIS
consumers while preserving the existing human-readable formatter.
"""

from typing import Any, Callable, Dict, Optional, Tuple


SupplyLookup = Callable[[str], Optional[str]]

DEFAULT_PROFILE_METRICS = (
    "price",
    "liquidity",
    "volume",
    "transactions",
    "holders",
)
SUPPORTED_PROFILE_METRICS = frozenset((*DEFAULT_PROFILE_METRICS, "supply"))


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _structured_report(snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    report = snapshot.get("_market_report") if isinstance(snapshot, dict) else None
    return report if isinstance(report, dict) else None


def _verified_market_values(snapshot: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Return current values safe to store as exact historical observations."""
    report = _structured_report(snapshot)
    if report is None:
        # Direct legacy callers remain supported for presentation compatibility.
        return {
            "price": _number(snapshot.get("price_usd_value")),
            "liquidity": _number(snapshot.get("liquidity")),
            "volume": _number(snapshot.get("vol24")),
            "transactions": _number(snapshot.get("transactions_24h")),
            "holders": _number(snapshot.get("holders")),
        }

    completeness = report.get("completeness") or {}

    def exact(report_key: str, completeness_key: str) -> Optional[float]:
        if not completeness.get(completeness_key):
            return None
        return _number(report.get(report_key))

    return {
        "price": exact("price_usd", "price"),
        "liquidity": exact("liquidity_usd", "liquidity"),
        "volume": exact("volume_24h_usd", "volume_24h"),
        "transactions": exact("transactions_24h", "transactions_24h"),
        "holders": exact("holders", "holders"),
    }


def _identity(snapshot: Dict[str, Any]) -> Tuple[str, str]:
    report = _structured_report(snapshot)
    if report is not None:
        return (
            str(report.get("mint") or snapshot.get("token_address") or "").strip(),
            str(report.get("symbol") or snapshot.get("symbol") or "").strip(),
        )
    return (
        str(snapshot.get("token_address") or "").strip(),
        str(snapshot.get("symbol") or "").strip(),
    )


def _current_observed_at(snapshot: Dict[str, Any]):
    report = _structured_report(snapshot)
    if report is None:
        return None
    provenance = report.get("provenance")
    if not isinstance(provenance, dict):
        return None
    return provenance.get("catalog_last_refresh_unix")


def _current_metric_verified(snapshot: Dict[str, Any], metric: str) -> bool:
    """Return explicit verification state for structured current facts.

    Legacy snapshot values remain usable by the compatibility formatter, but
    they are not silently upgraded to verified facts for downstream risk use.
    """
    report = _structured_report(snapshot)
    if report is None:
        return False

    completeness = report.get("completeness")
    if not isinstance(completeness, dict):
        return False

    completeness_key = {
        "price": "price",
        "liquidity": "liquidity",
        "volume": "volume_24h",
        "transactions": "transactions_24h",
        "holders": "holders",
    }.get(metric)
    return bool(completeness_key and completeness.get(completeness_key) is True)



def _normalize_profile_metrics(metrics: Any) -> tuple[str, ...]:
    if metrics is None:
        return DEFAULT_PROFILE_METRICS
    if isinstance(metrics, (str, bytes)):
        raw = [metrics]
    else:
        try:
            raw = list(metrics)
        except TypeError as exc:
            raise ValueError("profile metrics must be an iterable of metric names") from exc

    result: list[str] = []
    for value in raw:
        name = str(value or "").strip().lower()
        if not name:
            continue
        if name not in SUPPORTED_PROFILE_METRICS:
            raise ValueError(
                "unsupported historical profile metric: "
                f"{name}; supported={sorted(SUPPORTED_PROFILE_METRICS)!r}"
            )
        if name not in result:
            result.append(name)
    return tuple(result) or DEFAULT_PROFILE_METRICS


def _current_profile_values(
    snapshot: Dict[str, Any],
    *,
    get_total_supply: Optional[SupplyLookup] = None,
) -> tuple[str, str, Dict[str, Optional[float]], Dict[str, bool], Any]:
    mint, symbol = _identity(snapshot)
    symbol = symbol or "Unknown"
    values = _verified_market_values(snapshot)
    verified = {
        metric: (
            values.get(metric) is not None
            and _current_metric_verified(snapshot, metric)
        )
        for metric in ("price", "liquidity", "volume", "transactions", "holders")
    }

    supply_value = None
    if get_total_supply is not None and mint:
        supply_value = _number(get_total_supply(mint))
    values["supply"] = supply_value
    verified["supply"] = supply_value is not None and get_total_supply is not None
    return mint, symbol, values, verified, _current_observed_at(snapshot)


def _record_profile_snapshot(
    snapshot: Dict[str, Any],
    *,
    history_backend: Any,
    get_total_supply: Optional[SupplyLookup] = None,
) -> None:
    mint, symbol, values, verified, observed_at = _current_profile_values(
        snapshot,
        get_total_supply=get_total_supply,
    )
    if not mint:
        return

    report = _structured_report(snapshot) or {}
    kwargs = {
        "mint": mint,
        "symbol": symbol,
        "price": values.get("price") if verified.get("price") else None,
        "liquidity": values.get("liquidity") if verified.get("liquidity") else None,
        "volume24": values.get("volume") if verified.get("volume") else None,
        "transactions24": (
            values.get("transactions") if verified.get("transactions") else None
        ),
        "holders": values.get("holders") if verified.get("holders") else None,
        "total_supply": values.get("supply") if verified.get("supply") else None,
        "pool_count": report.get("lp_count"),
        "timestamp": observed_at,
    }

    writer = getattr(history_backend, "record_snapshot_if_due", None)
    if callable(writer):
        writer(**kwargs)
        return

    writer = getattr(history_backend, "record_snapshot", None)
    if callable(writer):
        # Legacy injected backends may not support the newer optional fields.
        legacy_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key not in {"transactions24", "timestamp"}
        }
        try:
            writer(**kwargs)
        except TypeError:
            writer(**legacy_kwargs)


def _normalized_series(
    history_backend: Any,
    mint: str,
    metric: str,
    *,
    current_value: Optional[float],
    current_verified: bool,
    current_observed_at: Any,
) -> list[Dict[str, float]]:
    reader = getattr(history_backend, "historical_series", None)
    if not callable(reader):
        return []

    raw = reader(mint, metric)
    result: list[Dict[str, float]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        timestamp = _number(item.get("timestamp"))
        value = _number(item.get("value"))
        if timestamp is None or value is None:
            continue
        result.append({"timestamp": int(timestamp), "value": float(value)})

    if (
        current_verified
        and current_value is not None
        and _number(current_observed_at) is not None
    ):
        current_point = {
            "timestamp": int(float(current_observed_at)),
            "value": float(current_value),
        }
        if not result or result[-1] != current_point:
            result.append(current_point)

    result.sort(key=lambda item: item["timestamp"])
    deduped: list[Dict[str, float]] = []
    for item in result:
        if deduped and item["timestamp"] == deduped[-1]["timestamp"]:
            deduped[-1] = item
        else:
            deduped.append(item)
    return deduped


def _sampled_max_drawdown_pct(series: list[Dict[str, float]]) -> Optional[float]:
    if len(series) < 2:
        return None
    peak = series[0]["value"]
    worst = 0.0
    for item in series[1:]:
        value = item["value"]
        if value > peak:
            peak = value
            continue
        if peak == 0:
            continue
        drawdown = ((value - peak) / peak) * 100.0
        if drawdown < worst:
            worst = drawdown
    return float(worst)


def _metric_profile(
    history_backend: Any,
    mint: str,
    metric: str,
    *,
    current_value: Optional[float],
    current_verified: bool,
    current_observed_at: Any,
    gap_threshold_seconds: int,
) -> Dict[str, Any]:
    series = _normalized_series(
        history_backend,
        mint,
        metric,
        current_value=current_value,
        current_verified=current_verified,
        current_observed_at=current_observed_at,
    )
    if not series:
        return {
            "status": "unavailable",
            "reason": "verified_history_unavailable",
            "observation_count": 0,
            "current_value": current_value,
            "current_verified": bool(current_verified),
            "first_observed_at": None,
            "last_observed_at": None,
            "coverage_seconds": None,
            "total_change_pct": None,
            "minimum_value": None,
            "maximum_value": None,
            "sampled_max_drawdown_pct": None,
            "observed_gap_count": None,
            "largest_observed_gap_seconds": None,
            "continuous_coverage_verified": False,
        }

    first = series[0]
    last = series[-1]
    gaps = [
        right["timestamp"] - left["timestamp"]
        for left, right in zip(series, series[1:])
        if right["timestamp"] >= left["timestamp"]
    ]
    flagged_gaps = [
        gap for gap in gaps if gap > max(0, int(gap_threshold_seconds))
    ]
    change = None
    if len(series) >= 2:
        calculator = getattr(history_backend, "percent_change", None)
        if callable(calculator):
            change = calculator(first["value"], last["value"])
        elif first["value"] != 0:
            change = ((last["value"] - first["value"]) / first["value"]) * 100.0

    minimum = min(series, key=lambda item: item["value"])
    maximum = max(series, key=lambda item: item["value"])

    return {
        "status": "ok" if len(series) >= 2 else "partial",
        "reason": None if len(series) >= 2 else "single_verified_observation_only",
        "observation_count": len(series),
        "current_value": current_value,
        "current_verified": bool(current_verified),
        "first_value": first["value"],
        "first_observed_at": first["timestamp"],
        "last_value": last["value"],
        "last_observed_at": last["timestamp"],
        "coverage_seconds": max(0, last["timestamp"] - first["timestamp"]),
        "total_change_pct": None if change is None else float(change),
        "minimum_value": minimum["value"],
        "minimum_observed_at": minimum["timestamp"],
        "maximum_value": maximum["value"],
        "maximum_observed_at": maximum["timestamp"],
        "sampled_max_drawdown_pct": (
            _sampled_max_drawdown_pct(series) if metric == "price" else None
        ),
        "observed_gap_count": len(flagged_gaps),
        "largest_observed_gap_seconds": max(gaps) if gaps else 0,
        "gap_threshold_seconds": max(0, int(gap_threshold_seconds)),
        "continuous_coverage_verified": False,
    }


def build_all_available_history_profile(
    snapshot: Dict[str, Any],
    *,
    history_backend: Any,
    get_total_supply: Optional[SupplyLookup] = None,
    metrics: Any = None,
    gap_threshold_seconds: int = 129600,
) -> Dict[str, Any]:
    """Summarize every verified local historical observation available to CMIS.

    "All available" is intentionally not relabeled as the asset's full lifetime.
    The profile reports the exact stored observation bounds and keeps continuous
    coverage/lifetime completeness false until separately proven.
    """

    if not isinstance(snapshot, dict):
        raise TypeError("snapshot must be a mapping")

    selected = _normalize_profile_metrics(metrics)
    mint, symbol, values, verified, current_observed_at = _current_profile_values(
        snapshot,
        get_total_supply=get_total_supply,
    )

    _record_profile_snapshot(
        snapshot,
        history_backend=history_backend,
        get_total_supply=get_total_supply,
    )

    profiles = {
        metric: _metric_profile(
            history_backend,
            mint,
            metric,
            current_value=values.get(metric),
            current_verified=verified.get(metric, False),
            current_observed_at=current_observed_at,
            gap_threshold_seconds=gap_threshold_seconds,
        )
        for metric in selected
    }
    available = [
        item for item in profiles.values()
        if item.get("observation_count", 0) > 0
    ]
    multi_point = [
        item for item in profiles.values()
        if item.get("observation_count", 0) >= 2
    ]

    starts = [
        item.get("first_observed_at")
        for item in available
        if item.get("first_observed_at") is not None
    ]
    ends = [
        item.get("last_observed_at")
        for item in available
        if item.get("last_observed_at") is not None
    ]

    status = "unavailable"
    reason = "verified_history_unavailable"
    if available:
        status = "partial"
        reason = "asset_lifetime_coverage_unverified"
        if multi_point:
            reason = "all_available_verified_observations_summarized"

    return {
        "status": status,
        "mode": "all_available",
        "asset": {"symbol": symbol or None, "mint": mint or None},
        "current_observed_at": current_observed_at,
        "source": "historical_db",
        "coverage_scope": "cmis_stored_verified_observations",
        "first_verified_observed_at": min(starts) if starts else None,
        "last_verified_observed_at": max(ends) if ends else None,
        "coverage_seconds": (
            max(ends) - min(starts) if starts and ends else None
        ),
        "available_metric_count": len(available),
        "multi_point_metric_count": len(multi_point),
        "requested_metrics": list(selected),
        "metrics": profiles,
        "asset_lifetime_start_verified": False,
        "full_asset_lifetime_verified": False,
        "continuous_coverage_verified": False,
        "provider_history_imported": False,
        "reason": reason,
        "limitations": [
            "all_available_means_all_verified_observations_currently_stored_by_cmis",
            "asset_creation_or_first_trade_time_not_verified",
            "continuous_historical_coverage_not_verified",
            "external_ohlcv_or_archive_history_not_promoted_into_this_profile",
            "sampled_max_drawdown_uses_stored_price_observations_only",
        ],
    }


def _common_window_metric(
    history_backend: Any,
    metric: str,
    primary_mint: str,
    secondary_mint: str,
    primary_metric: Dict[str, Any],
    secondary_metric: Dict[str, Any],
    *,
    anchor_tolerance_seconds: int,
) -> Dict[str, Any]:
    starts = [
        primary_metric.get("first_observed_at"),
        secondary_metric.get("first_observed_at"),
    ]
    ends = [
        primary_metric.get("last_observed_at"),
        secondary_metric.get("last_observed_at"),
    ]
    if any(value is None for value in starts + ends):
        return {
            "status": "unavailable",
            "reason": "common_verified_window_unavailable",
        }

    start = max(int(value) for value in starts)
    end = min(int(value) for value in ends)
    if end <= start:
        return {
            "status": "unavailable",
            "reason": "verified_history_does_not_overlap",
            "start_observed_at": start,
            "end_observed_at": end,
        }

    reader = getattr(history_backend, "historical_value_at", None)
    if not callable(reader):
        return {
            "status": "unavailable",
            "reason": "aligned_history_lookup_unavailable",
            "start_observed_at": start,
            "end_observed_at": end,
        }

    anchors = {
        "primary_start": reader(
            primary_mint,
            metric,
            start,
            tolerance_seconds=anchor_tolerance_seconds,
        ),
        "secondary_start": reader(
            secondary_mint,
            metric,
            start,
            tolerance_seconds=anchor_tolerance_seconds,
        ),
        "primary_end": reader(
            primary_mint,
            metric,
            end,
            tolerance_seconds=anchor_tolerance_seconds,
        ),
        "secondary_end": reader(
            secondary_mint,
            metric,
            end,
            tolerance_seconds=anchor_tolerance_seconds,
        ),
    }
    if not all(isinstance(value, dict) for value in anchors.values()):
        return {
            "status": "unavailable",
            "reason": "aligned_common_window_anchors_unavailable",
            "start_observed_at": start,
            "end_observed_at": end,
            "anchor_tolerance_seconds": int(anchor_tolerance_seconds),
        }

    calculator = getattr(history_backend, "percent_change", None)
    if not callable(calculator):
        calculator = lambda old, new: None if old == 0 else ((new - old) / old) * 100.0

    primary_change = calculator(
        anchors["primary_start"]["value"],
        anchors["primary_end"]["value"],
    )
    secondary_change = calculator(
        anchors["secondary_start"]["value"],
        anchors["secondary_end"]["value"],
    )

    if primary_change is None or secondary_change is None:
        return {
            "status": "partial",
            "reason": "common_window_change_unavailable",
            "start_observed_at": start,
            "end_observed_at": end,
            "anchors": anchors,
        }

    return {
        "status": "ok",
        "reason": None,
        "start_observed_at": start,
        "end_observed_at": end,
        "coverage_seconds": end - start,
        "anchor_tolerance_seconds": int(anchor_tolerance_seconds),
        "primary_change_pct": float(primary_change),
        "secondary_change_pct": float(secondary_change),
        "performance_difference_pct_points": float(
            primary_change - secondary_change
        ),
        "anchors": anchors,
    }


def build_all_available_pair_comparison(
    primary_snapshot: Dict[str, Any],
    secondary_snapshot: Dict[str, Any],
    *,
    history_backend: Any,
    get_total_supply: Optional[SupplyLookup] = None,
    metrics: Any = None,
    gap_threshold_seconds: int = 129600,
    anchor_tolerance_seconds: int = 21600,
) -> Dict[str, Any]:
    """Compare two assets over their overlapping verified CMIS history."""

    selected = _normalize_profile_metrics(metrics)
    primary = build_all_available_history_profile(
        primary_snapshot,
        history_backend=history_backend,
        get_total_supply=get_total_supply,
        metrics=selected,
        gap_threshold_seconds=gap_threshold_seconds,
    )
    secondary = build_all_available_history_profile(
        secondary_snapshot,
        history_backend=history_backend,
        get_total_supply=get_total_supply,
        metrics=selected,
        gap_threshold_seconds=gap_threshold_seconds,
    )

    primary_asset = primary["asset"]
    secondary_asset = secondary["asset"]
    common = {}
    for metric in selected:
        common[metric] = _common_window_metric(
            history_backend,
            metric,
            str(primary_asset.get("mint") or ""),
            str(secondary_asset.get("mint") or ""),
            primary["metrics"][metric],
            secondary["metrics"][metric],
            anchor_tolerance_seconds=anchor_tolerance_seconds,
        )

    comparable = [
        value for value in common.values()
        if value.get("status") == "ok"
    ]
    status = "partial" if comparable else "unavailable"
    reason = (
        "common_verified_history_compared"
        if comparable
        else "common_verified_history_unavailable"
    )

    return {
        "status": status,
        "mode": "all_available_pair",
        "asset": dict(primary_asset),
        "compare_asset": dict(secondary_asset),
        "primary_profile": primary,
        "secondary_profile": secondary,
        "common_window_metrics": common,
        "comparable_metric_count": len(comparable),
        "requested_metrics": list(selected),
        "coverage_scope": "overlapping_cmis_stored_verified_observations",
        "full_asset_lifetime_verified": False,
        "continuous_coverage_verified": False,
        "reason": reason,
        "limitations": [
            "assets_may_have_different_verified_history_start_times",
            "comparison_uses_only_overlapping_verified_cmis_observation_windows",
            "aligned_common_window_anchors_require_explicit_tolerance",
            "external_ohlcv_or_archive_history_not_promoted_into_this_comparison",
            "no_claim_of_complete_asset_lifetime_history",
        ],
        "source": "historical_db",
    }


def _base_result(
    *,
    metric: str,
    period: str,
    period_seconds: Any,
    mint: str,
    symbol: str,
    current_value: Optional[float],
    current_verified: bool,
    current_observed_at: Any,
) -> Dict[str, Any]:
    return {
        "status": "unavailable",
        "metric": metric,
        "period": period,
        "period_seconds": period_seconds,
        "asset": {"symbol": symbol or None, "mint": mint or None},
        "current_value": current_value,
        "historical_value": None,
        "current_verified": bool(current_verified),
        "historical_verified": False,
        "change_pct": None,
        "absolute_change": None,
        "current_observed_at": current_observed_at,
        "historical_observed_at": None,
        "source": "historical_db",
        "threshold": None,
        "direction": None,
        "threshold_met": None,
        "reason": None,
    }


def build_historical_comparison(
    question: str,
    snapshot: Dict[str, Any],
    *,
    history_backend: Any,
    get_total_supply: Optional[SupplyLookup] = None,
) -> Optional[Dict[str, Any]]:
    """Build one structured deterministic historical comparison.

    The returned object is suitable for downstream CMIS services such as
    ``risk_check``. Derived percentage change is recomputed from the stored and
    current values rather than trusted from presentation text. Structured XDEX
    facts are marked verified only when their completeness flag is true.
    """
    request = history_backend.parse_historical_comparison(question)
    if not request:
        return None

    metric = request["metric"]
    period = request["period"]
    period_seconds = request["period_seconds"]
    mint, symbol = _identity(snapshot)
    symbol = symbol or "Unknown"
    market_values = _verified_market_values(snapshot)

    if metric == "supply":
        amount = get_total_supply(mint) if get_total_supply and mint else None
        current_value = _number(amount)
        current_verified = current_value is not None and get_total_supply is not None
    else:
        current_value = market_values.get(metric)
        current_verified = (
            current_value is not None and _current_metric_verified(snapshot, metric)
        )

    result = _base_result(
        metric=metric,
        period=period,
        period_seconds=period_seconds,
        mint=mint,
        symbol=symbol,
        current_value=current_value,
        current_verified=current_verified,
        current_observed_at=_current_observed_at(snapshot),
    )
    result["threshold"] = request.get("threshold")
    result["direction"] = request.get("direction")

    if not period_seconds:
        result["reason"] = "comparison_period_required"
        return result

    if metric == "burns":
        result["reason"] = "historical_burn_comparison_not_enabled"
        return result

    if current_value is None:
        result["reason"] = "current_metric_unverified"
        return result

    # Preserve current compatibility behavior: legacy snapshots can still be
    # recorded/formatted, but downstream structured consumers can see that the
    # current value did not carry explicit structured verification metadata.
    history_backend.record_snapshot(
        mint=mint,
        symbol=symbol,
        price=market_values.get("price"),
        liquidity=market_values.get("liquidity"),
        volume24=market_values.get("volume"),
        transactions24=market_values.get("transactions"),
        holders=market_values.get("holders"),
        total_supply=current_value if metric == "supply" else None,
        pool_count=(
            (_structured_report(snapshot) or {}).get("lp_count")
            if _structured_report(snapshot) is not None
            else snapshot.get("pool_count")
        ),
    )

    old = history_backend.historical_value(mint, metric, period_seconds)
    if not isinstance(old, dict):
        result["reason"] = "historical_value_unavailable"
        return result

    old_value = _number(old.get("value"))
    result["historical_value"] = old_value
    result["historical_observed_at"] = old.get("timestamp")
    result["historical_verified"] = old_value is not None

    if old_value is None:
        result["reason"] = "historical_value_unverified"
        return result

    change = history_backend.percent_change(old_value, current_value)
    if change is None:
        result["status"] = "partial"
        result["reason"] = "historical_baseline_zero"
        return result

    result["change_pct"] = float(change)
    result["absolute_change"] = current_value - old_value
    result["status"] = "ok" if current_verified else "partial"
    result["reason"] = None if current_verified else "current_metric_legacy_unverified"

    threshold = request.get("threshold")
    direction = request.get("direction")
    if threshold is not None:
        threshold_met = history_backend.threshold_result(change, direction, threshold)
        if threshold_met is not None:
            result["threshold_met"] = bool(threshold_met)

    return result


def format_historical_comparison(
    question: str,
    snapshot: Dict[str, Any],
    *,
    history_backend: Any,
    get_total_supply: Optional[SupplyLookup] = None,
) -> Optional[str]:
    """Format the structured comparison using the legacy presentation style."""
    comparison = build_historical_comparison(
        question,
        snapshot,
        history_backend=history_backend,
        get_total_supply=get_total_supply,
    )
    if comparison is None:
        return None

    metric = comparison["metric"]
    period = comparison["period"]
    symbol = comparison["asset"]["symbol"] or "Unknown"
    mint = comparison["asset"]["mint"] or ""
    reason = comparison.get("reason")

    if reason == "comparison_period_required":
        return (
            f"Liquidity Scout reply: {symbol} • "
            "Please specify a comparison period such as 24h, 7d, or 30d."
        )

    if reason == "historical_burn_comparison_not_enabled":
        return (
            f"Liquidity Scout reply: {symbol} • "
            "Historical burn percentage comparisons are not yet enabled in "
            "the live listener. Verified burn history is maintained separately "
            "by the X1 burn scanner."
        )

    current_value = comparison.get("current_value")
    if reason == "current_metric_unverified" or current_value is None:
        return (
            f"Liquidity Scout reply: {symbol} • "
            f"Current {metric} data is not available from a verified source."
        )

    if reason == "historical_value_unavailable":
        current_text = history_backend.format_number(metric, current_value)
        return (
            history_backend.history_not_ready_message(
                symbol,
                metric,
                period,
                mint,
            )
            + f" Current {metric}: {current_text}."
        )

    if comparison.get("change_pct") is None:
        return (
            f"Liquidity Scout reply: {symbol} • "
            f"Historical {metric} percentage change cannot be calculated "
            "because the earlier value was zero."
        )

    old_value = comparison["historical_value"]
    change = comparison["change_pct"]
    current_text = history_backend.format_number(metric, current_value)
    old_text = history_backend.format_number(metric, old_value)
    answer = (
        f"Liquidity Scout reply: {symbol} • "
        f"Current {metric}: {current_text} "
        f"• {period} ago: {old_text} "
        f"• Change: {change:+.2f}%"
    )

    threshold = comparison.get("threshold")
    direction = comparison.get("direction")
    threshold_met = comparison.get("threshold_met")
    if threshold is not None and threshold_met is not None:
        direction_text = (
            "decline"
            if direction == "down"
            else "increase"
            if direction == "up"
            else "change"
        )
        answer += (
            f" • {direction_text.title()} of at least {threshold:g}%: "
            f"{'YES' if threshold_met else 'NO'}"
        )

    return answer


__all__ = [
    "DEFAULT_PROFILE_METRICS",
    "SUPPORTED_PROFILE_METRICS",
    "build_all_available_history_profile",
    "build_all_available_pair_comparison",
    "build_historical_comparison",
    "format_historical_comparison",
]
