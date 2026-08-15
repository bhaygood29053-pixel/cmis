"""CMIS-backed tokenomics presentation for the canonical MoltGrid listener.

This integration layer recognizes tokenomics-specific asset questions, dispatches
them through ``CMISGateway.tokenomics``, and renders only facts present in the
returned CMIS envelope.  It never launches the standalone burn/mint scanner and
never infers circulating supply, maximum supply, market cap, FDV, or safety.
"""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
import re


_TOKENOMICS_PHRASES = (
    "tokenomics",
    "total supply",
    "current supply",
    "circulating supply",
    "circulating tokens",
    "tokens circulating",
    "max supply",
    "maximum supply",
    "mint authority",
    "minting authority",
    "freeze authority",
    "future minting",
    "net issuance",
    "mint burn activity",
    "mint/burn activity",
    "minted tokens",
    "burned tokens",
)

_EXCLUDED_PHRASES = (
    "market cap",
    "marketcap",
    "fully diluted",
    "fdv",
    "supply valuation",
    "current supply valuation",
    "total supply valuation",
    "token address",
    "mint address",
    "asset address",
    "contract address",
)


def _text(value):
    text = str(value or "").strip()
    return text or None


def wants_cmis_tokenomics(question):
    """Return True only for ordinary tokenomics-specific asset questions.

    Market valuation and identity-address questions remain on their dedicated
    CMIS routes.  Safety/risk wording is also excluded because ``risk_check`` is
    the authoritative CMIS risk service, not tokenomics.
    """
    text = _text(question) or ""
    lower = text.lower()
    if not lower:
        return False

    if any(phrase in lower for phrase in _EXCLUDED_PHRASES):
        return False

    if re.search(r"\b(?:safe|safety|risk|risky|scam|dangerous?)\b", lower):
        return False

    if any(phrase in lower for phrase in _TOKENOMICS_PHRASES):
        return True

    if re.search(r"\bdecimals?\b", lower):
        return True

    if re.search(r"\b(?:can|could)\b[^?]{0,80}\bmint(?:ed|ing)?\b", lower):
        return True

    return False


def build_cmis_tokenomics_request(asset):
    return {
        "service": "tokenomics",
        "chain": "x1",
        "asset": _text(asset) or "",
        "params": {},
    }


def _decimal_text(value):
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    if not number.is_finite():
        return str(value)
    return f"{number:,f}"


def _token_amount(value, symbol=None):
    text = _decimal_text(value)
    if text is None:
        return "unavailable"
    symbol_text = _text(symbol)
    return f"{text} {symbol_text}" if symbol_text else text


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


def _authority_line(label, state, address, verified):
    if verified is not True:
        return f"{label}: unavailable from verified X1 RPC data"

    state_text = (_text(state) or "unavailable").upper()
    if state_text == "ACTIVE" and _text(address):
        return f"{label}: ACTIVE — {_text(address)}"
    return f"{label}: {state_text}"


def _append_activity(lines, data, symbol):
    activity = data.get("token_activity")
    activity = activity if isinstance(activity, Mapping) else {}

    if activity.get("available") is not True:
        lines.append(
            "Bounded mint/burn activity: unavailable — standalone scanner result "
            "was not supplied to this ordinary tokenomics request"
        )
        return

    verified = activity.get("activity_verified") is True
    scope = _text(activity.get("coverage_scope")) or "unknown"
    lines.append(
        "Bounded mint/burn activity: "
        + ("VERIFIED" if verified else "UNVERIFIED")
        + f" • Coverage scope: {scope}"
    )

    mint_events = activity.get("mint_events_observed")
    burn_events = activity.get("burn_events_observed")
    if mint_events is not None:
        lines.append(f"Mint events observed: {mint_events}")
    if burn_events is not None:
        lines.append(f"Burn events observed: {burn_events}")

    minted = activity.get("minted_tokens_observed")
    burned = activity.get("burned_tokens_observed")
    if minted is not None:
        lines.append(f"Minted tokens observed: {_token_amount(minted, symbol)}")
    if burned is not None:
        lines.append(f"Burned tokens observed: {_token_amount(burned, symbol)}")

    if activity.get("net_issuance_verified") is True:
        lines.append(
            "Net issuance in verified scan window: "
            + _token_amount(activity.get("net_issuance_tokens"), symbol)
        )
    else:
        lines.append("Net issuance: unavailable from verified scanner coverage")

    if activity.get("lifetime_coverage_verified") is True:
        lines.append("Chain-lifetime activity coverage: VERIFIED")
    else:
        lines.append("Chain-lifetime activity coverage: UNVERIFIED")


