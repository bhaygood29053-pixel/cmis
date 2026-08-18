"""Deterministic top-account concentration primitives.

This module measures concentration only across an explicit observed account set
against an independently supplied total-supply fact. It never equates token
accounts with wallets, people, beneficial owners, or complete holder coverage.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Any, Iterable, Mapping


_DISPLAY_PRECISION = 50


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


def _positive_int(name: str, value: Any) -> int:
    result = _nonnegative_int(name, value)
    if result == 0:
        raise ValueError(f"{name} must be a positive integer.")
    return result


def _bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean.")
    return value


def _decimal_ratio(numerator: int, denominator: int) -> str:
    """Return a deterministic decimal presentation for an exact raw ratio.

    The raw numerator/denominator remain the source of truth. This presentation
    is intentionally finite and must never be used as the exact comparison key.
    """
    with localcontext() as context:
        context.prec = _DISPLAY_PRECISION
        value = Decimal(numerator) / Decimal(denominator)
        return format(value, "f")


def build_top_account_concentration(
    *,
    chain: Any,
    asset_id: Any,
    source: Any,
    supply_raw: Any,
    supply_decimals: Any,
    requested_account_limit: Any,
    accounts: Iterable[Mapping[str, Any]],
    supply_identity_verified: bool,
    account_identity_verified: bool,
) -> dict[str, Any]:
    """Measure observed top-account concentration without holder semantics.

    ``accounts`` must contain unique ``address`` and raw base-unit ``amount``
    values using the same decimals as ``supply_raw``. ``requested_account_limit``
    records the top-N scope contract independently from how many rows were
    actually observed. The exact share is preserved as raw numerator/denominator
    evidence; decimal strings are presentation only.
    """
    chain_text = _text("chain", chain)
    asset_text = _text("asset_id", asset_id)
    source_text = _text("source", source)
    total_supply = _nonnegative_int("supply_raw", supply_raw)
    decimals = _nonnegative_int("supply_decimals", supply_decimals)
    requested_limit = _positive_int("requested_account_limit", requested_account_limit)
    supply_identity = _bool("supply_identity_verified", supply_identity_verified)
    account_identity = _bool("account_identity_verified", account_identity_verified)

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    observed_sum = 0
    previous_amount: int | None = None

    try:
        iterator = iter(accounts)
    except TypeError as exc:
        raise ValueError("accounts must be an iterable of account objects.") from exc

    for index, account in enumerate(iterator):
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

    observed_count = len(normalized)
    if observed_count > requested_limit:
        raise ValueError("observed account count exceeds requested_account_limit.")
    if total_supply > 0 and observed_count == 0:
        raise ValueError(
            "positive total supply requires at least one observed top account; "
            "empty evidence is not zero concentration."
        )
    if total_supply == 0 and observed_count > 0:
        raise ValueError("zero total supply requires an empty observed account set.")
    if total_supply > 0 and observed_sum > total_supply:
        raise ValueError("observed account balances exceed total supply.")

    if total_supply == 0:
        share_exact = None
        share = None
        share_bps = None
    else:
        share_exact = {
            "numerator": str(observed_sum),
            "denominator": str(total_supply),
        }
        share = _decimal_ratio(observed_sum, total_supply)
        share_bps = _decimal_ratio(observed_sum * 10000, total_supply)

    identity_verified = supply_identity and account_identity
    return {
        "schema": "cmis_top_account_concentration.v1",
        "chain": chain_text,
        "asset_id": asset_text,
        "source": source_text,
        "supply_raw": str(total_supply),
        "decimals": decimals,
        "requested_account_limit": requested_limit,
        "observed_account_count": observed_count,
        "scope_limit_filled": observed_count == requested_limit,
        "observed_balance_raw": str(observed_sum),
        "observed_share_exact": share_exact,
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
            "decimal_share_is_presentation_only_exact_ratio_is_raw_numerator_denominator",
        ],
    }


__all__ = ["build_top_account_concentration"]
