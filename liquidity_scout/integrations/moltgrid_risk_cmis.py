"""CMIS-backed standalone risk presentation for the MoltGrid listener.

This adapter recognizes risk/safety questions for one already-resolved asset,
dispatches the deterministic ``risk_check`` service, and renders only facts in
the returned CMIS envelope. It never asks an LLM to manufacture or override a
risk outcome and never treats PASS/WARN/BLOCK as execution authorization.
"""

from collections.abc import Mapping
import re


_RISK_PHRASES = (
    "risk check",
    "risk assessment",
    "risk profile",
    "red flag",
    "red flags",
    "how safe",
    "is it safe",
    "is this safe",
    "is that safe",
    "safe to hold",
    "safe token",
    "token safety",
    "safety score",
)


def _text(value):
    text = str(value or "").strip()
    return text or None


def wants_cmis_risk(question):
    """Return True for standalone deterministic risk/safety questions."""
    text = _text(question) or ""
    lower = text.lower()
    if not lower:
        return False

    if any(phrase in lower for phrase in _RISK_PHRASES):
        return True

    return bool(
        re.search(
            r"\b(?:risk|risky|safe|safety|dangerous|scam)\b",
            lower,
        )
    )


def build_cmis_risk_request(asset):
    return {
        "service": "risk_check",
        "chain": "x1",
        "asset": _text(asset) or "",
        "params": {},
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


def _source_lines(envelope):
    records = envelope.get("sources") if isinstance(envelope, Mapping) else None
    if not isinstance(records, list):
        return []

    lines = []
    for record in records:
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


def _component_label(name):
    return {
        "liquidity": "Liquidity",
        "activity": "24h activity",
        "tokenomics": "Tokenomics",
        "history": "History",
    }.get(name, str(name).replace("_", " ").title())


def format_cmis_risk_answer(listener_module, question, asset, *, gateway):
    """Dispatch and render one deterministic standalone CMIS risk request."""
    if not wants_cmis_risk(question):
        return None

    envelope = gateway.dispatch(build_cmis_risk_request(asset))
    if not isinstance(envelope, Mapping):
        return (
            "Liquidity Scout reply:\n"
            "CMIS returned an invalid response for this risk request."
        )

    identity = envelope.get("asset")
    identity = identity if isinstance(identity, Mapping) else {}
    symbol = _text(identity.get("symbol")) or _text(asset) or "Unknown"

    risk = envelope.get("risk")
    risk = risk if isinstance(risk, Mapping) else {}

    lines = [
        "Liquidity Scout reply:",
        f"CMIS risk check — {symbol}",
        f"Service status: {str(envelope.get('status') or 'unknown').upper()}",
    ]

    recommendation = _text(risk.get("recommendation"))
    if recommendation:
        lines.append(f"Risk result: {recommendation.upper()}")
    else:
        lines.append("Risk result: UNAVAILABLE")

    confidence = risk.get("confidence")
    confidence = confidence if isinstance(confidence, Mapping) else {}
    verified = confidence.get("verified_checks")
    total = confidence.get("total_checks")
    level = _text(confidence.get("level"))
    if isinstance(verified, int) and isinstance(total, int):
        prefix = f"Risk evidence verified: {verified}/{total} checks"
        if level:
            prefix += f" ({level.lower()} confidence)"
        lines.append(prefix)

    components = risk.get("components")
    if isinstance(components, Mapping) and components:
        lines.append("Component results:")
        for name in ("liquidity", "activity", "tokenomics", "history"):
            component = components.get(name)
            if not isinstance(component, Mapping):
                continue
            status = _text(component.get("status")) or "UNAVAILABLE"
            lines.append(f"• {_component_label(name)}: {status.upper()}")

    reasons = risk.get("reasons")
    if isinstance(reasons, list) and reasons:
        lines.append("Risk findings:")
        for reason in reasons:
            text = _text(reason)
            if text:
                # Native XNT has no mint account. Keep the public wording aligned
                # with native-network semantics when the shared risk flag refers
                # to unavailable token activity.
                if (
                    symbol.upper() == "XNT"
                    and text == "Verified bounded mint/burn activity was not supplied."
                ):
                    text = "Verified native-network issuance/burn activity was not supplied."
                lines.append(f"• {text}")

    if risk.get("score_verified") is True and risk.get("score") is not None:
        lines.append(f"Risk score: {risk.get('score')}")
    else:
        lines.append("Risk score: unavailable — CMIS has no calibrated numeric risk score")

    scope = risk.get("assessment_scope")
    scope = scope if isinstance(scope, Mapping) else {}
    not_included = scope.get("not_yet_included")
    if isinstance(not_included, list) and not_included:
        lines.append(
            "Not yet included: "
            + ", ".join(str(item).replace("_", " ") for item in not_included)
            + "."
        )

    observed_at = envelope.get("observed_at")
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

    lines.append("Deterministic analysis only. Execution authorized: NO.")
    return "\n".join(lines)


__all__ = [
    "build_cmis_risk_request",
    "format_cmis_risk_answer",
    "wants_cmis_risk",
]
