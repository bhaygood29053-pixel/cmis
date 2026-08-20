"""Bounded X1.Ninja trade-history sample evidence.

This module is transport-free. It consumes one already-fetched X1.Ninja
``/v1/trades/{address}`` observation and independently produced X1 RPC
``VerificationReport`` objects. It verifies only facts that can be established
for a bounded prefix of the returned rows.

Important boundary: a Ninja row can name an independently verified pool while
the supplied ``VerificationReport`` still does not prove that the transaction
invoked that exact pool account. Row pool identity and transaction pool
membership are therefore separate facts, and transaction pool membership is
always left unverified here.

No pagination/range, exhaustiveness, retention, finality, timestamp, amount,
price, stable ordering, or CMIS-promotion claim is made by this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.providers.x1.ninja_history import (
    CHAIN,
    OBSERVED_TRADE_HISTORY_TOP_LEVEL_KEYS,
    OBSERVED_TRADE_ROW_KEYS,
    X1_NINJA_SOURCE,
)
from liquidity_scout.providers.x1.transaction_semantics import VerificationReport


CONTRACT_VERSION = "x1_ninja_trade_history_sample_evidence/v2"
EVIDENCE_SOURCE = (
    "X1.Ninja Developer API + independently produced X1 RPC verification reports"
)
WALLET_DIRECTION_BASIS = "SIGNER_OR_ROUTED_BALANCE_DIRECTION"
CONFIRMED_SIDE_LEVEL = "PROVIDER_SIDE_ONCHAIN_CONFIRMED"
_MAX_SAMPLE_ROWS = 100
_SUPPORTED_SIDES = frozenset({"BUY", "SELL"})
_UNVERIFIED_INPUT_SEMANTICS = (
    "side_classification_verified",
    "token_amount_units_verified",
    "usd_value_source_verified",
    "lp_event_semantics_verified",
    "transaction_signature_verified",
    "finality_verified",
    "pagination_or_range_verified",
)


class X1NinjaTradeHistorySampleEvidenceError(ValueError):
    """Raised when supplied evidence is malformed or violates exact scope."""


def _strict_true(name: str, value: Any) -> None:
    if not isinstance(value, bool):
        raise X1NinjaTradeHistorySampleEvidenceError(f"{name} must be a boolean")
    if value is not True:
        raise X1NinjaTradeHistorySampleEvidenceError(f"{name} must be verified")


def _strict_false(name: str, value: Any) -> None:
    if not isinstance(value, bool):
        raise X1NinjaTradeHistorySampleEvidenceError(f"{name} must be a boolean")
    if value is not False:
        raise X1NinjaTradeHistorySampleEvidenceError(
            f"{name} must remain explicitly unverified"
        )


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
    for raw_signature, report in verification_reports.items():
        signature = _required_text("verification_reports key", raw_signature)
        if not isinstance(report, VerificationReport):
            raise TypeError(
                "verification_reports values must be VerificationReport objects"
            )
        if report.signature != signature:
            raise X1NinjaTradeHistorySampleEvidenceError(
                "verification report signature does not match mapping key"
            )
        normalized[signature] = report
    return normalized


def _revalidate_observed_shape(
    raw_response: Mapping[str, Any],
    trades: list[Any],
) -> None:
    missing_top = sorted(
        OBSERVED_TRADE_HISTORY_TOP_LEVEL_KEYS - set(raw_response.keys())
    )
    if missing_top:
        raise X1NinjaTradeHistorySampleEvidenceError(
            "raw_response is missing observed top-level field(s): "
            + ", ".join(missing_top)
        )

    for index, row in enumerate(trades):
        if not isinstance(row, Mapping):
            raise X1NinjaTradeHistorySampleEvidenceError(
                f"trade row {index} must be a mapping"
            )
        missing_row = sorted(OBSERVED_TRADE_ROW_KEYS - set(row.keys()))
        if missing_row:
            raise X1NinjaTradeHistorySampleEvidenceError(
                f"trade row {index} is missing observed field(s): "
                + ", ".join(missing_row)
            )


def _validate_input_observation(
    *,
    observation: Mapping[str, Any],
    expected_pool: str,
) -> list[Any]:
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
    _strict_true(
        "contract.response_contract_verified",
        contract.get("response_contract_verified"),
    )
    _strict_true(
        "contract.trade_row_shape_verified",
        contract.get("trade_row_shape_verified"),
    )

    semantics = observation.get("semantics")
    if not isinstance(semantics, Mapping):
        raise X1NinjaTradeHistorySampleEvidenceError("observation semantics are required")
    _strict_true(
        "semantics.trade_rows_verified",
        semantics.get("trade_rows_verified"),
    )
    for semantic_name in _UNVERIFIED_INPUT_SEMANTICS:
        _strict_false(
            f"semantics.{semantic_name}",
            semantics.get(semantic_name),
        )

    raw_response = observation.get("raw_response")
    if not isinstance(raw_response, Mapping):
        raise X1NinjaTradeHistorySampleEvidenceError("raw_response must be a mapping")
    trades = raw_response.get("trades")
    if not isinstance(trades, list):
        raise X1NinjaTradeHistorySampleEvidenceError(
            "raw_response.trades must be a list"
        )
    _revalidate_observed_shape(raw_response, trades)

    returned_trade_count = contract.get("returned_trade_count")
    if (
        isinstance(returned_trade_count, bool)
        or not isinstance(returned_trade_count, int)
        or returned_trade_count != len(trades)
    ):
        raise X1NinjaTradeHistorySampleEvidenceError(
            "contract.returned_trade_count must exactly match raw_response.trades"
        )
    return trades


def verify_ninja_trade_history_sample(
    *,
    observation: Mapping[str, Any],
    verification_reports: Mapping[str, VerificationReport],
    pool_address: str,
    pool_identity_verified: bool,
    max_rows: int = 25,
) -> dict[str, Any]:
    """Cross-check a bounded returned Ninja trade-history prefix against X1 RPC.

    ``max_rows`` is a local verifier bound only. It is never sent to X1.Ninja
    and is not pagination/range evidence.
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
    trades = _validate_input_observation(
        observation=observation,
        expected_pool=expected_pool,
    )
    reports = _normalize_reports(verification_reports)

    selected_rows = trades[:max_rows]
    seen_signatures: set[str] = set()
    row_results: list[dict[str, Any]] = []
    verified_slots: list[int] = []

    report_binding_complete = True
    rpc_success_complete = True
    row_pool_identity_match_complete = True
    maker_match_complete = True
    rpc_slot_available_complete = True
    provider_slot_match_complete = True
    side_match_complete = True

    for index, raw_row in enumerate(selected_rows):
        row_pool = _required_text(
            f"trade row {index}.poolAddress", raw_row.get("poolAddress")
        )
        tx_hash = _required_text(
            f"trade row {index}.txHash", raw_row.get("txHash")
        )
        maker = _required_text(f"trade row {index}.maker", raw_row.get("maker"))

        provider_side_raw = raw_row.get("type")
        provider_side = (
            provider_side_raw
            if isinstance(provider_side_raw, str)
            and provider_side_raw in _SUPPORTED_SIDES
            else None
        )

        if tx_hash in seen_signatures:
            raise X1NinjaTradeHistorySampleEvidenceError(
                "sample contains duplicate X1.Ninja txHash values"
            )
        seen_signatures.add(tx_hash)

        row_pool_matches = row_pool == expected_pool
        row_pool_identity_match_complete = (
            row_pool_identity_match_complete and row_pool_matches
        )

        report = reports.get(tx_hash)
        rpc_bound = report is not None
        report_binding_complete = report_binding_complete and rpc_bound

        rpc_successful = False
        maker_matches = False
        rpc_slot_available = False
        provider_slot_matches = False
        wallet_side_matches = False
        rpc_slot: int | None = None

        if report is None:
            rpc_success_complete = False
            maker_match_complete = False
            rpc_slot_available_complete = False
            provider_slot_match_complete = False
            side_match_complete = False
        else:
            rpc_successful = bool(report.found and report.succeeded)
            rpc_success_complete = rpc_success_complete and rpc_successful

            maker_matches = report.primary_signer == maker
            maker_match_complete = maker_match_complete and maker_matches

            rpc_slot_available = _valid_slot(report.slot)
            rpc_slot_available_complete = (
                rpc_slot_available_complete and rpc_slot_available
            )
            if rpc_slot_available:
                rpc_slot = report.slot
                verified_slots.append(report.slot)

            provider_slot = raw_row.get("slot")
            provider_slot_matches = bool(
                rpc_slot_available
                and _valid_slot(provider_slot)
                and provider_slot == rpc_slot
            )
            provider_slot_match_complete = (
                provider_slot_match_complete and provider_slot_matches
            )

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

        row_results.append(
            {
                "index": index,
                "transaction_id": tx_hash,
                "rpc_report_bound": rpc_bound,
                "rpc_transaction_found_and_successful": rpc_successful,
                "row_pool_matches_verified_pool_identity": row_pool_matches,
                "transaction_pool_membership_verified": False,
                "maker_matches_rpc_primary_signer": maker_matches,
                "rpc_slot_available": rpc_slot_available,
                "provider_slot_matches_rpc_slot_observation": provider_slot_matches,
                "provider_side_matches_wallet_level_rpc_evidence": wallet_side_matches,
                "rpc_slot": rpc_slot,
            }
        )

    sample_size = len(selected_rows)
    has_sample = sample_size > 0

    sample_report_binding_complete = bool(has_sample and report_binding_complete)
    sample_rpc_success_complete = bool(has_sample and rpc_success_complete)
    sample_transaction_identity_binding_complete = bool(
        has_sample and report_binding_complete and rpc_success_complete
    )
    sample_row_pool_identity_match_complete = bool(
        has_sample and row_pool_identity_match_complete
    )
    sample_maker_match_complete = bool(has_sample and maker_match_complete)
    sample_rpc_slot_available_complete = bool(
        has_sample and rpc_slot_available_complete
    )
    sample_provider_slot_match_complete = bool(
        has_sample and provider_slot_match_complete
    )
    sample_side_match_complete = bool(has_sample and side_match_complete)

    order_observation = "unavailable"
    if sample_rpc_slot_available_complete and len(verified_slots) == sample_size:
        newest_first = all(
            earlier >= later
            for earlier, later in zip(verified_slots, verified_slots[1:])
        )
        order_observation = (
            "newest_to_oldest_by_verified_rpc_slot_observed"
            if newest_first
            else "not_newest_to_oldest_by_verified_rpc_slot_observed"
        )

    warnings = [
        "bounded_sample_only",
        "transaction_pool_membership_not_verified",
        "rpc_source_independence_not_established_by_this_evidence",
        "provider_pagination_and_range_unverified",
        "provider_exhaustiveness_unverified",
        "provider_retention_unverified",
        "transaction_finality_unverified",
        "provider_timestamp_semantics_unverified",
        "provider_amount_and_price_semantics_unverified",
        "observed_order_is_not_a_provider_ordering_contract",
    ]
    if not has_sample:
        warnings.append("empty_returned_history_sample")
    if len(trades) > sample_size:
        warnings.append("local_verifier_sample_truncated")
    if has_sample and not side_match_complete:
        warnings.append("provider_side_not_confirmed_for_every_sampled_row")
    if has_sample and not provider_slot_match_complete:
        warnings.append("provider_slot_not_confirmed_for_every_sampled_row")
    if has_sample and not row_pool_identity_match_complete:
        warnings.append("provider_row_pool_does_not_match_verified_pool_for_every_row")

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
        "distinct_sample_transaction_ids": bool(
            has_sample and len(seen_signatures) == sample_size
        ),
        "sample_rpc_report_binding_complete": sample_report_binding_complete,
        "sample_rpc_transaction_success_complete": sample_rpc_success_complete,
        "sample_transaction_identity_binding_complete": (
            sample_transaction_identity_binding_complete
        ),
        "sample_row_pool_identity_match_complete": (
            sample_row_pool_identity_match_complete
        ),
        "sample_transaction_pool_membership_verified": False,
        "sample_maker_primary_signer_match_complete": sample_maker_match_complete,
        "sample_rpc_slot_available_complete": sample_rpc_slot_available_complete,
        "sample_provider_slot_rpc_match_complete": sample_provider_slot_match_complete,
        "sample_wallet_side_rpc_match_complete": sample_side_match_complete,
        "returned_order_observation": order_observation,
        "rows": row_results,
        "semantics": {
            "sample_transaction_identity_crosscheck": (
                sample_transaction_identity_binding_complete
            ),
            "sample_row_pool_identity_crosscheck": (
                sample_row_pool_identity_match_complete
            ),
            "transaction_pool_membership_verified": False,
            "sample_provider_slot_crosscheck": sample_provider_slot_match_complete,
            "sample_provider_side_crosscheck": sample_side_match_complete,
            "rpc_source_independence_verified": False,
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
