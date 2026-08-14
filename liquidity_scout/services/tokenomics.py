"""Structured deterministic tokenomics facts for one verified X1 mint.

This service composes the reusable X1 RPC primitives into a machine-readable
report. It reports only facts that can be verified from current RPC responses.
It does not infer circulating supply, maximum supply, market cap, burns, mints,
net issuance, or safety scores.
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


def _authority_state(value, verified, *, absent_state):
    if not verified:
        return "unavailable"
    if value is None:
        return absent_state
    return "active"


def build_tokenomics_report(
    mint,
    *,
    symbol=None,
    name=None,
    rpc_url=DEFAULT_X1_RPC_URL,
    get_token_supply=core_get_token_supply,
    get_mint_info=core_get_mint_info,
):
    """Return verified current supply and authority facts for one X1 mint.

    Lookup functions are injectable so callers can test deterministically and
    integrations can choose their transport boundary. RPC failures are
    preserved as unavailable facts rather than converted to zero or revoked.
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
        # Current SPL mint supply is not circulating supply or maximum supply.
        "circulating_supply": None,
        "circulating_supply_verified": False,
        "maximum_supply": None,
        "maximum_supply_verified": False,
        "sources": {
            "current_supply": supply_record.get("source"),
            "mint_account": mint_record.get("source"),
        },
        "unavailable_reasons": unavailable_reasons,
    }
