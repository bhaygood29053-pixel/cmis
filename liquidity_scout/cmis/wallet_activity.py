"""Deterministic wallet-activity facts for CMIS Phase 11.

This module accepts already-observed facts. It does not discover wallets,
classify behavior, infer ownership, fetch provider data, or authorize execution.
Every activity label exposed here is gated by an explicit deterministic proof
flag, and every stored observation is content-addressed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
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
_VERIFICATION_FIELDS = (
    "wallet_identity_verified",
    "asset_identity_verified",
    "transaction_identity_verified",
    "amount_verified",
    "transfer_direction_verified",
    "trade_direction_verified",
    "lp_action_verified",
    "deployer_identity_verified",
    "token_account_ownership_verified",
    "quote_value_verified",
    "counterparty_verified",
)


def _text(name: str, value: Any, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    text = value.strip()
    if not text:
        if required:
            raise ValueError(f"{name} is required")
        return None
    return text


def _strict_bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _nonnegative_int(name: str, value: Any, *, required: bool = False) -> int | None:
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isdigit():
        result = int(value)
    else:
        raise ValueError(f"{name} must be a non-negative integer")
    if result < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return result


def _decimal_text(
    name: str,
    value: Any,
    *,
    required: bool = False,
    allow_negative: bool = False,
    allow_zero: bool = True,
) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite numeric value")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite numeric value") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be a finite numeric value")
    if not allow_negative and parsed < 0:
        raise ValueError(f"{name} must not be negative")
    if not allow_zero and parsed == 0:
        raise ValueError(f"{name} must be greater than zero")
    normalized = format(parsed, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if normalized in {"", "-0"} else normalized


def _canonical_utc_timestamp(name: str, value: Any) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    else:
        raise ValueError(f"{name} must be a timezone-aware datetime or ISO-8601 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp_value(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _limitations(values: Sequence[Any] | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise ValueError("limitations must be a sequence of strings")
    normalized: set[str] = set()
    for index, value in enumerate(values):
        text = _text(f"limitations[{index}]", value, required=True)
        assert text is not None
        normalized.add(text)
    return sorted(normalized)


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
    source: Any,
    verification_method: Any,
    evidence_scope: Any,
    asset_id: Any,
    block_slot: Any = None,
    asset_amount: Any = None,
    asset_unit: Any = None,
    quote_value: Any = None,
    quote_unit: Any = None,
    counterparty: Any = None,
    deployer_id: Any = None,
    token_account: Any = None,
    balance_before: Any = None,
    balance_after: Any = None,
    wallet_identity_verified: bool = False,
    asset_identity_verified: bool = False,
    transaction_identity_verified: bool = False,
    amount_verified: bool = False,
    transfer_direction_verified: bool = False,
    trade_direction_verified: bool = False,
    lp_action_verified: bool = False,
    deployer_identity_verified: bool = False,
    token_account_ownership_verified: bool = False,
    quote_value_verified: bool = False,
    counterparty_verified: bool = False,
    limitations: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build one verified, factual wallet-activity observation.

    The builder deliberately separates observed facts from behavioral labels.
    Missing amounts stay ``None``. Directional activity names are emitted only
    when their corresponding direction/action proof is explicitly ``True``.
    """

    flags = {
        name: _strict_bool(name, value)
        for name, value in {
            "wallet_identity_verified": wallet_identity_verified,
            "asset_identity_verified": asset_identity_verified,
            "transaction_identity_verified": transaction_identity_verified,
            "amount_verified": amount_verified,
            "transfer_direction_verified": transfer_direction_verified,
            "trade_direction_verified": trade_direction_verified,
            "lp_action_verified": lp_action_verified,
            "deployer_identity_verified": deployer_identity_verified,
            "token_account_ownership_verified": token_account_ownership_verified,
            "quote_value_verified": quote_value_verified,
            "counterparty_verified": counterparty_verified,
        }.items()
    }

    chain_text = _text("chain", chain, required=True)
    wallet_text = _text("wallet", wallet, required=True)
    activity = (_text("activity_type", activity_type, required=True) or "").upper()
    signature = _text("transaction_signature", transaction_signature, required=True)
    source_text = _text("source", source, required=True)
    method = _text("verification_method", verification_method, required=True)
    scope = _text("evidence_scope", evidence_scope, required=True)
    asset = _text("asset_id", asset_id, required=True)
    timestamp = _canonical_utc_timestamp("observed_at", observed_at)
    slot = _nonnegative_int("block_slot", block_slot)

    if activity not in ACTIVITY_TYPES:
        raise ValueError(f"unsupported wallet activity_type: {activity!r}")
    if flags["wallet_identity_verified"] is not True:
        raise ValueError("wallet activity requires verified wallet identity")
    if flags["asset_identity_verified"] is not True:
        raise ValueError("wallet activity requires verified asset identity")
    if flags["transaction_identity_verified"] is not True:
        raise ValueError("wallet activity requires verified transaction identity")

    unit = _text("asset_unit", asset_unit)
    amount_input = asset_amount
    amount = None

    if activity == "BALANCE_CHANGE":
        if amount_input is not None:
            raise ValueError("BALANCE_CHANGE asset_amount is derived and must not be supplied")
        if flags["amount_verified"] is not True:
            raise ValueError("BALANCE_CHANGE requires amount_verified=true")
        token_account_text = _text("token_account", token_account, required=True)
        if flags["token_account_ownership_verified"] is not True:
            raise ValueError("BALANCE_CHANGE requires verified token-account ownership")
        if unit is None:
            raise ValueError("BALANCE_CHANGE requires asset_unit")
        before = _decimal_text(
            "balance_before", balance_before, required=True, allow_negative=False
        )
        after = _decimal_text(
            "balance_after", balance_after, required=True, allow_negative=False
        )
        assert before is not None and after is not None
        amount = _decimal_text(
            "derived_balance_delta",
            Decimal(after) - Decimal(before),
            required=True,
            allow_negative=True,
        )
    else:
        token_account_text = _text("token_account", token_account)
        if token_account_text is not None or flags["token_account_ownership_verified"]:
            raise ValueError("token_account fields are supported only for BALANCE_CHANGE")
        if balance_before is not None or balance_after is not None:
            raise ValueError("balance fields are supported only for BALANCE_CHANGE")
        before = None
        after = None
        if flags["amount_verified"]:
            if unit is None:
                raise ValueError("verified amount requires asset_unit")
            amount = _decimal_text(
                "asset_amount",
                amount_input,
                required=True,
                allow_negative=False,
                allow_zero=False,
            )
        elif amount_input is not None or unit is not None:
            raise ValueError("unverified asset amount/unit must not be exposed")

    if activity in {"TRANSFER_IN", "TRANSFER_OUT", "DEPLOYER_ORIGINATED_TRANSFER"}:
        if flags["transfer_direction_verified"] is not True:
            raise ValueError("transfer wallet facts require verified transfer direction")
    if activity in {"BUY", "SELL"} and flags["trade_direction_verified"] is not True:
        raise ValueError("BUY/SELL wallet facts require verified trade direction")
    if activity in {"LP_ADD", "LP_REMOVE"} and flags["lp_action_verified"] is not True:
        raise ValueError("LP wallet facts require verified LP action semantics")

    counterparty_text = _text("counterparty", counterparty)
    if flags["counterparty_verified"] and counterparty_text is None:
        raise ValueError("verified counterparty requires counterparty identity")
    if counterparty_text is not None and flags["counterparty_verified"] is not True:
        raise ValueError("unverified counterparty identity must not be exposed")

    deployer = _text("deployer_id", deployer_id)
    if activity == "DEPLOYER_ORIGINATED_TRANSFER":
        if flags["deployer_identity_verified"] is not True or deployer is None:
            raise ValueError(
                "deployer-originated transfer requires independently verified deployer identity"
            )
        if flags["counterparty_verified"] is not True or counterparty_text != deployer:
            raise ValueError(
                "deployer-originated transfer requires the verified deployer as counterparty"
            )
    elif deployer is not None or flags["deployer_identity_verified"]:
        raise ValueError("deployer fields are supported only for DEPLOYER_ORIGINATED_TRANSFER")

    quote_unit_text = _text("quote_unit", quote_unit)
    if flags["quote_value_verified"]:
        if activity not in {"BUY", "SELL"}:
            raise ValueError("verified quote value is supported only for BUY/SELL facts")
        if quote_unit_text is None:
            raise ValueError("verified quote value requires quote_unit")
        quote = _decimal_text(
            "quote_value",
            quote_value,
            required=True,
            allow_negative=False,
            allow_zero=False,
        )
    else:
        if quote_value is not None or quote_unit_text is not None:
            raise ValueError("unverified quote value/unit must not be exposed")
        quote = None

    base = {
        "schema_version": SCHEMA_VERSION,
        "chain": chain_text.lower(),
        "wallet": wallet_text,
        "activity_type": activity,
        "transaction_signature": signature,
        "observed_at": timestamp,
        "block_slot": slot,
        "source": source_text,
        "verification_method": method,
        "evidence_scope": scope,
        "asset_id": asset,
        "asset_amount": amount if flags["amount_verified"] else None,
        "asset_unit": unit if flags["amount_verified"] else None,
        "quote_value": quote if flags["quote_value_verified"] else None,
        "quote_unit": quote_unit_text if flags["quote_value_verified"] else None,
        "counterparty": counterparty_text if flags["counterparty_verified"] else None,
        "deployer_id": deployer if activity == "DEPLOYER_ORIGINATED_TRANSFER" else None,
        "token_account": token_account_text if activity == "BALANCE_CHANGE" else None,
        "balance_before": before if activity == "BALANCE_CHANGE" else None,
        "balance_after": after if activity == "BALANCE_CHANGE" else None,
        "verification": flags,
        "limitations": _limitations(limitations),
        "classification_labels": [],
        "classification_authorized": False,
        "complete_wallet_history_proven": False,
    }
    return {"observation_id": _observation_id(base), **base}


