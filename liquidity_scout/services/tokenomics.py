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
        "coverage_verified": False,
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

    verification_reasons = []
    if not coverage_verified:
        verification_reasons.append("token_activity_coverage_unverified")
    if not scanner_activity_verified:
        verification_reasons.append("token_activity_scanner_unverified")
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

    coverage = activity_report.get("coverage")
    if not isinstance(coverage, dict):
        coverage = None

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
        "coverage_verified": coverage_verified,
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
    ``activity_report`` must come from a separate scanner boundary; this service
    never initiates token-history scanning.
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

    supply_verified = bool(supply_record.get("supply_verified"))
    current_total_supply = (
        supply_record.get("total_supply") if supply_verified else None
    )
    raw_supply = supply_record.get("raw_supply") if supply_verified else None
    decimals = supply_record.get("decimals") if supply_verified else None

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

    return {
        "mint": mint,
        "symbol": _text(symbol),
        "name": _text(name),
        "current_total_supply": current_total_supply,
        "raw_supply": raw_supply,
        "decimals": decimals,
        "supply_verified": supply_verified,
        "mint_authority": mint_authority,
        "mint_authority_verified": mint_authority_verified,
        "mint_authority_state": mint_authority_state,
        "freeze_authority": freeze_authority,
        "freeze_authority_verified": freeze_authority_verified,
        "freeze_authority_state": freeze_authority_state,
        "future_minting_possible": future_minting_possible,
        "token_activity": token_activity,
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
