"""Deterministic wallet-activity primitives for future CMIS intelligence.

This module does not discover wallets, classify behavior, infer counterparties,
or fetch chain/provider data. It accepts already-observed activity facts and
fails closed unless the proof gates required for a primitive are explicit.
Missing amounts/values remain unknown and are never converted to zero.

The output is intentionally factual. Terms such as insider, whale, bot,
accumulator, distributor, market maker, or manipulator do not exist in this
contract.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any


SCHEMA_VERSION = 1
ACTIVITY_TYPES = frozenset(
    {
        "TRANSFER_IN",
        "TRANSFER_OUT",
        "BUY",
        "SELL",
        "LP_ADD",
        "LP_REMOVE",
        "DEPLOYER_ORIGINATED_TRANSFER",
        "BALANCE_CHANGE",
    }
)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal_text(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not parsed.is_finite():
        return None
    normalized = format(parsed, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if normalized in {"", "-0"} else normalized


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _observation_id(record: Mapping[str, Any]) -> str:
    return "wa_" + hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()


def build_wallet_activity_observation(
    *,
    chain: Any,
    wallet: Any,
    activity_type: Any,
    transaction_signature: Any,
    observed_at: Any,
    verification_method: Any,
    evidence_scope: Any,
    asset_id: Any = None,
    asset_amount: Any = None,
    asset_unit: Any = None,
    quote_value: Any = None,
    quote_unit: Any = None,
    block_slot: Any = None,
    counterparty: Any = None,
    balance_before: Any = None,
    balance_after: Any = None,
    wallet_identity_verified: bool = False,
    asset_identity_verified: bool = False,
    amount_verified: bool = False,
    trade_direction_verified: bool = False,
    lp_action_verified: bool = False,
    deployer_identity_verified: bool = False,
    quote_value_verified: bool = False,
    counterparty_verified: bool = False,
    limitations: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build one validated factual wallet observation.

    Activity semantics are caller-supplied only after an upstream deterministic
    verifier establishes them. This builder re-checks the minimum gates needed
    before the fact can enter CMIS wallet intelligence.
    """

    chain_text = _text(chain)
    wallet_text = _text(wallet)
    activity = (_text(activity_type) or "").upper()
    signature = _text(transaction_signature)
    method = _text(verification_method)
    scope = _text(evidence_scope)
    if not all((chain_text, wallet_text, signature, method, scope)):
        raise ValueError(
            "wallet activity requires chain, wallet, transaction_signature, "
            "verification_method, and evidence_scope"
        )
    if activity not in ACTIVITY_TYPES:
        raise ValueError(f"unsupported wallet activity_type: {activity!r}")
    if wallet_identity_verified is not True:
        raise ValueError("wallet activity requires verified wallet identity")

    asset = _text(asset_id)
    amount = _decimal_text(asset_amount)
    unit = _text(asset_unit)
    quote = _decimal_text(quote_value)
    quote_unit_text = _text(quote_unit)
    before = _decimal_text(balance_before)
    after = _decimal_text(balance_after)

    if activity != "BALANCE_CHANGE" and asset is None:
        raise ValueError("asset_id is required for this wallet activity type")
    if asset is not None and asset_identity_verified is not True:
        raise ValueError("asset-scoped wallet activity requires verified asset identity")

    if amount_verified:
        if amount is None or unit is None:
            raise ValueError("verified amount requires asset_amount and asset_unit")
    elif amount is not None or unit is not None:
        raise ValueError("unverified asset amount/unit must not be exposed")

    if quote_value_verified:
        if quote is None or quote_unit_text is None:
            raise ValueError("verified quote value requires quote_value and quote_unit")
    elif quote is not None or quote_unit_text is not None:
        raise ValueError("unverified quote value/unit must not be exposed")

    if activity in {"BUY", "SELL"} and trade_direction_verified is not True:
        raise ValueError("BUY/SELL wallet facts require verified trade direction")
    if activity in {"LP_ADD", "LP_REMOVE"} and lp_action_verified is not True:
        raise ValueError("LP wallet facts require verified LP action semantics")
    if (
        activity == "DEPLOYER_ORIGINATED_TRANSFER"
        and deployer_identity_verified is not True
    ):
        raise ValueError(
            "deployer-originated transfer requires independently verified deployer identity"
        )

    counterparty_text = _text(counterparty)
    if counterparty_verified and counterparty_text is None:
        raise ValueError("verified counterparty requires counterparty identity")
    if counterparty_text is not None and counterparty_verified is not True:
        raise ValueError("unverified counterparty identity must not be exposed")

    if activity == "BALANCE_CHANGE":
        if before is None or after is None or unit is None:
            raise ValueError(
                "BALANCE_CHANGE requires verified balance_before, balance_after, and asset_unit"
            )
        if amount_verified is not True:
            raise ValueError("BALANCE_CHANGE requires amount_verified=true")
        amount = _decimal_text(Decimal(after) - Decimal(before))

    base = {
        "schema_version": SCHEMA_VERSION,
        "chain": chain_text.lower(),
        "wallet": wallet_text,
        "activity_type": activity,
        "transaction_signature": signature,
        "observed_at": observed_at,
        "block_slot": block_slot,
        "verification_method": method,
        "evidence_scope": scope,
        "asset_id": asset,
        "asset_amount": amount if amount_verified else None,
        "asset_unit": unit if amount_verified else None,
        "quote_value": quote if quote_value_verified else None,
        "quote_unit": quote_unit_text if quote_value_verified else None,
        "counterparty": counterparty_text if counterparty_verified else None,
        "balance_before": before if activity == "BALANCE_CHANGE" else None,
        "balance_after": after if activity == "BALANCE_CHANGE" else None,
        "verification": {
            "wallet_identity_verified": True,
            "asset_identity_verified": bool(asset_identity_verified),
            "amount_verified": bool(amount_verified),
            "trade_direction_verified": bool(trade_direction_verified),
            "lp_action_verified": bool(lp_action_verified),
            "deployer_identity_verified": bool(deployer_identity_verified),
            "quote_value_verified": bool(quote_value_verified),
            "counterparty_verified": bool(counterparty_verified),
        },
        "limitations": sorted(
            {text for text in (_text(item) for item in (limitations or ())) if text}
        ),
        "classification_labels": [],
        "classification_authorized": False,
    }
    return {"observation_id": _observation_id(base), **base}