def _validated_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild an observation to verify every invariant and its content ID."""

    if not isinstance(observation, Mapping):
        raise TypeError("wallet observations must be mappings")
    record = dict(observation)
    verification = record.get("verification")
    if not isinstance(verification, Mapping):
        raise ValueError("wallet observation verification object is required")
    if set(verification) != set(_VERIFICATION_FIELDS):
        raise ValueError("wallet observation verification fields are invalid")

    activity = _text("activity_type", record.get("activity_type"), required=True)
    assert activity is not None
    rebuilt = build_wallet_activity_observation(
        chain=record.get("chain"),
        wallet=record.get("wallet"),
        activity_type=activity,
        transaction_signature=record.get("transaction_signature"),
        observed_at=record.get("observed_at"),
        source=record.get("source"),
        verification_method=record.get("verification_method"),
        evidence_scope=record.get("evidence_scope"),
        asset_id=record.get("asset_id"),
        block_slot=record.get("block_slot"),
        asset_amount=None if activity.upper() == "BALANCE_CHANGE" else record.get("asset_amount"),
        asset_unit=record.get("asset_unit"),
        quote_value=record.get("quote_value"),
        quote_unit=record.get("quote_unit"),
        counterparty=record.get("counterparty"),
        deployer_id=record.get("deployer_id"),
        token_account=record.get("token_account"),
        balance_before=record.get("balance_before"),
        balance_after=record.get("balance_after"),
        limitations=record.get("limitations"),
        **{name: verification.get(name) for name in _VERIFICATION_FIELDS},
    )
    if rebuilt != record:
        raise ValueError("wallet observation content or content-addressed id is inconsistent")
    return rebuilt


def summarize_wallet_activity(
    *,
    chain: Any,
    wallet: Any,
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate verified wallet facts without behavioral interpretation."""

    chain_text = (_text("chain", chain, required=True) or "").lower()
    wallet_text = _text("wallet", wallet, required=True)
    if isinstance(observations, (str, bytes, bytearray)) or not isinstance(observations, Sequence):
        raise TypeError("observations must be a sequence of wallet observations")

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in observations:
        record = _validated_observation(item)
        if record["chain"] != chain_text:
            raise ValueError("wallet observation chain mismatch")
        if record["wallet"] != wallet_text:
            raise ValueError("wallet observation identity mismatch")
        observation_id = record["observation_id"]
        if observation_id in seen_ids:
            continue
        seen_ids.add(observation_id)
        records.append(record)

    records.sort(
        key=lambda item: (
            _timestamp_value(item["observed_at"]),
            item["transaction_signature"],
            item["observation_id"],
        )
    )
    observed_times = [item["observed_at"] for item in records]
    signatures = {item["transaction_signature"] for item in records}

    type_counts = {activity: 0 for activity in sorted(ACTIVITY_TYPES)}
    amount_totals: dict[tuple[str, str, str], Decimal] = defaultdict(Decimal)
    trade_volume_totals: dict[str, Decimal] = defaultdict(Decimal)
    sources: set[str] = set()
    scopes: set[str] = set()
    methods: set[str] = set()

    for item in records:
        activity = item["activity_type"]
        type_counts[activity] += 1
        sources.add(item["source"])
        scopes.add(item["evidence_scope"])
        methods.add(item["verification_method"])

        if item["asset_amount"] is not None and item["asset_unit"] is not None:
            amount_totals[(item["asset_id"], item["asset_unit"], activity)] += Decimal(
                item["asset_amount"]
            )
        if activity in {"BUY", "SELL"} and item["quote_value"] is not None:
            trade_volume_totals[item["quote_unit"]] += Decimal(item["quote_value"])

    by_asset: dict[str, dict[str, Any]] = {}
    for (asset, unit, activity), total in sorted(amount_totals.items()):
        asset_record = by_asset.setdefault(asset, {"units": {}})
        unit_record = asset_record["units"].setdefault(unit, {})
        unit_record[activity.lower()] = _decimal_text(
            "aggregate_amount", total, required=True, allow_negative=True
        )

    verified_volume = {
        unit: _decimal_text(
            "aggregate_trade_volume", total, required=True, allow_negative=False
        )
        for unit, total in sorted(trade_volume_totals.items())
    }

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
        "verified_trade_volume_by_quote_unit": verified_volume,
        "sources": sorted(sources),
        "evidence_scopes": sorted(scopes),
        "verification_methods": sorted(methods),
        "observations": records,
        "classifications": [],
        "classification_authorized": False,
        "complete_wallet_history_proven": False,
        "limitations": [
            "observed_activity_only",
            "continuous_wallet_history_not_proven",
            "behavioral_or_identity_labels_not_authorized",
            "missing_amounts_are_not_zero_filled",
        ],
    }


__all__ = [
    "ACTIVITY_TYPES",
    "SCHEMA_VERSION",
    "build_wallet_activity_observation",
    "summarize_wallet_activity",
]
