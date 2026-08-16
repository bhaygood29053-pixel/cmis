"""CMIS trade-verification service for X1.Ninja -> X1 RPC evidence.

Provider trade rows are candidates, not truth. BUY/SELL is promoted only after:
- the provider transaction signature resolves on X1 RPC,
- provider slot/time are compatible with chain identity,
- a recognized XDEX/XenDEX program is present, and
- the provider side is independently supported by transaction or exact pool-leg
  token balance evidence.

LP events remain gated because their semantics have not been independently
verified.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, X1RPCError
from liquidity_scout.providers.x1.transaction_semantics import (
    VerificationReport,
    verify_signature,
)
from liquidity_scout.services.cmis_contract import (
    AMBIGUOUS,
    ERROR,
    OK,
    PARTIAL,
    build_service_envelope,
)

SERVICE = "trade_verification"
CHAIN = "x1"
PROVIDER_SOURCE = "X1.Ninja Developer API"
CHAIN_SOURCE = "X1 RPC"
SWAP_TYPES = frozenset({"buy", "sell"})


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _positive_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def _provider_timestamp(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _identity_evidence(row: Mapping[str, Any], report: VerificationReport):
    provider_slot = row.get("slot")
    slot_verified = (
        isinstance(provider_slot, int)
        and not isinstance(provider_slot, bool)
        and provider_slot >= 0
        and report.slot == provider_slot
    )

    provider_time = _provider_timestamp(row.get("timestamp"))
    time_delta_seconds = None
    timestamp_verified = False
    if provider_time is not None and isinstance(report.block_time, int):
        chain_time = datetime.fromtimestamp(report.block_time, tz=timezone.utc)
        time_delta_seconds = abs((provider_time - chain_time).total_seconds())
        timestamp_verified = time_delta_seconds <= 1.0

    return {
        "provider_slot": provider_slot,
        "chain_slot": report.slot,
        "slot_verified": slot_verified,
        "provider_timestamp": (
            provider_time.isoformat() if provider_time is not None else None
        ),
        "chain_block_time": report.block_time_iso,
        "timestamp_delta_seconds": time_delta_seconds,
        "timestamp_verified": timestamp_verified,
        "identity_verified": slot_verified and timestamp_verified,
    }


def _base_sources():
    return [
        {"source": PROVIDER_SOURCE, "role": "provider_trade_candidate"},
        {"source": CHAIN_SOURCE, "role": "on_chain_verification"},
    ]


def build_x1_trade_verification_response(
    provider_row: Any,
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    verifier: Callable[..., VerificationReport] = verify_signature,
):
    """Verify one raw X1.Ninja trade row and return a CMIS envelope."""
    if not isinstance(provider_row, Mapping):
        return build_service_envelope(
            SERVICE,
            CHAIN,
            ERROR,
            sources=_base_sources(),
            errors=[{
                "code": "invalid_provider_trade_row",
                "message": "provider trade row must be a mapping",
            }],
        )

    row = dict(provider_row)
    provider_type = (_text(row.get("type")) or "").lower()
    signature = _text(row.get("txHash"))
    token_amount = _positive_decimal(row.get("amountToken"))
    native_amount = _positive_decimal(row.get("amountNative"))

    provider_data = {
        "provider_type": provider_type or None,
        "pool_address": _text(row.get("poolAddress")),
        "transaction_signature": signature,
        "provider_slot": row.get("slot"),
        "provider_timestamp": _text(row.get("timestamp")),
        "provider_token_amount": (
            None if token_amount is None else str(token_amount)
        ),
        "provider_native_amount": (
            None if native_amount is None else str(native_amount)
        ),
    }

    if provider_type not in SWAP_TYPES:
        return build_service_envelope(
            SERVICE,
            CHAIN,
            PARTIAL,
            data={
                **provider_data,
                "side": None,
                "side_verified": False,
                "verification_level": "PROVIDER_EVENT_SEMANTICS_GATED",
                "verification_basis": "NONE",
            },
            confidence={
                "level": "provider_structure_only",
                "side_verified": False,
            },
            sources=_base_sources(),
            warnings=[{
                "code": "non_swap_event_semantics_gated",
                "message": (
                    "Only X1.Ninja buy/sell rows have independently verified "
                    "swap semantics. LP-event semantics remain gated."
                ),
            }],
        )

    missing = []
    if not signature:
        missing.append("txHash")
    if token_amount is None:
        missing.append("amountToken")
    if native_amount is None:
        missing.append("amountNative")
    if missing:
        return build_service_envelope(
            SERVICE,
            CHAIN,
            PARTIAL,
            data={
                **provider_data,
                "side": None,
                "side_verified": False,
                "verification_level": "PROVIDER_ROW_INCOMPLETE_FOR_CHAIN_VERIFICATION",
                "verification_basis": "NONE",
            },
            confidence={"level": "unverified", "side_verified": False},
            sources=_base_sources(),
            warnings=[{
                "code": "provider_trade_evidence_incomplete",
                "message": (
                    "Required provider field(s) missing or invalid: "
                    + ", ".join(missing)
                ),
            }],
        )

    try:
        report = verifier(
            signature,
            rpc_url=rpc_url,
            expected_side=provider_type.upper(),
            expected_token_amount=token_amount,
            expected_native_amount=native_amount,
        )
    except Exception as exc:
        return build_service_envelope(
            SERVICE,
            CHAIN,
            PARTIAL,
            data={
                **provider_data,
                "side": None,
                "side_verified": False,
                "verification_level": "CHAIN_VERIFICATION_UNAVAILABLE",
                "verification_basis": "NONE",
            },
            confidence={"level": "provider_only", "side_verified": False},
            sources=_base_sources(),
            warnings=[{
                "code": "x1_trade_chain_verification_failed",
                "message": f"X1 transaction verification failed: {exc}",
            }],
        )

    identity = _identity_evidence(row, report)

    data = {
        **provider_data,
        "side": (
            report.inferred_side
            if report.inferred_side in {"BUY", "SELL"} else None
        ),
        "side_verified": False,
        "asset_mint": report.inferred_asset_mint,
        "quote_mint": report.inferred_quote_mint,
        "quote_amount": (
            None if report.inferred_quote_amount is None
            else str(report.inferred_quote_amount)
        ),
        "dex_protocol": report.dex_protocol,
        "verification_level": report.verification_level,
        "verification_basis": report.verification_basis,
        "expectation_match": report.expectation_match,
        "identity": identity,
        "program_ids": list(report.program_ids),
        "pool_leg": (
            None if report.pool_leg_match is None
            else report.pool_leg_match.to_jsonable()
        ),
        "chain_transaction_succeeded": report.succeeded,
    }

    warnings = []
    errors = []

    if report.verification_level == "PROVIDER_ONCHAIN_DIRECTION_MISMATCH":
        status = AMBIGUOUS
        errors.append({
            "code": "provider_chain_trade_direction_conflict",
            "message": (
                "Provider BUY/SELL direction conflicts with deterministic "
                "on-chain direction."
            ),
        })
    elif (
        report.verification_level == "PROVIDER_SIDE_ONCHAIN_CONFIRMED"
        and identity["identity_verified"]
    ):
        status = OK
        data["side_verified"] = True
    else:
        status = PARTIAL
        if not identity["slot_verified"]:
            warnings.append({
                "code": "provider_chain_slot_not_verified",
                "message": "Provider slot did not verify against the fetched transaction.",
            })
        if not identity["timestamp_verified"]:
            warnings.append({
                "code": "provider_chain_timestamp_not_verified",
                "message": (
                    "Provider timestamp did not verify within one second of "
                    "the chain block time."
                ),
            })
        if report.verification_level != "PROVIDER_SIDE_ONCHAIN_CONFIRMED":
            warnings.append({
                "code": "trade_side_not_fully_promoted",
                "message": (
                    "The chain transaction was inspected, but BUY/SELL did not "
                    "reach the on-chain-confirmed promotion level."
                ),
            })

    confidence = {
        "level": (
            "on_chain_verified"
            if data["side_verified"]
            else "conflict"
            if status == AMBIGUOUS
            else "partial"
        ),
        "side_verified": data["side_verified"],
        "identity_verified": identity["identity_verified"],
        "evidence_basis": report.verification_basis,
    }

    return build_service_envelope(
        SERVICE,
        CHAIN,
        status,
        asset=(
            {"mint": report.inferred_asset_mint}
            if report.inferred_asset_mint else None
        ),
        data=data,
        confidence=confidence,
        sources=_base_sources(),
        observed_at=row.get("timestamp"),
        warnings=warnings,
        errors=errors,
    )


__all__ = [
    "CHAIN",
    "PROVIDER_SOURCE",
    "SERVICE",
    "SWAP_TYPES",
    "build_x1_trade_verification_response",
]
