"""Bind one X1.Ninja pool-trade row to one verified X1 wallet trade fact.

This adapter is deliberately transport-free. It does not fetch X1.Ninja, call
X1 RPC, discover wallet history, or trust provider labels on their own. It
accepts one already-observed X1.Ninja trade row and one deterministic
``VerificationReport`` produced by ``transaction_semantics.verify_transaction``.

The adapter emits a CMIS wallet BUY/SELL observation only when:

* the X1.Ninja ``maker`` exactly equals the requested wallet;
* the X1.Ninja ``txHash`` exactly equals the verified RPC signature;
* the RPC primary signer exactly equals that wallet;
* the transaction succeeded and invoked a recognized XDEX/XenDEX AMM;
* the provider side was ``PROVIDER_SIDE_ONCHAIN_CONFIRMED``;
* the provider side and on-chain inferred side agree on BUY/SELL; and
* the expected and inferred asset mint exactly equal the caller-supplied,
  independently verified X1 mint identity.

Provider amount, timestamp, slot, pagination/range, and complete-history
semantics remain unverified. The resulting wallet observation therefore uses
RPC block time/slot, exposes no amount/quote value, proves no complete wallet
history, authorizes no behavioral classification, and remains non-promotable.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.cmis.wallet_activity import build_wallet_activity_observation
from liquidity_scout.providers.x1.transaction_semantics import VerificationReport


SOURCE = "X1.Ninja pool trade + X1 RPC transaction verification"
VERIFICATION_METHOD = "ninja_maker_txhash_bound_to_confirmed_x1_rpc_trade_semantics_v1"
EVIDENCE_SCOPE = "single_x1_ninja_pool_trade_row_and_exact_x1_rpc_transaction"
CONFIRMED_LEVEL = "PROVIDER_SIDE_ONCHAIN_CONFIRMED"
_SUPPORTED_SIDES = frozenset({"BUY", "SELL"})


class X1NinjaWalletTradeEvidenceError(ValueError):
    """Raised when one provider row cannot safely become a wallet trade fact."""


def _required_text(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise X1NinjaWalletTradeEvidenceError(f"{name} must be a string")
    text = value.strip()
    if not text:
        raise X1NinjaWalletTradeEvidenceError(f"{name} is required")
    return text


def _strict_true(name: str, value: Any) -> None:
    if not isinstance(value, bool):
        raise X1NinjaWalletTradeEvidenceError(f"{name} must be a boolean")
    if value is not True:
        raise X1NinjaWalletTradeEvidenceError(f"{name} must be verified")


def _provider_side(row: Mapping[str, Any]) -> str:
    raw = _required_text("trade_row.type", row.get("type"))
    side = raw.upper()
    if side not in _SUPPORTED_SIDES:
        raise X1NinjaWalletTradeEvidenceError(
            "trade_row.type must be BUY or SELL for wallet trade evidence"
        )
    return side


def build_verified_ninja_wallet_trade_observation(
    *,
    trade_row: Mapping[str, Any],
    verification_report: VerificationReport,
    wallet: str,
    asset_mint: str,
    asset_identity_verified: bool,
) -> dict[str, Any]:
    """Build one fail-closed wallet BUY/SELL observation from cross-source evidence.

    ``asset_mint`` is the exact X1 token mint represented by the wallet fact. The
    caller must separately verify that identity; symbols/names are not accepted as
    substitutes. No provider-supplied amount or timestamp is promoted here.
    """

    if not isinstance(trade_row, Mapping):
        raise TypeError("trade_row must be a mapping")
    if not isinstance(verification_report, VerificationReport):
        raise TypeError("verification_report must be a VerificationReport")

    wallet = _required_text("wallet", wallet)
    asset_mint = _required_text("asset_mint", asset_mint)
    _strict_true("asset_identity_verified", asset_identity_verified)

    maker = _required_text("trade_row.maker", trade_row.get("maker"))
    transaction_id = _required_text("trade_row.txHash", trade_row.get("txHash"))
    side = _provider_side(trade_row)

    if maker != wallet:
        raise X1NinjaWalletTradeEvidenceError(
            "X1.Ninja maker does not match requested wallet"
        )
    if verification_report.signature != transaction_id:
        raise X1NinjaWalletTradeEvidenceError(
            "X1.Ninja txHash does not match verified X1 RPC signature"
        )
    if verification_report.primary_signer != wallet:
        raise X1NinjaWalletTradeEvidenceError(
            "verified X1 RPC primary signer does not match requested wallet"
        )
    if not verification_report.found or not verification_report.succeeded:
        raise X1NinjaWalletTradeEvidenceError(
            "X1 transaction must be found and successful"
        )
    if not (
        verification_report.xdex_amm_invoked
        or verification_report.xendex_amm_invoked
    ):
        raise X1NinjaWalletTradeEvidenceError(
            "verified transaction does not invoke a recognized XDEX/XenDEX AMM"
        )
    if verification_report.verification_level != CONFIRMED_LEVEL:
        raise X1NinjaWalletTradeEvidenceError(
            "provider trade side is not deterministically on-chain confirmed"
        )
    if verification_report.expectation_match is not True:
        raise X1NinjaWalletTradeEvidenceError(
            "provider trade expectation is not exactly confirmed"
        )
    if verification_report.expected_side != side:
        raise X1NinjaWalletTradeEvidenceError(
            "provider trade side does not match verified expected side"
        )
    if verification_report.inferred_side != side:
        raise X1NinjaWalletTradeEvidenceError(
            "provider trade side does not match deterministic on-chain side"
        )
    if verification_report.expected_mint != asset_mint:
        raise X1NinjaWalletTradeEvidenceError(
            "verified expected mint does not match requested asset mint"
        )
    if verification_report.inferred_asset_mint != asset_mint:
        raise X1NinjaWalletTradeEvidenceError(
            "deterministic on-chain asset mint does not match requested asset mint"
        )
    if verification_report.block_time_iso is None:
        raise X1NinjaWalletTradeEvidenceError(
            "verified X1 RPC transaction block time is required"
        )
    if (
        isinstance(verification_report.slot, bool)
        or not isinstance(verification_report.slot, int)
        or verification_report.slot < 0
    ):
        raise X1NinjaWalletTradeEvidenceError(
            "verified X1 RPC transaction slot is required"
        )

    return build_wallet_activity_observation(
        chain="x1",
        wallet=wallet,
        activity_type=side,
        transaction_signature=transaction_id,
        observed_at=verification_report.block_time_iso,
        block_slot=verification_report.slot,
        source=SOURCE,
        verification_method=VERIFICATION_METHOD,
        evidence_scope=EVIDENCE_SCOPE,
        asset_id=asset_mint,
        wallet_identity_verified=True,
        asset_identity_verified=True,
        transaction_identity_verified=True,
        amount_verified=False,
        trade_direction_verified=True,
        limitations=(
            "single_transaction_fact_only",
            "x1_ninja_amount_units_not_promoted",
            "x1_ninja_timestamp_semantics_not_promoted",
            "x1_ninja_slot_semantics_not_promoted",
            "pool_trade_history_pagination_and_range_not_verified",
            "complete_wallet_history_not_proven",
            "behavioral_interpretation_not_authorized",
        ),
    )


__all__ = [
    "CONFIRMED_LEVEL",
    "EVIDENCE_SCOPE",
    "SOURCE",
    "VERIFICATION_METHOD",
    "X1NinjaWalletTradeEvidenceError",
    "build_verified_ninja_wallet_trade_observation",
]
