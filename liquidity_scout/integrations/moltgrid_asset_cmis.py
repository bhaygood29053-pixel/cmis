"""CMIS-backed asset lookup, market, and tokenomics presentation for MoltGrid.

This module is intentionally a thin integration layer. MoltGrid supplies the
already-resolved asset term, CMISGateway performs authoritative collection and
service composition, and this module renders the standard envelope for a human
Signal reply. No market or tokenomics values are calculated or invented here.
"""

import re
from collections.abc import Mapping

from liquidity_scout.integrations.moltgrid_tokenomics_cmis import (
    format_cmis_tokenomics_answer,
    wants_cmis_tokenomics,
)


_MARKET_CUES = (
    "price",
    "liquidity",
    "volume",
    "holder",
    "holders",
    "pool",
    "pools",
    "market cap",
    "marketcap",
    "fdv",
    "safety",
    "doing",
    "today",
    "right now",
    "current",
    "currently",
    "change",
    "up",
    "down",
)


def _text(value):
    text = str(value or "").strip()
    return text or None


def cmis_asset_service(question):
    """Choose the CMIS service for one ordinary resolved asset question.

    Tokenomics-specific wording selects ``tokenomics`` before generic market
    cues such as ``current`` are considered. Market-oriented wording selects
    ``market_report``. Everything else defaults to market_report except concise
    lookup/identity forms such as "What is XNT?" and "Find XNT".
    """
    text = _text(question) or ""
    lower = text.lower()

    if wants_cmis_tokenomics(text):
        return "tokenomics"

    if any(cue in lower for cue in _MARKET_CUES):
        return "market_report"

    if re.search(r"\b(?:mint|token address|asset address|identify|lookup)\b", lower):
        return "asset_lookup"

    normalized = re.sub(r"[^a-z0-9.]+", " ", lower).strip()
    if re.match(r"^(?:what is|whats|find)\s+\S+(?:\s+token)?$", normalized):
        return "asset_lookup"

    return "market_report"


def build_cmis_asset_request(question, asset):
    """Build the public CMIS request used by MoltGrid for ordinary asset data."""
    return {
        "service": cmis_asset_service(question),
        "chain": "x1",
        "asset": _text(asset) or "",
        "params": {},
    }


def _messages(envelope, field):
    output = []
    records = envelope.get(field) if isinstance(envelope, Mapping) else None
    if not isinstance(records, list):
        return output
    for record in records:
        if isinstance(record, Mapping):
            code = _text(record.get("code"))
            message = _text(record.get("message"))
            if code and message:
                output.append(f"{code}: {message}")
            elif message or code:
                output.append(message or code)
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
        observed = record.get("observed_at")
        if not source:
            continue
        line = f"Source: {source}"
        if role:
            line += f" ({role})"
        if observed is not None:
            line += f" @ {observed}"
        lines.append(line)
    return lines


def _confidence_line(envelope):
    confidence = envelope.get("confidence") if isinstance(envelope, Mapping) else None
    if not isinstance(confidence, Mapping):
        return None
    verified = confidence.get("verified_checks")
    total = confidence.get("total_checks")
    if isinstance(verified, int) and isinstance(total, int):
        return f"Confidence checks: {verified}/{total} verified"
    complete = confidence.get("complete")
    if isinstance(complete, bool):
        return "Confidence: complete" if complete else "Confidence: incomplete"
    return None


def _append_envelope_metadata(lines, envelope):
    confidence = _confidence_line(envelope)
    if confidence:
        lines.append(confidence)

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


