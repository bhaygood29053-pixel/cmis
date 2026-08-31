"""Structured deterministic tokenomics facts for one verified X1 mint.

This service composes reusable X1 RPC primitives into a machine-readable
report. It reports only facts that can be verified from current RPC responses.
A precomputed standalone token-activity scan may be attached, but this service
never triggers burn/mint scanning itself. Circulating supply, maximum supply,
market cap, and safety scores remain outside this layer until independently
verified.
"""

from liquidity_scout.tokenomics import (
    DEFAULT_X1_RPC_URL,
    X1RPCError,
    get_mint_info as core_get_mint_info,
    get_token_supply as core_get_token_supply,
)
from liquidity_scout.tokenomics.burn_metrics import build_burn_metrics


def _text(value):
    text = str(value or "").strip()
    return text or None


def _nonnegative_int(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _strict_nonnegative_int(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    text = str(value).strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def _authority_state(value, verified, *, absent_state):
    if not verified:
        return "unavailable"
    if value is None:
        return absent_state
    return "active"


def _empty_activity_section(reason="token_activity_not_supplied"):
    return {
        "available": False,
        "mint": None,
        "decimals": None,
        "mint_events_observed": None,
        "burn_events_observed": None,
        "minted_raw_observed": None,
        "burned_raw_observed": None,
        "minted_tokens_observed": None,
        "burned_tokens_observed": None,
        "coverage": None,
        "coverage_scope": None,
        "coverage_verified": False,
        "time_coverage_verified": False,
        "time_coverage_reason": reason,
        "coverage_start_time": None,
        "coverage_end_time": None,
        "coverage_time_semantics": None,
        "observed_at": None,
        "observation_time_semantics": None,
        "lifetime_coverage_verified": False,
        "lifetime_coverage_reason": reason,
        "scanner_activity_verified": False,
        "activity_verified": False,
        "net_issuance_verified": False,
        "net_issuance_raw": None,
        "net_issuance_tokens": None,
        "scan_id": None,
        "source": None,
        "storage": None,
        "verification_reasons": [reason],
    }


def _normalize_activity_report(
    activity_report,
    *,
    mint,
    verified_decimals,
):
    """Attach scanner output without upgrading unverified coverage.

    Raw observed event totals may remain visible when scan coverage is
    incomplete. Token-scaled observed totals require decimal agreement with
    verified current RPC supply metadata. Net issuance is exposed only when the
    scanner reports verified activity *and* the service independently confirms
    the same mint and decimals.

    Scanner window coverage and chain-lifetime coverage are separate concepts.
    This service exposes the scanner's window scope, but it does not upgrade any
    scanner lifetime claim to verified without an independent lifetime proof.
    """
    if activity_report is None:
        return _empty_activity_section()
    if not isinstance(activity_report, dict):
        return _empty_activity_section("token_activity_malformed")

    activity_mint = _text(activity_report.get("mint"))
    if activity_mint != mint:
        return _empty_activity_section("token_activity_mint_mismatch")

    activity_decimals = _nonnegative_int(activity_report.get("decimals"))
    coverage_verified = activity_report.get("coverage_verified") is True
    scanner_activity_verified = activity_report.get("activity_verified") is True
    decimals_match = (
        verified_decimals is not None
        and activity_decimals is not None
        and activity_decimals == verified_decimals
    )

    coverage = activity_report.get("coverage")
    if not isinstance(coverage, dict):
        coverage = None

    coverage_scope = _text(activity_report.get("coverage_scope"))
    if coverage_scope is None and coverage is not None:
        coverage_scope = _text(coverage.get("coverage_scope"))

    time_coverage_verified = activity_report.get("time_coverage_verified") is True
    time_coverage_reason = _text(activity_report.get("time_coverage_reason"))
    coverage_start_time = _strict_nonnegative_int(
        activity_report.get("coverage_start_time")
    )
    coverage_end_time = _strict_nonnegative_int(
        activity_report.get("coverage_end_time")
    )
    coverage_time_semantics = _text(
        activity_report.get("coverage_time_semantics")
    )
    activity_observed_at = _strict_nonnegative_int(
        activity_report.get("observed_at")
    )
    observation_time_semantics = _text(
        activity_report.get("observation_time_semantics")
    )

    if time_coverage_verified:
        time_contract_valid = (
            coverage_verified
            and coverage is not None
            and coverage_start_time is not None
            and coverage_end_time is not None
            and activity_observed_at is not None
            and coverage_start_time <= coverage_end_time
            and activity_observed_at == coverage_end_time
            and coverage_time_semantics == "start_exclusive_end_inclusive"
            and time_coverage_reason is None
            and observation_time_semantics
            == "newest_selected_transaction_block_time"
        )

        if time_contract_valid:
            coverage_time_values = (
                _strict_nonnegative_int(coverage.get("coverage_start_time")),
                _strict_nonnegative_int(coverage.get("coverage_end_time")),
                _text(coverage.get("coverage_time_semantics")),
                _strict_nonnegative_int(coverage.get("observed_at")),
                _text(coverage.get("observation_time_semantics")),
                coverage.get("time_coverage_verified") is True,
                _text(coverage.get("time_coverage_reason")),
            )
            time_contract_valid = coverage_time_values == (
                coverage_start_time,
                coverage_end_time,
                coverage_time_semantics,
                activity_observed_at,
                observation_time_semantics,
                True,
                None,
            )

        if not time_contract_valid:
            time_coverage_verified = False
            time_coverage_reason = "token_activity_time_coverage_malformed"
            coverage_start_time = None
            coverage_end_time = None
            coverage_time_semantics = None
            activity_observed_at = None
            observation_time_semantics = None

    scanner_lifetime_claim = (
        activity_report.get("lifetime_coverage_verified") is True
    )
    if scanner_lifetime_claim:
        lifetime_coverage_reason = (
            "token_activity_lifetime_claim_not_independently_verified"
        )
    else:
        lifetime_coverage_reason = (
            _text(activity_report.get("lifetime_coverage_reason"))
            or "token_activity_lifetime_coverage_unverified"
        )

    verification_reasons = []
    if not coverage_verified:
        verification_reasons.append("token_activity_coverage_unverified")
    if not scanner_activity_verified:
        verification_reasons.append("token_activity_scanner_unverified")
    if not time_coverage_verified:
        verification_reasons.append(
            time_coverage_reason or "token_activity_time_coverage_unverified"
        )
    if verified_decimals is None:
        verification_reasons.append("token_activity_rpc_decimals_unverified")
    elif activity_decimals != verified_decimals:
        verification_reasons.append("token_activity_decimals_mismatch")

    activity_verified = (
        coverage_verified
        and scanner_activity_verified
        and decimals_match
    )

    net_raw = activity_report.get("net_issuance_raw")
    net_tokens = activity_report.get("net_issuance_tokens")
    net_values_present = net_raw is not None and net_tokens is not None
    net_issuance_verified = activity_verified and net_values_present
    if activity_verified and not net_values_present:
        verification_reasons.append("token_activity_net_issuance_missing")

    return {
        "available": True,
        "mint": activity_mint,
        "decimals": activity_decimals,
        "mint_events_observed": _nonnegative_int(
            activity_report.get("mint_events_observed")
        ),
        "burn_events_observed": _nonnegative_int(
            activity_report.get("burn_events_observed")
        ),
        "minted_raw_observed": activity_report.get("minted_raw_observed"),
        "burned_raw_observed": activity_report.get("burned_raw_observed"),
        "minted_tokens_observed": (
            activity_report.get("minted_tokens_observed")
            if decimals_match
            else None
        ),
        "burned_tokens_observed": (
            activity_report.get("burned_tokens_observed")
            if decimals_match
            else None
        ),
        "coverage": dict(coverage) if coverage is not None else None,
        "coverage_scope": coverage_scope,
        "coverage_verified": coverage_verified,
        "time_coverage_verified": time_coverage_verified,
        "time_coverage_reason": time_coverage_reason,
        "coverage_start_time": coverage_start_time,
        "coverage_end_time": coverage_end_time,
        "coverage_time_semantics": coverage_time_semantics,
        "observed_at": activity_observed_at,
        "observation_time_semantics": observation_time_semantics,
        "lifetime_coverage_verified": False,
        "lifetime_coverage_reason": lifetime_coverage_reason,
        "scanner_activity_verified": scanner_activity_verified,
        "activity_verified": activity_verified,
        "net_issuance_verified": net_issuance_verified,
        "net_issuance_raw": net_raw if net_issuance_verified else None,
        "net_issuance_tokens": net_tokens if net_issuance_verified else None,
        "scan_id": activity_report.get("scan_id"),
        "source": activity_report.get("source"),
        "storage": activity_report.get("storage"),
        "verification_reasons": verification_reasons,
    }


def _empty_burn_metrics(reason):
    return {
        "available": False,
        "status": "unavailable",
        "reason": reason,
        "lifetime_total_burn_verified": False,
        "valuation": {
            "status": "unavailable",
            "reason": "historical_burn_time_valuation_not_supplied",
        },
        "circulating_supply": {
            "status": "unavailable",
            "reason": "circulating_supply_contract_not_supplied",
        },
    }


def _build_burn_metrics_section(activity_report, token_activity, *, decimals):
    if not isinstance(activity_report, dict):
        return _empty_burn_metrics("token_activity_not_supplied")
    if token_activity.get("activity_verified") is not True:
        return _empty_burn_metrics("token_activity_not_verified_for_burn_metrics")
    if token_activity.get("time_coverage_verified") is not True:
        return _empty_burn_metrics(
            token_activity.get("time_coverage_reason")
            or "token_activity_time_coverage_unverified"
        )

    events = activity_report.get("events")
    if not isinstance(events, list):
        return _empty_burn_metrics("token_activity_events_not_supplied")

    try:
        metrics = build_burn_metrics(
            events,
            decimals=decimals,
            observed_at=token_activity.get("observed_at"),
            coverage_verified=True,
            coverage_start_time=token_activity.get("coverage_start_time"),
            coverage_end_time=token_activity.get("coverage_end_time"),
        )
    except (TypeError, ValueError):
        return _empty_burn_metrics("burn_metrics_validation_error")

    if metrics.get("time_buckets_verified") is not True:
        return _empty_burn_metrics("burn_metric_event_time_unverified")

    expected_summary = {
        "mint_events_observed": _strict_nonnegative_int(
            activity_report.get("mint_events_observed")
        ),
        "minted_raw_observed": _strict_nonnegative_int(
            activity_report.get("minted_raw_observed")
        ),
        "burn_events_observed": _strict_nonnegative_int(
            activity_report.get("burn_events_observed")
        ),
        "burned_raw_observed": _strict_nonnegative_int(
            activity_report.get("burned_raw_observed")
        ),
    }
    actual_summary = {
        "mint_events_observed": metrics.get("mint_events_observed"),
        "minted_raw_observed": _strict_nonnegative_int(
            metrics.get("minted_raw_observed")
        ),
        "burn_events_observed": metrics.get("burn_events_observed"),
        "burned_raw_observed": _strict_nonnegative_int(
            metrics.get("burned_raw_observed")
        ),
    }
    if (
        any(value is None for value in expected_summary.values())
        or actual_summary != expected_summary
    ):
        return _empty_burn_metrics("token_activity_event_summary_mismatch")

    unavailable_windows = []
    unavailable_comparisons = []
    for label, window in (metrics.get("windows") or {}).items():
        if not isinstance(window, dict) or window.get("status") != "ok":
            unavailable_windows.append(label)
            continue
        comparison = window.get("period_over_period")
        if comparison is not None and (
            not isinstance(comparison, dict)
            or comparison.get("status") != "ok"
        ):
            unavailable_comparisons.append(label)

    metrics["available"] = True
    metrics["window_metrics_complete"] = (
        not unavailable_windows and not unavailable_comparisons
    )
    metrics["window_metrics_status"] = (
        "ok" if metrics["window_metrics_complete"] else "partial"
    )
    metrics["unavailable_windows"] = unavailable_windows
    metrics["unavailable_comparisons"] = unavailable_comparisons
    # Full #368 burn intelligence remains partial until the independently
    # verified circulating-supply and historical burn-time valuation layers
    # are supplied.
    metrics["status"] = "partial"
    metrics["partial_reasons"] = [
        "historical_burn_time_valuation_not_supplied",
        "circulating_supply_contract_not_supplied",
    ]
    if unavailable_windows:
        metrics["partial_reasons"].append("burn_window_coverage_incomplete")
    if unavailable_comparisons:
        metrics["partial_reasons"].append(
            "burn_period_comparison_coverage_incomplete"
        )
    metrics["source"] = token_activity.get("source")
    metrics["scan_id"] = token_activity.get("scan_id")
    return metrics

def build_tokenomics_report(
    mint,
    *,
    symbol=None,
    name=None,
    rpc_url=DEFAULT_X1_RPC_URL,
    get_token_supply=core_get_token_supply,
    get_mint_info=core_get_mint_info,
    activity_report=None,
):
    """Return verified current supply, authority, and bounded activity facts.

    Lookup functions are injectable so callers can test deterministically and
    integrations can choose their transport boundary. RPC failures are
    preserved as unavailable facts rather than converted to zero or revoked.
    When both RPC sources expose token decimals, a disagreement fails closed:
    raw supply remains observable, but scaled supply and token-activity values
    are not certified until the conflict is resolved. ``activity_report`` must
    come from a separate scanner boundary; this service never initiates token-
    history scanning.
    """
    mint = _text(mint)
    if not mint:
        raise ValueError("Token mint is required.")

    unavailable_reasons = []

    try:
        supply_record = get_token_supply(mint, rpc_url=rpc_url)
    except (X1RPCError, ValueError):
        supply_record = None
        unavailable_reasons.append("current_supply_rpc_unavailable")

    try:
        mint_record = get_mint_info(mint, rpc_url=rpc_url)
    except (X1RPCError, ValueError):
        mint_record = None
        unavailable_reasons.append("mint_account_rpc_unavailable")

    if not isinstance(supply_record, dict):
        supply_record = {}
    if not isinstance(mint_record, dict):
        mint_record = {}

    source_supply_verified = bool(supply_record.get("supply_verified"))
    supply_decimals = (
        _nonnegative_int(supply_record.get("decimals"))
        if source_supply_verified
        else None
    )
    mint_decimals = _nonnegative_int(mint_record.get("decimals"))

    rpc_decimals_consistent = None
    if supply_decimals is not None and mint_decimals is not None:
        rpc_decimals_consistent = supply_decimals == mint_decimals
        if not rpc_decimals_consistent:
            unavailable_reasons.append("rpc_decimals_mismatch")

    # getTokenSupply remains the primary current-supply source, but an explicit
    # disagreement with the mint account means the scaled value is not safe to
    # certify. Preserve raw supply for diagnostics while withholding scaled
    # supply and verified decimals.
    supply_verified = (
        source_supply_verified
        and rpc_decimals_consistent is not False
    )
    current_total_supply = (
        supply_record.get("total_supply") if supply_verified else None
    )
    raw_supply = (
        supply_record.get("raw_supply") if source_supply_verified else None
    )
    decimals = supply_decimals if supply_verified else None

    mint_authority_verified = bool(
        mint_record.get("mint_authority_verified")
    )
    mint_authority = (
        mint_record.get("mint_authority")
        if mint_authority_verified
        else None
    )
    mint_authority_state = _authority_state(
        mint_authority,
        mint_authority_verified,
        absent_state="revoked",
    )

    freeze_authority_verified = bool(
        mint_record.get("freeze_authority_verified")
    )
    freeze_authority = (
        mint_record.get("freeze_authority")
        if freeze_authority_verified
        else None
    )
    freeze_authority_state = _authority_state(
        freeze_authority,
        freeze_authority_verified,
        absent_state="none",
    )

    if not supply_verified and "current_supply_rpc_unavailable" not in unavailable_reasons:
        unavailable_reasons.append("current_supply_unverified")
    if not mint_authority_verified and "mint_account_rpc_unavailable" not in unavailable_reasons:
        unavailable_reasons.append("mint_authority_unverified")
    if not freeze_authority_verified and "mint_account_rpc_unavailable" not in unavailable_reasons:
        unavailable_reasons.append("freeze_authority_unverified")

    future_minting_possible = None
    if mint_authority_verified:
        future_minting_possible = mint_authority is not None

    token_activity = _normalize_activity_report(
        activity_report,
        mint=mint,
        verified_decimals=decimals,
    )
    burn_metrics = _build_burn_metrics_section(
        activity_report,
        token_activity,
        decimals=decimals,
    )

    return {
        "mint": mint,
        "symbol": _text(symbol),
        "name": _text(name),
        "current_total_supply": current_total_supply,
        "raw_supply": raw_supply,
        "decimals": decimals,
        "supply_verified": supply_verified,
        "rpc_decimals_consistent": rpc_decimals_consistent,
        "rpc_decimal_sources": {
            "token_supply": supply_decimals,
            "mint_account": mint_decimals,
        },
        "mint_authority": mint_authority,
        "mint_authority_verified": mint_authority_verified,
        "mint_authority_state": mint_authority_state,
        "freeze_authority": freeze_authority,
        "freeze_authority_verified": freeze_authority_verified,
        "freeze_authority_state": freeze_authority_state,
        "future_minting_possible": future_minting_possible,
        "token_activity": token_activity,
        "burn_metrics": burn_metrics,
        # Current SPL mint supply is not circulating supply or maximum supply.
        "circulating_supply": None,
        "circulating_supply_verified": False,
        "maximum_supply": None,
        "maximum_supply_verified": False,
        "sources": {
            "current_supply": supply_record.get("source"),
            "mint_account": mint_record.get("source"),
            "token_activity": token_activity.get("source"),
        },
        "unavailable_reasons": unavailable_reasons,
    }
