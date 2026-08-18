"""Fail-closed deterministic classification for XDEX executed-fee evidence.

This module performs no network I/O. It classifies already-observed historical
execution evidence for the exact XENCAT/native-XNT XDEX route accepted in
Issue #189 / PR #196.

The v1 contract deliberately remains route- and sequence-scoped. It may mark
one candidate execution model as strongly corroborated while keeping global
execution semantics, hidden-fee attribution, private backend behavior, fill
quality, route quality, and CMIS public-service promotion unverified.
"""

from __future__ import annotations

from typing import Any, Mapping


SCHEMA = "xdex_execution_fee_sequence_evidence.v1"

X1_PROGRAM = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
XENCAT_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XNT_MINT = "So11111111111111111111111111111111111111112"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
AMM_CONFIG = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"

CONFIGURED_FEE_PPM = 2800
REJECTED_EXECUTION_CANDIDATE_PPM = 3000
MIN_SEQUENCE_SWAPS = 5
MAX_SUPPORTED_ERROR_RAW = 10_000
MIN_REJECTION_ERROR_MULTIPLE = 1_000


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    text = value.strip()
    if not text or text != value:
        raise ValueError(f"{field} must be a normalized non-empty string")
    return text


def _literal_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{field} must be a literal boolean")
    return value


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def _positive_int(value: Any, field: str) -> int:
    result = _non_negative_int(value, field)
    if result <= 0:
        raise ValueError(f"{field} must be positive")
    return result


def _require_identity(observation: Mapping[str, Any]) -> dict[str, str]:
    identity = {
        "chain": _required_text(observation.get("chain"), "chain"),
        "program": _required_text(observation.get("program"), "program"),
        "pool": _required_text(observation.get("pool"), "pool"),
        "amm_config": _required_text(observation.get("amm_config"), "amm_config"),
        "asset_a_mint": _required_text(observation.get("asset_a_mint"), "asset_a_mint"),
        "asset_b_mint": _required_text(observation.get("asset_b_mint"), "asset_b_mint"),
    }
    if identity["chain"] != "x1":
        raise ValueError("chain must be x1")
    if identity["program"] != X1_PROGRAM:
        raise ValueError("program does not match the accepted XDEX X1 mainnet program")
    if identity["pool"] != POOL:
        raise ValueError("pool does not match the accepted XENCAT/native-XNT pool")
    if identity["amm_config"] != AMM_CONFIG:
        raise ValueError("amm_config does not match the accepted XDEX config")
    if {identity["asset_a_mint"], identity["asset_b_mint"]} != {XENCAT_MINT, XNT_MINT}:
        raise ValueError("asset mint pair does not match the accepted XENCAT/native-XNT route")
    return identity


