"""Deterministic historical market comparison over verified current facts.

The service keeps historical storage behind an injected backend and refuses to
persist structured XDEX metrics as exact values when the current market report
marks them missing or incomplete. This prevents legacy presentation zeroes from
becoming false historical observations.
"""

from typing import Any, Callable, Dict, Optional, Tuple


SupplyLookup = Callable[[str], Optional[str]]


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _structured_report(snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    report = snapshot.get("_market_report") if isinstance(snapshot, dict) else None
    return report if isinstance(report, dict) else None


def _verified_market_values(snapshot: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Return current values safe to store as exact historical observations."""
    report = _structured_report(snapshot)
    if report is None:
        # Direct legacy callers may still provide the old snapshot shape.
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


def format_historical_comparison(
    question: str,
    snapshot: Dict[str, Any],
    *,
    history_backend: Any,
    get_total_supply: Optional[SupplyLookup] = None,
) -> Optional[str]:
    """Format one deterministic historical comparison.

    ``history_backend`` supplies the existing SQLite/history functions. Keeping
    it injected makes storage independent from the live listener and keeps this
    service testable without touching the production database.
    """
    request = history_backend.parse_historical_comparison(question)
    if not request:
        return None

    metric = request["metric"]
    period = request["period"]
    period_seconds = request["period_seconds"]
    mint, symbol = _identity(snapshot)
    symbol = symbol or "Unknown"

    if not period_seconds:
        return (
            f"Liquidity Scout reply: {symbol} • "
            "Please specify a comparison period such as 24h, 7d, or 30d."
        )

    if metric == "burns":
        return (
            f"Liquidity Scout reply: {symbol} • "
            "Historical burn percentage comparisons are not yet enabled in "
            "the live listener. Verified burn history is maintained separately "
            "by the X1 burn scanner."
        )

    market_values = _verified_market_values(snapshot)

    if metric == "supply":
        amount = get_total_supply(mint) if get_total_supply and mint else None
        current_value = _number(amount)
    else:
        current_value = market_values.get(metric)

    if current_value is None:
        return (
            f"Liquidity Scout reply: {symbol} • "
            f"Current {metric} data is not available from a verified source."
        )

    # Persist only exact verified current facts. Structured missing/incomplete
    # values remain NULL rather than leaking compatibility zeroes into history.
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

    if not old:
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

    old_value = old["value"]
    change = history_backend.percent_change(old_value, current_value)

    if change is None:
        return (
            f"Liquidity Scout reply: {symbol} • "
            f"Historical {metric} percentage change cannot be calculated "
            "because the earlier value was zero."
        )

    current_text = history_backend.format_number(metric, current_value)
    old_text = history_backend.format_number(metric, old_value)
    answer = (
        f"Liquidity Scout reply: {symbol} • "
        f"Current {metric}: {current_text} "
        f"• {period} ago: {old_text} "
        f"• Change: {change:+.2f}%"
    )

    threshold = request.get("threshold")
    direction = request.get("direction")
    if threshold is not None:
        result = history_backend.threshold_result(change, direction, threshold)
        if result is not None:
            direction_text = (
                "decline"
                if direction == "down"
                else "increase"
                if direction == "up"
                else "change"
            )
            answer += (
                f" • {direction_text.title()} of at least {threshold:g}%: "
                f"{'YES' if result else 'NO'}"
            )

    return answer


__all__ = ["format_historical_comparison"]
