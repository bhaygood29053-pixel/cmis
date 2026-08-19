"""Bounded, transport-free evidence for X1.Ninja pool trade-history samples.

This module does not fetch X1.Ninja and does not claim that ``/v1/trades`` is
complete, paginated, retained for any particular duration, finalized, or
ordered by contract.  It accepts one already-fetched ``ninja_history``
observation plus independently produced X1 RPC ``VerificationReport`` objects
and records only what can be established for a bounded prefix of the returned
rows.

The strongest positive result is intentionally narrow: every sampled Ninja
``txHash`` can be bound to a found/successful X1 RPC transaction, every sampled
row is scoped to the independently verified requested pool, and the sequence
can be described observationally using RPC slots.  Provider amount, timestamp,
slot, side, pagination/range, finality, retention, and exhaustiveness semantics
remain separate gates.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.providers.x1.ninja_history import (
    CHAIN,
    X1_NINJA_SOURCE,
)
from liquidity_scout.providers.x1.transaction_semantics import VerificationReport


CONTRACT_VERSION = "x1_ninja_trade_history_sample_evidence/v1"
EVIDENCE_SOURCE = "X1.Ninja Developer API + independently verified X1 RPC transactions"
WALLET_DIRECTION_BASIS = "SIGNER_OR_ROUTED_BALANCE_DIRECTION"
CONFIRMED_SIDE_LEVEL = "PROVIDER_SIDE_ONCHAIN_CONFIRMED"
_MAX_SAMPLE_ROWS = 100
_SUPPORTED_SIDES = frozenset({"BUY", "SELL"})


class X1NinjaTradeHistorySampleEvidenceError(ValueError):
    """Raised when supplied evidence is malformed or violates exact scope."""


def _strict_true(name: str, value: Any) -> None:
    if not isinstance(value, bool):
        raise X1NinjaTradeHistorySampleEvidenceError(f"{name} must be a boolean")
    if value is not True:
        raise X1NinjaTradeHistorySampleEvidenceError(f"{name} must be verified")


def _required_text(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise X1NinjaTradeHistorySampleEvidenceError(f"{name} must be a string")
    text = value.strip()
    if not text:
        raise X1NinjaTradeHistorySampleEvidenceError(f"{name} is required")
    return text


def _valid_slot(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _normalize_reports(
    verification_reports: Mapping[str, VerificationReport],
) -> dict[str, VerificationReport]:
    if not isinstance(verification_reports, Mapping):
        raise TypeError("verification_reports must be a mapping keyed by signature")

    normalized: dict[str, VerificationReport] = {}
    for key, report in verification_reports.items():
        signature = _required_text("verification_reports key", key)
        if not isinstance(report, VerificationReport):
            raise TypeError("verification_reports values must be VerificationReport objects")
        if report.signature != signature:
            raise X1NinjaTradeHistorySampleEvidenceError(
                "verification report signature does not match mapping key"
            )
        normalized[signature] = report
    return normalized


def verify_ninja_trade_history_sample(
    *,
    observation: Mapping[str, Any],
    verification_reports: Mapping[str, VerificationReport],
    pool_address: str,
    pool_identity_verified: bool,
    max_rows: int = 25,
) -> dict[str, Any]:
    """Cross-check a bounded returned Ninja trade-history prefix against X1 RPC.

    ``pool_address`` must be independently verified before this evidence can be
    constructed.  ``max_rows`` bounds local analysis only; it is not sent to
    X1.Ninja and must never be described as provider pagination or range proof.
    """

    if not isinstance(observation, Mapping):
        raise TypeError("observation must be a mapping")
    if isinstance(max_rows, bool) or not isinstance(max_rows, int):
        raise X1NinjaTradeHistorySampleEvidenceError("max_rows must be an integer")
    if max_rows < 1 or max_rows > _MAX_SAMPLE_ROWS:
        raise X1NinjaTradeHistorySampleEvidenceError(
            f"max_rows must be between 1 and {_MAX_SAMPLE_ROWS}"
        )

    expected_pool = _required_text("pool_address", pool_address)
    _strict_true("pool_identity_verified", pool_identity_verified)

    if observation.get("chain") != CHAIN:
        raise X1NinjaTradeHistorySampleEvidenceError("observation chain must be x1")
    if observation.get("source") != X1_NINJA_SOURCE:
        raise X1NinjaTradeHistorySampleEvidenceError(
            "observation source must be the X1.Ninja Developer API"
        )
    if observation.get("pool_address") != expected_pool:
        raise X1NinjaTradeHistorySampleEvidenceError(
            "observation pool does not match independently verified pool"
        )
    if observation.get("cmis_promotable") is not False:
        raise X1NinjaTradeHistorySampleEvidenceError(
            "input history observation must preserve cmis_promotable=false"
        )

    contract = observation.get("contract")
    if not isinstance(contract, Mapping):
        raise X1NinjaTradeHistorySampleEvidenceError("observation contract is required")
    _strict_true("contract.response_contract_verified", contract.get("response_contract_verified"))
    _strict_true("contract.trade_row_shape_verified", contract.get("trade_row_shape_verified"))

    raw_response = observation.get("raw_response")
    if not isinstance(raw_response, Mapping):
        raise X1NinjaTradeHistorySampleEvidenceError("raw_response must be a mapping")
    trades = raw_response.get("trades")
    if not isinstance(trades, list):
        raise X1NinjaTradeHistorySampleEvidenceError("raw_response.trades must be a list")

    reports = _normalize_reports(verification_reports)
    selected_rows = trades[:max_rows]
    seen_signatures: set[str] = set()
    row_results: list[dict[str, Any]] = []
    verified_slots: list[int] = []

    binding_complete = True
    success_complete = True
    pool_scope_complete = True
    maker_match_complete = True
    slot_match_complete = True
    side_match_complete = True

    for index, raw_row in enumerate(selected_rows):
        if not isinstance(raw_row, Mapping):
            raise X1NinjaTradeHistorySampleEvidenceError(
                f"trade row {index} must be a mapping"
            )

        row_pool = _required_text(f"trade row {index}.poolAddress", raw_row.get("poolAddress"))
        tx_hash = _required_text(f"trade row {index}.txHash", raw_row.get("txHash"))
        maker = _required_text(f"trade row {index}.maker", raw_row.get("maker"))
        provider_side_raw = raw_row.get("type")
        provider_side = (
            provider_side_raw.upper()
            if isinstance(provider_side_raw, str) and provider_side_raw.upper() in _SUPPORTED_SIDES
            else None
        )

        if tx_hash in seen_signatures:
            raise X1NinjaTradeHistorySampleEvidenceError(
                "sample contains duplicate X1.Ninja txHash values"
            )
        seen_signatures.add(tx_hash)

        pool_matches = row_pool == expected_pool
        pool_scope_complete = pool_scope_complete and pool_matches

        report = reports.get(tx_hash)
        rpc_bound = report is not None
        binding_complete = binding_complete and rpc_bound

        rpc_successful = False
        maker_matches = False
        provider_slot_matches = False
        wallet_side_matches = False
        rpc_slot: int | None = None

        if report is not None:
            rpc_successful = bool(report.found and report.succeeded)
            success_complete = success_complete and rpc_successful

            maker_matches = report.primary_signer == maker
            maker_match_complete = maker_match_complete and maker_matches

            if _valid_slot(report.slot):
                rpc_slot = report.slot
                verified_slots.append(report.slot)
            else:
                binding_complete = False

            provider_slot = raw_row.get("slot")
            provider_slot_matches = (
                rpc_slot is not None
                and _valid_slot(provider_slot)
                and provider_slot == rpc_slot
            )
            slot_match_complete = slot_match_complete and provider_slot_matches

            wallet_side_matches = bool(
                provider_side is not None
                and report.verification_level == CONFIRMED_SIDE_LEVEL
                and report.verification_basis == WALLET_DIRECTION_BASIS
                and report.expectation_match is True
                and report.expected_side == provider_side
                and report.inferred_side == provider_side
                and maker_matches
            )
            side_match_complete = side_match_complete and wallet_side_matches
        else:
            success_complete = False
            maker_match_complete = False
            slot_match_complete = False
            side_match_complete = False

        row_results.append(
            {
                "index": index,
                "transaction_id": tx_hash,
                "rpc_bound": rpc_bound,
                "rpc_transaction_found_and_successful": rpc_successful,
                "pool_matches_verified_scope": pool_matches,
                "maker_matches_rpc_primary_signer": maker_matches,
                "provider_slot_matches_rpc_slot_observation": provider_slot_matches,
                "provider_side_matches_wallet_level_rpc_evidence": wallet_side_matches,
                "rpc_slot": rpc_slot,
            }
        )

    order_observation = "unavailable"
    if selected_rows and binding_complete and len(verified_slots) == len(selected_rows):
        newest_first = all(
            earlier >= later
            for earlier, later in zip(verified_slots, verified_slots[1:])
        )
        order_observation = (
            "newest_to_oldest_by_verified_rpc_slot_observed"
            if newest_first
            else "not_newest_to_oldest_by_verified_rpc_slot_observed"
        )

    sample_size = len(selected_rows)
    sample_verification_complete = bool(
        sample_size > 0
        and binding_complete
        and success_complete
        and pool_scope_complete
    )

    warnings = [
        "bounded_sample_only",
        "provider_pagination_and_range_unverified",
        "provider_exhaustiveness_unverified",
        "provider_retention_unverified",
        "transaction_finality_unverified",
        "provider_timestamp_semantics_unverified",
        "provider_amount_and_price_semantics_unverified",
        "observed_order_is_not_a_provider_ordering_contract",
    ]
    if len(trades) > sample_size:
        warnings.append("local_verifier_sample_truncated")
    if not side_match_complete:
        warnings.append("provider_side_not_confirmed_for_every_sampled_row")
    if not slot_match_complete:
        warnings.append("provider_slot_not_confirmed_for_every_sampled_row")

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "source": EVIDENCE_SOURCE,
        "pool_address": expected_pool,
        "pool_identity_verified": True,
        "returned_row_count": len(trades),
        "sample_size": sample_size,
        "sample_is_returned_prefix": True,
        "sample_truncated_by_local_verifier": len(trades) > sample_size,
        "distinct_sample_transaction_ids": len(seen_signatures) == sample_size,
        "sample_rpc_binding_complete": binding_complete,
        "sample_rpc_transaction_success_complete": success_complete,
        "sample_pool_scope_match_complete": pool_scope_complete,
        "sample_maker_primary_signer_match_complete": maker_match_complete,
        "sample_provider_slot_rpc_match_complete": slot_match_complete,
        "sample_wallet_side_rpc_match_complete": side_match_complete,
        "sample_verification_complete": sample_verification_complete,
        "returned_order_observation": order_observation,
        "rows": row_results,
        "semantics": {
            "sample_transaction_identity_crosscheck": sample_verification_complete,
            "sample_pool_scope_crosscheck": bool(sample_size > 0 and pool_scope_complete),
            "sample_provider_slot_crosscheck": bool(sample_size > 0 and slot_match_complete),
            "sample_provider_side_crosscheck": bool(sample_size > 0 and side_match_complete),
            "ordering_contract_verified": False,
            "pagination_or_range_verified": False,
            "history_exhaustive_verified": False,
            "retention_verified": False,
            "finality_verified": False,
            "timestamp_semantics_verified": False,
            "amount_price_units_verified": False,
        },
        "warnings": warnings,
        "cmis_promotable": False,
    }


__all__ = [
    "CONFIRMED_SIDE_LEVEL",
    "CONTRACT_VERSION",
    "EVIDENCE_SOURCE",
    "WALLET_DIRECTION_BASIS",
    "X1NinjaTradeHistorySampleEvidenceError",
    "verify_ninja_trade_history_sample",
]
