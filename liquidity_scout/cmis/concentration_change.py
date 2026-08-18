"""Deterministic comparison of compatible top-account concentration observations.

The comparator reports numeric change only. It never interprets a change as
accumulation, distribution, whale behavior, insider activity, or manipulation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any, Mapping


_DISPLAY_PRECISION = 50


def _observed_at(name: str, value: Any) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime.")
    return value


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _fraction_decimal(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = _DISPLAY_PRECISION
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
        return format(decimal_value, "f")


def _exact_fraction(value: Fraction) -> dict[str, str]:
    return {
        "numerator": str(value.numerator),
        "denominator": str(value.denominator),
    }


def _validated_share(name: str, observation: Mapping[str, Any]) -> Fraction:
    if observation.get("schema") != "cmis_top_account_concentration.v1":
        raise ValueError(f"{name} must use cmis_top_account_concentration.v1.")

    total_supply = _positive_int(f"{name}.supply_raw", observation.get("supply_raw"))
    observed_balance = _nonnegative_int(
        f"{name}.observed_balance_raw", observation.get("observed_balance_raw")
    )
    if observed_balance > total_supply:
        raise ValueError(f"{name}.observed_balance_raw cannot exceed supply_raw.")

    exact = observation.get("observed_share_exact")
    if not isinstance(exact, Mapping):
        raise ValueError(f"{name}.observed_share_exact must be an exact ratio object.")
    exact_numerator = _nonnegative_int(
        f"{name}.observed_share_exact.numerator", exact.get("numerator")
    )
    exact_denominator = _positive_int(
        f"{name}.observed_share_exact.denominator", exact.get("denominator")
    )
    if exact_numerator != observed_balance or exact_denominator != total_supply:
        raise ValueError(
            f"{name}.observed_share_exact must match observed_balance_raw/supply_raw."
        )

    return Fraction(observed_balance, total_supply)


def _validate_scope_contract(name: str, observation: Mapping[str, Any]) -> None:
    requested_limit = _positive_int(
        f"{name}.requested_account_limit", observation.get("requested_account_limit")
    )
    observed_count = _positive_int(
        f"{name}.observed_account_count", observation.get("observed_account_count")
    )
    if observed_count > requested_limit:
        raise ValueError(f"{name}.observed_account_count exceeds requested_account_limit.")
    if observation.get("scope_limit_filled") is not (observed_count == requested_limit):
        raise ValueError(f"{name}.scope_limit_filled is inconsistent with observed account count.")

    accounts = observation.get("accounts")
    if not isinstance(accounts, list) or len(accounts) != observed_count:
        raise ValueError(f"{name}.accounts must match observed_account_count.")

    if observation.get("identity_verified") is not True:
        raise ValueError(f"{name} requires verified asset/account identity.")
    if observation.get("scope") != "observed_top_token_accounts":
        raise ValueError(f"{name} uses an unsupported concentration scope.")
    if observation.get("scope_complete") is not False:
        raise ValueError(f"{name} must remain explicitly incomplete scope.")
    if observation.get("holder_semantics_verified") is not False:
        raise ValueError(f"{name} holder semantics must remain unverified.")
    if observation.get("beneficial_owner_identity_verified") is not False:
        raise ValueError(f"{name} beneficial-owner identity must remain unverified.")
    if observation.get("cmis_promotable") is not False:
        raise ValueError(f"{name} must not be CMIS-promotable.")


def compare_top_account_concentration(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    before_observed_at: datetime,
    after_observed_at: datetime,
) -> dict[str, Any]:
    """Compare two compatible account-level concentration observations.

    Compatibility is deliberately strict: same chain, asset, source, decimals,
    top-N request scope, and observed account count, with verified identity on
    both observations. Exact raw ratios drive the comparison; decimal strings
    are presentation only.
    """
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise ValueError("before and after must be concentration observation objects.")

    before_time = _observed_at("before_observed_at", before_observed_at)
    after_time = _observed_at("after_observed_at", after_observed_at)
    if after_time <= before_time:
        raise ValueError("after_observed_at must be later than before_observed_at.")

    _validate_scope_contract("before", before)
    _validate_scope_contract("after", after)

    for field in (
        "chain",
        "asset_id",
        "source",
        "decimals",
        "scope",
        "requested_account_limit",
        "observed_account_count",
    ):
        if before.get(field) != after.get(field):
            raise ValueError(f"before and after must have matching {field}.")

    before_share = _validated_share("before", before)
    after_share = _validated_share("after", after)
    delta = after_share - before_share
    if delta > 0:
        direction = "INCREASE"
    elif delta < 0:
        direction = "DECREASE"
    else:
        direction = "NO_CHANGE"

    return {
        "schema": "cmis_top_account_concentration_change.v1",
        "chain": before["chain"],
        "asset_id": before["asset_id"],
        "source": before["source"],
        "scope": before["scope"],
        "requested_account_limit": before["requested_account_limit"],
        "observed_account_count": before["observed_account_count"],
        "before_observed_at": _iso_utc(before_time),
        "after_observed_at": _iso_utc(after_time),
        "before_share_exact": _exact_fraction(before_share),
        "after_share_exact": _exact_fraction(after_share),
        "delta_share_exact": _exact_fraction(delta),
        "before_share": _fraction_decimal(before_share),
        "after_share": _fraction_decimal(after_share),
        "delta_share": _fraction_decimal(delta),
        "delta_bps": _fraction_decimal(delta * 10000),
        "direction": direction,
        "identity_verified": True,
        "scope_complete": False,
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "behavioral_interpretation_verified": False,
        "cmis_promotable": False,
        "limitations": [
            "numeric_change_does_not_establish_accumulation_or_distribution",
            "token_accounts_are_not_unique_holder_identities",
            "observed_top_account_scope_is_incomplete",
            "comparison_requires_same_source_top_n_and_observed_account_count",
            "decimal_share_is_presentation_only_exact_ratio_drives_comparison",
        ],
    }


__all__ = ["compare_top_account_concentration"]
