"""Fail-closed classification of XDEX executed-fee evidence.

This module classifies already-observed execution evidence. It performs no
network I/O and never infers executed fee semantics from gross vault balances
alone. Historical active reserves must account for accrued pool fee counters
before curve comparisons can become execution evidence.
"""

from __future__ import annotations

from typing import Any, Mapping


SCHEMA = "xdex_execution_fee_evidence.v1"
_ALLOWED_DIRECT_SOURCES = {"diagnostic_log", "swap_event", "verified_historical_state"}


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _literal_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{field} must be a literal boolean")
    return value


def _optional_ppm(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer ppm value")
    if not 0 <= value < 1_000_000:
        raise ValueError(f"{field} must be between 0 and 999999 ppm")
    return value


def classify_xdex_execution_fee_evidence(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Classify whether an observed completed swap can establish execution fee semantics.

    Direct fee evidence may identify an executed trade-fee rate when it comes
    from a recognized transaction-level source. Otherwise curve-based
    discrimination requires independently verified active pre-swap reserves,
    including the historical pool fee counters needed to convert gross vault
    balances into active reserves.
    """
    if not isinstance(observation, Mapping):
        raise TypeError("observation must be a mapping")

    chain = _required_text(observation.get("chain"), "chain")
    if chain != "x1":
        raise ValueError("chain must be x1")
    signature = _required_text(observation.get("signature"), "signature")
    pool = _required_text(observation.get("pool"), "pool")
    amm_config = _required_text(observation.get("amm_config"), "amm_config")

    configured_fee_ppm = _optional_ppm(observation.get("configured_fee_ppm"), "configured_fee_ppm")
    candidate_fee_ppm = _optional_ppm(observation.get("candidate_fee_ppm"), "candidate_fee_ppm")
    direct_trade_fee_ppm = _optional_ppm(observation.get("direct_trade_fee_ppm"), "direct_trade_fee_ppm")

    active_reserves_verified = _literal_bool(
        observation.get("active_reserves_verified", False), "active_reserves_verified"
    )
    fee_counters_verified = _literal_bool(
        observation.get("fee_counters_verified", False), "fee_counters_verified"
    )
    gross_vault_balances_observed = _literal_bool(
        observation.get("gross_vault_balances_observed", False), "gross_vault_balances_observed"
    )

    direct_source_raw = observation.get("direct_fee_source")
    direct_source = None if direct_source_raw is None else _required_text(direct_source_raw, "direct_fee_source")
    if direct_source is not None and direct_source not in _ALLOWED_DIRECT_SOURCES:
        raise ValueError("direct_fee_source is not an accepted execution-evidence source")
    if direct_trade_fee_ppm is not None and direct_source is None:
        raise ValueError("direct_trade_fee_ppm requires direct_fee_source")
    if direct_source is not None and direct_trade_fee_ppm is None:
        raise ValueError("direct_fee_source requires direct_trade_fee_ppm")

    direct_fee_verified = direct_trade_fee_ppm is not None and direct_source is not None
    active_reserve_comparison_eligible = active_reserves_verified and fee_counters_verified

    if direct_fee_verified:
        status = "DIRECT_FEE_EVIDENCE"
        executed_fee_semantics_verified = True
        executed_fee_ppm = direct_trade_fee_ppm
        reason = "transaction_level_fee_evidence_available"
    elif active_reserve_comparison_eligible and candidate_fee_ppm is not None:
        status = "ACTIVE_RESERVE_COMPARISON_ELIGIBLE"
        executed_fee_semantics_verified = False
        executed_fee_ppm = None
        reason = "active_reserves_verified_but_curve_match_still_required"
    else:
        status = "INSUFFICIENT_EVIDENCE"
        executed_fee_semantics_verified = False
        executed_fee_ppm = None
        if gross_vault_balances_observed and not active_reserves_verified:
            reason = "gross_vault_balances_do_not_prove_active_reserves"
        elif not fee_counters_verified:
            reason = "historical_pool_fee_counters_not_verified"
        else:
            reason = "execution_fee_evidence_incomplete"

    warnings: list[str] = []
    if gross_vault_balances_observed and not active_reserves_verified:
        warnings.append("gross_vault_curve_diagnostics_are_not_execution_fee_proof")
    if not fee_counters_verified:
        warnings.append("historical_fee_counter_state_missing_or_unverified")
    if configured_fee_ppm is not None and direct_fee_verified and configured_fee_ppm != direct_trade_fee_ppm:
        warnings.append("executed_fee_differs_from_configured_fee")

    return {
        "schema": SCHEMA,
        "chain": chain,
        "signature": signature,
        "pool": pool,
        "amm_config": amm_config,
        "status": status,
        "reason": reason,
        "configured_fee_ppm": configured_fee_ppm,
        "candidate_fee_ppm": candidate_fee_ppm,
        "direct_trade_fee_ppm": direct_trade_fee_ppm,
        "direct_fee_source": direct_source,
        "gross_vault_balances_observed": gross_vault_balances_observed,
        "active_reserves_verified": active_reserves_verified,
        "fee_counters_verified": fee_counters_verified,
        "active_reserve_comparison_eligible": active_reserve_comparison_eligible,
        "executed_fee_semantics_verified": executed_fee_semantics_verified,
        "executed_fee_ppm": executed_fee_ppm,
        "quote_fee_semantics_verified": False,
        "slippage_semantics_verified": False,
        "fill_quality_verified": False,
        "execution_quality_verified": False,
        "cmis_promotable": False,
        "warnings": warnings,
    }


__all__ = ["SCHEMA", "classify_xdex_execution_fee_evidence"]
