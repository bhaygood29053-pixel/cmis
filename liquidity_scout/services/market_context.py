"""Deterministic market classifications and verified AI context construction.

This module keeps qualitative labels deterministic and builds the exact market
facts that may be supplied to an explanation model. It consumes the structured
``market_report`` service output so missing or incomplete XDEX values remain
explicit instead of being silently converted to verified zeroes.
"""

from typing import Any, Callable, Dict, Iterable, Optional


UsdFormatter = Callable[[Any], str]
AgeFormatter = Callable[[Any], str]


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def liquidity_depth_label(liquidity: Any) -> Optional[str]:
    """Return the deterministic Liquidity Scout liquidity classification."""
    value = _number(liquidity)
    if value is None:
        return None
    if value < 5_000:
        return "very thin"
    if value < 25_000:
        return "fairly thin"
    if value >= 100_000:
        return "comparatively deep"
    return "not qualitatively classified"


def volume_activity_label(volume_24h: Any) -> Optional[str]:
    """Return the deterministic Liquidity Scout 24h-volume classification."""
    value = _number(volume_24h)
    if value is None:
        return None
    if value < 1_000:
        return "light"
    if value >= 25_000:
        return "strong"
    return "not qualitatively classified"


def price_movement_label(change_24h: Any) -> Optional[str]:
    """Return the deterministic Liquidity Scout 24h price-movement label."""
    value = _number(change_24h)
    if value is None:
        return None
    if value <= -10:
        return "down sharply"
    if value <= -3:
        return "under noticeable selling pressure"
    if value >= 10:
        return "up sharply"
    if value >= 3:
        return "a solid upward move"
    return "relatively modest"


def _market_title(report: Dict[str, Any]) -> str:
    symbol = str(report.get("symbol") or "").strip() or "Unknown"
    name = str(report.get("name") or "").strip()
    if symbol.upper() == "XNT":
        return "XNT"
    if name and name.upper() != symbol.upper():
        return f"{symbol} ({name})"
    return symbol


def _safety_text(report: Dict[str, Any]) -> str:
    grade = str(report.get("safety_grade") or "").strip() or "N/A"
    score = _number(report.get("safety_score"))
    if score is not None and score > 0:
        grade += f" ({score:g}/100)"
    return grade


def _complete(report: Dict[str, Any], key: str) -> bool:
    completeness = report.get("completeness") or {}
    return bool(completeness.get(key))


def build_verified_market_context(
    report: Dict[str, Any],
    fields: Iterable[str],
    *,
    format_usd: UsdFormatter,
    format_age: Optional[AgeFormatter] = None,
) -> str:
    """Serialize only verified/qualified market facts approved for AI use.

    Asset-wide metrics are classified only when their XDEX pool coverage is
    complete. Partial sums are explicitly labelled as lower bounds and are not
    given qualitative classifications. Missing values remain unavailable rather
    than becoming zeroes.
    """
    lines = [f"Token: {_market_title(report)}"]

    for field in fields:
        if field == "price":
            value = _number(report.get("price_usd"))
            if value is None:
                lines.append("Price: Not available from verified data")
            else:
                lines.append(f"Price: {format_usd(value)}")

        elif field == "age":
            created_at = report.get("created_at")
            if created_at and format_age is not None:
                lines.append(f"Age: {format_age(created_at)}")
            else:
                lines.append("Age: N/A")

        elif field == "holders":
            holders = report.get("holders")
            if _complete(report, "holders") and holders is not None:
                lines.append(f"Holders: {int(holders):,}")
            elif report.get("holders_observed"):
                lines.append(
                    "Holders: Not verified — conflicting or incomplete "
                    "XDEX pool observations"
                )
            else:
                lines.append("Holders: Not available from verified data")

        elif field == "txns24":
            value = _number(report.get("transactions_24h"))
            if value is None:
                lines.append("Transactions 24h: Not available from verified data")
            elif _complete(report, "transactions_24h"):
                lines.append(f"Transactions 24h: {int(value):,}")
            else:
                lines.append(
                    f"Transactions 24h: at least {int(value):,} — "
                    "incomplete XDEX pool data"
                )

        elif field == "volume24":
            value = _number(report.get("volume_24h_usd"))
            if value is None:
                lines.append("Volume 24h: Not available from verified data")
            elif _complete(report, "volume_24h"):
                lines.append(f"Volume 24h: {format_usd(value)}")
                label = volume_activity_label(value)
                if label is not None:
                    lines.append(f"Volume classification: {label}")
            else:
                lines.append(
                    f"Volume 24h: at least {format_usd(value)} — "
                    "incomplete XDEX pool data"
                )

        elif field == "change1h":
            value = _number(report.get("price_change_1h_pct"))
            if value is None:
                lines.append("Change 1h: Not available from verified data")
            else:
                lines.append(f"Change 1h: {value:+.2f}%")

        elif field == "change24h":
            value = _number(report.get("price_change_24h_pct"))
            if value is None:
                lines.append("Change 24h: Not available from verified data")
            else:
                lines.append(f"Change 24h: {value:+.2f}%")
                label = price_movement_label(value)
                if label is not None:
                    lines.append(f"24h price-movement classification: {label}")

        elif field == "liquidity":
            value = _number(report.get("liquidity_usd"))
            if value is None:
                lines.append("Liquidity: Not available from verified data")
            elif _complete(report, "liquidity"):
                lines.append(f"Liquidity: {format_usd(value)}")
                label = liquidity_depth_label(value)
                if label is not None:
                    lines.append(f"Liquidity classification: {label}")
            else:
                lines.append(
                    f"Liquidity: at least {format_usd(value)} — "
                    "incomplete XDEX pool data"
                )

        elif field == "market_cap":
            lines.append(
                "Market Cap: Not verified — "
                "circulating supply unavailable from verified data"
            )

        elif field == "safety":
            lines.append(f"Tokenomics Safety: {_safety_text(report)}")

        elif field == "pool_address":
            primary_pool = report.get("primary_pool") or {}
            lines.append(
                f"Pool address: {primary_pool.get('address') or 'N/A'}"
            )

    return "\n".join(lines)
