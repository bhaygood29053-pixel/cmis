"""Deterministic top-account concentration primitives.

This module measures concentration only across an explicit observed account set
against an independently supplied total-supply fact. It never equates token
accounts with wallets, people, beneficial owners, or complete holder coverage.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, getcontext
from typing import Any, Iterable, Mapping

getcontext().prec = 50


def _text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty.")
    return text


def _nonnegative_int(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative integer.")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isdigit():
        result = int(value)
    else:
        raise ValueError(f"{name} must be a non-negative integer.")
    if result < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return result


def _bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean.")
    return value


def build_top_account_concentration(
    *,
    chain: Any,
    asset_id: Any,
    source: Any,
    supply_raw: Any,
    supply_decimals: Any,
    accounts: Iterable[Mapping[str, Any]],
    supply_identity_verified: bool,
    account_identity_verified: bool,
) -> dict[str, Any]:
    """Measure observed top-account concentration without holder semantics.

    ``accounts`` must contain unique ``address`` and raw base-unit ``amount``
    values using the same decimals as ``supply_raw``. The function reports only
    the share represented by the supplied observed account set.
    """
    chain_text = _text("chain", chain)
    asset_text = _text("asset_id", asset_id)
    source_text = _text("source", source)
    total_supply = _nonnegative_int("supply_raw", supply_raw)
    decimals = _nonnegative_int("supply_decimals", supply_decimals)
    supply_identity = _bool("supply_identity_verified", supply_identity_verified)
    account_identity = _bool("account_identity_verified", account_identity_verified)

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    observed_sum = 0
    previous_amount: int | None = None

    for index, account in enumerate(accounts):
        if not isinstance(account, Mapping):
            raise ValueError(f"accounts[{index}] must be an object.")
        address = _text(f"accounts[{index}].address", account.get("address"))
        if address in seen:
            raise ValueError("accounts must not contain duplicate addresses.")
        amount = _nonnegative_int(f"accounts[{index}].amount", account.get("amount"))
        account_decimals = _nonnegative_int(
            f"accounts[{index}].decimals", account.get("decimals")
        )
        if account_decimals != decimals:
            raise ValueError("account decimals must match supply decimals.")
        if previous_amount is not None and amount > previous_amount:
            raise ValueError("accounts must be ordered by descending raw amount.")
        previous_amount = amount
        seen.add(address)
        observed_sum += amount
        normalized.append(
            {"address": address, "amount": str(amount), "decimals": decimals}
        )

    if total_supply == 0 and observed_sum > 0:
        raise ValueError("positive observed balances cannot exceed zero total supply.")
    if total_supply > 0 and observed_sum > total_supply:
        raise ValueError("observed account balances exceed total supply.")

    if total_supply == 0:
        share = None
        share_bps = None
    else:
        try:
            share_decimal = Decimal(observed_sum) / Decimal(total_supply)
        except (InvalidOperation, ZeroDivisionError) as exc:  # pragma: no cover
            raise ValueError("unable to calculate concentration share.") from exc
        share = format(share_decimal, "f")
        share_bps = format(share_decimal * Decimal(10000), "f")

    identity_verified = supply_identity and account_identity
    return {
        "schema": "cmis_top_account_concentration.v1",
        "chain": chain_text,
        "asset_id": asset_text,
        "source": source_text,
        "supply_raw": str(total_supply),
        "decimals": decimals,
        "observed_account_count": len(normalized),
        "observed_balance_raw": str(observed_sum),
        "observed_share": share,
        "observed_share_bps": share_bps,
        "accounts": normalized,
        "identity_verified": identity_verified,
        "scope": "observed_top_token_accounts",
        "scope_complete": False,
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
        "limitations": [
            "token_accounts_are_not_unique_holder_identities",
            "observed_top_account_set_is_not_total_holder_coverage",
            "concentration_is_account_level_not_beneficial_owner_level",
        ],
    }


__all__ = ["build_top_account_concentration"]