def classify_xdex_execution_fee_sequence_evidence(
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify the accepted historical state-contiguous execution experiment.

    The classifier intentionally distinguishes bounded corroboration from global
    verification. Gross-vault observations alone remain insufficient. The
    stronger path requires a state-contiguous, bidirectional sequence with an
    opposite-direction seed and holdout validation under the corroborated
    Raydium-derived fee-counter accounting model.
    """

    if not isinstance(observation, Mapping):
        raise TypeError("observation must be a mapping")

    identity = _require_identity(observation)

    configured_fee_ppm = _non_negative_int(
        observation.get("configured_fee_ppm"), "configured_fee_ppm"
    )
    supported_candidate_ppm = _non_negative_int(
        observation.get("supported_candidate_ppm"), "supported_candidate_ppm"
    )
    rejected_candidate_ppm = _non_negative_int(
        observation.get("rejected_candidate_ppm"), "rejected_candidate_ppm"
    )
    if configured_fee_ppm != CONFIGURED_FEE_PPM:
        raise ValueError("configured_fee_ppm must be 2800 for the accepted v1 scope")
    if supported_candidate_ppm != CONFIGURED_FEE_PPM:
        raise ValueError("supported_candidate_ppm must be 2800 for the accepted v1 scope")
    if rejected_candidate_ppm != REJECTED_EXECUTION_CANDIDATE_PPM:
        raise ValueError("rejected_candidate_ppm must be 3000 for the accepted v1 scope")

    swap_count = _positive_int(observation.get("swap_count"), "swap_count")
    seed_swap_count = _positive_int(observation.get("seed_swap_count"), "seed_swap_count")
    holdout_swap_count = _non_negative_int(
        observation.get("holdout_swap_count"), "holdout_swap_count"
    )
    if seed_swap_count != 2:
        raise ValueError("seed_swap_count must be 2 for the accepted opposite-direction seed")
    if seed_swap_count + holdout_swap_count != swap_count:
        raise ValueError("seed_swap_count + holdout_swap_count must equal swap_count")

    first_slot = _non_negative_int(observation.get("first_slot"), "first_slot")
    last_slot = _non_negative_int(observation.get("last_slot"), "last_slot")
    if last_slot < first_slot:
        raise ValueError("last_slot must not precede first_slot")

    gross_vault_balances_observed = _literal_bool(
        observation.get("gross_vault_balances_observed"),
        "gross_vault_balances_observed",
    )
    state_contiguous = _literal_bool(
        observation.get("state_contiguous"), "state_contiguous"
    )
    both_directions_observed = _literal_bool(
        observation.get("both_directions_observed"), "both_directions_observed"
    )
    opposite_direction_seed_verified = _literal_bool(
        observation.get("opposite_direction_seed_verified"),
        "opposite_direction_seed_verified",
    )
    holdout_validation_performed = _literal_bool(
        observation.get("holdout_validation_performed"),
        "holdout_validation_performed",
    )
    fee_accounting_model_corroborated = _literal_bool(
        observation.get("fee_accounting_model_corroborated"),
        "fee_accounting_model_corroborated",
    )
    initial_fee_counters_inferred = _literal_bool(
        observation.get("initial_fee_counters_inferred"),
        "initial_fee_counters_inferred",
    )
    initial_fee_counters_observed = _literal_bool(
        observation.get("initial_fee_counters_observed"),
        "initial_fee_counters_observed",
    )
    quote_baseline_verified = _literal_bool(
        observation.get("quote_baseline_verified"), "quote_baseline_verified"
    )

    if initial_fee_counters_observed:
        raise ValueError(
            "v1 describes the accepted inferred-counter evidence; directly observed historical counters require a new contract"
        )

    supported_max_abs_error_raw = _non_negative_int(
        observation.get("supported_max_abs_error_raw"),
        "supported_max_abs_error_raw",
    )
    supported_sum_abs_error_raw = _non_negative_int(
        observation.get("supported_sum_abs_error_raw"),
        "supported_sum_abs_error_raw",
    )
    rejected_max_abs_error_raw = _non_negative_int(
        observation.get("rejected_max_abs_error_raw"),
        "rejected_max_abs_error_raw",
    )
    rejected_sum_abs_error_raw = _non_negative_int(
        observation.get("rejected_sum_abs_error_raw"),
        "rejected_sum_abs_error_raw",
    )
    if supported_sum_abs_error_raw < supported_max_abs_error_raw:
        raise ValueError("supported_sum_abs_error_raw cannot be smaller than the maximum error")
    if rejected_sum_abs_error_raw < rejected_max_abs_error_raw:
        raise ValueError("rejected_sum_abs_error_raw cannot be smaller than the maximum error")

    quote_baseline_ppm = _non_negative_int(
        observation.get("quote_baseline_ppm"), "quote_baseline_ppm"
    )

    requirements = {
        "minimum_sequence_length": swap_count >= MIN_SEQUENCE_SWAPS,
        "gross_vault_state_observed": gross_vault_balances_observed,
        "state_contiguous": state_contiguous,
        "both_directions_observed": both_directions_observed,
        "opposite_direction_seed_verified": opposite_direction_seed_verified,
        "holdout_validation_performed": holdout_validation_performed and holdout_swap_count > 0,
        "fee_accounting_model_corroborated": fee_accounting_model_corroborated,
        "initial_fee_counters_inferred": initial_fee_counters_inferred,
        "supported_candidate_error_bounded": supported_max_abs_error_raw <= MAX_SUPPORTED_ERROR_RAW,
        "rejected_candidate_materially_worse": (
            rejected_max_abs_error_raw
            > supported_max_abs_error_raw * MIN_REJECTION_ERROR_MULTIPLE
        ),
        "rejected_sum_error_worse": rejected_sum_abs_error_raw > supported_sum_abs_error_raw,
    }
    strong = all(requirements.values())

    if strong:
        status = "STRONGLY_CORROBORATED"
        reason = "state_contiguous_sequence_strongly_supports_2800_over_3000"
    else:
        status = "INSUFFICIENT_EVIDENCE"
        failed = [name for name, passed in requirements.items() if not passed]
        reason = "sequence_contract_requirements_not_satisfied:" + ",".join(failed)

    quote_execution_divergence_localized = bool(
        strong
        and quote_baseline_verified
        and quote_baseline_ppm == rejected_candidate_ppm
        and supported_candidate_ppm != quote_baseline_ppm
    )

    warnings = [
        "gross_vault_balances_alone_are_not_execution_fee_proof",
        "historical_fee_counters_inferred_not_observed",
        "route_pool_config_and_sequence_scoped_only",
        "global_execution_semantics_unverified",
        "private_quote_backend_reason_unavailable",
        "hidden_router_platform_or_protocol_fee_attribution_unproven",
    ]
    if not quote_baseline_verified:
        warnings.append("quote_baseline_not_independently_verified_in_this_observation")
    elif quote_baseline_ppm != rejected_candidate_ppm:
        warnings.append("quote_baseline_does_not_match_rejected_execution_candidate")

    return {
        "schema": SCHEMA,
        **identity,
        "status": status,
        "reason": reason,
        "scope": "BOUNDED",
        "configured_fee_ppm": configured_fee_ppm,
        "supported_candidate_ppm": supported_candidate_ppm,
        "rejected_candidate_ppm": rejected_candidate_ppm,
        "swap_count": swap_count,
        "seed_swap_count": seed_swap_count,
        "holdout_swap_count": holdout_swap_count,
        "first_slot": first_slot,
        "last_slot": last_slot,
        "gross_vault_balances_observed": gross_vault_balances_observed,
        "state_contiguous": state_contiguous,
        "both_directions_observed": both_directions_observed,
        "opposite_direction_seed_verified": opposite_direction_seed_verified,
        "holdout_validation_performed": holdout_validation_performed,
        "fee_accounting_model_corroborated": fee_accounting_model_corroborated,
        "initial_fee_counters_inferred": initial_fee_counters_inferred,
        "initial_fee_counters_observed": initial_fee_counters_observed,
        "supported_max_abs_error_raw": supported_max_abs_error_raw,
        "supported_sum_abs_error_raw": supported_sum_abs_error_raw,
        "rejected_max_abs_error_raw": rejected_max_abs_error_raw,
        "rejected_sum_abs_error_raw": rejected_sum_abs_error_raw,
        "acceptance_thresholds": {
            "minimum_sequence_swaps": MIN_SEQUENCE_SWAPS,
            "maximum_supported_candidate_error_raw": MAX_SUPPORTED_ERROR_RAW,
            "minimum_rejection_error_multiple": MIN_REJECTION_ERROR_MULTIPLE,
        },
        "requirements": requirements,
        "bounded_execution_model_supported": strong,
        "bounded_supported_execution_fee_ppm": (
            supported_candidate_ppm if strong else None
        ),
        "executed_fee_global_verified": False,
        "quote_baseline_ppm": quote_baseline_ppm,
        "quote_baseline_verified": quote_baseline_verified,
        "quote_execution_divergence_localized": quote_execution_divergence_localized,
        "hidden_fee_attribution_verified": False,
        "private_backend_reason_verified": False,
        "fill_quality_verified": False,
        "route_quality_verified": False,
        "execution_quality_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "warnings": warnings,
    }


__all__ = [
    "AMM_CONFIG",
    "CONFIGURED_FEE_PPM",
    "MAX_SUPPORTED_ERROR_RAW",
    "MIN_REJECTION_ERROR_MULTIPLE",
    "MIN_SEQUENCE_SWAPS",
    "POOL",
    "REJECTED_EXECUTION_CANDIDATE_PPM",
    "SCHEMA",
    "X1_PROGRAM",
    "XENCAT_MINT",
    "XNT_MINT",
    "classify_xdex_execution_fee_sequence_evidence",
]