def format_cmis_tokenomics_answer(listener_module, question, asset, *, gateway):
    """Dispatch and render one ordinary tokenomics request through CMIS."""
    if not wants_cmis_tokenomics(question):
        return None

    request = build_cmis_tokenomics_request(asset)
    envelope = gateway.dispatch(request)
    if not isinstance(envelope, Mapping):
        return (
            "Liquidity Scout reply:\n"
            "CMIS returned an invalid response for this tokenomics request."
        )

    data = envelope.get("data")
    data = data if isinstance(data, Mapping) else {}
    identity = envelope.get("asset")
    identity = identity if isinstance(identity, Mapping) else {}

    symbol = _text(identity.get("symbol")) or _text(data.get("symbol")) or _text(asset) or "Unknown"
    name = _text(identity.get("name")) or _text(data.get("name"))
    mint = _text(identity.get("mint")) or _text(data.get("mint"))

    lines = [
        "Liquidity Scout reply:",
        f"CMIS tokenomics — {symbol}",
        f"Service status: {str(envelope.get('status') or 'unknown').upper()}",
    ]
    if name:
        lines.append(f"Name: {name}")
    if mint:
        lines.append(f"Mint: {mint}")

    total_supply = data.get("current_total_supply")
    if data.get("supply_verified") is True and total_supply is not None:
        lines.append(f"Current total supply: {_token_amount(total_supply, symbol)}")
    else:
        lines.append("Current total supply: unavailable from verified X1 RPC data")

    decimals = data.get("decimals")
    if data.get("supply_verified") is True and decimals is not None:
        lines.append(f"Decimals: {decimals}")
    else:
        lines.append("Decimals: unavailable from verified X1 RPC data")

    decimal_consistency = data.get("rpc_decimals_consistent")
    if decimal_consistency is True:
        lines.append("RPC decimals consistent: YES")
    elif decimal_consistency is False:
        lines.append("RPC decimals consistent: NO — scaled supply is withheld")

    lines.append(
        _authority_line(
            "Mint authority",
            data.get("mint_authority_state"),
            data.get("mint_authority"),
            data.get("mint_authority_verified"),
        )
    )
    lines.append(
        _authority_line(
            "Freeze authority",
            data.get("freeze_authority_state"),
            data.get("freeze_authority"),
            data.get("freeze_authority_verified"),
        )
    )

    future_minting = data.get("future_minting_possible")
    if isinstance(future_minting, bool):
        lines.append(f"Future minting possible: {'YES' if future_minting else 'NO'}")
    else:
        lines.append("Future minting possible: unavailable from verified authority data")

    circulating = data.get("circulating_supply")
    if data.get("circulating_supply_verified") is True and circulating is not None:
        lines.append(f"Circulating supply: {_token_amount(circulating, symbol)}")
    else:
        lines.append("Circulating supply: unavailable from independently verified data")

    maximum = data.get("maximum_supply")
    if data.get("maximum_supply_verified") is True and maximum is not None:
        lines.append(f"Maximum supply: {_token_amount(maximum, symbol)}")
    else:
        lines.append("Maximum supply: unavailable from independently verified data")

    _append_activity(lines, data, symbol)
    _append_metadata(lines, envelope)
    return "\n".join(lines)


__all__ = [
    "build_cmis_tokenomics_request",
    "format_cmis_tokenomics_answer",
    "wants_cmis_tokenomics",
]
