"""Deterministic burn-intelligence arithmetic for verified X1 token events.

This module is pure business logic. It performs no RPC calls and does not
promote bounded activity to lifetime completeness, circulating supply, or
historical valuation. Callers must provide explicit time-coverage evidence.
"""

from decimal import Decimal, localcontext

from .activity import scale_raw_amount


WINDOW_SECONDS = {
    "1h": 60 * 60,
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
}
COMPARISON_WINDOWS = {"24h", "7d", "30d"}


def _nonnegative_int(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    text = str(value).strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def _raw_integer(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    text = str(value).strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def _decimal_text(value):
    if value is None:
        return None
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _ratio_text(numerator, denominator):
    with localcontext() as ctx:
        ctx.prec = 40
        return _decimal_text(Decimal(numerator) / Decimal(denominator))


def _percent_change(current, prior):
    if prior == 0:
        if current == 0:
            return "0", "NO_CHANGE_ZERO_BASE"
        return None, "NEW_BURN_ACTIVITY"
    with localcontext() as ctx:
        ctx.prec = 40
        value = (Decimal(current - prior) / Decimal(prior)) * Decimal(100)
    return _decimal_text(value), "AVAILABLE"


def _window_complete(*, coverage_verified, coverage_start_time,
                     coverage_end_time, required_start, observed_at,
                     time_buckets_verified):
    return (
        coverage_verified is True
        and time_buckets_verified is True
        and coverage_start_time is not None
        and coverage_end_time is not None
        and coverage_start_time <= required_start
        and coverage_end_time >= observed_at
    )


def _sum_window(events, *, start_exclusive, end_inclusive):
    burned_raw = 0
    minted_raw = 0
    burn_events = 0
    mint_events = 0

    for event in events:
        block_time = event["block_time"]
        if not (start_exclusive < block_time <= end_inclusive):
            continue
        if event["kind"] == "burn":
            burned_raw += event["raw_amount"]
            burn_events += 1
        else:
            minted_raw += event["raw_amount"]
            mint_events += 1

    return {
        "burned_raw": burned_raw,
        "minted_raw": minted_raw,
        "burn_events": burn_events,
        "mint_events": mint_events,
    }


def _issuance_fields(summary, *, decimals, verified):
    net_raw = summary["minted_raw"] - summary["burned_raw"]

    if not verified:
        return {
            "burn_to_emission_ratio": None,
            "net_issuance_raw": None,
            "net_issuance_tokens": None,
            "issuance_state": "INSUFFICIENT_COVERAGE",
        }

    minted = summary["minted_raw"]
    burned = summary["burned_raw"]
    if minted == 0 and burned == 0:
        ratio = None
        state = "NO_ACTIVITY"
    elif minted == 0:
        ratio = None
        state = "BURN_WITHOUT_EMISSION"
    else:
        ratio = _ratio_text(burned, minted)
        if burned > minted:
            state = "DEFLATIONARY"
        elif burned < minted:
            state = "INFLATIONARY"
        else:
            state = "NEUTRAL"

    return {
        "burn_to_emission_ratio": ratio,
        "net_issuance_raw": str(net_raw),
        "net_issuance_tokens": scale_raw_amount(net_raw, decimals),
        "issuance_state": state,
    }


def build_burn_metrics(
    events,
    *,
    decimals,
    observed_at,
    coverage_verified,
    coverage_start_time,
    coverage_end_time,
):
    """Build deterministic burn metrics from accepted mint/burn events.

    Time windows use UTC Unix-second boundaries with start-exclusive and
    end-inclusive semantics.

    Window metrics are verified only when explicit compatible coverage reaches
    from the required start boundary through observed_at and every accepted
    event has a usable canonical block time. Missing time never gets silently
    bucketed.

    Lifetime completeness remains false here by design. Historical valuation
    and circulating-supply semantics are separate layers.
    """
    decimals = _nonnegative_int(decimals)
    observed_at = _nonnegative_int(observed_at)
    coverage_start_time = _nonnegative_int(coverage_start_time)
    coverage_end_time = _nonnegative_int(coverage_end_time)

    if decimals is None:
        raise ValueError("Verified token decimals are required.")
    if observed_at is None:
        raise ValueError("A non-negative observed_at Unix timestamp is required.")

    normalized = []
    malformed_events = 0
    untimed_events = 0
    future_timed_events = 0
    pre_coverage_events = 0
    burned_observed = 0
    burn_events_observed = 0
    minted_observed = 0
    mint_events_observed = 0

    for event in events or []:
        if not isinstance(event, dict):
            malformed_events += 1
            continue

        kind = str(event.get("kind") or "").strip().lower()
        raw_amount = _raw_integer(event.get("raw_amount"))
        if kind not in {"mint", "burn"} or raw_amount is None:
            malformed_events += 1
            continue

        block_time = _nonnegative_int(event.get("block_time"))
        if block_time is None:
            untimed_events += 1
        elif block_time > observed_at:
            future_timed_events += 1
        elif (
            coverage_start_time is not None
            and block_time < coverage_start_time
        ):
            pre_coverage_events += 1

        normalized.append({
            "kind": kind,
            "raw_amount": raw_amount,
            "block_time": block_time,
        })

        if kind == "burn":
            burned_observed += raw_amount
            burn_events_observed += 1
        else:
            minted_observed += raw_amount
            mint_events_observed += 1

    input_events_verified = malformed_events == 0
    event_time_contract_verified = (
        input_events_verified
        and untimed_events == 0
        and future_timed_events == 0
        and pre_coverage_events == 0
    )
    observed_event_totals_verified = (
        event_time_contract_verified and coverage_verified is True
    )
    time_buckets_verified = event_time_contract_verified
    timed_events = [
        event for event in normalized
        if event["block_time"] is not None and event["block_time"] <= observed_at
    ]

    windows = {}
    for label, seconds in WINDOW_SECONDS.items():
        start = observed_at - seconds
        verified = _window_complete(
            coverage_verified=coverage_verified,
            coverage_start_time=coverage_start_time,
            coverage_end_time=coverage_end_time,
            required_start=start,
            observed_at=observed_at,
            time_buckets_verified=time_buckets_verified,
        )
        summary = _sum_window(
            timed_events,
            start_exclusive=start,
            end_inclusive=observed_at,
        )

        window = {
            "status": "ok" if verified else "unavailable",
            "window_seconds": seconds,
            "start_exclusive": start,
            "end_inclusive": observed_at,
            "coverage_verified": verified,
            "burned_raw": str(summary["burned_raw"]) if verified else None,
            "burned_tokens": (
                scale_raw_amount(summary["burned_raw"], decimals)
                if verified else None
            ),
            "burn_events": summary["burn_events"] if verified else None,
            "minted_raw": str(summary["minted_raw"]) if verified else None,
            "minted_tokens": (
                scale_raw_amount(summary["minted_raw"], decimals)
                if verified else None
            ),
            "mint_events": summary["mint_events"] if verified else None,
        }
        window.update(_issuance_fields(summary, decimals=decimals, verified=verified))

        if label in COMPARISON_WINDOWS:
            prior_start = observed_at - (2 * seconds)
            prior_end = observed_at - seconds
            comparison_verified = _window_complete(
                coverage_verified=coverage_verified,
                coverage_start_time=coverage_start_time,
                coverage_end_time=coverage_end_time,
                required_start=prior_start,
                observed_at=observed_at,
                time_buckets_verified=time_buckets_verified,
            )
            prior = _sum_window(
                timed_events,
                start_exclusive=prior_start,
                end_inclusive=prior_end,
            )
            if verified and comparison_verified:
                percent, change_state = _percent_change(
                    summary["burned_raw"],
                    prior["burned_raw"],
                )
                prior_raw = str(prior["burned_raw"])
                prior_tokens = scale_raw_amount(prior["burned_raw"], decimals)
            else:
                percent = None
                change_state = "INSUFFICIENT_COVERAGE"
                prior_raw = None
                prior_tokens = None

            window["period_over_period"] = {
                "status": (
                    "ok"
                    if verified and comparison_verified
                    else "unavailable"
                ),
                "prior_start_exclusive": prior_start,
                "prior_end_inclusive": prior_end,
                "prior_burned_raw": prior_raw,
                "prior_burned_tokens": prior_tokens,
                "percent_change": percent,
                "change_state": change_state,
            }

        windows[label] = window

    return {
        "mint_events_observed": mint_events_observed,
        "minted_raw_observed": str(minted_observed),
        "minted_tokens_observed": scale_raw_amount(minted_observed, decimals),
        "burn_events_observed": burn_events_observed,
        "burned_raw_observed": str(burned_observed),
        "burned_tokens_observed": scale_raw_amount(burned_observed, decimals),
        "observed_event_totals_verified": observed_event_totals_verified,
        "verified_burned_raw_observed": (
            str(burned_observed) if observed_event_totals_verified else None
        ),
        "verified_burned_observed": (
            scale_raw_amount(burned_observed, decimals)
            if observed_event_totals_verified
            else None
        ),
        "lifetime_total_burn_verified": False,
        "malformed_events": malformed_events,
        "untimed_events": untimed_events,
        "future_timed_events": future_timed_events,
        "pre_coverage_events": pre_coverage_events,
        "time_buckets_verified": time_buckets_verified,
        "coverage_verified": coverage_verified is True,
        "coverage_start_time": coverage_start_time,
        "coverage_end_time": coverage_end_time,
        "observed_at": observed_at,
        "windows": windows,
        "valuation": {
            "status": "unavailable",
            "reason": "historical_burn_time_valuation_not_supplied",
        },
        "circulating_supply": {
            "status": "unavailable",
            "reason": "circulating_supply_contract_not_supplied",
        },
    }


__all__ = ["COMPARISON_WINDOWS", "WINDOW_SECONDS", "build_burn_metrics"]
