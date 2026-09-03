"""Bounded completeness evidence for X1 positive-balance token populations.

This module does not define beneficial owners or persons. It evaluates whether a
mint-filtered X1 RPC token-account enumeration accounts for the full verified
mint supply over a tightly bounded slot span, then derives distribution metrics
for the exact token-account authority addresses present in that observation.

One matching observation is evidence, not a promotion. Repeated observations are
required before positive-balance population coverage may be marked verified.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any

from liquidity_scout.providers.x1.rpc_token_account_enumeration import (
    RPC_METHOD as ENUMERATION_METHOD,
    RPC_SOURCE,
)
from liquidity_scout.providers.x1.rpc_token_supply import (
    RPC_METHOD as SUPPLY_METHOD,
)


VERSION = "1.0"
DEFAULT_MAX_SLOT_SPAN = 2
DEFAULT_MINIMUM_OBSERVATIONS = 3
AUTHORITY_BUCKETS = (1, 5, 10, 20)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _slot(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _raw_amount(value: Any) -> int | None:
    if not isinstance(value, str) or not value.isdigit():
        return None
    return int(value)


def _percent(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator * 100.0 / denominator, 12)


def evaluate_x1_positive_balance_population_observation(
    enumeration: Mapping[str, Any],
    supply: Mapping[str, Any],
    *,
    max_slot_span: int = DEFAULT_MAX_SLOT_SPAN,
) -> dict[str, Any]:
    """Evaluate one supply-conservation observation without overclaiming."""

    if not isinstance(enumeration, Mapping):
        raise TypeError("enumeration must be a mapping")
    if not isinstance(supply, Mapping):
        raise TypeError("supply must be a mapping")
    if isinstance(max_slot_span, bool) or not isinstance(max_slot_span, int) or max_slot_span < 0:
        raise ValueError("max_slot_span must be a non-negative integer")

    mint = _text(enumeration.get("mint"))
    program = _text(enumeration.get("token_program_id"))
    enum_slot = _slot(enumeration.get("slot"))
    supply_slot = _slot(supply.get("slot"))
    supply_amount = _raw_amount(supply.get("amount"))
    supply_decimals = supply.get("decimals")

    errors: list[str] = []
    if enumeration.get("chain") != "x1":
        errors.append("enumeration_wrong_chain")
    if enumeration.get("source") != RPC_SOURCE:
        errors.append("enumeration_source_mismatch")
    if enumeration.get("method") != ENUMERATION_METHOD:
        errors.append("enumeration_method_mismatch")
    if enumeration.get("returned_account_identity_verified") is not True:
        errors.append("enumeration_identity_unverified")
    if enumeration.get("token_account_semantics_verified") is not True:
        errors.append("token_account_semantics_unverified")
    if mint is None or program is None:
        errors.append("enumeration_identity_incomplete")
    if enum_slot is None:
        errors.append("enumeration_slot_invalid")

    if supply.get("chain") != "x1":
        errors.append("supply_wrong_chain")
    if supply.get("source") != RPC_SOURCE:
        errors.append("supply_source_mismatch")
    if supply.get("method") != SUPPLY_METHOD:
        errors.append("supply_method_mismatch")
    if supply.get("mint_supply_observed") is not True:
        errors.append("mint_supply_unverified")
    if _text(supply.get("mint")) != mint:
        errors.append("supply_mint_mismatch")
    if supply_slot is None:
        errors.append("supply_slot_invalid")
    if supply_amount is None:
        errors.append("supply_amount_invalid")
    if isinstance(supply_decimals, bool) or not isinstance(supply_decimals, int) or supply_decimals < 0:
        errors.append("supply_decimals_invalid")

    accounts = enumeration.get("accounts")
    if not isinstance(accounts, list):
        errors.append("enumeration_accounts_invalid")
        accounts = []

    seen: set[str] = set()
    returned_balance = 0
    positive_accounts = 0
    authority_balances: dict[str, int] = defaultdict(int)
    account_rows: list[tuple[str, str, int]] = []

    for index, item in enumerate(accounts):
        if not isinstance(item, Mapping):
            errors.append(f"account_{index}_malformed")
            continue
        address = _text(item.get("address"))
        authority = _text(item.get("owner"))
        raw = _raw_amount(item.get("raw_amount"))
        decimals = item.get("decimals")
        if address is None:
            errors.append(f"account_{index}_address_missing")
            continue
        if address in seen:
            errors.append("duplicate_account_address")
            continue
        seen.add(address)
        if _text(item.get("mint")) != mint:
            errors.append(f"account_{index}_mint_mismatch")
        if _text(item.get("token_program_id")) != program:
            errors.append(f"account_{index}_program_mismatch")
        if raw is None:
            errors.append(f"account_{index}_amount_invalid")
            continue
        if decimals != supply_decimals:
            errors.append(f"account_{index}_decimals_mismatch")
            continue

        returned_balance += raw
        if raw > 0:
            positive_accounts += 1
            if authority is None:
                errors.append(f"account_{index}_positive_balance_authority_missing")
            else:
                authority_balances[authority] += raw
                account_rows.append((address, authority, raw))

    slot_span = (
        abs(enum_slot - supply_slot)
        if enum_slot is not None and supply_slot is not None
        else None
    )
    slot_scope_bounded = slot_span is not None and slot_span <= max_slot_span
    conservation = supply_amount is not None and returned_balance == supply_amount

    sorted_authorities = sorted(
        authority_balances.items(),
        key=lambda item: (-item[1], item[0]),
    )
    authority_buckets: dict[str, dict[str, Any]] = {}
    if supply_amount is not None:
        for count in AUTHORITY_BUCKETS:
            selected = sorted_authorities[:count]
            amount = sum(value for _authority, value in selected)
            authority_buckets[f"top_{count}"] = {
                "requested_authority_count": count,
                "available_authority_count": len(selected),
                "amount_base_units": str(amount),
                "percent_of_mint_supply": _percent(amount, supply_amount),
            }

    candidate_complete = (
        not errors
        and conservation
        and slot_scope_bounded
        and len(authority_balances) <= positive_accounts
    )

    digest = sha256(
        "\n".join(
            f"{address}|{authority}|{raw}"
            for address, authority, raw in sorted(account_rows)
        ).encode("utf-8")
    ).hexdigest()

    return {
        "service": "x1_positive_balance_population_observation",
        "version": VERSION,
        "chain": "x1",
        "status": "ok" if candidate_complete else "partial",
        "mint": mint,
        "token_program_id": program,
        "enumeration_slot": enum_slot,
        "supply_slot": supply_slot,
        "slot_span": slot_span,
        "max_slot_span": max_slot_span,
        "slot_scope_bounded": slot_scope_bounded,
        "returned_balance_base_units": str(returned_balance),
        "verified_mint_supply_base_units": (
            str(supply_amount) if supply_amount is not None else None
        ),
        "supply_conservation_observed": conservation,
        "positive_balance_token_account_count": positive_accounts,
        "unique_positive_balance_authority_address_count": len(authority_balances),
        "authority_address_distribution": {
            "counted_entity": "token_account_authority_address",
            "beneficial_owner_semantics_verified": False,
            "buckets": authority_buckets,
        },
        "population_evidence_sha256": digest,
        "positive_balance_population_candidate_complete": candidate_complete,
        "positive_balance_population_coverage_verified": False,
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
        "errors": list(dict.fromkeys(errors)),
        "warnings": [
            "single_observation_does_not_prove_repeatable_rpc_population_completeness",
            "token_account_authority_addresses_are_not_beneficial_owner_identities",
        ],
        "execution_authorized": False,
    }


def verify_x1_positive_balance_population_series(
    observations: Sequence[Mapping[str, Any]],
    *,
    minimum_observations: int = DEFAULT_MINIMUM_OBSERVATIONS,
) -> dict[str, Any]:
    """Promote only repeated bounded supply-conservation evidence."""

    if (
        isinstance(minimum_observations, bool)
        or not isinstance(minimum_observations, int)
        or minimum_observations < 2
    ):
        raise ValueError("minimum_observations must be an integer >= 2")

    usable = [dict(item) for item in observations if isinstance(item, Mapping)]
    if len(usable) < minimum_observations:
        raise ValueError(
            f"at least {minimum_observations} observations are required"
        )

    mints = {_text(item.get("mint")) for item in usable}
    programs = {_text(item.get("token_program_id")) for item in usable}
    all_candidates_complete = all(
        item.get("positive_balance_population_candidate_complete") is True
        and item.get("supply_conservation_observed") is True
        and item.get("slot_scope_bounded") is True
        and not item.get("errors")
        for item in usable
    )
    identity_stable = len(mints) == 1 and None not in mints and len(programs) == 1 and None not in programs

    coverage_verified = all_candidates_complete and identity_stable

    return {
        "service": "x1_positive_balance_population_series",
        "version": VERSION,
        "chain": "x1",
        "status": "ok" if coverage_verified else "partial",
        "mint": next(iter(mints)) if len(mints) == 1 else None,
        "token_program_id": next(iter(programs)) if len(programs) == 1 else None,
        "observation_count": len(usable),
        "minimum_observations": minimum_observations,
        "all_supply_conservation_observations_passed": all_candidates_complete,
        "identity_stable": identity_stable,
        "positive_balance_population_coverage_verified": coverage_verified,
        "counted_entity": "positive_balance_token_account",
        "authority_distribution_counted_entity": "token_account_authority_address",
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
        "warnings": [
            "verified_positive_balance_population_is_not_beneficial_owner_population",
            "authority_addresses_may_include_wallets_program_derived_addresses_or_other_controllers",
        ],
        "execution_authorized": False,
    }


__all__ = [
    "AUTHORITY_BUCKETS",
    "DEFAULT_MAX_SLOT_SPAN",
    "DEFAULT_MINIMUM_OBSERVATIONS",
    "VERSION",
    "evaluate_x1_positive_balance_population_observation",
    "verify_x1_positive_balance_population_series",
]
