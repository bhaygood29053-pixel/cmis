"""Verify X1.Ninja priceNative against exact XDEX swap prices."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from liquidity_scout.providers.x1.candidate_pool_role import verify_candidate_pool_role
from liquidity_scout.providers.x1.program_accounts import RECOGNIZED_AMM_PROGRAM_IDS
from liquidity_scout.providers.x1.transaction_pool_membership import prove_transaction_pool_membership
from liquidity_scout.providers.x1.transaction_semantics import (
    DEFAULT_X1_RPC,
    WXNT_MINT,
    VerificationReport,
    fetch_transaction,
    verify_transaction,
)

VERSION = "1.0"
DEFAULT_RELATIVE_TOLERANCE = Decimal("5e-9")
DEFAULT_ABSOLUTE_TOLERANCE = Decimal("5e-15")


def _text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def _decimal(value: Any, *, name: str, positive: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be finite")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be finite")
    if positive and parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _compare(observed: Decimal, expected: Decimal, *, relative: Decimal, absolute: Decimal) -> dict[str, Any]:
    err = abs(observed - expected)
    rel = err / abs(expected) if expected != 0 else (Decimal(0) if err == 0 else None)
    allowed = max(absolute, abs(expected) * relative)
    return {
        "observed": format(observed, "f"),
        "expected": format(expected, "f"),
        "absolute_error": format(err, "f"),
        "relative_error": format(rel, "e") if rel is not None else None,
        "allowed_absolute_error": format(allowed, "f"),
        "within_tolerance": err <= allowed,
    }


def _identity(pool_address: str, structural: Mapping[str, Any]) -> dict[str, Any]:
    if structural.get("summary", {}).get("pool_state_structural_role_verified") is not True:
        raise ValueError("pool structural role unverified")
    decoded = structural.get("decoded_state")
    decoded = decoded if isinstance(decoded, Mapping) else {}
    mint0 = _text(decoded.get("mint_0"))
    mint1 = _text(decoded.get("mint_1"))
    vault0 = _text(decoded.get("vault_0"))
    vault1 = _text(decoded.get("vault_1"))
    owner = _text(structural.get("shared_vault_authority"))
    if not all((mint0, mint1, vault0, vault1, owner)):
        raise ValueError("verified pool identity incomplete")

    if mint0 == WXNT_MINT and mint1 != WXNT_MINT:
        quote_mint, quote_vault, asset_mint, asset_vault = mint0, vault0, mint1, vault1
    elif mint1 == WXNT_MINT and mint0 != WXNT_MINT:
        quote_mint, quote_vault, asset_mint, asset_vault = mint1, vault1, mint0, vault0
    else:
        raise ValueError("pool must contain exactly one wrapped-XNT mint")

    return {
        "chain": "x1",
        "pool_address": pool_address,
        "asset_mint": asset_mint,
        "asset_vault": asset_vault,
        "counter_mint": quote_mint,
        "counter_vault": quote_vault,
        "shared_owner": owner,
        "identity_verified": True,
    }


def _vault_delta(report: VerificationReport, account: str, mint: str):
    rows = [row for row in report.token_deltas if row.account == account and row.mint == mint]
    if len(rows) != 1:
        raise ValueError("exact vault delta unavailable or ambiguous")
    return rows[0]


def verify_ninja_trade_execution_price(
    *,
    pool_address: str,
    trade_row: Mapping[str, Any],
    current_pool_row: Mapping[str, Any] | None = None,
    structural_verifier: Callable[..., Mapping[str, Any]] = verify_candidate_pool_role,
    transaction_fetcher: Callable[..., Mapping[str, Any] | None] = fetch_transaction,
    transaction_verifier: Callable[..., VerificationReport] = verify_transaction,
    membership_prover: Callable[..., Mapping[str, Any]] = prove_transaction_pool_membership,
    recognized_program_ids: Sequence[str] = RECOGNIZED_AMM_PROGRAM_IDS,
    rpc_url: str = DEFAULT_X1_RPC,
    relative_tolerance: Any = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance: Any = DEFAULT_ABSOLUTE_TOLERANCE,
) -> dict[str, Any]:
    pool_address = _text(pool_address)
    if not pool_address:
        raise ValueError("pool_address is required")
    if _text(trade_row.get("poolAddress")) != pool_address:
        raise ValueError("trade row poolAddress mismatch")

    side = _text(trade_row.get("type"))
    if side not in {"BUY", "SELL"}:
        raise ValueError("trade type must be BUY or SELL")
    signature = _text(trade_row.get("txHash"))
    if not signature:
        raise ValueError("trade txHash is required")

    provider_price = _decimal(trade_row.get("priceNative"), name="priceNative", positive=True)
    provider_asset = _decimal(trade_row.get("amountToken"), name="amountToken", positive=True)
    provider_quote = _decimal(trade_row.get("amountNative"), name="amountNative", positive=True)
    relative = _decimal(relative_tolerance, name="relative_tolerance")
    absolute = _decimal(absolute_tolerance, name="absolute_tolerance")
    if relative < 0 or absolute < 0 or (relative == 0 and absolute == 0):
        raise ValueError("comparison tolerances invalid")

    structural = None
    program_id = None
    for raw_program in recognized_program_ids:
        candidate = _text(raw_program)
        if not candidate:
            continue
        try:
            report = structural_verifier(
                account=pool_address,
                target_mint=WXNT_MINT,
                program_id=candidate,
                rpc_url=rpc_url,
                signature_limit=1,
            )
        except Exception:
            continue
        if report.get("summary", {}).get("pool_state_structural_role_verified") is True:
            structural = report
            program_id = candidate
            break
    if structural is None:
        raise ValueError("exact XNT pool structural verification failed")

    identity = _identity(pool_address, structural)
    tx = transaction_fetcher(signature, rpc_url=rpc_url)
    report = transaction_verifier(
        tx,
        signature=signature,
        rpc_url=rpc_url,
        expected_side=side,
        expected_mint=identity["asset_mint"],
        expected_token_amount=provider_asset,
        expected_native_amount=provider_quote,
    )
    membership = membership_prover(
        verification_report=report,
        pool_identity=identity,
        transaction=tx,
    )
    if membership.get("transaction_pool_membership_verified") is not True:
        raise ValueError("exact transaction-pool membership unverified")

    asset_delta = _vault_delta(report, identity["asset_vault"], identity["asset_mint"])
    quote_delta = _vault_delta(report, identity["counter_vault"], identity["counter_mint"])

    signs_ok = (
        asset_delta.delta_ui < 0 and quote_delta.delta_ui > 0
        if side == "BUY"
        else asset_delta.delta_ui > 0 and quote_delta.delta_ui < 0
    )
    if not signs_ok:
        raise ValueError("vault delta signs do not match side")

    leg = report.pool_leg_match
    amounts_ok = bool(
        leg is not None
        and leg.amount_match is True
        and leg.asset_account == identity["asset_vault"]
        and leg.quote_account == identity["counter_vault"]
    )

    asset_amount = abs(asset_delta.delta_ui)
    quote_amount = abs(quote_delta.delta_ui)
    execution_price = quote_amount / asset_amount
    if asset_delta.post_ui <= 0 or quote_delta.post_ui <= 0:
        raise ValueError("post-trade reserves must be positive")
    reserve_ratio = quote_delta.post_ui / asset_delta.post_ui

    vs_execution = _compare(provider_price, execution_price, relative=relative, absolute=absolute)
    vs_reserve = _compare(provider_price, reserve_ratio, relative=relative, absolute=absolute)

    catalog_link = None
    if isinstance(current_pool_row, Mapping):
        address = _text(
            current_pool_row.get("address")
            or current_pool_row.get("poolAddress")
            or current_pool_row.get("pool_address")
        )
        if address != pool_address:
            raise ValueError("current pool row address mismatch")
        catalog_price = _decimal(current_pool_row.get("priceNative"), name="catalog priceNative", positive=True)
        catalog_link = _compare(catalog_price, provider_price, relative=relative, absolute=absolute)

    verified = bool(
        report.found
        and report.succeeded
        and report.xdex_amm_invoked
        and amounts_ok
        and signs_ok
        and vs_execution["within_tolerance"]
    )

    return {
        "service": "x1_ninja_trade_execution_price",
        "version": VERSION,
        "chain": "x1",
        "status": "verified" if verified else "partial",
        "pool_address": pool_address,
        "program_id": program_id,
        "transaction_signature": signature,
        "transaction_slot": report.slot,
        "transaction_block_time": report.block_time,
        "provider_side": side,
        "transaction_pool_membership_verified": True,
        "provider_amounts_match_exact_pool_leg": amounts_ok,
        "pool_vault_delta_signs_verified": signs_ok,
        "onchain": {
            "asset_amount": format(asset_amount, "f"),
            "quote_amount": format(quote_amount, "f"),
            "effective_execution_price_native": format(execution_price, "f"),
            "post_trade_asset_reserve": format(asset_delta.post_ui, "f"),
            "post_trade_quote_reserve": format(quote_delta.post_ui, "f"),
            "post_trade_reserve_ratio_native": format(reserve_ratio, "f"),
        },
        "provider": {
            "trade_amountToken": format(provider_asset, "f"),
            "trade_amountNative": format(provider_quote, "f"),
            "trade_priceNative": format(provider_price, "f"),
            "trade_slot_raw": trade_row.get("slot"),
            "trade_timestamp_raw": trade_row.get("timestamp"),
        },
        "comparisons": {
            "trade_priceNative_vs_execution_price": vs_execution,
            "trade_priceNative_vs_post_trade_reserve_ratio": vs_reserve,
            "current_pool_priceNative_vs_trade_priceNative": catalog_link,
        },
        "trade_price_native_execution_semantics_verified": verified,
        "current_pool_price_native_latest_trade_link_verified": bool(
            verified and catalog_link and catalog_link.get("within_tolerance") is True
        ),
        "provider_fact_time_verified": False,
        "freshness_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def aggregate_ninja_execution_price_samples(
    samples: Sequence[Mapping[str, Any]],
    *,
    minimum_verified_swaps: int = 5,
) -> dict[str, Any]:
    if isinstance(minimum_verified_swaps, bool) or not isinstance(minimum_verified_swaps, int):
        raise ValueError("minimum_verified_swaps must be an integer")
    if minimum_verified_swaps < 5:
        raise ValueError("minimum_verified_swaps must be at least 5")

    rows = [dict(row) for row in samples if isinstance(row, Mapping)]
    verified = [row for row in rows if row.get("trade_price_native_execution_semantics_verified") is True]
    linked = [row for row in verified if row.get("current_pool_price_native_latest_trade_link_verified") is True]
    sides = {row.get("provider_side") for row in verified}

    trade_ok = bool(len(verified) >= minimum_verified_swaps and len(verified) == len(rows))
    catalog_ok = bool(trade_ok and len(linked) == len(rows))

    return {
        "service": "x1_ninja_execution_price_semantics",
        "version": VERSION,
        "chain": "x1",
        "status": "verified" if trade_ok else ("partial" if rows else "unavailable"),
        "sample_count": len(rows),
        "verified_swap_count": len(verified),
        "minimum_verified_swaps": minimum_verified_swaps,
        "distinct_pool_count": len({row.get("pool_address") for row in verified if row.get("pool_address")}),
        "observed_sides": sorted(side for side in sides if side),
        "both_swap_directions_observed": {"BUY", "SELL"}.issubset(sides),
        "trade_price_native_execution_semantics_verified": trade_ok,
        "current_pool_price_native_latest_trade_link_verified": catalog_ok,
        "universal_pool_catalog_price_native_semantics_verified": False,
        "provider_fact_time_verified": False,
        "freshness_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "samples": rows,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "VERSION",
    "aggregate_ninja_execution_price_samples",
    "verify_ninja_trade_execution_price",
]
