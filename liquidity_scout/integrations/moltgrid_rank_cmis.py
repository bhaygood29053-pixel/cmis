"""CMIS-backed ranking presentation for MoltGrid.

This module translates MoltGrid ranking questions into the public ``rank``
service contract. Ranking facts remain owned by CMIS; this layer only selects
request parameters and renders the returned envelope for a human Signal reply.
"""

import re
from collections.abc import Mapping


_ASSET_RANK_LIMIT = 100000


def _text(value):
    text = str(value or "").strip()
    return text or None


def _messages(envelope, field):
    records = envelope.get(field) if isinstance(envelope, Mapping) else None
    if not isinstance(records, list):
        return []

    output = []
    for record in records:
        if isinstance(record, Mapping):
            code = _text(record.get("code"))
            message = _text(record.get("message"))
            if code and message:
                output.append(f"{code}: {message}")
            elif code or message:
                output.append(code or message)
        else:
            text = _text(record)
            if text:
                output.append(text)
    return output


def _append_metadata(lines, envelope):
    confidence = envelope.get("confidence") if isinstance(envelope, Mapping) else None
    if isinstance(confidence, Mapping):
        verified = confidence.get("verified_checks")
        total = confidence.get("total_checks")
        if isinstance(verified, int) and isinstance(total, int):
            lines.append(f"Confidence checks: {verified}/{total} verified")
        elif isinstance(confidence.get("complete"), bool):
            lines.append(
                "Confidence: complete"
                if confidence.get("complete")
                else "Confidence: incomplete"
            )

    observed_at = envelope.get("observed_at") if isinstance(envelope, Mapping) else None
    if observed_at is not None:
        lines.append(f"Observed at: {observed_at}")

    sources = envelope.get("sources") if isinstance(envelope, Mapping) else None
    if isinstance(sources, list):
        for record in sources:
            if not isinstance(record, Mapping):
                continue
            source = _text(record.get("source"))
            role = _text(record.get("role"))
            source_observed = record.get("observed_at")
            if not source:
                continue
            line = f"Source: {source}"
            if role:
                line += f" ({role})"
            if source_observed is not None:
                line += f" @ {source_observed}"
            lines.append(line)

    warnings = _messages(envelope, "warnings")
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"• {message}" for message in warnings)

    errors = _messages(envelope, "errors")
    if errors:
        lines.append("Errors:")
        lines.extend(f"• {message}" for message in errors)


def _metric_label(metric, trending_basis=None):
    labels = {
        "volume": "24H VOLUME",
        "liquidity": "LIQUIDITY",
        "holders": "HOLDERS",
        "safety": "TOKENOMICS SAFETY",
        "gainers": "24H GAINERS",
        "losers": "24H LOSERS",
    }
    if metric == "trending":
        return (
            "1H TRENDING — TRANSACTIONS"
            if trending_basis == "1h transactions"
            else "1H TRENDING — VOLUME"
        )
    return labels.get(metric, str(metric or "RANK").upper())


def _format_metric_value(listener_module, metric, value, trending_basis=None):
    if value is None:
        return "unavailable"
    if metric in {"volume", "liquidity"}:
        return listener_module.format_usd(value)
    if metric == "holders":
        return f"{int(value):,}"
    if metric == "safety":
        return f"{float(value):.0f}/100"
    if metric in {"gainers", "losers"}:
        return f"{float(value):+.2f}%"
    if metric == "trending":
        if trending_basis == "1h transactions":
            return f"{int(value):,} txns"
        return listener_module.format_usd(value)
    return str(value)


def _format_liquidity(listener_module, row):
    value = row.get("liquidity_usd")
    if value is None:
        return "unavailable"
    formatted = listener_module.format_usd(value)
    return formatted if row.get("liquidity_complete") is True else f">={formatted}"


def _ranking_row_text(listener_module, row, metric, trending_basis=None):
    rank = row.get("rank")
    symbol = _text(row.get("symbol")) or "?"
    value = _format_metric_value(
        listener_module,
        metric,
        row.get("value"),
        trending_basis,
    )
    lp_count = row.get("#LPs")
    if lp_count is None:
        lp_count = row.get("lp_count")

    if metric == "liquidity":
        return f"#{rank} {symbol} • {value} • #LPs {lp_count}"

    liquidity = _format_liquidity(listener_module, row)
    return (
        f"#{rank} {symbol} • {value} • Liquidity {liquidity} • #LPs {lp_count}"
    )


def _dispatch_rank(listener_module, question, *, gateway, limit):
    metric = listener_module.xdex_ranking_metric(question)
    return metric, gateway.dispatch({
        "service": "rank",
        "chain": "x1",
        "asset": "",
        "params": {
            "metric": metric,
            "limit": limit,
        },
    })


