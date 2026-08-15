"""CMIS-backed ranking compatibility for the current MoltGrid listener.

The legacy listener still calls ``xdex_rankings.format_top`` and
``xdex_rankings.find_asset_rank``.  During the canonical MoltGrid runtime the
compatibility shim delegates those calls here, where ranking facts are
collected through ``CMISGateway``.  Shared ranking calculations remain pure in
``liquidity_scout.services.market_rankings``.
"""

from collections.abc import Mapping

from liquidity_scout.cmis import CMISGateway
from liquidity_scout.services.market_rankings import (
    ranking_header as core_ranking_header,
    ranking_row as core_ranking_row,
    ranking_separator as core_ranking_separator,
    ranking_style as core_ranking_style,
)


_ASSET_RANK_LIMIT = 100000
_GATEWAY = None


def _text(value):
    text = str(value or "").strip()
    return text or None


def _gateway_instance(gateway=None):
    if gateway is not None:
        return gateway

    global _GATEWAY
    if _GATEWAY is None:
        _GATEWAY = CMISGateway()
    return _GATEWAY


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


def _source_lines(envelope):
    lines = []
    sources = envelope.get("sources") if isinstance(envelope, Mapping) else None
    if not isinstance(sources, list):
        return lines

    for record in sources:
        if not isinstance(record, Mapping):
            continue
        source = _text(record.get("source"))
        role = _text(record.get("role"))
        observed_at = record.get("observed_at")
        if not source:
            continue
        line = f"Source: {source}"
        if role:
            line += f" ({role})"
        if observed_at is not None:
            line += f" @ {observed_at}"
        lines.append(line)
    return lines


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

    lines.extend(_source_lines(envelope))

    warnings = _messages(envelope, "warnings")
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"• {message}" for message in warnings)

    errors = _messages(envelope, "errors")
    if errors:
        lines.append("Errors:")
        lines.extend(f"• {message}" for message in errors)


def _rank_envelope(metric, limit, *, gateway=None):
    metric_text = str(metric or "volume").strip().lower()
    print(f"CMIS Gateway: RANK | metric: {metric_text} | limit: {limit}")
    return _gateway_instance(gateway).dispatch({
        "service": "rank",
        "chain": "x1",
        "asset": "",
        "params": {
            "metric": metric_text,
            "limit": limit,
        },
    })


def _legacy_row(row, metric, trending_basis=None):
    """Translate one CMIS rank row into the existing presentation shape."""
    if not isinstance(row, Mapping):
        return {}

    value = row.get("value")
    liquidity = row.get("liquidity_usd")
    lp_count = row.get("#LPs")
    if lp_count is None:
        lp_count = row.get("lp_count")

    converted = {
        "rank": row.get("rank"),
        "symbol": row.get("symbol"),
        "name": row.get("name"),
        "mint": row.get("mint"),
        "pool_count": lp_count,
        "liquidity": liquidity,
        "completeness": {
            "liquidity": row.get("liquidity_complete") is True,
        },
    }

    if metric == "volume":
        converted["volume24"] = value
    elif metric == "liquidity":
        converted["liquidity"] = value
        converted["completeness"]["liquidity"] = True
    elif metric == "holders":
        converted["holders"] = value
    elif metric == "safety":
        converted["safety_score"] = value
        converted["safety_grade"] = None
    elif metric in {"gainers", "losers"}:
        converted["change24"] = value
    elif metric == "trending":
        if trending_basis == "1h transactions":
            converted["txns1h"] = value
        else:
            converted["volume1h"] = value

    return converted


def _meta(envelope, data):
    data = data if isinstance(data, Mapping) else {}
    return {
        "trending_basis": data.get("trending_basis"),
        "ranked_count": int(data.get("ranked_count") or 0),
        "incomplete_count": int(data.get("incomplete_count") or 0),
        "unranked_incomplete": data.get("unranked_incomplete") or [],
        "unranked_zero": data.get("unranked_non_positive") or [],
        "_cmis_envelope": envelope,
    }


