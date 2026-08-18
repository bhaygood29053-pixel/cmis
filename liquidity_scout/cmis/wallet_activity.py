"""Deterministic wallet/account activity primitives for CMIS.

This module records already-observed account deltas. It does not fetch chain
history, infer trade intent, identify beneficial owners, or classify wallets.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


SCHEMA_VERSION = "cmis.wallet_activity.v1"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _amount(value: Any) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("Wallet activity amount must be a finite decimal value.")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError("Wallet activity amount must be a finite decimal value.") from None
    if not parsed.is_finite():
        raise ValueError("Wallet activity amount must be a finite decimal value.")
    return parsed


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def build_balance_change_observation(
    *,
    chain: Any,
    account_id: Any,
    asset_id: Any,
    before_amount: Any,
    after_amount: Any,
    unit: Any,
    observed_at: Any,
    source: Any,
    block_slot: Any = None,
    transaction_id: Any = None,
    account_identity_verified: bool = False,
    asset_identity_verified: bool = False,
    amount_semantics_verified: bool = False,
) -> dict[str, Any]:
    """Record one exact account balance change without assigning intent.

    Positive deltas are observable inflows and negative deltas observable
    outflows only when amount semantics are verified. BUY/SELL, LP, bridge,
    deployer, whale, bot, or beneficial-owner labels are never inferred here.
    """
    required = {
        "chain": _text(chain),
        "account_id": _text(account_id),
        "asset_id": _text(asset_id),
        "unit": _text(unit),
        "source": _text(source),
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError("CMIS wallet activity requires: " + ", ".join(missing))

    before = _amount(before_amount)
    after = _amount(after_amount)
    delta = after - before
    semantics_ok = bool(amount_semantics_verified)

    if not semantics_ok:
        direction = "UNVERIFIED"
    elif delta > 0:
        direction = "INFLOW"
    elif delta < 0:
        direction = "OUTFLOW"
    else:
        direction = "UNCHANGED"

    return {
        "schema_version": SCHEMA_VERSION,
        **required,
        "observed_at": observed_at,
        "block_slot": block_slot,
        "transaction_id": _text(transaction_id),
        "before_amount": _decimal_text(before),
        "after_amount": _decimal_text(after),
        "delta_amount": _decimal_text(delta),
        "direction": direction,
        "account_identity_verified": bool(account_identity_verified),
        "asset_identity_verified": bool(asset_identity_verified),
        "amount_semantics_verified": semantics_ok,
        "trade_direction_verified": False,
        "lp_action_verified": False,
        "bridge_action_verified": False,
        "deployer_identity_verified": False,
        "beneficial_owner_identity_verified": False,
        "wallet_classification": None,
        "cmis_promotable": False,
    }


__all__ = ["SCHEMA_VERSION", "build_balance_change_observation"]