def format_cmis_global_rank_answer(listener_module, question, *, gateway):
    """Render a global leaderboard from the CMIS ``rank`` envelope."""
    limit = listener_module.xdex_ranking_limit(question)
    metric, envelope = _dispatch_rank(
        listener_module,
        question,
        gateway=gateway,
        limit=limit,
    )

    data = envelope.get("data") if isinstance(envelope, Mapping) else None
    data = data if isinstance(data, Mapping) else {}
    rows = data.get("rankings")
    rows = rows if isinstance(rows, list) else []
    trending_basis = data.get("trending_basis")

    lines = [
        "Liquidity Scout reply:",
        f"CMIS rank — {_metric_label(metric, trending_basis)}",
        f"Service status: {str(envelope.get('status') or 'unknown').upper()}",
        f"Returned: {len(rows)} of {int(data.get('ranked_count') or 0)} rankable assets",
    ]

    for row in rows:
        if isinstance(row, Mapping):
            lines.append(
                _ranking_row_text(
                    listener_module,
                    row,
                    metric,
                    trending_basis,
                )
            )

    _append_metadata(lines, envelope)
    return "\n".join(lines)


def _matches_identity(record, mint, symbol):
    if not isinstance(record, Mapping):
        return False
    record_mint = _text(record.get("mint"))
    if mint and record_mint:
        return record_mint == mint
    record_symbol = _text(record.get("symbol"))
    return bool(symbol and record_symbol and record_symbol.upper() == symbol.upper())


def _top_n(question):
    match = re.search(r"\b(?:the\s+)?top\s+(\d+)\b", str(question or "").lower())
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def format_cmis_asset_rank_answer(listener_module, question, asset, *, gateway):
    """Render one asset's rank using CMIS asset identity plus the rank service."""
    lookup = gateway.dispatch({
        "service": "asset_lookup",
        "chain": "x1",
        "asset": str(asset or "").strip(),
        "params": {},
    })

    identity = lookup.get("asset") if isinstance(lookup, Mapping) else None
    identity = identity if isinstance(identity, Mapping) else {}
    symbol = _text(identity.get("symbol")) or _text(asset) or "Unknown"
    mint = _text(identity.get("mint"))

    if lookup.get("status") != "ok" or not mint:
        lines = [
            "Liquidity Scout reply:",
            f"CMIS asset rank — {symbol}",
            f"Asset lookup status: {str(lookup.get('status') or 'unknown').upper()}",
            "Exact asset rank unavailable because CMIS could not verify one unique mint.",
        ]
        _append_metadata(lines, lookup)
        return "\n".join(lines)

    metric, envelope = _dispatch_rank(
        listener_module,
        question,
        gateway=gateway,
        limit=_ASSET_RANK_LIMIT,
    )
    data = envelope.get("data") if isinstance(envelope, Mapping) else None
    data = data if isinstance(data, Mapping) else {}
    rows = data.get("rankings")
    rows = rows if isinstance(rows, list) else []
    trending_basis = data.get("trending_basis")

    ranked_row = next(
        (row for row in rows if _matches_identity(row, mint, symbol)),
        None,
    )
    incomplete_rows = data.get("unranked_incomplete")
    incomplete_rows = incomplete_rows if isinstance(incomplete_rows, list) else []
    non_positive_rows = data.get("unranked_non_positive")
    non_positive_rows = non_positive_rows if isinstance(non_positive_rows, list) else []

    lines = [
        "Liquidity Scout reply:",
        f"CMIS asset rank — {symbol}",
        f"Metric: {_metric_label(metric, trending_basis)}",
        f"Service status: {str(envelope.get('status') or 'unknown').upper()}",
    ]

    if ranked_row is not None:
        rank = int(ranked_row.get("rank") or 0)
        ranked_count = int(data.get("ranked_count") or 0)
        lines.append(
            f"Rank among verified rankable assets: #{rank} of {ranked_count}"
        )
        lines.append(
            "Metric value: "
            + _format_metric_value(
                listener_module,
                metric,
                ranked_row.get("value"),
                trending_basis,
            )
        )
        lp_count = ranked_row.get("#LPs")
        if lp_count is None:
            lp_count = ranked_row.get("lp_count")
        lines.append(f"#LPs: {lp_count}")

        requested_top = _top_n(question)
        if requested_top is not None:
            lines.append(
                f"Top {requested_top} among verified rankable assets: "
                + ("YES" if rank <= requested_top else "NO")
            )

        incomplete_count = int(data.get("incomplete_count") or 0)
        if incomplete_count:
            lines.append(
                "Full-universe rank is partial because "
                f"{incomplete_count} asset(s) were excluded for incomplete {metric} data."
            )
    elif any(_matches_identity(row, mint, symbol) for row in incomplete_rows):
        lines.append(
            "Exact rank unavailable: this asset's requested ranking metric is incomplete."
        )
    elif any(_matches_identity(row, mint, symbol) for row in non_positive_rows):
        lines.append(
            "Exact rank unavailable: the verified metric is non-positive and is excluded by ranking policy."
        )
    else:
        lines.append(
            "Exact rank unavailable: the verified asset was not present in the returned ranking universe."
        )

    _append_metadata(lines, envelope)
    return "\n".join(lines)


__all__ = [
    "format_cmis_asset_rank_answer",
    "format_cmis_global_rank_answer",
]