def _query_matches(record, query):
    if not isinstance(record, Mapping):
        return False
    query_text = str(query or "").strip().upper()
    if not query_text:
        return False
    return any(
        str(record.get(field) or "").strip().upper() == query_text
        for field in ("symbol", "mint", "name")
    )


def format_top(_pools, metric="volume", limit=10, *, gateway=None):
    """Legacy ``format_top`` signature backed entirely by CMIS ``rank``."""
    envelope = _rank_envelope(metric, limit, gateway=gateway)
    data = envelope.get("data") if isinstance(envelope, Mapping) else None
    data = data if isinstance(data, Mapping) else {}
    trending_basis = data.get("trending_basis")
    rows = data.get("rankings")
    rows = rows if isinstance(rows, list) else []
    converted = [
        _legacy_row(row, metric, trending_basis)
        for row in rows
        if isinstance(row, Mapping)
    ]
    meta = _meta(envelope, data)
    style = core_ranking_style(metric, meta)

    lines = [
        f"{style['icon']} CMIS / X1.NINJA / XDEX TOP {len(converted)}",
        style["label"],
        f"Service status: {str(envelope.get('status') or 'unknown').upper()}",
        "",
        core_ranking_header(metric, meta),
        core_ranking_separator(metric),
    ]

    for asset in converted:
        lines.append(core_ranking_row(asset, metric, meta))

    ranked_count = int(data.get("ranked_count") or 0)
    if ranked_count:
        lines.extend(["", f"Rankable assets: {ranked_count}"])

    _append_metadata(lines, envelope)
    return "\n".join(lines)


def find_asset_rank(_pools, query, metric="volume", *, gateway=None):
    """Legacy asset-rank signature backed entirely by CMIS ``rank``."""
    envelope = _rank_envelope(metric, _ASSET_RANK_LIMIT, gateway=gateway)
    data = envelope.get("data") if isinstance(envelope, Mapping) else None
    data = data if isinstance(data, Mapping) else {}
    trending_basis = data.get("trending_basis")
    rows = data.get("rankings")
    rows = rows if isinstance(rows, list) else []
    meta = _meta(envelope, data)

    for row in rows:
        if _query_matches(row, query):
            meta["query_status"] = "ranked"
            return (
                _legacy_row(row, metric, trending_basis),
                int(data.get("ranked_count") or 0),
                meta,
            )

    incomplete = data.get("unranked_incomplete")
    incomplete = incomplete if isinstance(incomplete, list) else []
    for row in incomplete:
        if _query_matches(row, query):
            meta["query_status"] = "incomplete"
            meta["query_asset"] = row
            return None, int(data.get("ranked_count") or 0), meta

    non_positive = data.get("unranked_non_positive")
    non_positive = non_positive if isinstance(non_positive, list) else []
    for row in non_positive:
        if _query_matches(row, query):
            meta["query_status"] = "verified_non_positive"
            meta["query_asset"] = row
            return None, int(data.get("ranked_count") or 0), meta

    meta["query_status"] = "not_found"
    return None, int(data.get("ranked_count") or 0), meta


def ranking_row(asset, metric, meta=None):
    """Preserve the legacy row while surfacing CMIS provenance for asset rank."""
    text = core_ranking_row(asset, metric, meta)
    envelope = meta.get("_cmis_envelope") if isinstance(meta, Mapping) else None
    if not isinstance(envelope, Mapping):
        return text

    lines = [
        text,
        f"CMIS status: {str(envelope.get('status') or 'unknown').upper()}",
    ]

    data = envelope.get("data")
    data = data if isinstance(data, Mapping) else {}
    incomplete_count = int(data.get("incomplete_count") or 0)
    if incomplete_count:
        lines.append(
            "Full-universe rank is partial: "
            f"{incomplete_count} asset(s) excluded for incomplete {metric} data."
        )

    _append_metadata(lines, envelope)
    return "\n".join(lines)


__all__ = ["find_asset_rank", "format_top", "ranking_row"]
