"""Fail-closed comparison of verified direct XDEX candidate quote outputs.

This module consumes an already-complete direct-route discovery observation and
caller-supplied read-only quote observations. It can identify only the highest
zero-slippage quote output among the verified direct candidates in the accepted
XDEX program family. It does not claim execution quality, expected fill,
global route optimality, or coverage across every X1 DEX.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Any


CHAIN = "x1"
VERSION = "1.0"
SELECTION_CLAIM = "highest_zero_slippage_quote_output_among_verified_direct_xdex_candidates"


class XDEXDirectCandidateQuoteComparisonError(ValueError):
    """Raised when candidate/quote evidence cannot support a comparison."""


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise XDEXDirectCandidateQuoteComparisonError(f"{name} must be non-empty text")
    return value.strip()


def _positive_decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, bool):
        raise XDEXDirectCandidateQuoteComparisonError(f"{name} must be a positive number")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise XDEXDirectCandidateQuoteComparisonError(f"{name} must be a positive number") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise XDEXDirectCandidateQuoteComparisonError(f"{name} must be a positive number")
    return parsed


def _candidate_rows(discovery: Mapping[str, Any], token_in: str, token_out: str) -> list[dict[str, str]]:
    if discovery.get("chain") != CHAIN:
        raise XDEXDirectCandidateQuoteComparisonError("discovery chain must be x1")
    if discovery.get("token_in_mint") != token_in or discovery.get("token_out_mint") != token_out:
        raise XDEXDirectCandidateQuoteComparisonError("discovery mint direction does not match request")
    if discovery.get("program_family_pair_enumeration_complete") is not True:
        raise XDEXDirectCandidateQuoteComparisonError("pair enumeration completeness is unverified")
    if discovery.get("candidate_verification_complete") is not True:
        raise XDEXDirectCandidateQuoteComparisonError("candidate verification is incomplete")
    if discovery.get("rejected_candidates") not in ([], None):
        raise XDEXDirectCandidateQuoteComparisonError("discovery contains rejected candidates")

    raw = discovery.get("candidates")
    if not isinstance(raw, list) or not raw:
        raise XDEXDirectCandidateQuoteComparisonError("no verified direct candidates are available")

    rows: list[dict[str, str]] = []
    pools: set[str] = set()
    configs: set[str] = set()
    for candidate in raw:
        if not isinstance(candidate, Mapping):
            raise XDEXDirectCandidateQuoteComparisonError("candidate must be a mapping")
        if candidate.get("token_in_mint") != token_in or candidate.get("token_out_mint") != token_out:
            raise XDEXDirectCandidateQuoteComparisonError("candidate mint direction does not match request")
        for flag in ("pool_state_verified", "amm_config_verified", "vault_identity_verified", "active_reserves_verified"):
            if candidate.get(flag) is not True:
                raise XDEXDirectCandidateQuoteComparisonError(f"candidate {flag} is not verified")
        pool = _text(candidate.get("pool"), "candidate pool")
        config = _text(candidate.get("amm_config"), "candidate amm_config")
        if pool in pools:
            raise XDEXDirectCandidateQuoteComparisonError("duplicate candidate pool")
        if config in configs:
            raise XDEXDirectCandidateQuoteComparisonError(
                "candidate AMM configs must be unique before config-pinned quotes can distinguish pools"
            )
        pools.add(pool)
        configs.add(config)
        rows.append({"pool": pool, "amm_config": config})

    if discovery.get("verified_candidate_count") != len(rows):
        raise XDEXDirectCandidateQuoteComparisonError("verified candidate count does not match candidates")
    return rows


def compare_direct_candidate_quotes(
    token_in_mint: str,
    token_out_mint: str,
    token_in_amount: Any,
    *,
    discovery: Mapping[str, Any],
    quote_provider: Callable[[Mapping[str, str], str, str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare zero-slippage outputs for every fully verified direct candidate.

    ``quote_provider`` is deliberately injected. It must return a mapping whose
    route identity is explicitly bound to the candidate pool/config and whose
    zero-slippage output has already passed the accepted exact-route semantic
    validation. Any failed or unverified candidate quote makes the whole
    comparison incomplete and prevents selection.
    """

    token_in = _text(token_in_mint, "token_in_mint")
    token_out = _text(token_out_mint, "token_out_mint")
    if token_in == token_out:
        raise XDEXDirectCandidateQuoteComparisonError("token mints must differ")
    amount = _positive_decimal(token_in_amount, "token_in_amount")
    amount_text = format(amount, "f")
    if not isinstance(discovery, Mapping):
        raise XDEXDirectCandidateQuoteComparisonError("discovery must be a mapping")
    candidates = _candidate_rows(discovery, token_in, token_out)

    observations: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    output_decimals: int | None = None
    for candidate in candidates:
        try:
            quote = quote_provider(candidate, token_in, token_out, amount_text)
            if not isinstance(quote, Mapping):
                raise XDEXDirectCandidateQuoteComparisonError("quote provider did not return a mapping")
            if quote.get("token_in_mint") != token_in or quote.get("token_out_mint") != token_out:
                raise XDEXDirectCandidateQuoteComparisonError("quote mint direction mismatch")
            if quote.get("pool") != candidate["pool"] or quote.get("amm_config") != candidate["amm_config"]:
                raise XDEXDirectCandidateQuoteComparisonError("quote route identity mismatch")
            if quote.get("route_identity_verified") is not True or quote.get("zero_slippage_output_verified") is not True:
                raise XDEXDirectCandidateQuoteComparisonError("quote semantics are not verified")
            decimals = quote.get("output_decimals")
            if isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0:
                raise XDEXDirectCandidateQuoteComparisonError("output_decimals must be a non-negative integer")
            if output_decimals is None:
                output_decimals = decimals
            elif decimals != output_decimals:
                raise XDEXDirectCandidateQuoteComparisonError("candidate output decimals do not match")
            output = _positive_decimal(quote.get("zero_slippage_output"), "zero_slippage_output")
            scale = Decimal(10) ** decimals
            raw = output * scale
            if raw != raw.to_integral_value():
                raise XDEXDirectCandidateQuoteComparisonError(
                    "zero_slippage_output is not exactly representable in output token decimals"
                )
            observations.append({
                "pool": candidate["pool"],
                "amm_config": candidate["amm_config"],
                "zero_slippage_output": format(output, "f"),
                "zero_slippage_output_raw": int(raw),
                "output_decimals": decimals,
            })
        except Exception as exc:
            failures.append({"pool": candidate["pool"], "reason": f"{type(exc).__name__}: {exc}"})

    if failures or len(observations) != len(candidates):
        status = "comparison_incomplete"
        preferred = None
        claim = None
    else:
        best_raw = max(row["zero_slippage_output_raw"] for row in observations)
        winners = [row for row in observations if row["zero_slippage_output_raw"] == best_raw]
        if len(winners) == 1:
            status = "preferred"
            preferred = dict(winners[0])
            claim = SELECTION_CLAIM
        else:
            status = "tie"
            preferred = None
            claim = None

    return {
        "service": "xdex_direct_candidate_quote_comparison",
        "version": VERSION,
        "chain": CHAIN,
        "token_in_mint": token_in,
        "token_out_mint": token_out,
        "token_in_amount": amount_text,
        "status": status,
        "selection_claim": claim,
        "preferred_candidate": preferred,
        "candidate_count": len(candidates),
        "quoted_candidate_count": len(observations),
        "quotes": observations,
        "quote_failures": failures,
        "comparison_complete": not failures and len(observations) == len(candidates),
        "same_provider_quotes_independently_corroborated": False,
        "accepted_xdex_program_family_only": True,
        "all_x1_dex_routes_compared": False,
        "multi_hop_evaluated": False,
        "execution_quality_verified": False,
        "expected_fill_verified": False,
        "expected_slippage_verified": False,
        "global_optimality_claimed": False,
        "execution_authorized": False,
        "read_only": True,
    }


__all__ = [
    "CHAIN",
    "SELECTION_CLAIM",
    "VERSION",
    "XDEXDirectCandidateQuoteComparisonError",
    "compare_direct_candidate_quotes",
]