def summarize_wallet_activity(
    *,
    chain: Any,
    wallet: Any,
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate verified wallet primitives without inferring behavior labels."""

    chain_text = (_text(chain) or "").lower()
    wallet_text = _text(wallet)
    if not chain_text or wallet_text is None:
        raise ValueError("chain and wallet are required")

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in observations:
        if not isinstance(item, Mapping):
            raise TypeError("wallet observations must be mappings")
        if item.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported wallet activity schema")
        if _text(item.get("chain")) != chain_text:
            raise ValueError("wallet observation chain mismatch")
        if _text(item.get("wallet")) != wallet_text:
            raise ValueError("wallet observation identity mismatch")
        if item.get("classification_authorized") is not False:
            raise ValueError("wallet observation classification boundary violated")
        observation_id = _text(item.get("observation_id"))
        if observation_id is None or not observation_id.startswith("wa_"):
            raise ValueError("wallet observation id is invalid")
        if observation_id in seen_ids:
            continue
        seen_ids.add(observation_id)
        records.append(dict(item))

    observed_times = sorted(
        text for text in (_text(item.get("observed_at")) for item in records) if text
    )
    signatures = sorted(
        {
            text
            for text in (_text(item.get("transaction_signature")) for item in records)
            if text
        }
    )
    type_counts = {activity: 0 for activity in sorted(ACTIVITY_TYPES)}
    for item in records:
        activity = _text(item.get("activity_type"))
        if activity in type_counts:
            type_counts[activity] += 1

    # Amounts are aggregated only within identical asset + unit + primitive
    # direction. No price conversion or cross-asset summation is attempted.
    amount_totals: dict[tuple[str, str, str], Decimal] = defaultdict(Decimal)
    quote_totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for item in records:
        activity = _text(item.get("activity_type")) or ""
        asset = _text(item.get("asset_id"))
        amount = _decimal_text(item.get("asset_amount"))
        unit = _text(item.get("asset_unit"))
        if asset and amount is not None and unit:
            amount_totals[(asset, unit, activity)] += Decimal(amount)

        quote = _decimal_text(item.get("quote_value"))
        quote_unit = _text(item.get("quote_unit"))
        if quote is not None and quote_unit:
            quote_totals[(quote_unit, activity)] += Decimal(quote)

    by_asset: dict[str, dict[str, Any]] = {}
    for (asset, unit, activity), total in sorted(amount_totals.items()):
        asset_record = by_asset.setdefault(asset, {"units": {}})
        unit_record = asset_record["units"].setdefault(unit, {})
        unit_record[activity.lower()] = _decimal_text(total)

    verified_volume_by_unit: dict[str, str] = {}
    for (unit, activity), total in quote_totals.items():
        if activity in {"BUY", "SELL"}:
            verified_volume_by_unit[unit] = _decimal_text(
                Decimal(verified_volume_by_unit.get(unit, "0")) + total
            ) or "0"

    return {
        "schema_version": SCHEMA_VERSION,
        "chain": chain_text,
        "wallet": wallet_text,
        "first_observed_activity": observed_times[0] if observed_times else None,
        "last_observed_activity": observed_times[-1] if observed_times else None,
        "activity_window": {
            "start": observed_times[0] if observed_times else None,
            "end": observed_times[-1] if observed_times else None,
            "continuous_coverage_proven": False,
            "complete_wallet_history_proven": False,
        },
        "unique_transaction_count": len(signatures),
        "observation_count": len(records),
        "activity_counts": type_counts,
        "verified_amounts_by_asset": by_asset,
        "verified_trade_volume_by_quote_unit": dict(sorted(verified_volume_by_unit.items())),
        "observations": sorted(
            records,
            key=lambda item: (
                _text(item.get("observed_at")) or "",
                _text(item.get("transaction_signature")) or "",
                _text(item.get("observation_id")) or "",
            ),
        ),
        "classifications": [],
        "classification_authorized": False,
        "limitations": [
            "observed_activity_only",
            "continuous_wallet_history_not_proven",
            "behavioral_or_identity_labels_not_authorized",
        ],
    }


__all__ = [
    "ACTIVITY_TYPES",
    "SCHEMA_VERSION",
    "build_wallet_activity_observation",
    "summarize_wallet_activity",
]
