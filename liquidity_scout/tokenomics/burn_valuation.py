"""Deterministic historical burn-time valuation for exact X1 token burns.

This module performs arithmetic and evidence validation only. It does not fetch
prices, substitute current prices, interpolate candles, or infer USD/native
units. Price evidence must be supplied by a separate verified historical-price
boundary and must bind exactly to the burn event under the initial strict
fact-time policy.
"""

from decimal import Decimal, DecimalException, InvalidOperation, localcontext

from .activity import scale_raw_amount
from .burn_metrics import WINDOW_SECONDS


VALUATION_CONTRACT = "verified_burn_time_price_evidence_v1"
FACT_TIME_POLICY = "exact_burn_time_v1"
MAX_SUPPORTED_DECIMAL_EXPONENT = 10_000


def _text(value):
    text = str(value or "").strip()
    return text or None


def _nonnegative_int(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    text = str(value).strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def _positive_decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed <= 0:
        return None
    return parsed


def _decimal_exponent_supported(value):
    adjusted = value.adjusted()
    return -MAX_SUPPORTED_DECIMAL_EXPONENT <= adjusted <= (
        MAX_SUPPORTED_DECIMAL_EXPONENT
    )


def _decimal_text(value):
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _token_decimal(raw_amount, decimals):
    with localcontext() as ctx:
        ctx.prec = max(40, len(str(raw_amount)) + decimals + 10)
        return Decimal(raw_amount) / (Decimal(10) ** decimals)


def _product_precision(left, right):
    """Return enough significant digits for an exact Decimal product."""
    return max(1, len(left.as_tuple().digits) + len(right.as_tuple().digits))


def _sum_precision(values):
    """Return enough precision to add finite Decimals without rounding."""
    if not values:
        return 1
    highest_place = max(value.adjusted() for value in values)
    lowest_place = min(value.as_tuple().exponent for value in values)
    carry_digits = len(str(len(values)))
    return max(1, highest_place - lowest_place + 1 + carry_digits)


def _empty_denomination(total_raw, decimals, reason):
    return {
        "status": "unavailable",
        "reason": reason,
        "valuation_coverage_complete": False,
        "burn_events_total": None,
        "burn_events_valued": 0,
        "burn_events_unvalued": None,
        "valued_burn_raw": (
            "0" if total_raw is not None else None
        ),
        "valued_burn_amount": (
            scale_raw_amount(0, decimals)
            if total_raw is not None
            else None
        ),
        "unvalued_burn_raw": (
            str(total_raw) if total_raw is not None else None
        ),
        "unvalued_burn_amount": (
            scale_raw_amount(total_raw, decimals)
            if total_raw is not None
            else None
        ),
        "verified_value_destroyed": None,
        "complete_value_destroyed": None,
        "sources": [],
    }


def _unavailable(reason, *, mint=None, decimals=None, total_burn_raw=None):
    return {
        "available": False,
        "status": "unavailable",
        "reason": reason,
        "mint": mint,
        "decimals": decimals,
        "contract": VALUATION_CONTRACT,
        "contract_verified": False,
        "fact_time_policy": FACT_TIME_POLICY,
        "valuation_coverage_complete": False,
        "burn_events_observed": None,
        "burned_raw_observed": (
            str(total_burn_raw) if total_burn_raw is not None else None
        ),
        "burned_observed": (
            scale_raw_amount(total_burn_raw, decimals)
            if total_burn_raw is not None and decimals is not None
            else None
        ),
        "native": _empty_denomination(total_burn_raw, decimals, reason),
        "usd": _empty_denomination(total_burn_raw, decimals, reason),
        "events": [],
        "windows": {},
        "sources": [],
    }


def _price_result(
    price_evidence,
    *,
    denomination,
    expected_unit,
    burn_time,
    token_amount,
):
    if not isinstance(price_evidence, dict):
        return {
            "verified": False,
            "reason": f"{denomination}_price_evidence_missing",
        }

    price = _positive_decimal(price_evidence.get("price"))
    fact_time = _nonnegative_int(price_evidence.get("price_fact_time"))
    observed_at = price_evidence.get("price_observed_at")
    if observed_at is not None:
        observed_at = _nonnegative_int(observed_at)
        if observed_at is None or (
            fact_time is not None and observed_at < fact_time
        ):
            return {
                "verified": False,
                "reason": f"{denomination}_price_observation_time_malformed",
            }

    source = _text(price_evidence.get("source"))
    unit = _text(price_evidence.get("unit"))
    policy = _text(price_evidence.get("fact_time_policy"))

    if price is not None and not _decimal_exponent_supported(price):
        return {
            "verified": False,
            "reason": f"{denomination}_price_numeric_range_unsupported",
        }

    verified = (
        price is not None
        and price_evidence.get("price_verified") is True
        and price_evidence.get("historical_price_verified") is True
        and price_evidence.get("unit_verified") is True
        and unit == expected_unit
        and policy == FACT_TIME_POLICY
        and fact_time == burn_time
        and source is not None
    )
    if not verified:
        return {
            "verified": False,
            "reason": f"{denomination}_historical_price_unverified",
        }

    try:
        with localcontext() as ctx:
            ctx.prec = _product_precision(token_amount, price)
            ctx.Emax = MAX_SUPPORTED_DECIMAL_EXPONENT
            ctx.Emin = -MAX_SUPPORTED_DECIMAL_EXPONENT
            value = token_amount * price
    except DecimalException:
        return {
            "verified": False,
            "reason": f"{denomination}_price_numeric_range_unsupported",
        }
    if not _decimal_exponent_supported(value):
        return {
            "verified": False,
            "reason": f"{denomination}_price_numeric_range_unsupported",
        }

    result = {
        "verified": True,
        "reason": None,
        "unit": expected_unit,
        "price": _decimal_text(price),
        "price_fact_time": fact_time,
        "price_observed_at": observed_at,
        "fact_time_policy": FACT_TIME_POLICY,
        "source": source,
        "value_destroyed": _decimal_text(value),
    }
    if price_evidence.get("evidence_receipt") is not None:
        result["evidence_receipt"] = price_evidence.get("evidence_receipt")
    if price_evidence.get("proof_score") is not None:
        result["proof_score"] = price_evidence.get("proof_score")
    return result


def _aggregate(event_rows, *, denomination, decimals):
    total_raw = sum(row["raw_amount"] for row in event_rows)
    valued_rows = [
        row
        for row in event_rows
        if row[denomination].get("verified") is True
    ]
    valued_raw = sum(row["raw_amount"] for row in valued_rows)
    unvalued_raw = total_raw - valued_raw

    values = [
        Decimal(row[denomination]["value_destroyed"])
        for row in valued_rows
    ]
    with localcontext() as ctx:
        ctx.prec = _sum_precision(values)
        value = sum(values, Decimal(0))

    complete = len(valued_rows) == len(event_rows)
    if complete:
        status = "ok"
        reason = None
    elif valued_rows:
        status = "partial"
        reason = f"{denomination}_valuation_coverage_incomplete"
    else:
        status = "unavailable"
        reason = f"{denomination}_historical_price_evidence_unavailable"

    sources = sorted({
        row[denomination]["source"]
        for row in valued_rows
        if row[denomination].get("source")
    })
    value_text = _decimal_text(value) if valued_rows or not event_rows else None

    return {
        "status": status,
        "reason": reason,
        "valuation_coverage_complete": complete,
        "burn_events_total": len(event_rows),
        "burn_events_valued": len(valued_rows),
        "burn_events_unvalued": len(event_rows) - len(valued_rows),
        "valued_burn_raw": str(valued_raw),
        "valued_burn_amount": scale_raw_amount(valued_raw, decimals),
        "unvalued_burn_raw": str(unvalued_raw),
        "unvalued_burn_amount": scale_raw_amount(unvalued_raw, decimals),
        "verified_value_destroyed": value_text,
        "complete_value_destroyed": value_text if complete else None,
        "sources": sources,
    }


def _normalize_burn_events(events, *, mint, decimals, observed_at):
    normalized = []
    seen_keys = set()

    for event in events or []:
        if not isinstance(event, dict):
            return None, "burn_event_payload_malformed"
        kind = _text(event.get("kind"))
        if kind is None:
            return None, "burn_event_payload_malformed"
        kind = kind.lower()
        if kind == "mint":
            continue
        if kind != "burn":
            return None, "burn_event_payload_malformed"

        event_key = _text(event.get("event_key"))
        raw_amount = _nonnegative_int(event.get("raw_amount"))
        block_time = _nonnegative_int(event.get("block_time"))

        if raw_amount is None or block_time is None or block_time > observed_at:
            return None, "burn_event_identity_or_time_unverified"
        if not event_key:
            return None, "burn_event_key_unverified"
        if event_key in seen_keys:
            return None, "duplicate_burn_event_key"

        seen_keys.add(event_key)
        normalized.append({
            "event_key": event_key,
            "mint": mint,
            "raw_amount": raw_amount,
            "burn_amount": scale_raw_amount(raw_amount, decimals),
            "block_time": block_time,
        })

    return normalized, None


def build_burn_valuation(
    events,
    evidence,
    *,
    mint,
    decimals,
    observed_at,
    burn_events_verified,
    burn_windows=None,
):
    """Value verified burn events with exact historical price evidence.

    The initial accepted fact-time policy is intentionally strict:
    price_fact_time must equal the burn block time. No preceding-price
    tolerance, nearest-neighbor lookup, candle interpolation, or current-price
    fallback is authorized by this contract.

    Native and USD evidence are independent. USD evidence must explicitly prove
    the USD unit; a configured stable-quote relationship alone is insufficient.
    """
    mint = _text(mint)
    decimals = _nonnegative_int(decimals)
    observed_at = _nonnegative_int(observed_at)

    if not mint:
        return _unavailable("token_mint_required")
    if decimals is None:
        return _unavailable("verified_token_decimals_required", mint=mint)
    if observed_at is None:
        return _unavailable(
            "burn_observation_time_unverified",
            mint=mint,
            decimals=decimals,
        )
    if burn_events_verified is not True:
        return _unavailable(
            "burn_events_unverified_for_valuation",
            mint=mint,
            decimals=decimals,
        )

    if not isinstance(evidence, dict):
        return _unavailable(
            "historical_burn_time_valuation_not_supplied",
            mint=mint,
            decimals=decimals,
        )

    if not isinstance(events, list):
        return _unavailable(
            "burn_event_payload_malformed",
            mint=mint,
            decimals=decimals,
        )

    burn_events, event_error = _normalize_burn_events(
        events,
        mint=mint,
        decimals=decimals,
        observed_at=observed_at,
    )
    if burn_events is None:
        return _unavailable(event_error, mint=mint, decimals=decimals)

    total_burn_raw = sum(row["raw_amount"] for row in burn_events)

    if (
        _text(evidence.get("mint")) != mint
        or _nonnegative_int(evidence.get("decimals")) != decimals
    ):
        return _unavailable(
            "burn_valuation_identity_mismatch",
            mint=mint,
            decimals=decimals,
            total_burn_raw=total_burn_raw,
        )
    if (
        _text(evidence.get("contract")) != VALUATION_CONTRACT
        or evidence.get("contract_verified") is not True
        or _text(evidence.get("source")) is None
    ):
        return _unavailable(
            "burn_valuation_contract_unverified",
            mint=mint,
            decimals=decimals,
            total_burn_raw=total_burn_raw,
        )

    supplied = evidence.get("events")
    if not isinstance(supplied, list):
        return _unavailable(
            "burn_valuation_event_evidence_malformed",
            mint=mint,
            decimals=decimals,
            total_burn_raw=total_burn_raw,
        )

    evidence_by_key = {}
    for item in supplied:
        if not isinstance(item, dict):
            return _unavailable(
                "burn_valuation_event_evidence_malformed",
                mint=mint,
                decimals=decimals,
                total_burn_raw=total_burn_raw,
            )
        key = _text(item.get("event_key"))
        if not key or key in evidence_by_key:
            return _unavailable(
                "burn_valuation_event_evidence_duplicate_or_unkeyed",
                mint=mint,
                decimals=decimals,
                total_burn_raw=total_burn_raw,
            )
        evidence_by_key[key] = item

    burn_keys = {row["event_key"] for row in burn_events}
    if set(evidence_by_key) - burn_keys:
        return _unavailable(
            "burn_valuation_unknown_event_evidence",
            mint=mint,
            decimals=decimals,
            total_burn_raw=total_burn_raw,
        )

    valued_events = []
    for burn in burn_events:
        event_evidence = evidence_by_key.get(burn["event_key"])
        if event_evidence is not None:
            identity_valid = (
                _text(event_evidence.get("mint")) == mint
                and _nonnegative_int(event_evidence.get("raw_amount"))
                == burn["raw_amount"]
                and _nonnegative_int(event_evidence.get("burn_block_time"))
                == burn["block_time"]
            )
            if not identity_valid:
                return _unavailable(
                    "burn_valuation_event_identity_mismatch",
                    mint=mint,
                    decimals=decimals,
                    total_burn_raw=total_burn_raw,
                )

        token_amount = _token_decimal(burn["raw_amount"], decimals)
        native = _price_result(
            event_evidence.get("native") if event_evidence else None,
            denomination="native",
            expected_unit="XNT",
            burn_time=burn["block_time"],
            token_amount=token_amount,
        )
        usd = _price_result(
            event_evidence.get("usd") if event_evidence else None,
            denomination="usd",
            expected_unit="USD",
            burn_time=burn["block_time"],
            token_amount=token_amount,
        )
        valued_events.append({
            **burn,
            "native": native,
            "usd": usd,
        })

    native = _aggregate(valued_events, denomination="native", decimals=decimals)
    usd = _aggregate(valued_events, denomination="usd", decimals=decimals)

    windows = {}
    burn_windows = burn_windows if isinstance(burn_windows, dict) else {}
    for label, seconds in WINDOW_SECONDS.items():
        burn_window = burn_windows.get(label)
        if not isinstance(burn_window, dict) or burn_window.get("status") != "ok":
            windows[label] = {
                "status": "unavailable",
                "reason": "burn_window_unverified",
                "window_seconds": seconds,
                "native": _empty_denomination(
                    None,
                    decimals,
                    "burn_window_unverified",
                ),
                "usd": _empty_denomination(
                    None,
                    decimals,
                    "burn_window_unverified",
                ),
            }
            continue

        start = observed_at - seconds
        window_events = [
            row
            for row in valued_events
            if start < row["block_time"] <= observed_at
        ]
        window_native = _aggregate(
            window_events,
            denomination="native",
            decimals=decimals,
        )
        window_usd = _aggregate(
            window_events,
            denomination="usd",
            decimals=decimals,
        )
        window_complete = (
            window_native["valuation_coverage_complete"]
            and window_usd["valuation_coverage_complete"]
        )
        if window_complete:
            window_status = "ok"
        elif (
            window_native["status"] != "unavailable"
            or window_usd["status"] != "unavailable"
        ):
            window_status = "partial"
        else:
            window_status = "unavailable"

        windows[label] = {
            "status": window_status,
            "reason": (
                None
                if window_complete
                else "burn_time_valuation_coverage_incomplete"
            ),
            "window_seconds": seconds,
            "start_exclusive": start,
            "end_inclusive": observed_at,
            "native": window_native,
            "usd": window_usd,
        }

    overall_complete = (
        native["valuation_coverage_complete"]
        and usd["valuation_coverage_complete"]
    )
    if overall_complete:
        status = "ok"
        reason = None
    elif native["status"] != "unavailable" or usd["status"] != "unavailable":
        status = "partial"
        reason = "burn_time_valuation_coverage_incomplete"
    else:
        status = "unavailable"
        reason = "historical_burn_time_price_evidence_unavailable"

    sources = sorted({
        *native["sources"],
        *usd["sources"],
        _text(evidence.get("source")),
    } - {None})

    return {
        "available": status != "unavailable",
        "status": status,
        "reason": reason,
        "mint": mint,
        "decimals": decimals,
        "contract": VALUATION_CONTRACT,
        "contract_verified": True,
        "fact_time_policy": FACT_TIME_POLICY,
        "valuation_coverage_complete": overall_complete,
        "burn_events_observed": len(valued_events),
        "burned_raw_observed": str(total_burn_raw),
        "burned_observed": scale_raw_amount(total_burn_raw, decimals),
        "native": native,
        "usd": usd,
        "verified_native_value_destroyed_observed": (
            native["verified_value_destroyed"]
        ),
        "verified_usd_value_destroyed_observed": (
            usd["verified_value_destroyed"]
        ),
        "events": valued_events,
        "windows": windows,
        "source": _text(evidence.get("source")),
        "sources": sources,
    }


__all__ = [
    "FACT_TIME_POLICY",
    "VALUATION_CONTRACT",
    "build_burn_valuation",
]
