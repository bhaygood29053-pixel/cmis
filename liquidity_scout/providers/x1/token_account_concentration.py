"""Calculate X1 top-token-account share of total mint supply.

This module consumes contract-shaped ``getTokenLargestAccounts`` and
``getTokenSupply`` observations and calculates account-level concentration only.
Token accounts are not necessarily unique wallets or beneficial owners, so the
result must never be labeled holder concentration or holder coverage.

No network calls are performed here. Observation-scope/freshness remains an
explicit upstream concern and is never inferred from nearby RPC slots.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any


VERSION = "1.0"
LARGEST_METHOD = "getTokenLargestAccounts"
SUPPLY_METHOD = "getTokenSupply"
RPC_SOURCE = "X1 RPC"
BUCKETS = (1, 5, 10, 20)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _nonnegative_integer_text(value: Any) -> str | None:
    if not isinstance(value, str) or not value.isdigit():
        return None
    return value


def _decimals(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _slot(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _ratio_text(numerator: int, denominator: int) -> str:
    value = Decimal(numerator) / Decimal(denominator)
    rendered = format(value.quantize(Decimal("0.000000000000000001")), "f")
    rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _percent_text(numerator: int, denominator: int) -> str:
    value = Decimal(numerator) * Decimal(100) / Decimal(denominator)
    rendered = format(value.quantize(Decimal("0.000000000001")), "f")
    rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def analyze_x1_token_account_concentration(
    largest_accounts: Mapping[str, Any],
    token_supply: Mapping[str, Any],
    *,
    observation_scope_verified: bool = False,
) -> dict[str, Any]:
    """Calculate top-account shares while refusing holder semantics."""
    if not isinstance(largest_accounts, Mapping):
        raise TypeError("largest_accounts must be a mapping")
    if not isinstance(token_supply, Mapping):
        raise TypeError("token_supply must be a mapping")

    errors: list[str] = []
    warnings: list[str] = [
        "token_accounts_are_not_unique_holder_or_beneficial_owner_identities",
        "largest_accounts_rpc_is_partial_account_coverage_not_total_holder_coverage",
    ]

    if largest_accounts.get("chain") != "x1":
        errors.append("largest_accounts_wrong_chain")
    if token_supply.get("chain") != "x1":
        errors.append("token_supply_wrong_chain")
    if largest_accounts.get("source") != RPC_SOURCE:
        errors.append("largest_accounts_source_mismatch")
    if token_supply.get("source") != RPC_SOURCE:
        errors.append("token_supply_source_mismatch")
    if largest_accounts.get("method") != LARGEST_METHOD:
        errors.append("largest_accounts_method_mismatch")
    if token_supply.get("method") != SUPPLY_METHOD:
        errors.append("token_supply_method_mismatch")
    if largest_accounts.get("descending_amount_order_verified") is not True:
        errors.append("largest_accounts_order_unverified")
    if token_supply.get("mint_supply_observed") is not True:
        errors.append("mint_supply_observation_unverified")

    largest_mint = _text(largest_accounts.get("mint"))
    supply_mint = _text(token_supply.get("mint"))
    if largest_mint is None or supply_mint is None:
        errors.append("mint_missing")
    elif largest_mint != supply_mint:
        errors.append("mint_identity_mismatch")

    supply_amount_text = _nonnegative_integer_text(token_supply.get("amount"))
    supply_decimals = _decimals(token_supply.get("decimals"))
    if supply_amount_text is None:
        errors.append("supply_amount_invalid")
    if supply_decimals is None:
        errors.append("supply_decimals_invalid")

    accounts_value = largest_accounts.get("accounts")
    if not isinstance(accounts_value, list):
        errors.append("largest_accounts_list_invalid")
        accounts_value = []

    parsed_accounts: list[dict[str, Any]] = []
    seen: set[str] = set()
    previous_amount: int | None = None
    for index, item in enumerate(accounts_value):
        if not isinstance(item, Mapping):
            errors.append(f"account_{index}:invalid_record")
            continue
        address = _text(item.get("address"))
        amount_text = _nonnegative_integer_text(item.get("amount"))
        decimals = _decimals(item.get("decimals"))
        if address is None:
            errors.append(f"account_{index}:address_missing")
        elif address in seen:
            errors.append(f"account_{index}:duplicate_address")
        if amount_text is None:
            errors.append(f"account_{index}:amount_invalid")
        if decimals is None:
            errors.append(f"account_{index}:decimals_invalid")
        elif supply_decimals is not None and decimals != supply_decimals:
            errors.append(f"account_{index}:decimals_mismatch")

        if address is None or amount_text is None or decimals is None:
            continue
        amount = int(amount_text)
        if previous_amount is not None and amount > previous_amount:
            errors.append(f"account_{index}:descending_order_violation")
        previous_amount = amount
        seen.add(address)
        parsed_accounts.append(
            {
                "address": address,
                "amount": amount_text,
                "amount_base_units": amount,
                "decimals": decimals,
            }
        )

    largest_slot = _slot(largest_accounts.get("slot"))
    supply_slot = _slot(token_supply.get("slot"))
    if largest_slot is None:
        warnings.append("largest_accounts_slot_unavailable_or_invalid")
    if supply_slot is None:
        warnings.append("token_supply_slot_unavailable_or_invalid")
    rpc_slot_span = (
        abs(largest_slot - supply_slot)
        if largest_slot is not None and supply_slot is not None
        else None
    )

    scope_verified = bool(observation_scope_verified)
    if not scope_verified:
        warnings.append("observation_scope_unverified")

    if errors:
        return {
            "service": "x1_token_account_concentration",
            "version": VERSION,
            "chain": "x1",
            "status": "error",
            "mint": largest_mint if largest_mint == supply_mint else None,
            "data": {},
            "observation_scope_verified": scope_verified,
            "holder_concentration_verified": False,
            "beneficial_owner_identity_verified": False,
            "holder_coverage_verified": False,
            "cmis_promotable": False,
            "warnings": list(dict.fromkeys(warnings)),
            "errors": list(dict.fromkeys(errors)),
        }

    supply_amount = int(supply_amount_text)
    if supply_amount == 0:
        return {
            "service": "x1_token_account_concentration",
            "version": VERSION,
            "chain": "x1",
            "status": "unavailable",
            "mint": largest_mint,
            "data": {
                "mint_supply_base_units": "0",
                "decimals": supply_decimals,
                "observed_token_account_count": len(parsed_accounts),
                "largest_accounts_slot": largest_slot,
                "token_supply_slot": supply_slot,
                "rpc_slot_span": rpc_slot_span,
            },
            "observation_scope_verified": scope_verified,
            "holder_concentration_verified": False,
            "beneficial_owner_identity_verified": False,
            "holder_coverage_verified": False,
            "cmis_promotable": False,
            "warnings": list(dict.fromkeys(warnings + ["zero_mint_supply"])),
            "errors": [],
        }

    observed_sum = sum(item["amount_base_units"] for item in parsed_accounts)
    if any(item["amount_base_units"] > supply_amount for item in parsed_accounts):
        errors.append("token_account_amount_exceeds_mint_supply")
    if observed_sum > supply_amount:
        errors.append("observed_top_account_sum_exceeds_mint_supply")
    if errors:
        return {
            "service": "x1_token_account_concentration",
            "version": VERSION,
            "chain": "x1",
            "status": "error",
            "mint": largest_mint,
            "data": {},
            "observation_scope_verified": scope_verified,
            "holder_concentration_verified": False,
            "beneficial_owner_identity_verified": False,
            "holder_coverage_verified": False,
            "cmis_promotable": False,
            "warnings": list(dict.fromkeys(warnings)),
            "errors": list(dict.fromkeys(errors)),
        }

    bucket_results: dict[str, dict[str, Any]] = {}
    for count in BUCKETS:
        selected = parsed_accounts[:count]
        bucket_sum = sum(item["amount_base_units"] for item in selected)
        bucket_results[f"top_{count}"] = {
            "requested_account_count": count,
            "available_account_count": len(selected),
            "amount_base_units": str(bucket_sum),
            "share_of_mint_supply": _ratio_text(bucket_sum, supply_amount),
            "percent_of_mint_supply": _percent_text(bucket_sum, supply_amount),
        }

    if len(parsed_accounts) < max(BUCKETS):
        warnings.append("fewer_than_20_largest_token_accounts_observed")

    status = "ok" if scope_verified else "partial"
    return {
        "service": "x1_token_account_concentration",
        "version": VERSION,
        "chain": "x1",
        "status": status,
        "mint": largest_mint,
        "data": {
            "metric_semantics": "token_account_share_of_total_mint_supply",
            "mint_supply_base_units": supply_amount_text,
            "decimals": supply_decimals,
            "observed_token_account_count": len(parsed_accounts),
            "observed_top_account_sum_base_units": str(observed_sum),
            "observed_set_share_of_mint_supply": _ratio_text(
                observed_sum, supply_amount
            ),
            "observed_set_percent_of_mint_supply": _percent_text(
                observed_sum, supply_amount
            ),
            "buckets": bucket_results,
            "largest_accounts_slot": largest_slot,
            "token_supply_slot": supply_slot,
            "rpc_slot_span": rpc_slot_span,
        },
        "observation_scope_verified": scope_verified,
        "token_account_concentration_calculated": True,
        "holder_concentration_verified": False,
        "beneficial_owner_identity_verified": False,
        "holder_coverage_verified": False,
        "cmis_promotable": False,
        "warnings": list(dict.fromkeys(warnings)),
        "errors": [],
    }


__all__ = [
    "BUCKETS",
    "LARGEST_METHOD",
    "RPC_SOURCE",
    "SUPPLY_METHOD",
    "VERSION",
    "analyze_x1_token_account_concentration",
]