def _format_asset_lookup(envelope):
    asset = envelope.get("asset") if isinstance(envelope, Mapping) else None
    asset = asset if isinstance(asset, Mapping) else {}
    data = envelope.get("data") if isinstance(envelope, Mapping) else None
    data = data if isinstance(data, Mapping) else {}

    symbol = _text(asset.get("symbol")) or "Unknown"
    lines = [
        "Liquidity Scout reply:",
        f"CMIS asset lookup — {symbol}",
        f"Service status: {str(envelope.get('status') or 'unknown').upper()}",
    ]

    name = _text(asset.get("name"))
    mint = _text(asset.get("mint"))
    if name:
        lines.append(f"Name: {name}")
    if mint:
        lines.append(f"Mint: {mint}")

    resolved_by = _text(data.get("resolved_by"))
    if resolved_by:
        lines.append(f"Resolved by: {resolved_by}")

    lp_count = data.get("#LPs")
    if lp_count is None:
        lp_count = data.get("lp_count")
    if lp_count is not None:
        lines.append(f"#LPs: {lp_count}")

    _append_envelope_metadata(lines, envelope)
    return "\n".join(lines)


def _verified_metric(lines, label, data, completeness, key, format_value):
    value = data.get(key)
    verified = completeness.get(key) is True
    if key == "volume_24h_usd":
        verified = completeness.get("volume_24h") is True
    elif key == "transactions_24h":
        verified = completeness.get("transactions_24h") is True
    elif key == "liquidity_usd":
        verified = completeness.get("liquidity") is True
    elif key == "price_usd":
        verified = completeness.get("price") is True
    elif key == "holders":
        verified = completeness.get("holders") is True

    if verified and value is not None:
        lines.append(f"{label}: {format_value(value)}")
    elif value is not None:
        lines.append(f"{label}: at least {format_value(value)} — incomplete coverage")
    else:
        lines.append(f"{label}: unavailable from verified data")


def _format_market_report(listener_module, envelope):
    asset = envelope.get("asset") if isinstance(envelope, Mapping) else None
    asset = asset if isinstance(asset, Mapping) else {}
    data = envelope.get("data") if isinstance(envelope, Mapping) else None
    data = data if isinstance(data, Mapping) else {}
    completeness = data.get("completeness")
    completeness = completeness if isinstance(completeness, Mapping) else {}

    symbol = _text(asset.get("symbol")) or "Unknown"
    lines = [
        "Liquidity Scout reply:",
        f"CMIS market report — {symbol}",
        f"Service status: {str(envelope.get('status') or 'unknown').upper()}",
    ]

    if data:
        _verified_metric(
            lines,
            "Verified price",
            data,
            completeness,
            "price_usd",
            listener_module.format_usd,
        )
        _verified_metric(
            lines,
            "Asset-wide liquidity",
            data,
            completeness,
            "liquidity_usd",
            listener_module.format_usd,
        )
        _verified_metric(
            lines,
            "24h volume",
            data,
            completeness,
            "volume_24h_usd",
            listener_module.format_usd,
        )
        _verified_metric(
            lines,
            "24h transactions",
            data,
            completeness,
            "transactions_24h",
            lambda value: f"{int(value):,}",
        )
        _verified_metric(
            lines,
            "Holders",
            data,
            completeness,
            "holders",
            lambda value: f"{int(value):,}",
        )

        lp_count = data.get("#LPs")
        if lp_count is None:
            lp_count = data.get("lp_count")
        if lp_count is not None:
            lines.append(f"#LPs: {lp_count}")

    _append_envelope_metadata(lines, envelope)
    return "\n".join(lines)


def format_cmis_asset_answer(listener_module, question, asset, *, gateway):
    """Dispatch and render one ordinary CMIS asset service envelope."""
    request = build_cmis_asset_request(question, asset)

    if request["service"] == "tokenomics":
        return format_cmis_tokenomics_answer(
            listener_module,
            question,
            asset,
            gateway=gateway,
        )

    envelope = gateway.dispatch(request)
    if not isinstance(envelope, Mapping):
        return (
            "Liquidity Scout reply:\n"
            "CMIS returned an invalid response for this asset request."
        )

    if request["service"] == "asset_lookup":
        return _format_asset_lookup(envelope)
    return _format_market_report(listener_module, envelope)


__all__ = [
    "build_cmis_asset_request",
    "cmis_asset_service",
    "format_cmis_asset_answer",
]
