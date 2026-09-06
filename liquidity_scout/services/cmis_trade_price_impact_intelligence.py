"""Verified X1 trade attribution + pool-local price-impact intelligence.

Issue #498 composes already-verified CMIS/X1 evidence.  It does not fetch
providers, re-run RPC discovery, trust provider labels independently, infer a
real-world wallet owner, or widen one AMM pool state transition into a
whole-market causality claim.

Required upstream evidence:
- one wallet trade observation whose wallet/asset/transaction/direction are
  already verified against X1 RPC;
- one exact X1.Ninja execution-price observation whose provider amount fields
  exactly match the selected pool vault deltas;
- one routed/multi-AMM characterization proving the transaction contains one
  normalized recognized AMM occurrence and one selected-pool occurrence;
- one complete exact-pool 24h chain window when volume contribution is claimed.

The service is read-only and always preserves execution_authorized=false.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.services.cmis_contract import OK, build_service_envelope


SERVICE = "trade_price_impact_intelligence"
CONTRACT_VERSION = "trade_price_impact_intelligence/v1"
SUPPORTED_CHAIN = "x1"
EXECUTION_EVIDENCE_SERVICE = "x1_ninja_trade_execution_price"
ROUTING_EVIDENCE_SERVICE = "x1_routed_multi_amm_ambiguity"
POOL_WINDOW_CONTRACT = "x1_pool_24h_chain_activity/v1"
SINGLE_AMM_CAUSE = "single_or_no_recognized_amm_instruction"


class TradePriceImpactIntelligenceError(ValueError):
    """Raised when supplied evidence cannot support the #498 contract."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TradePriceImpactIntelligenceError(f"{field} must be an object")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TradePriceImpactIntelligenceError(f"{field} is required")
    return value.strip()


def _strict_true(value: Any, field: str) -> None:
    if value is not True:
        raise TradePriceImpactIntelligenceError(f"{field} must be verified")


def _strict_false(value: Any, field: str) -> None:
    if value is not False:
        raise TradePriceImpactIntelligenceError(f"{field} must remain false")


