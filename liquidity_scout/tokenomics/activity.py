"""Deterministic parsed token mint/burn activity helpers.

This module only interprets explicit parsed token-program MintTo/MintToChecked
and Burn/BurnChecked instructions from already-fetched transactions. It does
not perform RPC calls, infer unobserved supply changes, or claim lifetime
coverage unless the caller supplies verified coverage metadata.
"""


def _text(value):
    return str(value or "").strip()


def _decimals(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _raw_integer(value):
    text = _text(value)
    if not text or not text.isdigit():
        return None
    return text.lstrip("0") or "0"


def scale_raw_amount(raw_amount, decimals):
    """Scale a signed or unsigned raw integer exactly into a token string."""
    decimals = _decimals(decimals)
    if decimals is None:
        return None

    text = _text(raw_amount)
    if not text:
        return None

    sign = ""
    if text.startswith("-"):
        sign = "-"
        text = text[1:]

    if not text.isdigit():
        return None

    digits = text.lstrip("0") or "0"
    if digits == "0":
        sign = ""

    if decimals == 0:
        return f"{sign}{digits}"

    digits = digits.rjust(decimals + 1, "0")
    whole = digits[:-decimals] or "0"
    fraction = digits[-decimals:].rstrip("0")

    if fraction:
        return f"{sign}{whole}.{fraction}"
    return f"{sign}{whole}"


def extract_token_events(tx, mint):
    """Extract explicit parsed mint/burn events for one token mint.

    Only transactions with an explicitly present, successful ``meta.err``
    field are eligible. Both top-level and inner CPI parsed token instructions
    are inspected. Malformed or missing raw amounts are ignored rather than
    coerced to zero.
    """
    mint = _text(mint)
    if not mint:
        raise ValueError("Token mint is required.")

    if not isinstance(tx, dict):
        return []

    meta = tx.get("meta")
    if not isinstance(meta, dict) or "err" not in meta:
        return []
    if meta.get("err") is not None:
        return []

    events = []
    block_time = tx.get("blockTime")

    def inspect(ix, location):
        if not isinstance(ix, dict):
            return

        parsed = ix.get("parsed")
        if not isinstance(parsed, dict):
            return

        instruction_type = _text(parsed.get("type")).lower()
        if instruction_type in ("mintto", "minttochecked"):
            kind = "mint"
        elif instruction_type in ("burn", "burnchecked"):
            kind = "burn"
        else:
            return

        info = parsed.get("info")
        if not isinstance(info, dict):
            return

        if _text(info.get("mint")) != mint:
            return

        token_amount = info.get("tokenAmount")
        if not isinstance(token_amount, dict):
            token_amount = {}

        raw_amount = _raw_integer(
            token_amount.get("amount")
            if token_amount.get("amount") is not None
            else info.get("amount")
        )
        if raw_amount is None:
            return

        authority = _text(
            info.get("authority")
            or info.get("mintAuthority")
        )
        account = _text(
            info.get("account")
            or info.get("destination")
        )

        events.append(
            {
                "kind": kind,
                "instruction_type": instruction_type,
                "raw_amount": raw_amount,
                "authority": authority,
                "account": account,
                "location": location,
                "block_time": block_time,
            }
        )

    message = (tx.get("transaction") or {}).get("message") or {}
    for index, ix in enumerate(message.get("instructions") or []):
        inspect(ix, f"top:{index}")

    for group_index, group in enumerate(meta.get("innerInstructions") or []):
        if not isinstance(group, dict):
            continue
        for ix_index, ix in enumerate(group.get("instructions") or []):
            inspect(ix, f"inner:{group_index}:{ix_index}")

    return events


def _coverage_state(coverage):
    if not isinstance(coverage, dict):
        return False, "coverage metadata unavailable"

    signatures = coverage.get("signatures_scanned")
    retrieved = coverage.get("transactions_retrieved")
    errors = coverage.get("rpc_errors")
    selection_complete = coverage.get("selection_complete") is True

    for value in (signatures, retrieved, errors):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return False, "coverage counts are incomplete or malformed"

    if not selection_complete:
        return False, "signature-window selection is incomplete"
    if errors != 0:
        return False, "one or more selected transactions were not retrieved"
    if retrieved != signatures:
        return False, "not all selected signatures were retrieved"

    return True, None


def summarize_token_events(events, *, mint, decimals, coverage):
    """Summarize observed token events with explicit coverage verification.

    Observed mint/burn totals are preserved even when coverage is incomplete,
    but net issuance is only emitted when every selected transaction was
    retrieved and all event amounts/decimals are valid for the same bounded
    signature window.
    """
    mint = _text(mint)
    if not mint:
        raise ValueError("Token mint is required.")

    decimals = _decimals(decimals)
    minted_raw = 0
    burned_raw = 0
    mint_events = 0
    burn_events = 0
    malformed_events = 0

    for event in events or []:
        if not isinstance(event, dict):
            malformed_events += 1
            continue

        raw_amount = _raw_integer(event.get("raw_amount"))
        kind = _text(event.get("kind")).lower()
        if raw_amount is None or kind not in ("mint", "burn"):
            malformed_events += 1
            continue

        amount = int(raw_amount)
        if kind == "mint":
            minted_raw += amount
            mint_events += 1
        else:
            burned_raw += amount
            burn_events += 1

    coverage_verified, coverage_reason = _coverage_state(coverage)
    amounts_verified = decimals is not None and malformed_events == 0
    activity_verified = coverage_verified and amounts_verified

    net_raw = minted_raw - burned_raw

    return {
        "mint": mint,
        "decimals": decimals,
        "mint_events_observed": mint_events,
        "burn_events_observed": burn_events,
        "malformed_events": malformed_events,
        "minted_raw_observed": str(minted_raw),
        "burned_raw_observed": str(burned_raw),
        "minted_tokens_observed": scale_raw_amount(minted_raw, decimals),
        "burned_tokens_observed": scale_raw_amount(burned_raw, decimals),
        "coverage": dict(coverage) if isinstance(coverage, dict) else None,
        "coverage_verified": coverage_verified,
        "coverage_unverified_reason": coverage_reason,
        "amounts_verified": amounts_verified,
        "activity_verified": activity_verified,
        "net_issuance_raw": str(net_raw) if activity_verified else None,
        "net_issuance_tokens": (
            scale_raw_amount(net_raw, decimals)
            if activity_verified
            else None
        ),
        "source": "X1 RPC parsed token instructions",
    }
