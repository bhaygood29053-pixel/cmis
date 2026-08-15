"""Deterministic historical comparison over verified current facts.

The service keeps historical storage behind an injected backend and refuses to
persist structured XDEX metrics as exact values when the current market report
marks them missing or incomplete. It exposes a structured comparison for CMIS
consumers while preserving the existing human-readable formatter.
"""

from typing import Any, Callable, Dict, Optional, Tuple


SupplyLookup = Callable[[str], Optional[str]]


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
        "holders": "holders",
    }.get(metric)
    return bool(completeness_key and completeness.get(completeness_key) is True)


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


__all__ = ["build_historical_comparison", "format_historical_comparison"]