def _decimal(value: Any, field: str, *, positive: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise TradePriceImpactIntelligenceError(f"{field} must be numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise TradePriceImpactIntelligenceError(
            f"{field} must be numeric"
        ) from exc
    if not parsed.is_finite():
        raise TradePriceImpactIntelligenceError(f"{field} must be finite")
    if positive and parsed <= 0:
        raise TradePriceImpactIntelligenceError(f"{field} must be positive")
    return parsed


def _int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TradePriceImpactIntelligenceError(
            f"{field} must be a non-negative integer"
        )
    return value


def _fmt(value: Decimal) -> str:
    return format(value, "f")


def _percent(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        raise TradePriceImpactIntelligenceError(
            "percentage denominator must be non-zero"
        )
    return numerator / denominator * Decimal("100")


def _validate_wallet_observation(
    observation: Mapping[str, Any],
    *,
    requested_asset_mint: str,
) -> dict[str, Any]:
    if observation.get("chain") != SUPPORTED_CHAIN:
        raise TradePriceImpactIntelligenceError(
            "wallet observation chain must be x1"
        )
    signature = _text(
        observation.get("transaction_signature"),
        "wallet_observation.transaction_signature",
    )
    wallet = _text(observation.get("wallet"), "wallet_observation.wallet")
    asset_id = _text(
        observation.get("asset_id"),
        "wallet_observation.asset_id",
    )
    if asset_id != requested_asset_mint:
        raise TradePriceImpactIntelligenceError(
            "wallet observation asset identity mismatch"
        )
    side = _text(
        observation.get("activity_type"),
        "wallet_observation.activity_type",
    ).upper()
    if side not in {"BUY", "SELL"}:
        raise TradePriceImpactIntelligenceError(
            "wallet observation must be BUY or SELL"
        )

    verification = _mapping(
        observation.get("verification"),
        "wallet_observation.verification",
    )
    for field in (
        "wallet_identity_verified",
        "asset_identity_verified",
        "transaction_identity_verified",
        "trade_direction_verified",
    ):
        _strict_true(
            verification.get(field),
            f"wallet_observation.verification.{field}",
        )

    slot = _int(
        observation.get("block_slot"),
        "wallet_observation.block_slot",
    )
    observed_at = _text(
        observation.get("observed_at"),
        "wallet_observation.observed_at",
    )
    if observation.get("classification_authorized") is not False:
        raise TradePriceImpactIntelligenceError(
            "wallet observation must not authorize behavioral classification"
        )
    if observation.get("complete_wallet_history_proven") is not False:
        raise TradePriceImpactIntelligenceError(
            "single trade observation must not claim complete wallet history"
        )

    return {
        "wallet": wallet,
        "signature": signature,
        "asset_mint": asset_id,
        "side": side,
        "slot": slot,
        "observed_at": observed_at,
    }


def _validate_execution_evidence(
    evidence: Mapping[str, Any],
    *,
    signature: str,
    side: str,
    requested_asset_mint: str,
) -> dict[str, Any]:
    if evidence.get("service") != EXECUTION_EVIDENCE_SERVICE:
        raise TradePriceImpactIntelligenceError(
            "execution evidence service mismatch"
        )
    if evidence.get("chain") != SUPPORTED_CHAIN:
        raise TradePriceImpactIntelligenceError(
            "execution evidence chain must be x1"
        )
    if evidence.get("status") != "verified":
        raise TradePriceImpactIntelligenceError(
            "execution evidence must be verified"
        )
    if evidence.get("transaction_signature") != signature:
        raise TradePriceImpactIntelligenceError(
            "execution evidence signature mismatch"
        )
    if evidence.get("onchain_side") != side:
        raise TradePriceImpactIntelligenceError(
            "wallet and exact pool-leg directions disagree"
        )
    for field in (
        "transaction_pool_membership_verified",
        "provider_amounts_match_exact_pool_leg",
        "provider_asset_amount_matches_vault_delta",
        "provider_quote_amount_matches_vault_delta",
        "provider_slot_matches_rpc_slot",
        "pool_vault_delta_signs_verified",
        "trade_price_native_execution_semantics_verified",
    ):
        _strict_true(evidence.get(field), f"execution_evidence.{field}")
    _strict_false(
        evidence.get("execution_authorized"),
        "execution_evidence.execution_authorized",
    )

    pool_address = _text(
        evidence.get("pool_address"), "execution_evidence.pool_address"
    )
    slot = _int(
        evidence.get("transaction_slot"),
        "execution_evidence.transaction_slot",
    )
    onchain = _mapping(evidence.get("onchain"), "execution_evidence.onchain")
    asset_amount = _decimal(
        onchain.get("asset_amount"),
        "execution_evidence.onchain.asset_amount",
        positive=True,
    )
    quote_amount = _decimal(
        onchain.get("quote_amount"),
        "execution_evidence.onchain.quote_amount",
        positive=True,
    )
    average_execution = _decimal(
        onchain.get("effective_execution_price_native"),
        "execution_evidence.onchain.effective_execution_price_native",
        positive=True,
    )
    post_asset = _decimal(
        onchain.get("post_trade_asset_reserve"),
        "execution_evidence.onchain.post_trade_asset_reserve",
        positive=True,
    )
    post_quote = _decimal(
        onchain.get("post_trade_quote_reserve"),
        "execution_evidence.onchain.post_trade_quote_reserve",
        positive=True,
    )

    # The exact execution module already proves amount units against the
    # selected pool vault deltas.  This composition only reconstructs the
    # transaction-adjacent pre-state algebraically from exact post-state + delta.
    if side == "BUY":
        pre_asset = post_asset + asset_amount
        pre_quote = post_quote - quote_amount
    else:
        pre_asset = post_asset - asset_amount
        pre_quote = post_quote + quote_amount
    if pre_asset <= 0 or pre_quote <= 0:
        raise TradePriceImpactIntelligenceError(
            "transaction-adjacent pre-trade reserves must be positive"
        )

    pre_spot = pre_quote / pre_asset
    post_spot = post_quote / post_asset
    calculated_average = quote_amount / asset_amount
    if calculated_average != average_execution:
        raise TradePriceImpactIntelligenceError(
            "execution price does not equal exact quote/asset pool-leg amounts"
        )

    return {
        "pool_address": pool_address,
        "slot": slot,
        "block_time": evidence.get("transaction_block_time"),
        "asset_amount": asset_amount,
        "quote_amount": quote_amount,
        "pre_asset": pre_asset,
        "pre_quote": pre_quote,
        "post_asset": post_asset,
        "post_quote": post_quote,
        "pre_spot": pre_spot,
        "average_execution": average_execution,
        "post_spot": post_spot,
        "raw": dict(evidence),
    }


def _validate_single_pool_attribution(
    routing: Mapping[str, Any],
    *,
    signature: str,
    pool_address: str,
) -> None:
    if routing.get("service") != ROUTING_EVIDENCE_SERVICE:
        raise TradePriceImpactIntelligenceError(
            "routing evidence service mismatch"
        )
    if routing.get("chain") != SUPPORTED_CHAIN or routing.get("status") != "verified":
        raise TradePriceImpactIntelligenceError(
            "routing evidence must be verified X1 evidence"
        )
    if routing.get("signature") != signature:
        raise TradePriceImpactIntelligenceError(
            "routing evidence signature mismatch"
        )
    if routing.get("pool_address") != pool_address:
        raise TradePriceImpactIntelligenceError(
            "routing evidence pool mismatch"
        )
    _strict_true(
        routing.get("exact_vault_deltas_verified"),
        "routing_evidence.exact_vault_deltas_verified",
    )
    if routing.get("ambiguity_cause") != SINGLE_AMM_CAUSE:
        raise TradePriceImpactIntelligenceError(
            "routed or multi-AMM transaction cannot be attributed as one wallet-to-pool trade"
        )
    if routing.get("recognized_amm_instruction_count_normalized") != 1:
        raise TradePriceImpactIntelligenceError(
            "exactly one normalized recognized AMM instruction is required"
        )
    if routing.get("selected_pool_instruction_count_normalized") != 1:
        raise TradePriceImpactIntelligenceError(
            "exactly one selected-pool instruction is required"
        )
    if routing.get("additional_recognized_instruction_count_normalized") != 0:
        raise TradePriceImpactIntelligenceError(
            "additional recognized AMM instructions are not allowed"
        )
    _strict_false(
        routing.get("genuine_instruction_multiplicity_observed"),
        "routing_evidence.genuine_instruction_multiplicity_observed",
    )
    _strict_false(
        routing.get("execution_authorized"),
        "routing_evidence.execution_authorized",
    )


def _exact_swap_rows(window: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = window.get("transactions")
    if not isinstance(rows, Sequence) or isinstance(
        rows, (str, bytes, bytearray)
    ):
        raise TradePriceImpactIntelligenceError(
            "pool window transactions must be a list"
        )
    return [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get("classification") == "EXACT_POOL_SWAP"
    ]


def _window_contribution(
    window: Mapping[str, Any],
    *,
    signature: str,
    pool_address: str,
    requested_asset_mint: str,
    target_slot: int,
) -> dict[str, Any]:
    if window.get("contract_version") != POOL_WINDOW_CONTRACT:
        raise TradePriceImpactIntelligenceError(
            "pool window contract mismatch"
        )
    if window.get("chain") != SUPPORTED_CHAIN:
        raise TradePriceImpactIntelligenceError(
            "pool window chain must be x1"
        )
    if window.get("pool_address") != pool_address:
        raise TradePriceImpactIntelligenceError(
            "pool window pool identity mismatch"
        )
    if window.get("asset_mint") != requested_asset_mint:
        raise TradePriceImpactIntelligenceError(
            "pool window asset identity mismatch"
        )
    for field in (
        "history_range_proven",
        "history_integrity_verified",
        "all_successful_transactions_verified",
        "all_pool_relevant_transactions_classified",
        "transactions_24h_window_coverage_verified",
        "swap_count_semantics_verified",
        "usd_valuation_coverage_verified",
        "volume_24h_value_verified",
    ):
        _strict_true(window.get(field), f"pool_window.{field}")
    _strict_false(
        window.get("execution_authorized"),
        "pool_window.execution_authorized",
    )

    swaps = _exact_swap_rows(window)
    targets = [row for row in swaps if row.get("signature") == signature]
    if len(targets) != 1:
        raise TradePriceImpactIntelligenceError(
            "target signature must occur exactly once in the verified pool window"
        )
    target = targets[0]
    if target.get("slot") != target_slot:
        raise TradePriceImpactIntelligenceError(
            "target window slot does not match verified transaction slot"
        )
    _strict_true(
        target.get("historical_usd_value_verified"),
        "pool_window target historical_usd_value_verified",
    )
    target_usd = _decimal(
        target.get("usd_value"),
        "pool_window target usd_value",
        positive=True,
    )
    total_usd = _decimal(
        window.get("verified_volume_24h_usd"),
        "pool_window.verified_volume_24h_usd",
        positive=True,
    )
    if target_usd > total_usd:
        raise TradePriceImpactIntelligenceError(
            "target USD value cannot exceed verified window volume"
        )

    return {
        "target_usd": target_usd,
        "window_usd": total_usd,
        "contribution_pct": _percent(target_usd, total_usd),
        "swaps": swaps,
        "requested_window": dict(
            _mapping(window.get("requested_window"), "pool_window.requested_window")
        ),
    }


def _next_verified_trade(
    *,
    swaps: Sequence[Mapping[str, Any]],
    target_signature: str,
    target_slot: int,
    pool_address: str,
    next_execution_evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    # Slot ordering is only promoted when the candidate is in a strictly later
    # slot.  Same-slot swaps have no deterministic transaction index here and
    # therefore keep next-trade ordering unavailable.
    same_slot_other = [
        row
        for row in swaps
        if row.get("signature") != target_signature
        and row.get("slot") == target_slot
    ]
    later = [
        row
        for row in swaps
        if isinstance(row.get("slot"), int)
        and not isinstance(row.get("slot"), bool)
        and row.get("slot") > target_slot
    ]
    later.sort(key=lambda row: (row.get("slot"), str(row.get("signature") or "")))

    if same_slot_other or not later:
        return {
            "verified": False,
            "reason": (
                "same_slot_ordering_unavailable"
                if same_slot_other
                else "no_later_verified_trade_in_measured_window"
            ),
            "signature": None,
            "slot": None,
            "block_time": None,
            "execution_price_native": None,
        }

    candidate = later[0]
    signature = _text(candidate.get("signature"), "next pool swap signature")
    slot = _int(candidate.get("slot"), "next pool swap slot")

    if next_execution_evidence is None:
        return {
            "verified": False,
            "reason": "next_trade_execution_price_evidence_not_supplied",
            "signature": signature,
            "slot": slot,
            "block_time": candidate.get("block_time"),
            "execution_price_native": None,
        }

    evidence = _mapping(
        next_execution_evidence,
        "next_execution_evidence",
    )
    if (
        evidence.get("service") != EXECUTION_EVIDENCE_SERVICE
        or evidence.get("status") != "verified"
        or evidence.get("transaction_signature") != signature
        or evidence.get("transaction_slot") != slot
        or evidence.get("pool_address") != pool_address
        or evidence.get("transaction_pool_membership_verified") is not True
        or evidence.get("provider_amounts_match_exact_pool_leg") is not True
        or evidence.get("trade_price_native_execution_semantics_verified") is not True
        or evidence.get("execution_authorized") is not False
    ):
        raise TradePriceImpactIntelligenceError(
            "next trade execution evidence does not match the deterministic next pool swap"
        )
    onchain = _mapping(
        evidence.get("onchain"),
        "next_execution_evidence.onchain",
    )
    price = _decimal(
        onchain.get("effective_execution_price_native"),
        "next_execution_evidence execution price",
        positive=True,
    )
    return {
        "verified": True,
        "reason": "strictly_next_verified_exact_pool_swap_by_rpc_slot",
        "signature": signature,
        "slot": slot,
        "block_time": candidate.get("block_time"),
        "execution_price_native": _fmt(price),
    }


def build_trade_price_impact_intelligence_response(
    *,
    requested_asset_mint: str,
    wallet_observation: Mapping[str, Any],
    execution_evidence: Mapping[str, Any],
    routing_evidence: Mapping[str, Any],
    pool_window: Mapping[str, Any],
    next_execution_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose one verified wallet trade + selected-pool state transition."""

    requested_asset_mint = _text(
        requested_asset_mint, "requested_asset_mint"
    )
    wallet = _validate_wallet_observation(
        _mapping(wallet_observation, "wallet_observation"),
        requested_asset_mint=requested_asset_mint,
    )
    execution = _validate_execution_evidence(
        _mapping(execution_evidence, "execution_evidence"),
        signature=wallet["signature"],
        side=wallet["side"],
        requested_asset_mint=requested_asset_mint,
    )
    if execution["slot"] != wallet["slot"]:
        raise TradePriceImpactIntelligenceError(
            "wallet and execution evidence slots disagree"
        )

    _validate_single_pool_attribution(
        _mapping(routing_evidence, "routing_evidence"),
        signature=wallet["signature"],
        pool_address=execution["pool_address"],
    )

    window = _window_contribution(
        _mapping(pool_window, "pool_window"),
        signature=wallet["signature"],
        pool_address=execution["pool_address"],
        requested_asset_mint=requested_asset_mint,
        target_slot=wallet["slot"],
    )
    next_trade = _next_verified_trade(
        swaps=window["swaps"],
        target_signature=wallet["signature"],
        target_slot=wallet["slot"],
        pool_address=execution["pool_address"],
        next_execution_evidence=next_execution_evidence,
    )

    spot_change_pct = _percent(
        execution["post_spot"] - execution["pre_spot"],
        execution["pre_spot"],
    )
    execution_impact_pct = _percent(
        execution["average_execution"] - execution["pre_spot"],
        execution["pre_spot"],
    )

    data = {
        "contract_version": CONTRACT_VERSION,
        "public_service_promoted": True,
        "scout_reliance_promoted": True,
        "read_only": True,
        "wallet_trade": {
            "wallet_address": wallet["wallet"],
            "real_world_identity_verified": False,
            "transaction_signature": wallet["signature"],
            "slot": wallet["slot"],
            "fact_time": wallet["observed_at"],
            "requested_asset_mint": requested_asset_mint,
            "direction": wallet["side"],
            "wallet_trade_amount_attribution_verified": True,
            "asset_amount": _fmt(execution["asset_amount"]),
            "quote_amount": _fmt(execution["quote_amount"]),
            "amount_basis": (
                "single_recognized_amm_transaction_plus_exact_selected_pool_vault_deltas"
            ),
        },
        "pool": {
            "pool_address": execution["pool_address"],
            "transaction_pool_membership_verified": True,
            "single_recognized_amm_attribution_verified": True,
            "pre_trade_asset_reserve": _fmt(execution["pre_asset"]),
            "pre_trade_quote_reserve": _fmt(execution["pre_quote"]),
            "post_trade_asset_reserve": _fmt(execution["post_asset"]),
            "post_trade_quote_reserve": _fmt(execution["post_quote"]),
            "pre_trade_spot_price_native": _fmt(execution["pre_spot"]),
            "average_execution_price_native": _fmt(
                execution["average_execution"]
            ),
            "post_trade_spot_price_native": _fmt(execution["post_spot"]),
            "spot_price_change_percent": _fmt(spot_change_pct),
            "execution_price_impact_percent_vs_pre_spot": _fmt(
                execution_impact_pct
            ),
            "pool_local_state_transition_verified": True,
        },
        "next_verified_trade": next_trade,
        "measured_window": {
            "scope": "exact_selected_pool_rolling_24h",
            "requested_window": window["requested_window"],
            "trade_usd_notional": _fmt(window["target_usd"]),
            "verified_window_volume_usd": _fmt(window["window_usd"]),
            "trade_volume_contribution_percent": _fmt(
                window["contribution_pct"]
            ),
            "numerator_denominator_same_verified_usd_basis": True,
            "window_coverage_verified": True,
        },
        "evidence_boundaries": {
            "wallet_owner_identity_inference_authorized": False,
            "whale_insider_manipulator_label_authorized": False,
            "intent_inference_authorized": False,
            "coordinated_wallet_inference_authorized": False,
            "whole_market_price_impact_claim_authorized": False,
            "volume_causality_claim_authorized": False,
            "automatic_risk_conclusion_authorized": False,
            "trade_recommendation_authorized": False,
            "pool_local_causal_state_transition_authorized": True,
            "source_independence_verified": False,
        },
        "execution_authorized": False,
    }

    warnings = [
        {
            "code": "pool_local_scope_only",
            "message": (
                "The verified state transition applies to the exact selected AMM "
                "pool. It does not prove whole-market price impact."
            ),
        },
        {
            "code": "wallet_address_is_not_real_world_identity",
            "message": (
                "The transaction is attributed to a verified public wallet "
                "address/signing path, not to a real-world person or entity."
            ),
        },
        {
            "code": "volume_contribution_is_not_volume_causality",
            "message": (
                "The trade's measured-window volume contribution is arithmetic "
                "within one verified pool window; it does not prove causation of "
                "broader market activity."
            ),
        },
    ]
    if not next_trade["verified"]:
        warnings.append(
            {
                "code": "next_trade_price_not_verified",
                "message": (
                    "The next verified trade execution price is unavailable under "
                    "the current deterministic ordering/evidence requirements."
                ),
            }
        )

    response = build_service_envelope(
        SERVICE,
        SUPPORTED_CHAIN,
        OK,
        asset={
            "canonical_id": requested_asset_mint,
            "mint": requested_asset_mint,
        },
        data=data,
        risk=None,
        confidence={
            "wallet_transaction_direction_verified": True,
            "single_pool_amount_attribution_verified": True,
            "pool_state_transition_verified": True,
            "measured_window_volume_contribution_verified": True,
            "next_trade_execution_price_verified": next_trade["verified"],
        },
        sources=[
            {
                "source": "X1 RPC + accepted XDEX/X1.Ninja CMIS evidence",
                "scope": "single_exact_x1_pool_transaction_and_verified_pool_window",
                "transaction_signature": wallet["signature"],
                "pool_address": execution["pool_address"],
            }
        ],
        observed_at=wallet["observed_at"],
        warnings=warnings,
        errors=[],
    )
    response["execution_authorized"] = False
    return response


__all__ = [
    "CONTRACT_VERSION",
    "SERVICE",
    "SUPPORTED_CHAIN",
    "TradePriceImpactIntelligenceError",
    "build_trade_price_impact_intelligence_response",
]
