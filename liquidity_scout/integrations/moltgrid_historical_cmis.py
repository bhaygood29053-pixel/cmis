"""CMIS-backed historical comparison presentation for MoltGrid.

This integration layer recognizes historical questions using the existing
historical query parser, sends the actual comparison through ``CMISGateway``,
and renders only facts present in the returned CMIS envelope. Historical
storage remains owned by the injected CMIS history backend; this module neither
reads nor writes the database directly.
"""

from collections.abc import Mapping


def _text(value):
    text = str(value or "").strip()
    return text or None


def wants_cmis_historical(listener_module, question):
    """Return True only when the deterministic history parser recognizes it."""
    history = getattr(listener_module, "history", None)
    parser = getattr(history, "parse_historical_comparison", None)
    if not callable(parser):
        return False
    try:
        return bool(parser(question))
    except (KeyError, TypeError, ValueError):
        return False


def build_cmis_historical_request(question, asset):
    return {
        "service": "historical_compare",
        "chain": "x1",
        "asset": _text(asset) or "",
        "params": {"question": _text(question) or ""},
    }


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


def _format_metric_value(listener_module, metric, value):
    if value is None:
        return "unavailable"

    history = getattr(listener_module, "history", None)
    formatter = getattr(history, "format_number", None)
    if callable(formatter):
        try:
            formatted = formatter(metric, value)
        except (TypeError, ValueError):
            formatted = None
        if _text(formatted):
            return str(formatted)

    if metric in {"price", "liquidity", "volume"}:
        usd = getattr(listener_module, "format_usd", None)
        if callable(usd):
            try:
                return str(usd(value))
            except (TypeError, ValueError):
                pass

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.8g}"


def _source_lines(envelope):
    sources = envelope.get("sources") if isinstance(envelope, Mapping) else None
    if not isinstance(sources, list):
        return []

    lines = []
    for record in sources:
        if not isinstance(record, Mapping):
            continue
        source = _text(record.get("source"))
        if not source:
            continue
        role = _text(record.get("role"))
        observed_at = record.get("observed_at")
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


def format_cmis_historical_answer(
    listener_module,
    question,
    asset,
    *,
    gateway,
):
    """Dispatch and render a recognized historical question through CMIS."""
    if not wants_cmis_historical(listener_module, question):
        return None

    request = build_cmis_historical_request(question, asset)
    print(f"CMIS Gateway: HISTORICAL_COMPARE | asset: {request['asset']}")
    envelope = gateway.dispatch(request)
    if not isinstance(envelope, Mapping):
        return (
            "Liquidity Scout reply:\n"
            "CMIS returned an invalid response for this historical comparison."
        )

    data = envelope.get("data")
    data = data if isinstance(data, Mapping) else {}
    identity = envelope.get("asset")
    if not isinstance(identity, Mapping):
        identity = data.get("asset")
    identity = identity if isinstance(identity, Mapping) else {}

    symbol = _text(identity.get("symbol")) or _text(asset) or "Unknown"
    metric = _text(data.get("metric")) or "metric"
    period = _text(data.get("period")) or "requested period"

    lines = [
        "Liquidity Scout reply:",
        f"CMIS historical compare — {symbol}",
        f"Service status: {str(envelope.get('status') or 'unknown').upper()}",
        f"Metric: {metric.upper()}",
        f"Period: {period}",
    ]

    current_value = data.get("current_value")
    if data.get("current_verified") is True and current_value is not None:
        lines.append(
            f"Current {metric}: "
            + _format_metric_value(listener_module, metric, current_value)
        )
    elif current_value is not None:
        lines.append(
            f"Current {metric}: "
            + _format_metric_value(listener_module, metric, current_value)
            + " — UNVERIFIED"
        )
    else:
        lines.append(f"Current {metric}: unavailable from verified data")

    historical_value = data.get("historical_value")
    if data.get("historical_verified") is True and historical_value is not None:
        lines.append(
            f"{period} ago: "
            + _format_metric_value(listener_module, metric, historical_value)
        )
    else:
        lines.append(f"{period} ago: unavailable from verified history")

    change = data.get("change_pct")
    confidence = envelope.get("confidence")
    confidence = confidence if isinstance(confidence, Mapping) else {}
    checks = confidence.get("checks")
    checks = checks if isinstance(checks, Mapping) else {}
    if change is not None:
        suffix = "" if checks.get("change_verified") is True else " — UNVERIFIED"
        try:
            lines.append(f"Change: {float(change):+.2f}%{suffix}")
        except (TypeError, ValueError):
            lines.append(f"Change: {change}{suffix}")
    else:
        lines.append("Change: unavailable from verified history")

    threshold = data.get("threshold")
    threshold_met = data.get("threshold_met")
    if threshold is not None and isinstance(threshold_met, bool):
        direction = _text(data.get("direction")) or "change"
        try:
            threshold_text = f"{float(threshold):g}%"
        except (TypeError, ValueError):
            threshold_text = str(threshold)
        lines.append(
            f"Threshold test ({direction} {threshold_text}): "
            + ("YES" if threshold_met else "NO")
        )

    _append_metadata(lines, envelope)
    return "\n".join(lines)


__all__ = [
    "build_cmis_historical_request",
    "format_cmis_historical_answer",
    "wants_cmis_historical",
]
