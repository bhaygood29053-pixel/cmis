"""Deterministic comparison of compatible top-account concentration observations.

The comparator reports numeric change only. It never interprets a change as
accumulation, distribution, whale behavior, insider activity, or manipulation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


def _observed_at(name: str, value: Any) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime.")
    return value


def _share(name: str, observation: Mapping[str, Any]) -> Decimal:
    if observation.get("schema") != "cmis_top_account_concentration.v1":
        raise ValueError(f"{name} must use cmis_top_account_concentration.v1.")
    if observation.get("observed_share") is None:
        raise ValueError(f"{name} must contain a calculable observed_share.")
    try:
        value = Decimal(str(observation["observed_share"]))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name}.observed_share must be numeric.") from exc
    if not value.is_finite() or value < 0 or value > 1:
        raise ValueError(f"{name}.observed_share must be finite and between 0 and 1.")
    return value


def compare_top_account_concentration(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    before_observed_at: datetime,
    after_observed_at: datetime,
) -> dict[str, Any]:
    """Compare two compatible account-level concentration observations."""
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise ValueError("before and after must be concentration observation objects.")

    before_time = _observed_at("before_observed_at", before_observed_at)
    after_time = _observed_at("after_observed_at", after_observed_at)
    if after_time <= before_time:
        raise ValueError("after_observed_at must be later than before_observed_at.")

    for field in ("chain", "asset_id", "decimals", "scope"):
        if before.get(field) != after.get(field):
            raise ValueError(f"before and after must have matching {field}.")

    if before.get("scope") != "observed_top_token_accounts":
        raise ValueError("unsupported concentration scope.")
    if before.get("scope_complete") is not False or after.get("scope_complete") is not False:
        raise ValueError("top-account observations must remain explicitly incomplete scope.")
    if before.get("holder_semantics_verified") is not False or after.get("holder_semantics_verified") is not False:
        raise ValueError("holder semantics must remain unverified for this comparator.")
    if before.get("beneficial_owner_identity_verified") is not False or after.get("beneficial_owner_identity_verified") is not False:
        raise ValueError("beneficial-owner identity must remain unverified for this comparator.")
    if before.get("cmis_promotable") is not False or after.get("cmis_promotable") is not False:
        raise ValueError("input concentration observations must not be CMIS-promotable.")

    before_share = _share("before", before)
    after_share = _share("after", after)
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
        "scope": before["scope"],
        "before_observed_at": before_time.isoformat(),
        "after_observed_at": after_time.isoformat(),
        "before_share": format(before_share, "f"),
        "after_share": format(after_share, "f"),
        "delta_share": format(delta, "f"),
        "delta_bps": format(delta * Decimal(10000), "f"),
        "direction": direction,
        "scope_complete": False,
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "behavioral_interpretation_verified": False,
        "cmis_promotable": False,
        "limitations": [
            "numeric_change_does_not_establish_accumulation_or_distribution",
            "token_accounts_are_not_unique_holder_identities",
            "observed_top_account_scope_is_incomplete",
        ],
    }


__all__ = ["compare_top_account_concentration"]
