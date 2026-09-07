"""Deterministic reflection-flow intelligence for CMIS.

This contract composes exact, already-verified flow observations for one
Uniswap v4 hook/pool pair. It does not infer holder-distribution semantics from
hook permission bits, token names, marketing claims, or transfer presence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.services.cmis_uniswap_v4_hook_intelligence import (
    CONTRACT_VERSION as HOOK_CONTRACT_VERSION,
)

CONTRACT_VERSION = "reflection_flow_intelligence/v1"
DEFAULT_EXECUTION_AUTHORIZED = False


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _decimal(value: Any, field: str, *, allow_zero: bool = True) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field} must be finite")
    if parsed < 0 or (not allow_zero and parsed == 0):
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{field} must be {qualifier}")
    return parsed


def _strict_true(value: Any, field: str) -> None:
    if value is not True:
        raise ValueError(f"{field} must be verified")


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field} must be a list")
    return list(value)


def _fmt(value: Decimal) -> str:
    return format(value, "f")


def build_reflection_flow_intelligence(
    *,
    hook_intelligence: Mapping[str, Any],
    window_start: Any,
    window_end: Any,
    reflection_asset_id: Any,
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate exact reflection-flow observations for one verified hook/pool."""

    hook_evidence = _mapping(hook_intelligence, "hook_intelligence")
    if hook_evidence.get("contract_version") != HOOK_CONTRACT_VERSION:
        raise ValueError("hook_intelligence contract mismatch")

    pool = _mapping(hook_evidence.get("pool"), "hook_intelligence.pool")
    hook = _mapping(hook_evidence.get("hook"), "hook_intelligence.hook")
    verification = _mapping(
        hook_evidence.get("verification"),
        "hook_intelligence.verification",
    )

    _strict_true(
        verification.get("pool_key_verified"),
        "hook_intelligence.verification.pool_key_verified",
    )
    _strict_true(
        verification.get("hook_code_verified"),
        "hook_intelligence.verification.hook_code_verified",
    )
    if hook.get("present") is not True:
        raise ValueError("reflection flow requires a non-zero hook")

    pool_id = _required_text(pool.get("pool_id"), "hook_intelligence.pool.pool_id")
    hook_address = _required_text(hook.get("address"), "hook_intelligence.hook.address")
    asset_id = _required_text(reflection_asset_id, "reflection_asset_id")

    start = _decimal(window_start, "window_start")
    end = _decimal(window_end, "window_end")
    if end <= start:
        raise ValueError("window_end must be greater than window_start")

    rows = _sequence(observations, "observations")
    seen_transactions: set[str] = set()
    total = Decimal(0)
    distribution_semantics_count = 0
    normalized: list[dict[str, Any]] = []

    for index, raw in enumerate(rows):
        row = _mapping(raw, f"observations[{index}]")
        transaction_id = _required_text(
            row.get("transaction_id"),
            f"observations[{index}].transaction_id",
        )
        if transaction_id in seen_transactions:
            raise ValueError("duplicate reflection transaction_id")
        seen_transactions.add(transaction_id)

        if _required_text(
            row.get("pool_id"),
            f"observations[{index}].pool_id",
        ) != pool_id:
            raise ValueError("reflection observation pool mismatch")
        if _required_text(
            row.get("hook_address"),
            f"observations[{index}].hook_address",
        ).casefold() != hook_address.casefold():
            raise ValueError("reflection observation hook mismatch")
        if _required_text(
            row.get("reflection_asset_id"),
            f"observations[{index}].reflection_asset_id",
        ) != asset_id:
            raise ValueError("reflection observation asset mismatch")

        observed_at = _decimal(
            row.get("observed_at"),
            f"observations[{index}].observed_at",
        )
        if observed_at < start or observed_at > end:
            raise ValueError("reflection observation lies outside requested window")

        amount = _decimal(
            row.get("reflection_amount"),
            f"observations[{index}].reflection_amount",
        )
        _strict_true(
            row.get("transfer_verified"),
            f"observations[{index}].transfer_verified",
        )
        _strict_true(
            row.get("hook_attribution_verified"),
            f"observations[{index}].hook_attribution_verified",
        )

        evidence_id = _required_text(
            row.get("source_evidence_id"),
            f"observations[{index}].source_evidence_id",
        )
        destination = _required_text(
            row.get("destination"),
            f"observations[{index}].destination",
        )
        distribution_semantics_verified = (
            row.get("distribution_semantics_verified") is True
        )
        if distribution_semantics_verified:
            distribution_semantics_count += 1

        total += amount
        normalized.append({
            "transaction_id": transaction_id,
            "observed_at": _fmt(observed_at),
            "reflection_amount": _fmt(amount),
            "reflection_asset_id": asset_id,
            "destination": destination,
            "transfer_verified": True,
            "hook_attribution_verified": True,
            "distribution_semantics_verified": distribution_semantics_verified,
            "source_evidence_id": evidence_id,
        })

    all_distribution_semantics_verified = bool(rows) and (
        distribution_semantics_count == len(rows)
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": hook_evidence.get("chain"),
        "scope": {
            "pool_id": pool_id,
            "hook_address": hook_address,
            "window_start": _fmt(start),
            "window_end": _fmt(end),
            "reflection_asset_id": asset_id,
        },
        "flow": {
            "verified_event_count": len(normalized),
            "total_reflection_amount": _fmt(total),
            "reflection_asset_id": asset_id,
            "observations": normalized,
        },
        "verification": {
            "exact_pool_hook_scope_verified": True,
            "all_transfers_verified": True,
            "all_hook_attributions_verified": True,
            "holder_distribution_semantics_verified": (
                all_distribution_semantics_verified
            ),
            "source_independence_verified": False,
            "window_completeness_verified": False,
        },
        "boundaries": {
            "permission_bits_alone_are_not_reflection_evidence": True,
            "holder_distribution_claim_authorized": (
                all_distribution_semantics_verified
            ),
            "lifetime_reflection_total_claim_authorized": False,
            "yield_claim_authorized": False,
            "automatic_risk_conclusion_authorized": False,
            "trade_recommendation_authorized": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": DEFAULT_EXECUTION_AUTHORIZED,
    }


__all__ = [
    "CONTRACT_VERSION",
    "DEFAULT_EXECUTION_AUTHORIZED",
    "build_reflection_flow_intelligence",
]
