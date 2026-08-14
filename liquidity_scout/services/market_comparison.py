"""Deterministic multi-asset market comparison presentation.

This service formats already-verified Liquidity Scout snapshots. When a snapshot
contains the structured ``_market_report`` metadata produced by the market-report
service, missing and incomplete XDEX facts remain explicit instead of being
silently interpreted as compatibility zeroes.
"""

from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .market_context import (
    liquidity_depth_label,
    price_movement_label,
    volume_activity_label,
)


UsdFormatter = Callable[[Any], str]
FieldFormatter = Callable[[str, Dict[str, Any]], str]


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _report(snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    report = snapshot.get("_market_report")
    return report if isinstance(report, dict) else None


def _complete(report: Dict[str, Any], key: str) -> bool:
    return bool((report.get("completeness") or {}).get(key))


def _metric(
    snapshot: Dict[str, Any],
    *,
    report_key: str,
    snapshot_key: str,
    completeness_key: Optional[str] = None,
) -> Tuple[Optional[float], bool]:
    report = _report(snapshot)
    if report is None:
        return _number(snapshot.get(snapshot_key)), True

    value = _number(report.get(report_key))
    if completeness_key is None:
        return value, value is not None
    return value, _complete(report, completeness_key)


def _price_text(snapshot: Dict[str, Any], format_usd: UsdFormatter) -> str:
    report = _report(snapshot)
    if report is None:
        return str(snapshot.get("price") or "Not available from verified data")
    value = _number(report.get("price_usd"))
    if value is None:
        return "Not available from verified data"
    return format_usd(value)


def _classified_metric_text(
    value: Optional[float],
    complete: bool,
    *,
    format_usd: UsdFormatter,
    classifier: Callable[[Any], Optional[str]],
) -> str:
    if value is None:
        return "Not available from verified data"
    if not complete:
        return f"at least {format_usd(value)} — incomplete XDEX pool data"

    text = format_usd(value)
    label = classifier(value)
    if label and label != "not qualitatively classified":
        text += f" ({label})"
    return text


def _change_text(snapshot: Dict[str, Any]) -> str:
    value, _ = _metric(
        snapshot,
        report_key="price_change_24h_pct",
        snapshot_key="change24",
    )
    if value is None:
        return "Not available from verified data"
    label = price_movement_label(value)
    if label:
        return f"{value:+.2f}% ({label})"
    return f"{value:+.2f}%"


def _all_complete(values: Sequence[Tuple[Optional[float], bool]]) -> bool:
    return bool(values) and all(value is not None and complete for value, complete in values)


def format_market_comparison(
    question: str,
    snapshots: Sequence[Dict[str, Any]],
    *,
    fields: Iterable[str] = (),
    format_usd: UsdFormatter,
    format_field_line: FieldFormatter,
    include_token_addresses: bool = False,
) -> str:
    """Format a deterministic multi-asset comparison.

    Structured snapshots suppress comparisons that would otherwise rank or
    ratio incomplete/missing facts. Legacy snapshots without ``_market_report``
    retain the historical v0.12 presentation contract.
    """
    fields = list(fields)
    snaps: List[Dict[str, Any]] = list(snapshots)
    lines = ["Liquidity Scout XDEX comparison:"]

    if fields:
        for index, snap in enumerate(snaps):
            if index:
                lines.append("")
            lines.append(str(snap.get("title") or snap.get("symbol") or "Unknown"))
            lines.extend(format_field_line(field, snap) for field in fields)
    else:
        liquidity_values: List[Tuple[Optional[float], bool]] = []
        volume_values: List[Tuple[Optional[float], bool]] = []
        change_values: List[Tuple[Optional[float], bool]] = []

        for index, snap in enumerate(snaps):
            if index:
                lines.append("")

            liquidity = _metric(
                snap,
                report_key="liquidity_usd",
                snapshot_key="liquidity",
                completeness_key="liquidity",
            )
            volume = _metric(
                snap,
                report_key="volume_24h_usd",
                snapshot_key="vol24",
                completeness_key="volume_24h",
            )
            change = _metric(
                snap,
                report_key="price_change_24h_pct",
                snapshot_key="change24",
            )
            liquidity_values.append(liquidity)
            volume_values.append(volume)
            change_values.append(change)

            lines.extend([
                str(snap.get("title") or snap.get("symbol") or "Unknown"),
                f"• Price: {_price_text(snap, format_usd)}",
                "• Liquidity: "
                + _classified_metric_text(
                    liquidity[0],
                    liquidity[1],
                    format_usd=format_usd,
                    classifier=liquidity_depth_label,
                ),
                "• Volume 24h: "
                + _classified_metric_text(
                    volume[0],
                    volume[1],
                    format_usd=format_usd,
                    classifier=volume_activity_label,
                ),
                f"• Change 24h: {_change_text(snap)}",
                "• Market Cap: Not verified — "
                "circulating supply unavailable from verified data",
                f"• Tokenomics Safety: {snap.get('safety') or 'N/A'}",
            ])

        if len(snaps) >= 2:
            lines.extend(["", "Analyst comparison:"])

            if len(snaps) == 2 and _all_complete(liquidity_values):
                a, b = snaps
                av, _ = liquidity_values[0]
                bv, _ = liquidity_values[1]
                assert av is not None and bv is not None
                winner, other = (a, b) if av >= bv else (b, a)
                winner_value, other_value = (av, bv) if av >= bv else (bv, av)

                if other_value > 0:
                    lines.append(
                        f"• Liquidity: {winner['symbol']} has "
                        f"{winner_value / other_value:.1f}× more available liquidity "
                        f"({format_usd(winner_value)} vs {format_usd(other_value)})."
                    )
                else:
                    lines.append(
                        f"• Liquidity: {winner['symbol']} has deeper available liquidity "
                        f"({format_usd(winner_value)} vs {format_usd(other_value)})."
                    )

            elif len(snaps) > 2 and _all_complete(liquidity_values):
                index = max(range(len(snaps)), key=lambda i: liquidity_values[i][0] or 0)
                value = liquidity_values[index][0]
                assert value is not None
                lines.append(
                    f"• Deepest liquidity: {snaps[index]['symbol']} ({format_usd(value)})"
                )

            if len(snaps) == 2 and _all_complete(volume_values):
                a, b = snaps
                av, _ = volume_values[0]
                bv, _ = volume_values[1]
                assert av is not None and bv is not None
                winner, other = (a, b) if av >= bv else (b, a)
                winner_value, other_value = (av, bv) if av >= bv else (bv, av)

                if other_value > 0:
                    lines.append(
                        f"• Trading activity: {winner['symbol']} has "
                        f"{winner_value / other_value:.1f}× more 24h volume "
                        f"({format_usd(winner_value)} vs {format_usd(other_value)})."
                    )
                else:
                    lines.append(
                        f"• Trading activity: {winner['symbol']} has higher 24h volume "
                        f"({format_usd(winner_value)} vs {format_usd(other_value)})."
                    )

            elif len(snaps) > 2 and _all_complete(volume_values):
                index = max(range(len(snaps)), key=lambda i: volume_values[i][0] or 0)
                value = volume_values[index][0]
                assert value is not None
                lines.append(
                    f"• Highest 24h volume: {snaps[index]['symbol']} ({format_usd(value)})"
                )

            if _all_complete(change_values):
                largest = max(range(len(snaps)), key=lambda i: abs(change_values[i][0] or 0))
                best = max(range(len(snaps)), key=lambda i: change_values[i][0] or 0)
                largest_value = change_values[largest][0]
                best_value = change_values[best][0]
                assert largest_value is not None and best_value is not None
                lines.extend([
                    f"• Largest absolute 24h price move: {snaps[largest]['symbol']} "
                    f"({largest_value:+.2f}%).",
                    f"• Best 24h return: {snaps[best]['symbol']} ({best_value:+.2f}%).",
                ])

            lines.append(
                "• Tokenomics: "
                + " • ".join(
                    f"{snap.get('symbol') or 'Unknown'} {snap.get('safety') or 'N/A'}"
                    for snap in snaps
                )
            )

            if len(snaps) == 2 and _all_complete(liquidity_values):
                av, _ = liquidity_values[0]
                bv, _ = liquidity_values[1]
                assert av is not None and bv is not None
                if av != bv:
                    deeper, thinner = (snaps[0], snaps[1]) if av > bv else (snaps[1], snaps[0])
                    lines.append(
                        f"• Execution: For similarly sized AMM trades, "
                        f"{deeper['symbol']}'s deeper available liquidity should generally "
                        f"reduce slippage and price-impact pressure relative to {thinner['symbol']}."
                    )

    if include_token_addresses:
        lines.extend(["", "Token Addresses:"])
        for snap in snaps:
            lines.append(
                f"• {snap.get('symbol') or 'Unknown'}: "
                f"{snap.get('token_address') or 'N/A'}"
            )

    return "\n".join(lines)
